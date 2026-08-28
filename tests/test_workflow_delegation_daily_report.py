import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import main  # noqa: F401  注册完整 SQLAlchemy 模型
from task_activity_service import activity_to_report_item
from task_models import DailyReportItem, TaskActivityEvent
from task_service import merge_daily_report_items
from workflow_delegation_service import permanent_handover_applies_to_current_item
from workflow_models import WorkflowHandoverRequest, WorkflowTaskDelegation
from workflow_schemas import WorkflowHandoverRequest as WorkflowHandoverPayload


def test_delegation_payload_requires_end_time():
    with pytest.raises(ValueError, match="计划结束时间"):
        WorkflowHandoverPayload(
            workflow_instance_ids=[uuid4()],
            target_user_id=uuid4(),
            handover_type="leave_time_off",
            transfer_mode="delegation",
        )


def test_permanent_payload_discards_delegation_end_time():
    payload = WorkflowHandoverPayload(
        workflow_instance_ids=[uuid4()],
        target_user_id=uuid4(),
        handover_type="daily_shift",
        transfer_mode="permanent",
        delegation_end_at=datetime.datetime(2026, 9, 1, 18, 0),
    )
    assert payload.delegation_end_at is None


def test_system_activity_is_zero_duration_report_item():
    event = SimpleNamespace(
        id=uuid4(),
        event_type="handover_in",
        counterpart_user_id=uuid4(),
        task_type="项目专员",
        task_name="测试项目",
        description="已接收临时代办任务",
        display_metadata={"order_no": "TP-001"},
        occurred_at=datetime.datetime(2026, 8, 28, 10, 0),
    )
    item = activity_to_report_item(event)
    assert item["source_type"] == "system_event"
    assert item["duration_minutes"] == 0
    assert item["display_metadata"]["event_type"] == "handover_in"


def test_client_cannot_remove_or_modify_system_events():
    client_items = [
        {"source_type": "manual", "task_name": "手工工作", "duration_minutes": 30},
        {"source_type": "system_event", "task_name": "伪造事件", "duration_minutes": 999},
    ]
    derived_items = [
        {"source_type": "system_event", "task_name": "真实交接", "duration_minutes": 10},
        {"source_type": "project", "task_name": "其他派生任务", "duration_minutes": 60},
    ]
    merged = merge_daily_report_items(client_items, derived_items)
    assert [item["task_name"] for item in merged] == ["手工工作", "真实交接"]
    assert merged[1]["duration_minutes"] == 0


def test_delegation_and_daily_report_model_contracts():
    delegation_columns = WorkflowTaskDelegation.__table__.columns
    assert "original_assignee_id" in delegation_columns
    assert "delegate_assignee_id" in delegation_columns
    assert "planned_end_at" in delegation_columns
    assert "overdue_notified_at" in delegation_columns
    handover_columns = WorkflowHandoverRequest.__table__.columns
    assert "transfer_mode" in handover_columns
    assert "delegation_end_at" in handover_columns
    source_constraint = next(
        item for item in DailyReportItem.__table__.constraints
        if item.name == "ck_daily_report_item_source_type"
    )
    assert "system_event" in str(source_constraint.sqltext)
    event_types = next(
        item for item in TaskActivityEvent.__table__.constraints
        if item.name == "ck_task_activity_event_type"
    )
    assert "return_in" in str(event_types.sqltext)


def test_permanent_handover_history_does_not_leak_into_next_role_pool_stage():
    target_user_id = uuid4()
    request = SimpleNamespace(target_user_id=target_user_id)

    assert permanent_handover_applies_to_current_item(
        {
            "assignment_type": "direct",
            "group_assign_role": None,
            "current_assignee_id": target_user_id,
        },
        request,
    )
    assert not permanent_handover_applies_to_current_item(
        {
            "assignment_type": "role_pool",
            "group_assign_role": "项目助理",
            "current_assignee_id": None,
        },
        request,
    )
    assert not permanent_handover_applies_to_current_item(
        {
            "assignment_type": "direct",
            "group_assign_role": None,
            "current_assignee_id": uuid4(),
        },
        request,
    )
