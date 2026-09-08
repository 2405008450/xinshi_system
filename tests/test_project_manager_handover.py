from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, joinedload, selectinload

# 单独运行本文件时也要先注册标注项目关联的计费模型。
import annotation_ops_models  # noqa: F401
import project_workbench_service
import workflow_crud
from project_workbench_service import TRANSLATION_INACTIVE_STATUSES
from workflow_models import ProjectManagerHandoverItem, ProjectManagerHandoverRequest


def test_project_manager_handover_lock_only_targets_request_table():
    """关联预加载存在外连接时，行锁不能覆盖外连接的可空侧。"""
    db = Session()
    query = (
        db.query(ProjectManagerHandoverRequest)
        .options(
            joinedload(ProjectManagerHandoverRequest.requester),
            joinedload(ProjectManagerHandoverRequest.target_manager),
            selectinload(ProjectManagerHandoverRequest.items).joinedload(
                ProjectManagerHandoverItem.project
            ),
        )
        .with_for_update(of=ProjectManagerHandoverRequest)
    )

    sql = str(query.statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE OF project_manager_handover_request" in sql


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.locked = False

    def options(self, *_args):
        return self

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def join(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def with_for_update(self, *_args, **_kwargs):
        self.locked = True
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, query_rows):
        self.query_rows = list(query_rows)
        self.queries = []
        self.committed = False

    def query(self, _model):
        query = FakeQuery(self.query_rows.pop(0))
        self.queries.append(query)
        return query

    def commit(self):
        self.committed = True

    def refresh(self, _record):
        return None


def test_project_manager_can_see_unassigned_management_projects(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    db = FakeDb([[]])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda *_args: ["项目经理"],
    )

    assert workflow_crud.get_management_projects(db, user) == []

    visibility_filter = db.queries[0].filters[-1]
    sql = str(visibility_filter.compile(dialect=postgresql.dialect()))
    assert "translation_project.project_manager_id IS NULL" in sql

    active_filter = db.queries[0].filters[0]
    compiled_active = active_filter.compile(dialect=postgresql.dialect())
    status_values = next(
        value
        for value in compiled_active.params.values()
        if isinstance(value, (list, tuple, set, frozenset))
    )
    assert set(status_values) == set(TRANSLATION_INACTIVE_STATUSES)


def test_project_manager_claims_unassigned_projects_with_row_lock(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    project = SimpleNamespace(id=uuid4(), project_manager_id=None)
    db = FakeDb([[project], []])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda *_args: ["项目经理"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)

    result = workflow_crud.claim_management_projects(db, user, [project.id, project.id])

    assert result == [project]
    assert project.project_manager_id == user.id
    assert db.queries[0].locked is True
    assert db.committed is True


def test_project_manager_cannot_claim_project_already_owned(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    project = SimpleNamespace(id=uuid4(), project_manager_id=uuid4())
    db = FakeDb([[project]])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda *_args: ["项目经理"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)

    with pytest.raises(LookupError, match="已被其他项目经理承接"):
        workflow_crud.claim_management_projects(db, user, [project.id])

    assert project.project_manager_id != user.id
    assert db.committed is False


def test_project_manager_cannot_claim_project_with_pending_handover(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    project = SimpleNamespace(id=uuid4(), project_manager_id=None)
    pending_item = SimpleNamespace(translation_project_id=project.id)
    db = FakeDb([[project], [pending_item]])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda *_args: ["项目经理"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)

    with pytest.raises(LookupError, match="已有待确认"):
        workflow_crud.claim_management_projects(db, user, [project.id])

    assert project.project_manager_id is None
    assert db.committed is False


def test_handover_model_supports_admin_direct_mode():
    constraint_names = {
        constraint.name for constraint in ProjectManagerHandoverRequest.__table__.constraints
    }
    assert "ck_pm_handover_request_mode" in constraint_names
    assert "ck_pm_handover_request_manager_role" in constraint_names
    assert ProjectManagerHandoverRequest.__table__.c.handover_mode.server_default is not None
    assert ProjectManagerHandoverRequest.__table__.c.manager_role.server_default is not None
    assert "annotation_project_id" in ProjectManagerHandoverItem.__table__.c


class DirectTransferQuery:
    def __init__(self, *, first_value=None, all_values=None):
        self.first_value = first_value
        self.all_values = list(all_values or [])
        self.locked = False

    def filter(self, *_conditions):
        return self

    def join(self, *_args):
        return self

    def with_for_update(self, *_args, **_kwargs):
        self.locked = True
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.all_values


class DirectTransferDb:
    def __init__(self, queries):
        self.queries = list(queries)
        self.added = []
        self.committed = False

    def query(self, _model):
        return self.queries.pop(0)

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.committed = True

    def refresh(self, _record):
        return None


def test_admin_direct_transfer_accepts_inactive_source_and_preserves_other_fields(monkeypatch):
    operator = SimpleNamespace(id=uuid4(), username="admin", full_name="管理员")
    source = SimpleNamespace(id=uuid4(), username="former", full_name="离职经理", is_active=False)
    target = SimpleNamespace(id=uuid4(), username="target", full_name="接收经理", is_active=True)
    project = SimpleNamespace(
        id=uuid4(),
        project_status="project_in_progress",
        client_manager_id=uuid4(),
        workbench_responsibilities=["保持其他角色"],
    )
    row = SimpleNamespace(
        id=uuid4(),
        annotation_project_id=project.id,
        assignee_id=source.id,
        project=project,
        updated_at=None,
    )
    pending = SimpleNamespace(status="pending", decision_note=None, decided_by=None, decided_at=None)
    pending_query = DirectTransferQuery(all_values=[pending])
    db = DirectTransferDb([
        DirectTransferQuery(first_value=source),
        DirectTransferQuery(first_value=target),
        pending_query,
    ])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda _db, user_id: ["超级管理员"] if user_id == operator.id else ["项目经理"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)
    responsibility_query = DirectTransferQuery(all_values=[row])
    responsibility_lock_args = []

    def fake_responsibility_query(*_args, **kwargs):
        responsibility_lock_args.append(kwargs.get("lock"))
        return responsibility_query

    monkeypatch.setattr(
        workflow_crud,
        "_annotation_manager_responsibility_query",
        fake_responsibility_query,
    )
    notifications = []

    def fake_notifications(_db, recipient_user_ids, **_kwargs):
        created = [SimpleNamespace(recipient_user_id=user_id) for user_id in recipient_user_ids]
        notifications.extend(created)
        return created

    monkeypatch.setattr(workflow_crud, "create_notifications_for_users", fake_notifications)
    monkeypatch.setattr(workflow_crud, "_push_notifications", lambda *_args: None)

    request = workflow_crud.direct_transfer_annotation_manager(
        db,
        operator,
        source.id,
        target.id,
        [project.id, project.id],
        "项目经理离职",
    )

    assert responsibility_lock_args == [True]
    assert pending_query.locked is True
    assert row.assignee_id == target.id
    assert project.client_manager_id is not None
    assert project.workbench_responsibilities == ["保持其他角色"]
    assert request.handover_mode == "admin_direct"
    assert request.status == "accepted"
    assert request.items[0].expected_manager_id == source.id
    assert pending.status == "rejected"
    assert notifications == [SimpleNamespace(recipient_user_id=target.id)]
    assert db.committed is True


def test_admin_direct_transfer_rejects_concurrent_manager_change(monkeypatch):
    operator = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4(), username="former", full_name=None, is_active=False)
    target = SimpleNamespace(id=uuid4(), username="target", full_name=None, is_active=True)
    db = DirectTransferDb([
        DirectTransferQuery(first_value=source),
        DirectTransferQuery(first_value=target),
    ])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda _db, user_id: ["超级管理员"] if user_id == operator.id else ["项目经理"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)
    monkeypatch.setattr(
        workflow_crud,
        "_annotation_manager_responsibility_query",
        lambda *_args, **_kwargs: DirectTransferQuery(all_values=[]),
    )

    with pytest.raises(LookupError, match="归属已变化"):
        workflow_crud.direct_transfer_annotation_manager(
            db,
            operator,
            source.id,
            target.id,
            [uuid4()],
            "离职交接",
        )

    assert db.committed is False


def test_direct_transfer_preview_only_returns_active_annotation_projects(monkeypatch):
    source = SimpleNamespace(id=uuid4(), username="former", full_name="离职经理", is_active=False)
    active_project = SimpleNamespace(
        id=uuid4(), order_no="AP-260908-001", project_status="project_in_progress"
    )
    ended_project = SimpleNamespace(
        id=uuid4(), order_no="AP-260908-002", project_status="sent_to_client"
    )
    rows = [
        SimpleNamespace(
            project=active_project,
            assignee_id=source.id,
        ),
        SimpleNamespace(
            project=ended_project,
            assignee_id=source.id,
        ),
    ]
    db = DirectTransferDb([DirectTransferQuery(first_value=source)])
    monkeypatch.setattr(
        workflow_crud,
        "_annotation_manager_responsibility_query",
        lambda *_args, **_kwargs: DirectTransferQuery(all_values=rows),
    )
    monkeypatch.setattr(
        project_workbench_service,
        "serialize_responsibility",
        lambda _db, row: {
            "project_id": row.project.id,
            "order_no": row.project.order_no,
            "current_assignee_name": source.full_name,
        },
    )

    preview = workflow_crud.preview_annotation_manager_direct_transfer(db, source.id)

    assert preview["project_count"] == 1
    assert preview["status_counts"] == {"project_in_progress": 1}
    assert [item["project_id"] for item in preview["projects"]] == [active_project.id]


def test_admin_direct_client_manager_transfer_preserves_project_manager(monkeypatch):
    operator = SimpleNamespace(id=uuid4(), username="admin", full_name="管理员")
    source = SimpleNamespace(id=uuid4(), username="former_sales", full_name="离职客户经理", is_active=False)
    target = SimpleNamespace(id=uuid4(), username="sales", full_name="接收客户经理", is_active=True)
    project_manager_id = uuid4()
    project = SimpleNamespace(
        id=uuid4(),
        project_status="project_in_progress",
        client_manager_id=source.id,
        workbench_responsibilities=[
            SimpleNamespace(role_code="project_manager", assignee_id=project_manager_id),
        ],
        updated_at=None,
    )
    pending = SimpleNamespace(status="pending", decision_note=None, decided_by=None, decided_at=None)
    pending_query = DirectTransferQuery(all_values=[pending])
    db = DirectTransferDb([
        DirectTransferQuery(first_value=source),
        DirectTransferQuery(first_value=target),
        pending_query,
    ])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda _db, user_id: ["超级管理员"] if user_id == operator.id else ["客户专员"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)
    project_query = DirectTransferQuery(all_values=[project])
    project_lock_args = []

    def fake_project_query(*_args, **kwargs):
        project_lock_args.append(kwargs.get("lock"))
        return project_query

    monkeypatch.setattr(
        workflow_crud,
        "_annotation_client_manager_project_query",
        fake_project_query,
    )
    notifications = []

    def fake_notifications(_db, recipient_user_ids, **_kwargs):
        created = [SimpleNamespace(recipient_user_id=user_id) for user_id in recipient_user_ids]
        notifications.extend(created)
        return created

    monkeypatch.setattr(workflow_crud, "create_notifications_for_users", fake_notifications)
    monkeypatch.setattr(workflow_crud, "_push_notifications", lambda *_args: None)

    request = workflow_crud.direct_transfer_annotation_client_manager(
        db,
        operator,
        source.id,
        target.id,
        [project.id, project.id],
        "客户经理离职",
    )

    assert project_lock_args == [True]
    assert pending_query.locked is True
    assert project.client_manager_id == target.id
    assert project.workbench_responsibilities[0].assignee_id == project_manager_id
    assert request.handover_mode == "admin_direct"
    assert request.manager_role == "client_manager"
    assert request.items[0].annotation_project_id == project.id
    assert request.items[0].project_responsibility_id is None
    assert request.items[0].expected_manager_id == source.id
    assert pending.status == "rejected"
    assert notifications == [SimpleNamespace(recipient_user_id=target.id)]
    assert db.committed is True


def test_admin_direct_client_manager_transfer_rejects_concurrent_change(monkeypatch):
    operator = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4(), username="former_sales", full_name=None, is_active=False)
    target = SimpleNamespace(id=uuid4(), username="sales", full_name=None, is_active=True)
    db = DirectTransferDb([
        DirectTransferQuery(first_value=source),
        DirectTransferQuery(first_value=target),
    ])
    monkeypatch.setattr(
        workflow_crud,
        "get_user_roles_with_role_names",
        lambda _db, user_id: ["超级管理员"] if user_id == operator.id else ["客户专员"],
    )
    monkeypatch.setattr(workflow_crud, "ensure_user_assignable", lambda *_args: None)
    monkeypatch.setattr(
        workflow_crud,
        "_annotation_client_manager_project_query",
        lambda *_args, **_kwargs: DirectTransferQuery(all_values=[]),
    )

    with pytest.raises(LookupError, match="客户经理归属已变化"):
        workflow_crud.direct_transfer_annotation_client_manager(
            db,
            operator,
            source.id,
            target.id,
            [uuid4()],
            "离职交接",
        )

    assert db.committed is False


def test_client_manager_transfer_preview_only_returns_active_projects(monkeypatch):
    source = SimpleNamespace(id=uuid4(), username="former_sales", full_name="离职客户经理", is_active=False)
    active_project = SimpleNamespace(
        id=uuid4(), order_no="AP-260908-011", project_name="活跃项目",
        project_status="project_in_progress", client_manager_id=source.id,
        client_manager=source, client_short_name="客户甲", language_items_display="中文",
        task_submitted_at=None,
    )
    ended_project = SimpleNamespace(
        id=uuid4(), order_no="AP-260908-012", project_name="已结束项目",
        project_status="sent_to_client", client_manager_id=source.id,
        client_manager=source, client_short_name="客户乙", language_items_display="英文",
        task_submitted_at=None,
    )
    db = DirectTransferDb([DirectTransferQuery(first_value=source)])
    monkeypatch.setattr(
        workflow_crud,
        "_annotation_client_manager_project_query",
        lambda *_args, **_kwargs: DirectTransferQuery(all_values=[active_project, ended_project]),
    )

    preview = workflow_crud.preview_annotation_client_manager_direct_transfer(db, source.id)

    assert preview["project_count"] == 1
    assert preview["status_counts"] == {"project_in_progress": 1}
    assert [item["project_id"] for item in preview["projects"]] == [active_project.id]
