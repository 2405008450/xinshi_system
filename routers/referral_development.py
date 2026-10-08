"""推荐拓展 API：图片、联系方式和所有写入均在服务端校验权限。"""
from datetime import date
from io import BytesIO
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from PIL import Image as PILImage, UnidentifiedImageError
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission
from referral_development_models import ReferralRecord as Record, ReferralImage as Image
from referral_development_schemas import RecordWrite, PaymentWrite
from referral_development_service import (READ_PERMISSIONS, WRITE_PERMISSIONS, access, audit, can_delegate,
    can_write, check_revision, duplicate_records, filtered_records, is_admin, locked_record, now,
    require_edit, save_record, serialization_context, serialize_record, set_payment, snapshot, touch)

router = APIRouter(prefix="/referral-development", tags=["referral_development"],
                   dependencies=[Depends(require_any_permission(*READ_PERMISSIONS))])
write = Depends(require_any_permission(*WRITE_PERMISSIONS))


@router.get("/options")
def options(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return dict(user_id=str(user.id), can_write=can_write(db, user), is_admin=is_admin(db, user), can_delegate=can_delegate(db, user),
                users=[dict(id=str(u.id), name=u.full_name or u.username) for u in db.query(AppUser).filter_by(is_active=True).order_by(AppUser.full_name)])


def filters(start: date | None = None, end: date | None = None, keyword: str | None = Query(None, max_length=255),
            payment_status: Literal["paid", "unpaid"] | None = None, creator_id: UUID | None = None,
            operator_id: UUID | None = None, paid_start: date | None = None, paid_end: date | None = None):
    for lower, upper in ((start, end), (paid_start, paid_end)):
        if lower and upper and lower > upper:
            raise HTTPException(422, "开始日期不能晚于结束日期")
    return dict(start=start, end=end, keyword=keyword, payment_status=payment_status,
                creator_id=creator_id, operator_id=operator_id, paid_start=paid_start, paid_end=paid_end)


@router.get("/records")
def records(params=Depends(filters), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = filtered_records(db, user, **params)
    context = serialization_context(db, user)
    return dict(total=q.count(), items=[serialize_record(db, user, row, context=context) for row in q.order_by(Record.work_date.desc(), Record.updated_at.desc(), Record.id.desc()).offset(skip).limit(limit)])


@router.get("/duplicates", dependencies=[write])
def duplicates(work_date: date, full_name: str = Query(..., min_length=1, max_length=255),
               wechat: str = Query("", max_length=100), exclude_id: UUID | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    return dict(items=duplicate_records(db, user, work_date, full_name, wechat, exclude_id))


@router.post("/records", dependencies=[write])
def write_record(payload: RecordWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = save_record(db, user, payload)
    db.commit()
    return serialize_record(db, user, row, True)


@router.get("/records/{record_id}")
def detail(record_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = db.get(Record, record_id)
    if not row:
        raise HTTPException(404, "推荐拓展记录不存在")
    return serialize_record(db, user, row, True)


@router.put("/records/{record_id}/payment", dependencies=[write])
def payment(record_id: UUID, payload: PaymentWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = set_payment(db, user, record_id, payload)
    db.commit()
    return serialize_record(db, user, row, True)


@router.delete("/records/{record_id}", dependencies=[write])
def remove(record_id: UUID, revision: int = Query(..., ge=1), db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = locked_record(db, record_id)
    if row.created_by != user.id and not is_admin(db, user):
        raise HTTPException(403, "代录权限不包含删除他人记录")
    check_revision(row, revision)
    before = snapshot(row)
    before["images"] = [snapshot(i) for i in db.query(Image).filter_by(record_id=row.id)]
    audit(db, user, row, "delete", before, {})
    db.query(Image).filter_by(record_id=row.id).delete()
    db.delete(row)
    db.commit()
    return dict(ok=True)


@router.post("/records/{record_id}/images", dependencies=[write])
def upload(record_id: UUID, category: Literal["pull", "moments", "groups", "qr"] = Form(...),
           image_id: UUID = Form(...), revision: int = Form(..., ge=1), file: UploadFile = File(...),
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = locked_record(db, record_id)
    require_edit(db, user, row)
    content = file.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(422, "每张图片不能超过5MB")
    try:
        with PILImage.open(BytesIO(content)) as img:
            content_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(img.format)
            if not content_type or img.width * img.height > 25000000:
                raise ValueError()
            img.verify()
    except (ValueError, OSError, UnidentifiedImageError, PILImage.DecompressionBombError):
        raise HTTPException(422, "请上传有效的 PNG、JPEG 或 WebP 图片")
    existing = db.get(Image, image_id)
    if existing:
        if existing.record_id != row.id or existing.category != category or existing.content != content:
            raise HTTPException(409, "图片标识冲突，请重新选择图片")
        return serialize_record(db, user, row, True)
    check_revision(row, revision)
    old = list(db.query(Image).filter_by(record_id=row.id, category="qr")) if category == "qr" else []
    before = {"images": [snapshot(i) for i in old]}
    for item in old:
        db.delete(item)
    if old:
        # 先释放收款码唯一索引，再插入替换图片；整个替换仍在同一事务中。
        db.flush()
    image = Image(id=image_id, record_id=row.id, category=category, name=(file.filename or "图片")[:255],
                  content_type=content_type, content=content, created_by=user.id, created_at=now())
    db.add(image)
    touch(row, user)
    db.flush()
    audit(db, user, row, "image_replace" if old else "image_add", before, {"images": [snapshot(image)]})
    db.commit()
    return serialize_record(db, user, row, True)


@router.get("/images/{image_id}")
def image_content(image_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    image = db.get(Image, image_id)
    if not image:
        raise HTTPException(404, "图片不存在")
    row = db.get(Record, image.record_id)
    if not row or not access(db, user, row):
        raise HTTPException(403, "没有查看该记录图片的权限")
    return Response(image.content, media_type=image.content_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/records/{record_id}/images/{image_id}", dependencies=[write])
def remove_image(record_id: UUID, image_id: UUID, revision: int = Query(..., ge=1),
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = locked_record(db, record_id)
    require_edit(db, user, row)
    check_revision(row, revision)
    image = db.get(Image, image_id)
    if not image or image.record_id != row.id:
        raise HTTPException(404, "图片不存在")
    audit(db, user, row, "image_delete", {"images": [snapshot(image)]}, {})
    db.delete(image)
    touch(row, user)
    db.commit()
    return serialize_record(db, user, row, True)
