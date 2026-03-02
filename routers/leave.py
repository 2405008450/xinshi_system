"""
员工请假 RESTful API
"""
from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import EmployeeLeave
from schemas import EmployeeLeaveCreate, EmployeeLeaveResponse

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("/on-leave", response_model=List[EmployeeLeaveResponse])
def get_on_leave_users(
    date: date = Query(..., description="查询日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """查询指定日期正在请假的员工列表"""
    records = db.query(EmployeeLeave).filter(
        EmployeeLeave.start_date <= date,
        EmployeeLeave.end_date >= date,
    ).all()
    return records


@router.get("/", response_model=List[EmployeeLeaveResponse])
def list_leave_records(db: Session = Depends(get_db)):
    """列出所有请假记录"""
    return db.query(EmployeeLeave).order_by(EmployeeLeave.start_date.desc()).all()


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


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave_record(leave_id: UUID, db: Session = Depends(get_db)):
    """删除请假记录"""
    record = db.query(EmployeeLeave).filter(EmployeeLeave.id == leave_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="请假记录不存在")
    db.delete(record)
    db.commit()
    return None
