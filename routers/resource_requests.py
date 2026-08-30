"""资源需求管理 API。"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from resource_request_models import ResourceRequest, ResourceRequestItem
from resource_request_schemas import ResourceProgressLogResponse, ResourceProgressUpdate, ResourceRequestResponse, ResourceRequestSourcePrefillResponse, ResourceRequestWrite
from resource_request_service import (
    count_resource_requests, create_resource_request, delete_resource_request,
    get_resource_request, get_resource_request_source_prefill, list_progress_logs, list_resource_requests,
    update_resource_progress, update_resource_request,
)
from routers.auth import get_current_user, require_any_permission, require_module_access
from concurrency import assert_fresh
from inline_text_update import (
    TextFieldRule,
    TextFieldUpdate,
    apply_text_field_update,
    normalize_text_value,
)
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters


router = APIRouter(
    prefix="/resource-requests", tags=["resource_requests"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)


RESOURCE_REQUEST_TEXT_FIELDS = {
    "request_detail": TextFieldRule(empty_as_null=False),
}

RESOURCE_REQUEST_FILTER_FIELDS = {
    "request_no", "source_type", "project_type", "project_status", "order_no",
    "project_name", "client_code", "client_short_name", "owner_name", "languages",
    "required_count", "request_detail", "priority", "progress_percent", "request_status",
    "requested_at", "request_category", "owner_id",
}


def _field_filters(raw: Optional[str]):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, RESOURCE_REQUEST_FILTER_FIELDS)
    ranges = {"required_count", "progress_percent", "requested_at"}
    enums = {"source_type", "project_type", "project_status", "languages", "priority", "request_status", "request_category", "owner_id"}
    ensure_filter_operators(value, {field: ({"between"} if field in ranges else {"in"} if field in enums else {"contains"}) for field in RESOURCE_REQUEST_FILTER_FIELDS})
    return value


def _filters(keyword=None, source_type=None, request_category=None, request_status=None, priority=None, owner_id=None, field_filters=None):
    return dict(keyword=keyword, source_type=source_type, request_category=request_category, request_status=request_status, priority=priority, owner_id=owner_id, field_filters=field_filters)


@router.get("/", response_model=List[ResourceRequestResponse])
def read_requests(skip: int = 0, limit: int = Query(100, ge=1, le=500), keyword: Optional[str] = None, source_type: Optional[str] = None, request_category: Optional[str] = None, request_status: Optional[str] = None, priority: Optional[str] = None, owner_id: Optional[UUID] = None, field_filters: Optional[str] = Query(None), db: Session = Depends(get_db)):
    return list_resource_requests(db, skip=skip, limit=limit, **_filters(keyword, source_type, request_category, request_status, priority, owner_id, _field_filters(field_filters)))


@router.get("/count")
def read_count(keyword: Optional[str] = None, source_type: Optional[str] = None, request_category: Optional[str] = None, request_status: Optional[str] = None, priority: Optional[str] = None, owner_id: Optional[UUID] = None, field_filters: Optional[str] = Query(None), db: Session = Depends(get_db)):
    return {"total": count_resource_requests(db, **_filters(keyword, source_type, request_category, request_status, priority, owner_id, _field_filters(field_filters)))}


@router.get("/source-prefill", response_model=ResourceRequestSourcePrefillResponse)
def read_source_prefill(source_type: str, source_project_id: UUID, db: Session = Depends(get_db)):
    try:
        value = get_resource_request_source_prefill(db, source_type, source_project_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not value:
        raise HTTPException(404, "来源项目不存在")
    return value


@router.post("/", response_model=ResourceRequestResponse, status_code=201, dependencies=[Depends(require_any_permission("projects:write"))])
def create_request(
    payload: ResourceRequestWrite,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(ResourceRequest).filter(
            ResourceRequest.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_resource_request(db, existing.id)
    try: return create_resource_request(db, payload, user.id, idempotency_key=idempotency_key)
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        if idempotency_key:
            existing = db.query(ResourceRequest).filter(
                ResourceRequest.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_resource_request(db, existing.id)
        raise HTTPException(400, str(exc))


@router.get("/{request_id}", response_model=ResourceRequestResponse)
def read_request(request_id: UUID, db: Session = Depends(get_db)):
    row = get_resource_request(db, request_id)
    if not row: raise HTTPException(404, "资源需求不存在")
    return row


@router.patch("/{request_id}/text-field", response_model=ResourceRequestResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def edit_request_text_field(request_id: UUID, payload: TextFieldUpdate, db: Session = Depends(get_db)):
    row = db.get(ResourceRequest, request_id)
    if not row:
        raise HTTPException(404, "资源需求不存在")
    try:
        changed = apply_text_field_update(row, payload, RESOURCE_REQUEST_TEXT_FIELDS)
        if changed:
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    return get_resource_request(db, request_id)


@router.patch("/{request_id}/items/{item_id}/text-field", response_model=ResourceRequestResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def edit_request_item_text_field(
    request_id: UUID,
    item_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
):
    request = db.get(ResourceRequest, request_id)
    item = db.query(ResourceRequestItem).filter(
        ResourceRequestItem.id == item_id,
        ResourceRequestItem.request_id == request_id,
    ).first()
    if not request or not item:
        raise HTTPException(404, "资源需求或语种明细不存在")
    if payload.field != "requirement_detail":
        raise HTTPException(400, "该语种明细字段不支持快捷编辑")
    try:
        assert_fresh(request, payload.expected_updated_at)
        value = normalize_text_value(payload.value, TextFieldRule())
        if item.requirement_detail != value:
            now = datetime.now()
            item.requirement_detail = value
            item.updated_at = now
            request.updated_at = now
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    return get_resource_request(db, request_id)


@router.put("/{request_id}", response_model=ResourceRequestResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def edit_request(request_id: UUID, payload: ResourceRequestWrite, db: Session = Depends(get_db)):
    try: row = update_resource_request(db, request_id, payload)
    except (ValueError, IntegrityError) as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    if not row: raise HTTPException(404, "资源需求不存在")
    return row


@router.patch("/{request_id}/progress", response_model=ResourceRequestResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def edit_progress(request_id: UUID, payload: ResourceProgressUpdate, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = update_resource_progress(db, request_id, payload, user.id)
    if not row: raise HTTPException(404, "资源需求不存在")
    return row


@router.get("/{request_id}/progress-logs", response_model=List[ResourceProgressLogResponse])
def progress_logs(request_id: UUID, db: Session = Depends(get_db)):
    return list_progress_logs(db, request_id)


@router.delete("/{request_id}", status_code=204, dependencies=[Depends(require_any_permission("projects:write"))])
def remove_request(request_id: UUID, db: Session = Depends(get_db)):
    if not delete_resource_request(db, request_id): raise HTTPException(404, "资源需求不存在")
