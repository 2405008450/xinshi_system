from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import inspect

import field_work as service
from company_management_image_service import MAX_IMAGE_BYTES, normalize_image
from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_permission


router = APIRouter(prefix="/attendance/field-work", tags=["field_work"])
customer_reader = require_permission("clients:read")


def field_work_db(db=Depends(get_db)):
    if not inspect(db.connection()).has_table(service.FieldWork.__tablename__):
        raise HTTPException(503, "外勤管理尚未初始化")
    return db


@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    people = service.people_query(db).filter(AppUser.id != user.id).order_by(AppUser.full_name, AppUser.username)
    return {"categories": service.CATEGORIES, "people": [service.person_option(row) for row in people]}


@router.get("")
def records(
    keyword: str = Query("", max_length=200), page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100), db=Depends(field_work_db), user=Depends(get_current_user),
):
    return service.list_records(db, user, keyword=keyword, page=page, limit=limit)


@router.get("/customers")
def customer_records(
    keyword: str = Query("", max_length=200), page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100), db=Depends(field_work_db), user=Depends(customer_reader),
):
    return service.list_records(db, user, customer_view=True, keyword=keyword, page=page, limit=limit)


@router.put("")
def save(
    payload: str = Form(..., max_length=24000), photo: UploadFile | None = File(None),
    db=Depends(field_work_db), user=Depends(get_current_user),
):
    try:
        data = service.FieldWorkWrite.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_input=False)[0]["msg"]) from exc
    image = None
    if photo is not None:
        content, media_type, _ = normalize_image(photo.file.read(MAX_IMAGE_BYTES + 1), photo.content_type or "")
        image = (content, media_type)
    return service.save_record(db, user, data, image)


def photo_response(db, record_id, *, owner_id=None):
    query = db.query(service.FieldWork.photo, service.FieldWork.photo_type).filter(service.FieldWork.id == record_id)
    if owner_id is None:
        query = query.filter(service.FieldWork.category == "customer")
    else:
        query = query.filter(service.FieldWork.user_id == owner_id)
    row = query.first()
    if not row or not row.photo:
        raise HTTPException(404, "外勤照片不存在")
    return Response(row.photo, media_type=row.photo_type, headers={
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/customers/{record_id}/photo")
def customer_photo(record_id: UUID, db=Depends(field_work_db), user=Depends(customer_reader)):
    return photo_response(db, record_id)


@router.get("/{record_id}/photo")
def photo(record_id: UUID, db=Depends(field_work_db), user=Depends(get_current_user)):
    return photo_response(db, record_id, owner_id=user.id)
