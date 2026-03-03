"""
员工请假 RESTful API
"""
from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import EmployeeLeave
from schemas import EmployeeLeaveCreate, EmployeeLeaveUpdate, EmployeeLeaveResponse

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("/on-leave", response_model=List[EmployeeLeaveResponse])
def get_on_leave_users(
    query_date: Optional[date] = Query(None, alias="date", description="查询日期 YYYY-MM-DD"),
    exact_time: Optional[datetime] = Query(None, description="查询精确时间 (ISO)"),
    db: Session = Depends(get_db),
):
    """查询指定日期或精确时间正在请假的员工列表"""
    if exact_time:
        query_time = exact_time.replace(tzinfo=None)
        records = db.query(EmployeeLeave).filter(
            EmployeeLeave.start_date <= query_time,
            EmployeeLeave.end_date >= query_time,
        ).all()
        return records
    elif query_date:
        start_of_day = datetime.combine(query_date, datetime.min.time())
        end_of_day = datetime.combine(query_date, datetime.max.time())
        records = db.query(EmployeeLeave).filter(
            EmployeeLeave.start_date <= end_of_day,
            EmployeeLeave.end_date >= start_of_day,
        ).all()
        return records
    else:
        now = datetime.now()
        records = db.query(EmployeeLeave).filter(
            EmployeeLeave.start_date <= now,
            EmployeeLeave.end_date >= now,
        ).all()
        return records
    return records


@router.get("/", response_model=List[EmployeeLeaveResponse])
def list_leave_records(
    start_date: Optional[datetime] = Query(None, description="筛选开始日期时间（>=）"),
    end_date: Optional[datetime] = Query(None, description="筛选结束日期时间（<=）"),
    db: Session = Depends(get_db),
):
    """列出请假记录，支持按日期范围筛选"""
    query = db.query(EmployeeLeave)
    if start_date:
        query = query.filter(EmployeeLeave.end_date >= start_date)
    if end_date:
        query = query.filter(EmployeeLeave.start_date <= end_date)
    return query.order_by(EmployeeLeave.start_date.desc()).all()


@router.post("/", response_model=EmployeeLeaveResponse, status_code=status.HTTP_201_CREATED)
def create_leave_record(data: EmployeeLeaveCreate, db: Session = Depends(get_db)):
    """新增请假记录"""
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    record = EmployeeLeave(
        employee_id=data.employee_id,
        employee_name=data.employee_name,
        start_date=data.start_date,
        end_date=data.end_date,
        leave_type=data.leave_type,
        reason=data.reason,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/{leave_id}", response_model=EmployeeLeaveResponse)
def update_leave_record(leave_id: UUID, data: EmployeeLeaveUpdate, db: Session = Depends(get_db)):
    """编辑请假记录"""
    record = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="请假记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    # 校验日期逻辑
    new_start = update_data.get("start_date", record.start_date)
    new_end = update_data.get("end_date", record.end_date)
    if new_end < new_start:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    for field, value in update_data.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave_record(leave_id: UUID, db: Session = Depends(get_db)):
    """删除请假记录"""
    record = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="请假记录不存在")
    db.delete(record)
    db.commit()
    return None
