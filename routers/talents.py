"""统一人才资源库 API。"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    count_talents,
    create_talent,
    find_duplicate_talents,
    get_talent,
    get_talents,
    update_recruitment_talent,
    update_talent,
    update_talent_name,
    update_talent_status,
)
from routers.auth import require_module_access


router = APIRouter(
    prefix="/talents",
    tags=["talents"],
    dependencies=[Depends(require_module_access("talents:read", "talents:write"))],
)

recruitment_router = APIRouter(
    prefix="/recruitment-talents",
    tags=["recruitment_talents"],
    dependencies=[Depends(require_module_access(
        "recruitment_talents:read", "recruitment_talents:write"
    ))],
)


def _filters(
    keyword=None, status=None, capability_type=None, capability_status=None,
    cooperation_type=None, industry_keyword=None, review_required=None,
):
    return dict(
        keyword=keyword,
        status=status,
        capability_type=capability_type,
        capability_status=capability_status,
        cooperation_type=cooperation_type,
        industry_keyword=industry_keyword,
        review_required=review_required,
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
    db: Session = Depends(get_db),
):
    return get_talents(db, skip=skip, limit=limit, **_filters(
        keyword, status, capability_type, capability_status, cooperation_type,
        industry_keyword, review_required,
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
    db: Session = Depends(get_db),
):
    return {"total": count_talents(db, **_filters(
        keyword, status, capability_type, capability_status, cooperation_type,
        industry_keyword, review_required,
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
def create_talent_endpoint(payload: ResourcePersonCreate, db: Session = Depends(get_db)):
    try:
        return create_talent(db, payload)
    except TalentDuplicateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_talent", "message": str(exc), "duplicates": exc.duplicates,
        })


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
