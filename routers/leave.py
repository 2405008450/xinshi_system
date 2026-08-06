"""员工请假、工作台概览与实时请假状态接口。"""
from datetime import date, datetime, time, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from leave_service import business_now, leave_status, normalize_business_datetime
from models import AppUser, EmployeeLeave
from routers.auth import get_current_user, require_permission
from schemas import EmployeeLeaveCreate, EmployeeLeaveResponse, EmployeeLeaveUpdate


router = APIRouter(prefix="/leave", tags=["leave"])


def _serialize_leave(record: EmployeeLeave, current_user_id: Optional[UUID] = None) -> dict:
    employee = record.employee
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "employee_name": (employee.full_name or employee.username) if employee else record.employee_name,
        "department": employee.department if employee else None,
        "start_date": record.start_date,
        "end_date": record.end_date,
        "leave_type": record.leave_type,
        "reason": record.reason,
        "status": leave_status(record),
        "is_current_user": bool(current_user_id and record.employee_id == current_user_id),
        "created_by": record.created_by,
        "updated_by": record.updated_by,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _get_employee(db: Session, employee_id: UUID) -> AppUser:
    employee = db.query(AppUser).filter(AppUser.id == employee_id, AppUser.is_active == True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="员工不存在或已停用")
    return employee


def _normalize_window(start_date: datetime, end_date: datetime) -> tuple[datetime, datetime]:
    start_value = normalize_business_datetime(start_date)
    end_value = normalize_business_datetime(end_date)
    if end_value <= start_value:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
    return start_value, end_value


def _ensure_no_overlap(
    db: Session,
    employee_id: UUID,
    start_date: datetime,
    end_date: datetime,
    exclude_id: Optional[UUID] = None,
) -> None:
    query = db.query(EmployeeLeave.id).filter(
        EmployeeLeave.employee_id == employee_id,
        EmployeeLeave.start_date < end_date,
        EmployeeLeave.end_date > start_date,
    )
    if exclude_id:
        query = query.filter(EmployeeLeave.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="该员工在所选时间段已有请假记录")


@router.get("/on-leave", response_model=List[EmployeeLeaveResponse])
def get_on_leave_users(
    query_date: Optional[date] = Query(None, alias="date"),
    exact_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(get_current_user),
):
    query = db.query(EmployeeLeave).options(joinedload(EmployeeLeave.employee))
    if exact_time:
        moment = normalize_business_datetime(exact_time)
        query = query.filter(EmployeeLeave.start_date <= moment, EmployeeLeave.end_date > moment)
    elif query_date:
        start_of_day = datetime.combine(query_date, time.min)
        end_of_day = start_of_day + timedelta(days=1)
        query = query.filter(EmployeeLeave.start_date < end_of_day, EmployeeLeave.end_date > start_of_day)
    else:
        moment = business_now()
        query = query.filter(EmployeeLeave.start_date <= moment, EmployeeLeave.end_date > moment)
    return [_serialize_leave(record) for record in query.order_by(EmployeeLeave.end_date.asc()).all()]


@router.get("/overview", response_model=List[EmployeeLeaveResponse])
def get_leave_overview(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    start_value = normalize_business_datetime(start_date) if start_date else business_now()
    end_value = normalize_business_datetime(end_date) if end_date else start_value + timedelta(days=30)
    query = (
        db.query(EmployeeLeave)
        .join(AppUser, AppUser.id == EmployeeLeave.employee_id)
        .options(joinedload(EmployeeLeave.employee))
        .filter(EmployeeLeave.start_date < end_value, EmployeeLeave.end_date > start_value)
    )
    # 公司内部请假属于全员可见信息；已登录用户不再按本人部门收窄范围。
    records = query.order_by(EmployeeLeave.start_date.asc()).all()
    return [_serialize_leave(record, current_user.id) for record in records]


@router.get("/", response_model=List[EmployeeLeaveResponse], dependencies=[Depends(require_permission("schedule:read"))])
def list_leave_records(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    employee_keyword: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(EmployeeLeave)
        .join(AppUser, AppUser.id == EmployeeLeave.employee_id)
        .options(joinedload(EmployeeLeave.employee))
    )
    if start_date:
        query = query.filter(EmployeeLeave.end_date > normalize_business_datetime(start_date))
    if end_date:
        query = query.filter(EmployeeLeave.start_date < normalize_business_datetime(end_date))
    if employee_keyword and employee_keyword.strip():
        pattern = f"%{employee_keyword.strip()}%"
        query = query.filter(or_(AppUser.full_name.ilike(pattern), AppUser.username.ilike(pattern)))
    moment = business_now()
    if status_filter == "active":
        query = query.filter(EmployeeLeave.start_date <= moment, EmployeeLeave.end_date > moment)
    elif status_filter == "upcoming":
        query = query.filter(EmployeeLeave.start_date > moment)
    elif status_filter == "past":
        query = query.filter(EmployeeLeave.end_date <= moment)
    return [_serialize_leave(record) for record in query.order_by(EmployeeLeave.start_date.desc()).all()]


@router.post("/", response_model=EmployeeLeaveResponse, status_code=status.HTTP_201_CREATED)
def create_leave_record(
    data: EmployeeLeaveCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_permission("schedule:write")),
):
    employee = _get_employee(db, data.employee_id)
    start_value, end_value = _normalize_window(data.start_date, data.end_date)
    _ensure_no_overlap(db, employee.id, start_value, end_value)
    record = EmployeeLeave(
        employee_id=employee.id,
        employee_name=employee.full_name or employee.username,
        start_date=start_value,
        end_date=end_value,
        leave_type=data.leave_type,
        reason=data.reason,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(record)
    db.commit()
    record = db.query(EmployeeLeave).options(joinedload(EmployeeLeave.employee)).filter(EmployeeLeave.id == record.id).first()
    return _serialize_leave(record)


@router.put("/{leave_id}", response_model=EmployeeLeaveResponse)
def update_leave_record(
    leave_id: UUID,
    data: EmployeeLeaveUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_permission("schedule:write")),
):
    record = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="请假记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    employee_id = update_data.get("employee_id", record.employee_id)
    employee = _get_employee(db, employee_id)
    start_value, end_value = _normalize_window(
        update_data.get("start_date", record.start_date),
        update_data.get("end_date", record.end_date),
    )
    _ensure_no_overlap(db, employee.id, start_value, end_value, exclude_id=record.id)
    record.employee_id = employee.id
    record.employee_name = employee.full_name or employee.username
    record.start_date = start_value
    record.end_date = end_value
    if "leave_type" in update_data:
        record.leave_type = update_data["leave_type"]
    if "reason" in update_data:
        record.reason = update_data["reason"]
    record.updated_by = current_user.id
    record.updated_at = business_now()
    db.commit()
    record = db.query(EmployeeLeave).options(joinedload(EmployeeLeave.employee)).filter(EmployeeLeave.id == record.id).first()
    return _serialize_leave(record)


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave_record(
    leave_id: UUID,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_permission("schedule:write")),
):
    record = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="请假记录不存在")
    db.delete(record)
    db.commit()
    return None
