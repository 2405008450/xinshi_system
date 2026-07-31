"""
排班管理 API 路由
支持按日期 CRUD 操作，项目经理每日微调排班数据
"""
from datetime import date, datetime, timedelta
from io import BytesIO
import json
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from openpyxl import load_workbook

from database import get_db
from models import WorkSchedule, AppUser, Translator, TranslatorSchedule
from schemas import (
    WorkScheduleCreate, WorkScheduleUpdate, WorkScheduleResponse,
    TranslatorScheduleCreate, TranslatorScheduleUpdate, TranslatorScheduleResponse
)
from routers.auth import require_module_access

router = APIRouter(prefix="/schedules", tags=["schedules"], dependencies=[Depends(require_module_access("schedule:read", "schedule:write"))])

WEEKDAY_HEADER_MAP = {
    "星期一": 0,
    "星期二": 1,
    "星期三": 2,
    "星期四": 3,
    "星期五": 4,
}


def _normalize_text(value) -> str:
    return str(value or "").strip()


def _normalize_person_name(value) -> str:
    return _normalize_text(value).replace(" ", "")


def _parse_excel_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = _normalize_text(value).replace(".", "/")
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_excel_date(value):
    dt = _parse_excel_datetime(value)
    if dt:
        return dt.date()
    text = _normalize_text(value).replace(".", "/")
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _cell_to_slot_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if float(value) <= 0:
            return ""
        if float(value).is_integer() and int(value) == 1:
            return "可接稿"
        return str(int(value) if float(value).is_integer() else value)
    text = _normalize_text(value)
    if not text:
        return ""
    normalized = text.lower()
    if normalized in {"1", "y", "yes", "true", "可", "可以"}:
        return "可接稿"
    if normalized in {"0", "n", "no", "false", "否"}:
        return ""
    return text


def _parse_acceptance_status(value: str) -> tuple[str, str]:
    normalized = _normalize_text(value)
    if normalized in {"2", "本周期不可接稿", "不能接稿"}:
        return "本周期不可接稿", "cycle_blocked"
    if normalized in {"1", "可接稿"}:
        return "可接稿（按日）", "day_by_day"
    return "可接稿（按日）", "day_by_day"


def _parse_schedule_day_available(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) == 1
    return _normalize_text(value) == "1"


def _resolve_schedule_slot(acceptance_mode: str, day_available: bool, raw_window_value: str) -> str:
    if acceptance_mode == "cycle_blocked":
        return "本周期不可接稿"
    if not day_available:
        return ""
    return raw_window_value or "可接稿"


def _parse_translator_schedule_demo_rows(content: bytes, filename: str, db: Session):
    try:
        workbook = load_workbook(filename=BytesIO(content), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"暂时只支持 Excel xlsx 文件导入：{exc}") from exc

    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel 内容不足，至少需要表头和一行数据")

    headers = [_normalize_text(cell) for cell in rows[0]]
    name_idx = next((i for i, h in enumerate(headers) if "姓名" in h), None)
    submit_time_idx = next((i for i, h in enumerate(headers) if "提交" in h and "时间" in h), None)
    fill_date_idx = next((i for i, h in enumerate(headers) if ("填写" in h and "日期" in h) or ("本周总" in h and "日期" in h)), None)
    remarks_idx = next((i for i, h in enumerate(headers) if "备注" in h), None)
    weekday_columns = {}
    for idx, header in enumerate(headers):
        for weekday, offset in WEEKDAY_HEADER_MAP.items():
            if weekday in header:
                weekday_columns[idx] = offset
                break

    if name_idx is None or not weekday_columns:
        raise HTTPException(status_code=400, detail="未识别到姓名列或星期列，请先保持当前导出模板格式")

    translators = db.query(Translator).all()
    translator_map = {}
    for translator in translators:
        translator_map.setdefault(_normalize_person_name(translator.translator_name), translator)

    preview_items = []
    matched_translators = set()
    unmatched_names = []

    for row_index, row in enumerate(rows[1:], start=2):
        if not row or all(cell in (None, "") for cell in row):
            continue
        raw_name = row[name_idx] if name_idx < len(row) else None
        normalized_name = _normalize_person_name(raw_name)
        if not normalized_name:
            continue

        translator = translator_map.get(normalized_name)
        if not translator:
            unmatched_names.append(_normalize_text(raw_name))
            continue

        base_date = None
        if fill_date_idx is not None and fill_date_idx < len(row):
            base_date = _parse_excel_date(row[fill_date_idx])
        if base_date is None and submit_time_idx is not None and submit_time_idx < len(row):
            submit_dt = _parse_excel_datetime(row[submit_time_idx])
            if submit_dt:
                base_date = submit_dt.date()
        if base_date is None:
            continue

        week_monday = base_date - timedelta(days=base_date.weekday())
        remarks = _normalize_text(row[remarks_idx]) if remarks_idx is not None and remarks_idx < len(row) else ""
        submitted_at = None
        if submit_time_idx is not None and submit_time_idx < len(row):
            submitted_at = _parse_excel_datetime(row[submit_time_idx])

        for col_idx, weekday_offset in weekday_columns.items():
            if col_idx >= len(row):
                continue
            slot_text = _cell_to_slot_text(row[col_idx])
            if not slot_text:
                continue

            schedule_day = week_monday + timedelta(days=weekday_offset)
            existing = (
                db.query(TranslatorSchedule)
                .filter(
                    TranslatorSchedule.translator_id == translator.id,
                    TranslatorSchedule.schedule_date == schedule_day,
                )
                .first()
            )
            preview_items.append({
                "row_no": row_index,
                "translator_id": str(translator.id),
                "translator_name": translator.translator_name,
                "schedule_date": schedule_day.isoformat(),
                "available_time_slot": slot_text,
                "remarks": remarks,
                "last_confirmed_at": submitted_at.isoformat() if submitted_at else None,
                "source_type": "excel_demo",
                "source_ref": filename,
                "action": "update" if existing else "create",
                "existing": bool(existing),
                "existing_available_time_slot": existing.available_time_slot if existing else None,
            })
            matched_translators.add(translator.translator_name)

    return {
        "file_name": filename,
        "sheet_name": sheet.title,
        "headers": headers,
        "preview_items": preview_items,
        "matched_translators": len(matched_translators),
        "unmatched_names": unmatched_names,
    }


def _parse_translator_schedule_demo_rows_v2(content: bytes, filename: str, db: Session):
    try:
        workbook = load_workbook(filename=BytesIO(content), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"暂时只支持 Excel xlsx 文件导入：{exc}") from exc

    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel 内容不足，至少需要表头和一行数据")

    translators = db.query(Translator).all()
    translator_map = {}
    for translator in translators:
        translator_map.setdefault(_normalize_person_name(translator.translator_name), translator)

    preview_items = []
    matched_translators = set()
    unmatched_names = []

    for row_index, row in enumerate(rows[1:], start=2):
        if not row or all(cell in (None, "") for cell in row):
            continue

        raw_name = row[6] if len(row) > 6 else None
        normalized_name = _normalize_person_name(raw_name)
        if not normalized_name:
            continue

        translator = translator_map.get(normalized_name)
        if not translator:
            unmatched_names.append(_normalize_text(raw_name))
            continue

        fill_date = _parse_excel_date(row[7] if len(row) > 7 else None)
        if fill_date is None:
            continue

        submitted_at = _parse_excel_datetime(row[1] if len(row) > 1 else None)
        acceptance_raw = _normalize_text(row[8] if len(row) > 8 else None)
        acceptance_status, acceptance_mode = _parse_acceptance_status(acceptance_raw)
        raw_window_value = _normalize_text(row[9] if len(row) > 9 else None)
        raw_remark_value = _normalize_text(row[15] if len(row) > 15 else None)
        raw_payload = {
            "acceptance_raw": acceptance_raw,
            "acceptance_status": acceptance_status,
            "acceptance_mode": acceptance_mode,
            "time_slot": raw_window_value,
            "note": raw_remark_value,
        }

        for day_offset, col_idx in enumerate(range(10, 15)):
            day_available = _parse_schedule_day_available(row[col_idx] if len(row) > col_idx else None)
            slot_text = _resolve_schedule_slot(acceptance_mode, day_available, raw_window_value)
            if not slot_text:
                continue

            schedule_day = fill_date + timedelta(days=day_offset)
            existing = (
                db.query(TranslatorSchedule)
                .filter(
                    TranslatorSchedule.translator_id == translator.id,
                    TranslatorSchedule.schedule_date == schedule_day,
                )
                .first()
            )
            preview_items.append({
                "row_no": row_index,
                "translator_id": str(translator.id),
                "translator_name": translator.translator_name,
                "fill_date": fill_date.isoformat(),
                "schedule_date": schedule_day.isoformat(),
                "available_time_slot": slot_text,
                "acceptance_raw": acceptance_raw,
                "acceptance_status": acceptance_status,
                "acceptance_mode": acceptance_mode,
                "day_available": day_available,
                "time_slot": raw_window_value,
                "note": raw_remark_value,
                "remarks": json.dumps(raw_payload, ensure_ascii=False),
                "last_confirmed_at": submitted_at.isoformat() if submitted_at else None,
                "source_type": "excel_demo_v2",
                "source_ref": filename,
                "action": "update" if existing else "create",
                "existing": bool(existing),
                "existing_available_time_slot": existing.available_time_slot if existing else None,
            })
            matched_translators.add(translator.translator_name)

    return {
        "file_name": filename,
        "sheet_name": sheet.title,
        "headers": [_normalize_text(cell) for cell in rows[0]],
        "preview_items": preview_items,
        "matched_translators": len(matched_translators),
        "unmatched_names": unmatched_names,
    }


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


def _format_cloud_revision(can_cloud_edit, can_revision) -> str:
    values = []
    for value in (can_cloud_edit, can_revision):
        if value is True:
            values.append("可")
        elif value is False:
            values.append("否")
        else:
            values.append("")
    return "/".join(values).strip("/")


def _format_daily_rate(daily_accept_count, hourly_speed, daily_word_capacity) -> str:
    values = [daily_accept_count, hourly_speed, daily_word_capacity]
    if all(value in (None, "") for value in values):
        return ""
    return "/".join("" if value in (None, "") else str(value) for value in values)


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
    active_only: bool = Query(False, description="仅返回活跃译员"),
    db: Session = Depends(get_db),
):
    """获取所有译员列表（含排班属性），用于译员优先次序表初始化"""
    query = db.query(Translator)
    if direction:
        query = query.filter(
            (Translator.direction == direction) | (Translator.direction == "both") | (Translator.direction == None)
        )
    if active_only:
        query = query.filter(Translator.status == "active")
    query = query.order_by(Translator.default_priority.asc())
    translators = query.all()
    result = []
    for t in translators:
        result.append({
            "id": str(t.id),
            "name": t.translator_name,
            "type": t.translation_type or "",
            "quality": t.quality_score or "",
            "cloudRev": _format_cloud_revision(t.can_cloud_edit, t.can_revision),
            "dailyRate": _format_daily_rate(t.daily_accept_count, t.hourly_speed, t.daily_word_capacity),
            "direction": t.direction or "",
            "order": str(t.default_priority) if t.default_priority else "N/A",
            "remarks": t.schedule_remarks or "",
            "status": t.status or "standby",
            "availableTimeSlot": t.available_time_slot or "",
            "dailyAcceptCount": t.daily_accept_count,
            "hourlySpeed": t.hourly_speed,
            "dailyWordCapacity": t.daily_word_capacity,
            "canCloudEdit": t.can_cloud_edit,
            "canRevision": t.can_revision,
            "domainSkills": t.domain_skills or [],
        })
    return result


@router.get("/translators/{translator_id}/availability", response_model=List[TranslatorScheduleResponse])
def get_translator_availability(
    translator_id: UUID,
    date_from: date = Query(..., description="开始日期"),
    date_to: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
):
    translator = db.query(Translator).filter(Translator.id == translator_id).first()
    if not translator:
        raise HTTPException(status_code=404, detail="译员不存在")
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    return (
        db.query(TranslatorSchedule)
        .filter(
            TranslatorSchedule.translator_id == translator_id,
            TranslatorSchedule.schedule_date >= date_from,
            TranslatorSchedule.schedule_date <= date_to,
        )
        .order_by(TranslatorSchedule.schedule_date.asc())
        .all()
    )


@router.put("/translators/{translator_id}/availability/{schedule_date}", response_model=TranslatorScheduleResponse)
def upsert_translator_availability(
    translator_id: UUID,
    schedule_date: date,
    data: TranslatorScheduleUpdate,
    db: Session = Depends(get_db),
):
    translator = db.query(Translator).filter(Translator.id == translator_id).first()
    if not translator:
        raise HTTPException(status_code=404, detail="译员不存在")

    record = (
        db.query(TranslatorSchedule)
        .filter(
            TranslatorSchedule.translator_id == translator_id,
            TranslatorSchedule.schedule_date == schedule_date,
        )
        .first()
    )
    payload = data.model_dump(exclude_unset=True)

    if record:
        for key, value in payload.items():
            setattr(record, key, value)
        record.updated_at = datetime.utcnow()
    else:
        record = TranslatorSchedule(
            translator_id=translator_id,
            schedule_date=schedule_date,
            **payload,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


@router.post("/translators/{translator_id}/availability", response_model=TranslatorScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_translator_availability(
    translator_id: UUID,
    data: TranslatorScheduleCreate,
    db: Session = Depends(get_db),
):
    translator = db.query(Translator).filter(Translator.id == translator_id).first()
    if not translator:
        raise HTTPException(status_code=404, detail="译员不存在")
    if data.translator_id != translator_id:
        raise HTTPException(status_code=400, detail="路径中的译员ID与请求体不一致")

    existing = (
        db.query(TranslatorSchedule)
        .filter(
            TranslatorSchedule.translator_id == translator_id,
            TranslatorSchedule.schedule_date == data.schedule_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="该日期排期已存在，请改用更新接口")

    record = TranslatorSchedule(**data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/translators/{translator_id}/availability/{schedule_date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_translator_availability(
    translator_id: UUID,
    schedule_date: date,
    db: Session = Depends(get_db),
):
    record = (
        db.query(TranslatorSchedule)
        .filter(
            TranslatorSchedule.translator_id == translator_id,
            TranslatorSchedule.schedule_date == schedule_date,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="该日期排期不存在")
    db.delete(record)
    db.commit()


@router.post("/translators/import-demo")
async def import_translator_schedule_demo(
    file: UploadFile = File(...),
    overwrite: bool = Form(True),
    db: Session = Depends(get_db),
):
    filename = file.filename or "translator_schedule_demo.xlsx"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        workbook = load_workbook(filename=BytesIO(content), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"暂时只支持 Excel xlsx 文件导入：{exc}") from exc

    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel 内容不足，至少需要表头和一行数据")

    headers = [_normalize_text(cell) for cell in rows[0]]
    name_idx = next((i for i, h in enumerate(headers) if "姓名" in h), None)
    submit_time_idx = next((i for i, h in enumerate(headers) if "提交" in h and "时间" in h), None)
    fill_date_idx = next((i for i, h in enumerate(headers) if ("填写" in h and "日期" in h) or ("本周总" in h and "日期" in h)), None)
    remarks_idx = next((i for i, h in enumerate(headers) if "备注" in h), None)
    weekday_columns = {}
    for idx, header in enumerate(headers):
        for weekday, offset in WEEKDAY_HEADER_MAP.items():
            if weekday in header:
                weekday_columns[idx] = offset
                break

    if name_idx is None or not weekday_columns:
        raise HTTPException(status_code=400, detail="未识别到姓名列或星期列，请先保持当前导出模板格式")

    translators = db.query(Translator).all()
    translator_map = {}
    for translator in translators:
        translator_map.setdefault(_normalize_person_name(translator.translator_name), translator)

    created_count = 0
    updated_count = 0
    imported_rows = 0
    matched_translators = set()
    unmatched_names = []

    for row in rows[1:]:
        if not row or all(cell in (None, "") for cell in row):
            continue
        raw_name = row[name_idx] if name_idx < len(row) else None
        normalized_name = _normalize_person_name(raw_name)
        if not normalized_name:
            continue

        translator = translator_map.get(normalized_name)
        if not translator:
            unmatched_names.append(_normalize_text(raw_name))
            continue

        base_date = None
        if fill_date_idx is not None and fill_date_idx < len(row):
            base_date = _parse_excel_date(row[fill_date_idx])
        if base_date is None and submit_time_idx is not None and submit_time_idx < len(row):
            submit_dt = _parse_excel_datetime(row[submit_time_idx])
            if submit_dt:
                base_date = submit_dt.date()
        if base_date is None:
            continue

        week_monday = base_date - timedelta(days=base_date.weekday())
        remarks = _normalize_text(row[remarks_idx]) if remarks_idx is not None and remarks_idx < len(row) else ""
        submitted_at = None
        if submit_time_idx is not None and submit_time_idx < len(row):
            submitted_at = _parse_excel_datetime(row[submit_time_idx])

        row_imported = False
        for col_idx, weekday_offset in weekday_columns.items():
            if col_idx >= len(row):
                continue
            slot_text = _cell_to_slot_text(row[col_idx])
            if not slot_text:
                continue

            schedule_day = week_monday + timedelta(days=weekday_offset)
            record = (
                db.query(TranslatorSchedule)
                .filter(
                    TranslatorSchedule.translator_id == translator.id,
                    TranslatorSchedule.schedule_date == schedule_day,
                )
                .first()
            )
            payload = {
                "available_time_slot": slot_text,
                "source_type": "excel_demo",
                "source_ref": filename,
                "last_confirmed_at": submitted_at,
                "remarks": remarks or None,
            }
            if record:
                if overwrite:
                    for key, value in payload.items():
                        setattr(record, key, value)
                    record.updated_at = datetime.utcnow()
                    updated_count += 1
                    row_imported = True
            else:
                db.add(TranslatorSchedule(
                    translator_id=translator.id,
                    schedule_date=schedule_day,
                    **payload,
                ))
                created_count += 1
                row_imported = True

        if row_imported:
            matched_translators.add(translator.translator_name)
            imported_rows += 1

    db.commit()
    return {
        "file_name": filename,
        "sheet_name": sheet.title,
        "imported_rows": imported_rows,
        "matched_translators": len(matched_translators),
        "created_records": created_count,
        "updated_records": updated_count,
        "unmatched_names": unmatched_names,
    }


@router.post("/translators/import-demo/preview")
async def preview_translator_schedule_demo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or "translator_schedule_demo.xlsx"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    parsed = _parse_translator_schedule_demo_rows(content, filename, db)
    return {
        "file_name": parsed["file_name"],
        "sheet_name": parsed["sheet_name"],
        "headers": parsed["headers"],
        "matched_translators": parsed["matched_translators"],
        "unmatched_names": parsed["unmatched_names"],
        "preview_count": len(parsed["preview_items"]),
        "preview_items": parsed["preview_items"][:200],
    }


@router.post("/translators/import-demo-v2/preview")
async def preview_translator_schedule_demo_v2(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or "translator_schedule_demo.xlsx"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    parsed = _parse_translator_schedule_demo_rows_v2(content, filename, db)
    return {
        "file_name": parsed["file_name"],
        "sheet_name": parsed["sheet_name"],
        "headers": parsed["headers"],
        "matched_translators": parsed["matched_translators"],
        "unmatched_names": parsed["unmatched_names"],
        "preview_count": len(parsed["preview_items"]),
        "preview_items": parsed["preview_items"][:200],
    }


@router.post("/translators/import-demo-v2")
async def import_translator_schedule_demo_v2(
    file: UploadFile = File(...),
    overwrite: bool = Form(True),
    db: Session = Depends(get_db),
):
    filename = file.filename or "translator_schedule_demo.xlsx"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    parsed = _parse_translator_schedule_demo_rows_v2(content, filename, db)
    created_count = 0
    updated_count = 0

    for item in parsed["preview_items"]:
        schedule_day = date.fromisoformat(item["schedule_date"])
        payload = {
            "available_time_slot": item["available_time_slot"],
            "source_type": item["source_type"],
            "source_ref": item["source_ref"],
            "last_confirmed_at": datetime.fromisoformat(item["last_confirmed_at"]) if item["last_confirmed_at"] else None,
            "remarks": item["remarks"],
        }
        record = (
            db.query(TranslatorSchedule)
            .filter(
                TranslatorSchedule.translator_id == item["translator_id"],
                TranslatorSchedule.schedule_date == schedule_day,
            )
            .first()
        )
        if record:
            if overwrite:
                for key, value in payload.items():
                    setattr(record, key, value)
                record.updated_at = datetime.utcnow()
                updated_count += 1
        else:
            db.add(TranslatorSchedule(
                translator_id=item["translator_id"],
                schedule_date=schedule_day,
                **payload,
            ))
            created_count += 1

    db.commit()
    return {
        "file_name": parsed["file_name"],
        "sheet_name": parsed["sheet_name"],
        "imported_rows": len({item["row_no"] for item in parsed["preview_items"]}),
        "matched_translators": parsed["matched_translators"],
        "created_records": created_count,
        "updated_records": updated_count,
        "unmatched_names": parsed["unmatched_names"],
    }


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
