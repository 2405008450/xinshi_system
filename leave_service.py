"""请假时间与任务可分配性公共规则。"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models import EmployeeLeave


BUSINESS_TIMEZONE = ZoneInfo("Asia/Hong_Kong")


def business_now() -> datetime:
    """数据库沿用无时区时间，统一以香港本地时间比较。"""
    return datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)


def normalize_business_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None)


def leave_status(record: EmployeeLeave, at: Optional[datetime] = None) -> str:
    moment = normalize_business_datetime(at) if at else business_now()
    if record.start_date <= moment < record.end_date:
        return "active"
    return "upcoming" if record.start_date > moment else "past"


def active_leave_query(db: Session, at: Optional[datetime] = None):
    moment = normalize_business_datetime(at) if at else business_now()
    return db.query(EmployeeLeave).filter(
        EmployeeLeave.start_date <= moment,
        EmployeeLeave.end_date > moment,
    )


def get_active_leave(db: Session, user_id: UUID, at: Optional[datetime] = None) -> Optional[EmployeeLeave]:
    return (
        active_leave_query(db, at)
        .filter(EmployeeLeave.employee_id == user_id)
        .order_by(EmployeeLeave.end_date.asc())
        .first()
    )


def get_active_leave_map(
    db: Session,
    user_ids: Iterable[UUID],
    at: Optional[datetime] = None,
) -> dict[UUID, EmployeeLeave]:
    ids = set(user_ids)
    if not ids:
        return {}
    records = (
        active_leave_query(db, at)
        .filter(EmployeeLeave.employee_id.in_(ids))
        .order_by(EmployeeLeave.end_date.asc())
        .all()
    )
    result: dict[UUID, EmployeeLeave] = {}
    for record in records:
        result.setdefault(record.employee_id, record)
    return result


def assignment_disabled_reason(record: Optional[EmployeeLeave]) -> Optional[str]:
    if not record:
        return None
    employee_name = record.employee.full_name or record.employee.username if record.employee else record.employee_name
    return f"{employee_name}正在请假，至{record.end_date.strftime('%Y-%m-%d %H:%M')}结束"


def ensure_user_assignable(db: Session, user_id: UUID, at: Optional[datetime] = None) -> None:
    record = get_active_leave(db, user_id, at)
    if record:
        raise ValueError(assignment_disabled_reason(record))

