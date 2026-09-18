from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.params import Depends

import annotation_ops_service
import recruitment_models  # noqa: F401  # 完整注册工作台关联模型，避免孤立测试配置 mapper 失败。
from annotation_ops_models import (
    AnnotationArrangementTaskType,
    AnnotationProjectArrangementScope,
    AnnotationProjectArrangementTask,
    AnnotationProjectStatusHistory,
)
from annotation_ops_schemas import (
    ArrangementBatchWrite,
    ArrangementMembershipWrite,
    ArrangementOverviewResponse,
    ArrangementTaskTypeWrite,
    ArrangementWorkloadResponse,
)
from annotation_ops_service import (
    ARRANGEMENT_INACTIVE_PROJECT_STATUSES,
    _arrangement_project_dict,
    set_arrangement_membership,
    update_progress_history,
)
from routers.annotation_ops import update_project_arrangement_membership
from routers.auth import require_super_admin


def test_arrangement_models_keep_project_fields_live_through_foreign_key():
    task_columns = AnnotationProjectArrangementTask.__table__.c
    assert "project_name" not in task_columns
    assert "client_name" not in task_columns
    assert "project_status" not in task_columns
    assert {
        foreign_key.target_fullname
        for foreign_key in task_columns.project_id.foreign_keys
    } == {"annotation_project.id"}
    assert next(iter(task_columns.project_id.foreign_keys)).ondelete == "CASCADE"
    scope_columns = AnnotationProjectArrangementScope.__table__.c
    assert {"project_id", "is_active", "membership_note", "created_by", "updated_by", "created_at", "updated_at"} <= set(scope_columns.keys())
    assert next(iter(scope_columns.project_id.foreign_keys)).target_fullname == "annotation_project.id"
    assert next(iter(scope_columns.project_id.foreign_keys)).ondelete == "CASCADE"


def test_arrangement_task_type_name_is_normalized_and_batch_defaults_are_empty():
    payload = ArrangementTaskTypeWrite(name="  数据   清洗  ")
    batch = ArrangementBatchWrite()

    assert payload.name == "数据 清洗"
    assert batch.items == []
    assert batch.deleted_items == []
    assert "normalized_name" in AnnotationArrangementTaskType.__table__.c


def test_progress_history_has_explicit_kind_and_edit_metadata():
    columns = AnnotationProjectStatusHistory.__table__.c
    assert columns.entry_kind.server_default.arg.text == "'status'"
    assert "updated_at" in columns
    assert "updated_by" in columns


def test_arrangement_overview_contract_covers_projects_summary_and_workloads():
    overview_fields = ArrangementOverviewResponse.model_fields
    workload_fields = ArrangementWorkloadResponse.model_fields

    assert {"items", "total", "summary", "task_types", "assignees"} <= set(overview_fields)
    assert {"items", "total"} <= set(workload_fields)
    assert ARRANGEMENT_INACTIVE_PROJECT_STATUSES == {
        "consultation_no_result",
        "resource_sourcing_cancelled",
        "cancelled",
        "actively_abandoned",
        "ended",
    }


def test_arrangement_overview_project_status_is_derived_from_selected_date_tasks():
    client = SimpleNamespace(client_short_name="瀹㈡埛A", client_name="瀹㈡埛A鍏ㄧО")
    manager = SimpleNamespace(id=uuid4(), full_name="椤圭洰缁忕悊", username="manager")
    project = SimpleNamespace(
        id=uuid4(), order_no="AP-260918-001", client_id=uuid4(), client=client,
        sub_client=None, project_name="鏍囨敞椤圭洰", project_types=["audio_annotation"],
        task_description="闊抽鏍囨敞", project_status="project_in_progress",
        priority="medium", status_effective_on=datetime(2026, 9, 18, 9, 0),
        custom_values={}, potential_demand=None, project_path=None,
        quotation_path=None, contract_path=None, task_dispatched_at=None,
        task_submitted_at=None, contact_name=None, customer_order_no=None,
        email_subject_preview=None, sub_client_id=None,
        client_short_name="瀹㈡埛A", client_code=None, client_full_name="瀹㈡埛A鍏ㄧО",
        sub_client_contact=None, language_items_display=None,
        customer_price_summary=None, assignee_summary=None,
        role_assignments=[], language_items=[], arrangement_included=True,
        arrangement_membership_updated_at=None,
        created_at=datetime(2026, 9, 18, 9, 0),
        updated_at=datetime(2026, 9, 18, 9, 0),
        client_manager_id=None, client_manager=None,
        workbench_responsibilities=[SimpleNamespace(
            role_code="project_manager", assignee=manager,
        )],
    )

    unarranged = _arrangement_project_dict(project, [])
    arranged = _arrangement_project_dict(project, [{"assignee_name": "Alice"}])

    assert unarranged["arrangement_status"] == "unarranged"
    assert unarranged["task_count"] == 0
    assert arranged["arrangement_status"] == "arranged"
    assert arranged["assignee_names"] == ["Alice"]
    assert arranged["project_manager_id"] == manager.id


class MembershipDb:
    def __init__(self, project, scope=None):
        self.project = project
        self.scope = scope
        self.added = None
        self.committed = False

    def get(self, model, _row_id):
        if model.__name__ == "AnnotationProject":
            return self.project
        return self.scope

    def add(self, row):
        self.scope = row
        self.added = row

    def commit(self):
        self.committed = True

    def refresh(self, _row):
        pass


def test_arrangement_membership_is_idempotent_and_soft_removed():
    project_id = uuid4()
    actor_id = uuid4()
    db = MembershipDb(SimpleNamespace(id=project_id))

    included = set_arrangement_membership(
        db, project_id, ArrangementMembershipWrite(included=True, membership_note="  优先安排  "), actor_id,
    )
    assert included["included"] is True
    assert included["membership_note"] == "优先安排"
    assert db.added.project_id == project_id
    assert db.committed is True

    db.committed = False
    repeated = set_arrangement_membership(
        db, project_id, ArrangementMembershipWrite(included=True, membership_note="优先安排"), actor_id,
    )
    assert repeated == included
    assert db.committed is False

    removed = set_arrangement_membership(
        db, project_id,
        ArrangementMembershipWrite(
            included=False, expected_updated_at=db.scope.updated_at,
        ),
        actor_id,
    )
    assert removed["included"] is False
    assert db.scope.is_active is False
    assert db.committed is True


def test_arrangement_membership_requires_note_when_included():
    with pytest.raises(ValueError, match="请填写备注"):
        ArrangementMembershipWrite(included=True, membership_note="   ")


def test_arrangement_membership_endpoint_requires_super_admin():
    import inspect

    dependency = inspect.signature(
        update_project_arrangement_membership,
    ).parameters["user"].default
    assert isinstance(dependency, Depends)
    assert dependency.dependency is require_super_admin


class ProgressDb:
    def __init__(self, row):
        self.row = row
        self.committed = False

    def get(self, _model, _row_id):
        return self.row

    def commit(self):
        self.committed = True


def test_only_progress_history_can_be_edited(monkeypatch):
    project_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        from_status="trial_in_progress",
        to_status="trial_passed",
        entry_kind="status",
        effective_on=datetime(2026, 9, 18, 9, 0),
        change_note="状态变化",
        updated_at=datetime(2026, 9, 18, 9, 0),
        updated_by=None,
    )
    payload = SimpleNamespace(
        effective_on=datetime(2026, 9, 18, 10, 0),
        change_note="不允许修改",
        expected_updated_at=row.updated_at,
    )

    with pytest.raises(ValueError, match="状态流转记录不可"):
        update_progress_history(ProgressDb(row), row.id, payload, uuid4())

    row.entry_kind = "progress"
    monkeypatch.setattr(annotation_ops_service, "list_status_history", lambda _db, value: [value])
    db = ProgressDb(row)
    result = update_progress_history(db, row.id, payload, uuid4())

    assert result == [project_id]
    assert row.change_note == "不允许修改"
    assert row.effective_on == payload.effective_on
    assert db.committed is True
