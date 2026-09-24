"""资源开拓 API；联系方式、截图和写入权限均由服务端控制。"""
from datetime import date, timedelta
import json
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from interpretation_models import InterpretationLanguage
from models import AppUser
from routers.auth import get_current_user, require_any_permission
from resource_development_models import DevelopmentAction as Action, DevelopmentOption as Option, DevelopmentRecord as Record, DevelopmentScreenshot as Screenshot, DevelopmentWork as Work
from resource_development_schemas import LanguageWrite, OptionWrite, RecordWrite, WorkWrite
from resource_development_service import active_user, audit, check_revision, duplicates, filtered_records, is_admin, lock_writes, owns, previous_workday, refresh_draft, require_owner, save_record, save_work, serialize_record, snapshot, work_result
from permission_service import user_has_permission
from resource_development_service import can_delegate, can_delete_record


router = APIRouter(prefix="/resource-development", tags=["resource_development"],
                   dependencies=[Depends(require_any_permission("talents:read", "talents:write", "translators:read", "translators:write", "resource_development:delegate"))])
write = Depends(require_any_permission("talents:write", "translators:write", "resource_development:delegate"))


@router.get("/options")
def options(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"options": [snapshot(o) for o in db.query(Option).order_by(Option.kind, Option.category, Option.name)],
            "users": [{"id": str(u.id), "name": u.full_name or u.username} for u in db.query(AppUser).filter(AppUser.is_active.is_(True)).order_by(AppUser.full_name)],
            "languages": [{"id": str(l.id), "label": l.label, "language_type": l.language_type} for l in db.query(InterpretationLanguage).filter(InterpretationLanguage.is_active.is_(True)).order_by(InterpretationLanguage.label)],
            "user_id": str(user.id), "is_admin": is_admin(db, user),
            "can_delegate": can_delegate(db, user),
            "can_write": can_delegate(db, user) or user_has_permission(db, user.id, "talents:write") or user_has_permission(db, user.id, "translators:write"),
            "default_date": previous_workday(date.today()).isoformat()}


@router.post("/options", dependencies=[write])
def create_option(payload: OptionWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lock_writes(db)
    if payload.kind == "platform" and not payload.category:
        raise HTTPException(422, "请选择平台分类")
    existing = db.query(Option).filter(Option.kind == payload.kind, func.lower(Option.name) == payload.name.lower()).first()
    if existing:
        return snapshot(existing)
    row = Option(id=uuid4(), kind=payload.kind, name=payload.name, category=payload.category,
                 description=payload.description, revision=1)
    if payload.kind == "platform":
        row.code = "P" + row.id.hex[:12].upper()
    db.add(row)
    audit(db, user, row, "create")
    db.commit()
    return snapshot(row)


@router.put("/options/{option_id}", dependencies=[write])
def update_option(option_id: UUID, payload: OptionWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lock_writes(db)
    row = db.get(Option, option_id)
    if not row:
        raise HTTPException(404, "平台不存在")
    check_revision(row, payload.revision)
    if payload.name != row.name or payload.kind != row.kind or payload.category != row.category:
        raise HTTPException(422, "此入口只修改平台说明")
    before = snapshot(row)
    row.description, row.revision = payload.description, row.revision + 1
    audit(db, user, row, "update", before)
    db.commit()
    return snapshot(row)


@router.post("/languages", dependencies=[write])
def create_language(payload: LanguageWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lock_writes(db)
    row = db.query(InterpretationLanguage).filter(func.lower(InterpretationLanguage.label) == payload.label.lower()).first()
    if row and (not row.is_active or row.language_type != payload.language_type):
        raise HTTPException(409, "已有同名语种，请使用字典中现有类型或联系管理员")
    if not row:
        row = InterpretationLanguage(id=uuid4(), label=payload.label, language_type=payload.language_type,
                                     is_custom=True, is_active=True, created_by=user.id)
        db.add(row)
        db.commit()
    return {"id": str(row.id), "label": row.label, "language_type": row.language_type}


def filters(start: date | None = None, end: date | None = None, keyword: str | None = Query(None, max_length=255),
            owner_id: UUID | None = None, platform_id: UUID | None = None, account_id: UUID | None = None,
            state: str | None = Query(None, max_length=100), column_filters: str | None = Query(None, max_length=12000)):
    end = end or date.today()
    start = start or end - timedelta(days=2)
    if start > end:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    try:
        columns = json.loads(column_filters) if column_filters else {}
        allowed = {'platform_name','full_name','language_names','owner_name','account_name','wechat_status','enterprise_status','group_status','communication_status','project_status','latest_follow_up','greeting_no','phone','wechat','resource_code','work_date','follow_up','remarks','updated_at'}
        if not isinstance(columns, dict) or not set(columns).issubset(allowed):
            raise ValueError()
        for value in columns.values():
            values = value if isinstance(value, list) else [value]
            if len(values) > 100 or any(not isinstance(v, str) or len(v) > 255 for v in values):
                raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, '列筛选参数无效')
    return dict(start=start, end=end, keyword=keyword, owner_id=owner_id, platform_id=platform_id, account_id=account_id, state=state, column_filters=columns)


@router.get("/days")
def days(params=Depends(filters), skip: int = Query(0, ge=0), limit: int = Query(7, ge=1, le=31),
         db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = filtered_records(db, user, **params)
    dates = q.with_entities(Record.work_date.label("work_date"))
    # 没有新增资源但填写了工时的日期，也能回查；筛选资源属性时只显示命中记录的日期。
    include_work = not any(params[k] for k in ["keyword", "platform_id", "account_id", "state"]) and not params.get('column_filters')
    works = db.query(Work).filter(Work.work_date.between(params["start"], params["end"]))
    if params["owner_id"]:
        works = works.filter_by(owner_id=params["owner_id"])
    if include_work:
        dates = dates.union(works.with_entities(Work.work_date.label("work_date")))
    dates = dates.distinct().order_by(None).subquery()
    total = db.query(func.count()).select_from(dates).scalar()
    selected = db.query(dates.c.work_date).order_by(dates.c.work_date.desc()).offset(skip).limit(limit).all()
    result = []
    for (day,) in selected:
        counts = dict(q.filter(Record.work_date == day).with_entities(Record.owner_id, func.count(Record.id)).group_by(Record.owner_id).all())
        if include_work:
            for (owner,) in works.filter(Work.work_date == day).with_entities(Work.owner_id):
                counts.setdefault(owner, 0)
        result.append({"date": day, "count": sum(counts.values()), "people": [
            {**work_result(db, user, day, owner), "count": count} for owner, count in counts.items()]})
    return {"items": result, "total": total}


@router.get("/records")
def records(params=Depends(filters), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = filtered_records(db, user, **params)
    return {"items": [serialize_record(db, user, row) for row in q.order_by(Record.updated_at.desc(), Record.id.desc()).offset(skip).limit(limit)],
            "total": q.count()}


@router.post("/duplicates", dependencies=[write])
def check_duplicates(payload: RecordWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_owner(db, user, payload.owner_id)
    row = db.get(Record, payload.id)
    if row:
        require_owner(db, user, row.owner_id)
    return {"items": duplicates(db, payload.full_name, payload.phone, payload.wechat)}


@router.post("/records", dependencies=[write])
def write_record(payload: RecordWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = save_record(db, user, payload)
    db.commit()
    return serialize_record(db, user, row, True)


@router.get("/records/{record_id}")
def read_record(record_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.get(Record, record_id)
    if not row:
        raise HTTPException(404, "开拓记录不存在")
    return serialize_record(db, user, row, True)


@router.delete("/records/{record_id}", dependencies=[write])
def delete_record(record_id: UUID, revision: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lock_writes(db)
    row = db.get(Record, record_id)
    if not row:
        raise HTTPException(404, "开拓记录不存在")
    if not can_delete_record(db, user, row.owner_id):
        raise HTTPException(403, "代录权限不包含删除他人记录")
    check_revision(row, revision)
    owner, day = row.owner_id, row.work_date
    audit(db, user, row, "delete", snapshot(row))
    db.delete(row)
    db.flush()
    refresh_draft(db, owner, day)
    db.commit()
    return {"ok": True}


@router.get("/work")
def read_work(work_date: date, owner_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return work_result(db, user, work_date, owner_id)


@router.put("/work", dependencies=[write])
def write_work(payload: WorkWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = save_work(db, user, payload)
    db.commit()
    return work_result(db, user, row.work_date, row.owner_id)


def screenshot_work(db, user, work_id):
    row = db.get(Work, work_id)
    if not row:
        raise HTTPException(404, "请先保存每日工作")
    require_owner(db, user, row.owner_id)
    return row


@router.post("/work/{work_id}/screenshots", dependencies=[write])
def upload_screenshot(work_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    screenshot_work(db, user, work_id)
    content = file.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(422, "截图不能超过5MB")
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(BytesIO(content)) as img:
            content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(img.format)
            if not content_type or img.width * img.height > 25000000:
                raise ValueError("图片格式或尺寸不支持")
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "请上传有效的 PNG、JPEG 或 WebP 截图")
    row = Screenshot(work_id=work_id, name=(file.filename or "截图")[:255], content_type=content_type,
                     content=content, created_by=user.id)
    db.add(row)
    audit(db, user, row, "create")
    db.commit()
    return {"id": str(row.id), "name": row.name}


@router.get("/screenshots/{screenshot_id}")
def read_screenshot(screenshot_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.get(Screenshot, screenshot_id)
    if not row:
        raise HTTPException(404, "截图不存在")
    screenshot_work(db, user, row.work_id)
    return Response(row.content, media_type=row.content_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/screenshots/{screenshot_id}", dependencies=[write])
def delete_screenshot(screenshot_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.get(Screenshot, screenshot_id)
    if not row:
        raise HTTPException(404, "截图不存在")
    screenshot_work(db, user, row.work_id)
    audit(db, user, row, "delete", snapshot(row))
    db.delete(row)
    db.commit()
    return {"ok": True}

# 群聊统计仅继承模块访问范围，写入权限在服务端单独检查。
from routers.resource_friend_daily import router as friend_daily_router
router.include_router(friend_daily_router)
