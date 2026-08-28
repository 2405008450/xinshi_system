"""任务交接活动与个人日报联动。"""
from __future__ import annotations

import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from task_models import DailyReport, DailyReportItem, TaskActivityEvent


BUSINESS_TZ = ZoneInfo("Asia/Hong_Kong")


def _now() -> datetime.datetime:
    return datetime.datetime.now(BUSINESS_TZ).replace(tzinfo=None)


def _append_event_to_draft(db: Session, event: TaskActivityEvent) -> None:
    report = db.query(DailyReport).filter(
        DailyReport.user_id == event.user_id,
        DailyReport.report_date == event.occurred_at.date(),
        DailyReport.status == "draft",
    ).first()
    if not report:
        return
    db.flush()
    exists = db.query(DailyReportItem.id).filter(
        DailyReportItem.report_id == report.id,
        DailyReportItem.source_type == "system_event",
        DailyReportItem.source_id == event.id,
    ).first()
    if exists:
        return
    next_order = max((item.sort_order for item in report.items), default=-1) + 1
    report.items.append(DailyReportItem(
        source_type="system_event",
        source_id=event.id,
        task_type=event.task_type,
        task_name=event.task_name,
        progress_content=event.description,
        result_content=None,
        duration_minutes=0,
        display_metadata={
            **(event.display_metadata or {}),
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "counterpart_user_id": str(event.counterpart_user_id) if event.counterpart_user_id else None,
        },
        sort_order=next_order,
    ))
    report.updated_at = _now()


def record_task_activity(
    db: Session,
    *,
    event_key: str,
    user_id: UUID,
    counterpart_user_id: UUID | None,
    event_type: str,
    workflow_instance_id: UUID | None,
    project_responsibility_id: UUID | None,
    handover_request_id: UUID | None,
    delegation_id: UUID | None,
    task_type: str,
    task_name: str,
    description: str,
    display_metadata: dict | None = None,
    occurred_at: datetime.datetime | None = None,
) -> TaskActivityEvent:
    existing = db.query(TaskActivityEvent).filter(
        TaskActivityEvent.event_key == event_key
    ).first()
    if existing:
        return existing
    event = TaskActivityEvent(
        event_key=event_key,
        user_id=user_id,
        counterpart_user_id=counterpart_user_id,
        event_type=event_type,
        workflow_instance_id=workflow_instance_id,
        project_responsibility_id=project_responsibility_id,
        handover_request_id=handover_request_id,
        delegation_id=delegation_id,
        task_type=(task_type or "项目任务")[:50],
        task_name=(task_name or "项目任务")[:255],
        description=description,
        display_metadata=display_metadata or {},
        occurred_at=occurred_at or _now(),
    )
    db.add(event)
    _append_event_to_draft(db, event)
    return event


def activity_to_report_item(event: TaskActivityEvent) -> dict:
    return {
        "source_type": "system_event",
        "source_id": event.id,
        "task_type": event.task_type,
        "task_name": event.task_name,
        "progress_content": event.description,
        "result_content": None,
        "duration_minutes": 0,
        "display_metadata": {
            **(event.display_metadata or {}),
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "counterpart_user_id": str(event.counterpart_user_id) if event.counterpart_user_id else None,
        },
    }
