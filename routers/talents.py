"""统一人才资源库 API。"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from resource_schemas import (
    DuplicateCheckResponse,
    ResourcePersonCreate,
    ResourcePersonDetailResponse,
    ResourcePersonListResponse,
    ResourcePersonNameUpdate,
    ResourcePersonStatusUpdate,
    ResourcePersonUpdate,
)
from resource_service import (
    TalentDuplicateError,
    TalentDeleteConflictError,
    count_talents,
    create_talent,
    delete_talent,
    find_duplicate_talents,
    get_talent,
    get_talents,
    update_recruitment_talent,
    update_talent,
    update_talent_name,
    update_talent_status,
)
from routers.auth import require_module_access
from resource_models import ResourcePerson
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters


router = APIRouter(
    prefix="/talents",
    tags=["talents"],
    dependencies=[Depends(require_module_access("talents:read", "talents:write"))],
)
logger = logging.getLogger(__name__)

recruitment_router = APIRouter(
    prefix="/recruitment-talents",
    tags=["recruitment_talents"],
    dependencies=[Depends(require_module_access(
        "recruitment_talents:read", "recruitment_talents:write"
    ))],
)

TALENT_FILTER_FIELDS = {
    "resource_code", "full_name", "capability_types", "language_directions",
    "annotation_language_directions", "industries", "job_titles", "years_experience",
    "status", "cooperation_type", "primary_phone", "primary_email", "gender", "age",
    "native_place", "residence_address", "dialects", "dialect_regions", "nationality",
    "overall_rating", "first_contact_date", "updated_at", "duplicate_review_required",
}


def _field_filters(raw: Optional[str]):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, TALENT_FILTER_FIELDS)
    ranges = {"years_experience", "age", "first_contact_date", "updated_at"}
    enums = {"capability_types", "status", "cooperation_type"}
    booleans = {"duplicate_review_required"}
    ensure_filter_operators(value, {field: ({"between"} if field in ranges else {"in"} if field in enums else {"eq"} if field in booleans else {"contains"}) for field in TALENT_FILTER_FIELDS})
    return value


def _filters(
    keyword=None, status=None, capability_type=None, capability_status=None,
    cooperation_type=None, industry_keyword=None, review_required=None, field_filters=None,
):
    return dict(
        keyword=keyword,
        status=status,
        capability_type=capability_type,
        capability_status=capability_status,
        cooperation_type=cooperation_type,
        industry_keyword=industry_keyword,
        review_required=review_required,
        field_filters=field_filters,
    )


@router.get("/", response_model=List[ResourcePersonListResponse])
def read_talents(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    capability_type: Optional[str] = None,
    capability_status: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    industry_keyword: Optional[str] = None,
    review_required: Optional[bool] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_talents(db, skip=skip, limit=limit, **_filters(
        keyword, status, capability_type, capability_status, cooperation_type,
        industry_keyword, review_required, _field_filters(field_filters),
    ))


@router.get("/count")
def read_talent_count(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    capability_type: Optional[str] = None,
    capability_status: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    industry_keyword: Optional[str] = None,
    review_required: Optional[bool] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return {"total": count_talents(db, **_filters(
        keyword, status, capability_type, capability_status, cooperation_type,
        industry_keyword, review_required, _field_filters(field_filters),
    ))}


@router.get("/duplicates", response_model=DuplicateCheckResponse)
def check_duplicates(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    exclude_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    return {"duplicates": find_duplicate_talents(
        db, phone=phone, email=email, exclude_id=exclude_id
    )}


@router.post("/", response_model=ResourcePersonDetailResponse, status_code=status.HTTP_201_CREATED)
def create_talent_endpoint(
    payload: ResourcePersonCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(ResourcePerson).filter(
            ResourcePerson.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_talent(db, existing.id)
    try:
        return create_talent(db, payload, idempotency_key=idempotency_key)
    except TalentDuplicateError as exc:
        db.rollback()
        if idempotency_key:
            existing = db.query(ResourcePerson).filter(
                ResourcePerson.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_talent(db, existing.id)
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_talent", "message": str(exc), "duplicates": exc.duplicates,
        })
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(ResourcePerson).filter(
                ResourcePerson.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_talent(db, existing.id)
        logger.exception("创建人才档案时触发数据库约束")
        raise HTTPException(status_code=400, detail="人才档案数据不符合保存要求，请检查后重试")


@router.get("/{person_id}", response_model=ResourcePersonDetailResponse)
def read_talent(person_id: UUID, db: Session = Depends(get_db)):
    person = get_talent(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return person


@router.put("/{person_id}", response_model=ResourcePersonDetailResponse)
def update_talent_endpoint(
    person_id: UUID, payload: ResourcePersonUpdate, db: Session = Depends(get_db)
):
    try:
        person = update_talent(db, person_id, payload)
    except TalentDuplicateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_talent", "message": str(exc), "duplicates": exc.duplicates,
        })
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return person


@router.patch("/{person_id}/name", response_model=ResourcePersonDetailResponse)
def update_talent_name_endpoint(
    person_id: UUID, payload: ResourcePersonNameUpdate, db: Session = Depends(get_db)
):
    person = update_talent_name(db, person_id, payload.full_name)
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return person


@router.patch("/{person_id}/status", response_model=ResourcePersonDetailResponse)
def update_talent_status_endpoint(
    person_id: UUID, payload: ResourcePersonStatusUpdate, db: Session = Depends(get_db)
):
    person = update_talent_status(db, person_id, payload.status)
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_talent_endpoint(person_id: UUID, db: Session = Depends(get_db)):
    try:
        deleted = delete_talent(db, person_id)
    except TalentDeleteConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="人才档案不存在")


def create_recruitment_talent_endpoint(
    payload: ResourcePersonCreate, db: Session = Depends(get_db)
):
    """招聘人才权限可新建主档与职业档案，不能借此授予专业项目能力。"""
    safe_payload = payload.model_copy(update={
        "capabilities": [],
        "written_profile": None,
        "interpretation_profile": None,
        "annotation_profile": None,
        "annotation_language_skills": [],
    })
    return create_talent_endpoint(safe_payload, db)


def update_recruitment_talent_endpoint(
    person_id: UUID,
    payload: ResourcePersonUpdate,
    db: Session = Depends(get_db),
):
    """招聘端编辑时保留原专业能力，能力只能由人才总库权限管理。"""
    try:
        person = update_recruitment_talent(db, person_id, payload)
    except TalentDuplicateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_talent", "message": str(exc), "duplicates": exc.duplicates,
        })
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return person


# 招聘人才库复用同一份人员主档，但使用独立权限边界。
recruitment_router.add_api_route(
    "/", read_talents, methods=["GET"], response_model=List[ResourcePersonListResponse]
)
recruitment_router.add_api_route("/count", read_talent_count, methods=["GET"])
recruitment_router.add_api_route(
    "/duplicates", check_duplicates, methods=["GET"], response_model=DuplicateCheckResponse
)
recruitment_router.add_api_route(
    "/", create_recruitment_talent_endpoint, methods=["POST"],
    response_model=ResourcePersonDetailResponse, status_code=status.HTTP_201_CREATED,
)
recruitment_router.add_api_route(
    "/{person_id}", read_talent, methods=["GET"], response_model=ResourcePersonDetailResponse
)
recruitment_router.add_api_route(
    "/{person_id}", update_recruitment_talent_endpoint, methods=["PUT"],
    response_model=ResourcePersonDetailResponse,
)
recruitment_router.add_api_route(
    "/{person_id}/status", update_talent_status_endpoint, methods=["PATCH"],
    response_model=ResourcePersonDetailResponse,
)
recruitment_router.add_api_route(
    "/{person_id}", delete_talent_endpoint, methods=["DELETE"],
    status_code=status.HTTP_204_NO_CONTENT,
)
