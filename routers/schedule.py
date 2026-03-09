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


def _normalize_task(task):
    task = task or {}
    return {
        "category": task.get("category") or "",
        "project_name": task.get("project_name")
        or task.get("projectName")
        or task.get("content")
        or task.get("project_or_task")
        or task.get("projectOrTask")
        or "",
        "order_no": task.get("order_no")
        or task.get("orderNo")
        or task.get("project_no")
        or task.get("projectNo")
        or "",
        "customer_deadline_time": task.get("customer_deadline_time")
        or task.get("customerDeadlineTime")
        or task.get("deadline")
        or "",
        "project_status": task.get("project_status")
        or task.get("projectStatus")
        or task.get("status")
        or "",
    }


def _normalize_dept_person(person):
    person = person or {}
    tasks = person.get("tasks")
    fixed_tasks = person.get("fixed_tasks") if person.get("fixed_tasks") is not None else person.get("fixedTasks")
    return {
        "name": person.get("name") or "",
        "dept": person.get("dept") or "",
        "status": person.get("status") or "scheduled",
        "tasks": [_normalize_task(t) for t in tasks] if isinstance(tasks, list) else [],
        "fixed_tasks": fixed_tasks if isinstance(fixed_tasks, list) else [],
    }


def _normalize_not_scheduled(item):
    item = item or {}
    return {
        "person_name": item.get("person_name") or item.get("personName") or "",
        "department": item.get("department") or "",
        "project_name": item.get("project_name")
        or item.get("projectName")
        or item.get("project_or_task")
        or item.get("projectOrTask")
        or "",
        "order_no": item.get("order_no")
        or item.get("orderNo")
        or item.get("project_no")
        or item.get("projectNo")
        or "",
        "customer_deadline_time": item.get("customer_deadline_time")
        or item.get("customerDeadlineTime")
        or item.get("deadline")
        or "",
        "remarks": item.get("remarks") or "",
    }


def _normalize_schedule_payload(payload: dict) -> dict:
    if "dept_person_data" in payload and isinstance(payload["dept_person_data"], list):
        payload["dept_person_data"] = [_normalize_dept_person(p) for p in payload["dept_person_data"]]
    if "not_scheduled_tasks" in payload and isinstance(payload["not_scheduled_tasks"], list):
        payload["not_scheduled_tasks"] = [_normalize_not_scheduled(i) for i in payload["not_scheduled_tasks"]]
    return payload


def _normalize_schedule_record(record: WorkSchedule) -> WorkSchedule:
    record.dept_person_data = [_normalize_dept_person(p) for p in (record.dept_person_data or [])]
    record.not_scheduled_tasks = [_normalize_not_scheduled(i) for i in (record.not_scheduled_tasks or [])]
    return record


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
    return _normalize_schedule_record(record)


@router.put("/{schedule_date}", response_model=WorkScheduleResponse)
def upsert_schedule(
    schedule_date: date,
    data: WorkScheduleUpdate,
    db: Session = Depends(get_db),
):
    """创建或更新某日的排班数据（Upsert）"""
    record = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == schedule_date).first()
    payload = _normalize_schedule_payload(data.model_dump(exclude_unset=True))

    if record:
        update_data = payload
        for key, value in update_data.items():
            setattr(record, key, value)
        record.updated_at = datetime.utcnow()
    else:
        create_data = payload
        record = WorkSchedule(schedule_date=schedule_date, **create_data)
        db.add(record)

    db.commit()
    db.refresh(record)
    return _normalize_schedule_record(record)


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

    normalized_dept_person_data = [_normalize_dept_person(p) for p in (source.dept_person_data or [])]
    normalized_not_scheduled_tasks = [_normalize_not_scheduled(i) for i in (source.not_scheduled_tasks or [])]

    existing = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == target_date).first()
    if existing:
        existing.shift_table = source.shift_table
        existing.leave_notes = source.leave_notes
        existing.urgent_table_zh_en = source.urgent_table_zh_en
        existing.urgent_table_en_zh = source.urgent_table_en_zh
        existing.dept_person_data = normalized_dept_person_data
        existing.not_scheduled_tasks = normalized_not_scheduled_tasks
        existing.pm_rotation_order = source.pm_rotation_order
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return _normalize_schedule_record(existing)
    else:
        new_record = WorkSchedule(
            schedule_date=target_date,
            shift_table=source.shift_table,
            leave_notes=source.leave_notes,
            urgent_table_zh_en=source.urgent_table_zh_en,
            urgent_table_en_zh=source.urgent_table_en_zh,
            dept_person_data=normalized_dept_person_data,
            not_scheduled_tasks=normalized_not_scheduled_tasks,
            pm_rotation_order=source.pm_rotation_order,
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return _normalize_schedule_record(new_record)


@router.delete("/{schedule_date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_date: date, db: Session = Depends(get_db)):
    """删除某日的排班数据"""
    record = db.query(WorkSchedule).filter(WorkSchedule.schedule_date == schedule_date).first()
    if not record:
        raise HTTPException(status_code=404, detail="该日期暂无排班数据")
    db.delete(record)
    db.commit()
