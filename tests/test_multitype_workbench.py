from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from project_workbench_service import (
    PROJECT_DETAIL_ROUTES,
    TRANSLATION_INACTIVE_STATUSES,
    _deadline,
    assignment_map_from_payload,
    is_active_project,
)
from workflow_crud import _active_translation_project_clause, _ensure_active_workflow_instances
from task_schemas import WorkEntryCreate
from task_service import create_work_entry
from workflow_models import ProjectWorkbenchResponsibility


@pytest.mark.parametrize(
    ("project_type", "status", "expected"),
    [
        ("translation", "translator_returned", True),
        ("translation", "sent_to_client", False),
        ("translation", "client_feedback", False),
        ("translation", "feedback_sent_to_client", False),
        ("interpretation", "initial_follow_up", True),
        ("interpretation", "ended", False),
        ("annotation", "sent_to_client", False),
        ("annotation", "client_feedback", False),
        ("recruitment", "probation", True),
        ("recruitment", "closed", False),
    ],
)
def test_multitype_workbench_active_status_scope(project_type, status, expected):
    assert is_active_project(project_type, status) is expected


def test_translation_workbench_query_excludes_every_delivered_status():
    sql = str(_active_translation_project_clause().compile(dialect=postgresql.dialect()))
    params = _active_translation_project_clause().compile(dialect=postgresql.dialect()).params

    assert "translation_project.project_status" in sql
    status_values = next(
        value
        for value in params.values()
        if isinstance(value, (list, tuple, set, frozenset))
    )
    assert set(status_values) == set(TRANSLATION_INACTIVE_STATUSES)


def test_workflow_actions_reject_delivered_projects():
    active = SimpleNamespace(
        translation_project=SimpleNamespace(project_status="translator_returned"),
        sub_order=None,
    )
    delivered = SimpleNamespace(
        translation_project=SimpleNamespace(project_status="sent_to_client"),
        sub_order=None,
    )

    _ensure_active_workflow_instances([active])
    with pytest.raises(LookupError, match="工作台活跃范围"):
        _ensure_active_workflow_instances([delivered])


def test_work_entry_rejects_inactive_project_responsibility():
    operator = SimpleNamespace(id=uuid4())
    responsibility = SimpleNamespace(
        assignee_id=operator.id,
        project_type="translation",
        project=SimpleNamespace(project_status="sent_to_client"),
    )

    class Query:
        def filter(self, *_conditions):
            return self

        def first(self):
            return responsibility

    db = SimpleNamespace(query=lambda _model: Query())
    payload = WorkEntryCreate(
        work_date=date(2026, 9, 3),
        project_responsibility_id=uuid4(),
        progress_content="补充项目进展",
    )

    with pytest.raises(ValueError, match="工作台活跃范围"):
        create_work_entry(db, operator, payload)


def test_multitype_deadline_adapters():
    interpretation = SimpleNamespace(time_ranges=[
        SimpleNamespace(scheduled_end=datetime(2026, 8, 25, 18)),
        SimpleNamespace(scheduled_end=datetime(2026, 8, 26, 12)),
    ])
    recruitment = SimpleNamespace(
        target_onboard_type="date",
        target_onboard_date=date(2026, 9, 1),
    )
    assert _deadline("interpretation", interpretation) == datetime(2026, 8, 26, 12)
    assert _deadline("annotation", SimpleNamespace()) is None
    assert _deadline("recruitment", recruitment) == datetime(2026, 9, 1, 23, 59, 59)


def test_assignment_payload_and_generic_work_entry_contract():
    manager_id = uuid4()
    assignments = assignment_map_from_payload([
        {"role_code": "project_manager", "assignee_id": manager_id},
        {"role_code": "project_specialist", "assignee_id": None},
    ])
    assert assignments == {
        "project_manager": manager_id,
        "project_specialist": None,
    }
    entry = WorkEntryCreate(
        work_date=date(2026, 8, 25),
        project_responsibility_id=uuid4(),
        progress_content="完成需求沟通",
    )
    assert entry.workflow_instance_id is None
    with pytest.raises(ValueError, match="必须且只能选择一个"):
        WorkEntryCreate(
            work_date=date(2026, 8, 25),
            project_responsibility_id=uuid4(),
            workflow_instance_id=uuid4(),
            progress_content="重复来源",
        )


def test_responsibility_model_constraints_and_routes():
    constraint_names = {item.name for item in ProjectWorkbenchResponsibility.__table__.constraints}
    assert "ck_workbench_resp_exactly_one_project" in constraint_names
    assert "uq_workbench_resp_interpretation_role" in constraint_names
    assert "uq_workbench_resp_annotation_role" in constraint_names
    assert "uq_workbench_resp_recruitment_role" in constraint_names
    assert PROJECT_DETAIL_ROUTES == {
        "translation": "TranslationProjectDetails",
        "interpretation": "InterpretationProjectDetails",
        "annotation": "AnnotationProjectDetails",
        "recruitment": "RecruitmentProjectDetails",
    }
