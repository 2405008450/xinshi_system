from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, joinedload, selectinload

import workflow_crud
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
