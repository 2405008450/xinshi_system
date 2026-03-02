"""
排班管理 API 路由
支持按日期 CRUD 操作，项目经理每日微调排班数据
"""
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from models import WorkSchedule, AppUser, Translator
from schemas import WorkScheduleCreate, WorkScheduleUpdate, WorkScheduleResponse

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("/staff/list")
def get_staff_list(db: Session = Depends(get_db)):
    """获取所有活跃内部员工列表（用于排班页面初始化人员模板）"""
    users = db.query(AppUser).filter(AppUser.is_active == True).all()
    result = []
    for u in users:
        result.append({
            "id": str(u.id),
            "name": u.full_name or u.username,
            "dept": u.department or "",
            "fixedTasks": u.fixed_tasks or [],
        })
    return result


@router.get("/translators/list")
def get_translator_list(
    direction: Optional[str] = Query(None, description="翻译方向: zh_en / en_zh / both"),
    db: Session = Depends(get_db),
):
    """获取所有译员列表（含排班属性），用于译员优先次序表初始化"""
    query = db.query(Translator)
    if direction:
        query = query.filter(
            (Translator.direction == direction) | (Translator.direction == "both") | (Translator.direction == None)
        )
    translators = query.all()
    result = []
    for t in translators:
        result.append({
            "id": str(t.id),
            "name": t.translator_name,
            "type": t.translation_type or "",
            "quality": t.quality_score or "",
            "cloudRev": t.cloud_revision or "",
            "dailyRate": t.daily_rate or "",
            "direction": t.direction or "",
            "order": str(t.default_priority) if t.default_priority else "N/A",
            "remarks": t.schedule_remarks or "",
        })
    return result


@router.get("/{schedule_date}", response_model=WorkScheduleResponse)
def get_schedule(schedule_date: date, db: Session = Depends(get_db)):
    """获取某日的排班数据"""
    record = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == schedule_date).first()
    if not record:
        raise HTTPException(status_code=404, detail="该日期暂无排班数据")
    return record


@router.put("/{schedule_date}", response_model=WorkScheduleResponse)
def upsert_schedule(
    schedule_date: date,
    data: WorkScheduleUpdate,
    db: Session = Depends(get_db),
):
    """创建或更新某日的排班数据（Upsert）"""
    record = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == schedule_date).first()

    if record:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(record, key, value)
        record.updated_at = datetime.utcnow()
    else:
        create_data = data.model_dump(exclude_unset=True)
        record = WorkSchedule(schedule_date=schedule_date, **create_data)
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


@router.post("/copy", response_model=WorkScheduleResponse)
def copy_schedule(
    source_date: date = Query(..., description="源日期"),
    target_date: date = Query(..., description="目标日期"),
    db: Session = Depends(get_db),
):
    """将某一天的排班复制到另外一天（用于"从昨日复制"功能）"""
    source = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == source_date).first()
    if not source:
        raise HTTPException(status_code=404, detail="源日期暂无排班数据")

    existing = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == target_date).first()
    if existing:
        existing.shift_table = source.shift_table
        existing.leave_notes = source.leave_notes
        existing.urgent_table_zh_en = source.urgent_table_zh_en
        existing.urgent_table_en_zh = source.urgent_table_en_zh
        existing.dept_person_data = source.dept_person_data
        existing.not_scheduled_tasks = source.not_scheduled_tasks
        existing.pm_rotation_order = source.pm_rotation_order
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_record = WorkSchedule(
            schedule_date=target_date,
            shift_table=source.shift_table,
            leave_notes=source.leave_notes,
            urgent_table_zh_en=source.urgent_table_zh_en,
            urgent_table_en_zh=source.urgent_table_en_zh,
            dept_person_data=source.dept_person_data,
            not_scheduled_tasks=source.not_scheduled_tasks,
            pm_rotation_order=source.pm_rotation_order,
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return new_record


@router.delete("/{schedule_date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_date: date, db: Session = Depends(get_db)):
    """删除某日的排班数据"""
    record = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == schedule_date).first()
    if not record:
        raise HTTPException(status_code=404, detail="该日期暂无排班数据")
    db.delete(record)
    db.commit()
