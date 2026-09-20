"""统一人才资源库 API。"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
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
    TalentAnnotationProjectPerformanceResponse,
    TalentAttachmentResponse,
    TalentProjectHistoryResponse,
)
from resource_service import (
    TalentDuplicateError,
    TalentDeleteConflictError,
    count_talents,
    create_talent,
    delete_talent,
    find_duplicate_talents,
    get_talent,
    get_talent_annotation_project_performance,
    get_talent_project_history,
    get_talent_project_history_page,
    get_talent_project_situations,
    get_talents,
    update_recruitment_talent,
    update_talent,
    update_talent_name,
    update_talent_status,
)
from routers.auth import (
    get_current_user,
    require_any_permission,
    require_module_access,
    require_permission,
    require_super_admin,
)
from resource_models import ResourcePerson, ResourcePersonAttachment
from talent_attachment_service import (
    attachment_path,
    delete_talent_attachment,
    save_talent_attachment,
)
from talent_overview_schemas import TalentOverviewResponse
from talent_overview_service import get_talent_overview
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters
from pagination_schemas import PageResponse, resolve_page_total
from talent_privacy import (
    RESOURCE_CONTACT_FIELDS,
    can_view_talent_contacts,
    has_contact_values,
    preserve_contact_fields,
    redact_contact_mapping,
    serialize_with_contact_access,
)


router = APIRouter(
    prefix="/talents",
    tags=["talents"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)

recruitment_router = APIRouter(
    prefix="/recruitment-talents",
    tags=["recruitment_talents"],
    dependencies=[Depends(get_current_user)],
)

talent_write_dependencies = [Depends(require_any_permission(
    "talents:write", "translators:write",
))]
recruitment_write_dependencies = [Depends(require_permission(
    "recruitment_talents:write"
))]

TALENT_FILTER_FIELDS = {
    "resource_code", "full_name", "capability_types", "language_directions",
    "annotation_language_directions", "industries", "job_titles", "years_experience",
    "status", "cooperation_type", "primary_phone", "primary_email", "gender", "age",
    "native_place", "residence_address", "dialects", "dialect_regions", "nationality",
    "employment_status", "highest_education", "language_skills", "certificate_received",
    "overall_score", "overall_rating", "audio_annotation_score",
    "non_audio_annotation_score", "collection_score", "first_contact_date", "updated_at",
    "duplicate_review_required",
}

TALENT_SORT_PATTERN = (
    "^(updated_desc|overall_score_(asc|desc)|audio_annotation_score_(asc|desc)|"
    "non_audio_annotation_score_(asc|desc)|collection_score_(asc|desc))$"
)


@router.get("/overview", response_model=TalentOverviewResponse)
def read_talent_overview():
    """返回人才概览统一快照；访问权限沿用人才资源库。"""
    return get_talent_overview()


def _field_filters(raw: Optional[str], *, allow_contact_filters: bool = True):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, TALENT_FILTER_FIELDS)
    if not allow_contact_filters and {"primary_phone", "primary_email"} & value.keys():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="联系方式筛选仅超级管理员可用",
        )
    ranges = {
        "years_experience", "age", "overall_score", "audio_annotation_score",
        "non_audio_annotation_score", "collection_score", "first_contact_date", "updated_at",
    }
    enums = {"capability_types", "status", "cooperation_type", "employment_status", "highest_education"}
    booleans = {"duplicate_review_required", "certificate_received"}
    ensure_filter_operators(value, {field: ({"between"} if field in ranges else {"in"} if field in enums else {"eq"} if field in booleans else {"contains"}) for field in TALENT_FILTER_FIELDS})
    return value


def _filters(
    keyword=None, status=None, capability_type=None, capability_status=None,
    cooperation_type=None, industry_keyword=None, review_required=None, field_filters=None,
    include_contact_search=True,
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
        include_contact_search=include_contact_search,
    )


def _duplicate_error_detail(exc: TalentDuplicateError, *, contacts_visible: bool):
    return {
        "code": "duplicate_talent",
        "message": str(exc),
        "duplicates": [
            redact_contact_mapping(
                item,
                ("primary_phone", "primary_email"),
                contacts_visible=contacts_visible,
            )
            for item in exc.duplicates
        ],
    }


@router.get("/", response_model=List[ResourcePersonListResponse], deprecated=True)
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
    sort: str = Query("updated_desc", pattern=TALENT_SORT_PATTERN),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    people = get_talents(db, skip=skip, limit=limit, sort=sort, **_filters(
        keyword, status, capability_type, capability_status, cooperation_type,
        industry_keyword, review_required,
        _field_filters(field_filters, allow_contact_filters=contacts_visible),
        contacts_visible,
    ))
    situations = get_talent_project_situations(db, [person.id for person in people])
    result = []
    for person in people:
        item = serialize_with_contact_access(
            person, ResourcePersonListResponse, RESOURCE_CONTACT_FIELDS,
            contacts_visible=contacts_visible,
        )
        item["project_situation"] = situations.get(person.id, {"total": 0, "primary": None})
        result.append(item)
    return result


@router.get("/count", deprecated=True)
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
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    return {"total": count_talents(db, **_filters(
        keyword, status, capability_type, capability_status, cooperation_type,
        industry_keyword, review_required,
        _field_filters(field_filters, allow_contact_filters=contacts_visible),
        contacts_visible,
    ))}


@router.get("/page", response_model=PageResponse[ResourcePersonListResponse])
def read_talent_page(
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
    sort: str = Query("updated_desc", pattern=TALENT_SORT_PATTERN),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    filters = _filters(
        keyword, status, capability_type, capability_status,
        cooperation_type, industry_keyword, review_required,
        _field_filters(field_filters, allow_contact_filters=contacts_visible),
        contacts_visible,
    )
    items = get_talents(db, skip=skip, limit=limit, sort=sort, **filters)
    total = resolve_page_total(
        items, skip, lambda: count_talents(db, **filters),
    )
    situations = get_talent_project_situations(db, [person.id for person in items])
    serialized_items = []
    for person in items:
        item = serialize_with_contact_access(
                person, ResourcePersonListResponse, RESOURCE_CONTACT_FIELDS,
                contacts_visible=contacts_visible,
            )
        item["project_situation"] = situations.get(person.id, {"total": 0, "primary": None})
        serialized_items.append(item)
    return {"items": serialized_items, "total": total}


@router.get(
    "/duplicates",
    response_model=DuplicateCheckResponse,
    dependencies=[Depends(require_super_admin)],
)
def check_duplicates(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    exclude_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    return {"duplicates": [
        redact_contact_mapping(
            item, ("primary_phone", "primary_email"), contacts_visible=True,
        )
        for item in find_duplicate_talents(
            db, phone=phone, email=email, exclude_id=exclude_id
        )
    ]}


@router.post(
    "/", response_model=ResourcePersonDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=talent_write_dependencies,
)
def create_talent_endpoint(
    payload: ResourcePersonCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    if not contacts_visible and has_contact_values(payload, RESOURCE_CONTACT_FIELDS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以录入人才联系方式",
        )
    if idempotency_key:
        existing = db.query(ResourcePerson).filter(
            ResourcePerson.idempotency_key == idempotency_key
        ).first()
        if existing:
            return serialize_with_contact_access(
                get_talent(db, existing.id), ResourcePersonDetailResponse,
                RESOURCE_CONTACT_FIELDS, contacts_visible=contacts_visible,
            )
    try:
        person = create_talent(db, payload, idempotency_key=idempotency_key)
        return serialize_with_contact_access(
            person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS,
            contacts_visible=contacts_visible,
        )
    except TalentDuplicateError as exc:
        db.rollback()
        if idempotency_key:
            existing = db.query(ResourcePerson).filter(
                ResourcePerson.idempotency_key == idempotency_key
            ).first()
            if existing:
                return serialize_with_contact_access(
                    get_talent(db, existing.id), ResourcePersonDetailResponse,
                    RESOURCE_CONTACT_FIELDS, contacts_visible=contacts_visible,
                )
        raise HTTPException(
            status_code=409,
            detail=_duplicate_error_detail(exc, contacts_visible=contacts_visible),
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(ResourcePerson).filter(
                ResourcePerson.idempotency_key == idempotency_key
            ).first()
            if existing:
                return serialize_with_contact_access(
                    get_talent(db, existing.id), ResourcePersonDetailResponse,
                    RESOURCE_CONTACT_FIELDS, contacts_visible=contacts_visible,
                )
        logger.exception("创建人才档案时触发数据库约束")
        raise HTTPException(status_code=400, detail="人才档案数据不符合保存要求，请检查后重试")


@router.get("/{person_id}", response_model=ResourcePersonDetailResponse)
def read_talent(
    person_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    person = get_talent(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return serialize_with_contact_access(
        person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS,
        contacts_visible=can_view_talent_contacts(db, current_user),
    )


@router.get("/{person_id}/projects", response_model=List[TalentProjectHistoryResponse])
def read_talent_projects(person_id: UUID, db: Session = Depends(get_db)):
    if not db.query(ResourcePerson.id).filter(ResourcePerson.id == person_id).first():
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return get_talent_project_history(db, person_id)


@router.get(
    "/{person_id}/projects/page",
    response_model=PageResponse[TalentProjectHistoryResponse],
)
def read_talent_project_page(
    person_id: UUID,
    keyword: Optional[str] = Query(default=None, max_length=200),
    project_type: Optional[str] = Query(
        default=None, pattern="^(translation|interpretation|annotation|recruitment)$",
    ),
    project_status: Optional[str] = Query(default=None, max_length=50),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if not db.query(ResourcePerson.id).filter(ResourcePerson.id == person_id).first():
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return get_talent_project_history_page(
        db, person_id, keyword=keyword, project_type=project_type,
        status=project_status, skip=skip, limit=limit,
    )


@router.get(
    "/{person_id}/projects/annotation/{project_id}/performance",
    response_model=TalentAnnotationProjectPerformanceResponse,
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)
def read_talent_annotation_project_performance(
    person_id: UUID, project_id: UUID, db: Session = Depends(get_db),
):
    if not db.query(ResourcePerson.id).filter(ResourcePerson.id == person_id).first():
        raise HTTPException(status_code=404, detail="人才档案不存在")
    result = get_talent_annotation_project_performance(db, person_id, project_id)
    if not result:
        raise HTTPException(status_code=404, detail="该人才未参与此标注项目")
    return result


@router.post(
    "/{person_id}/attachments", response_model=TalentAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=talent_write_dependencies,
)
async def upload_talent_attachment(
    person_id: UUID,
    category: str = Form(...),
    certificate_id: Optional[UUID] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return await save_talent_attachment(
            db, person_id, category, file,
            uploaded_by=current_user.id, certificate_id=certificate_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{person_id}/attachments/{attachment_id}")
def download_talent_attachment(
    person_id: UUID, attachment_id: UUID, db: Session = Depends(get_db),
):
    row = db.query(ResourcePersonAttachment).filter(
        ResourcePersonAttachment.id == attachment_id,
        ResourcePersonAttachment.person_id == person_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="人才附件不存在")
    path = attachment_path(row.storage_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="人才附件文件不存在")
    return FileResponse(path, media_type=row.content_type, filename=row.original_name)


@router.delete(
    "/{person_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=talent_write_dependencies,
)
def remove_talent_attachment(
    person_id: UUID, attachment_id: UUID, db: Session = Depends(get_db),
):
    if not delete_talent_attachment(db, person_id, attachment_id):
        raise HTTPException(status_code=404, detail="人才附件不存在")


@router.put(
    "/{person_id}", response_model=ResourcePersonDetailResponse,
    dependencies=talent_write_dependencies,
)
def update_talent_endpoint(
    person_id: UUID,
    payload: ResourcePersonUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    contacts_visible = can_view_talent_contacts(db, current_user)
    if not contacts_visible:
        existing = get_talent(db, person_id)
        if not existing:
            raise HTTPException(status_code=404, detail="人才档案不存在")
        payload = preserve_contact_fields(payload, existing, RESOURCE_CONTACT_FIELDS)
    try:
        person = update_talent(
            db,
            person_id,
            payload,
            check_contact_duplicates=contacts_visible,
        )
    except TalentDuplicateError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=_duplicate_error_detail(exc, contacts_visible=contacts_visible),
        )
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return serialize_with_contact_access(
        person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS,
        contacts_visible=contacts_visible,
    )


@router.patch(
    "/{person_id}/name", response_model=ResourcePersonDetailResponse,
    dependencies=talent_write_dependencies,
)
def update_talent_name_endpoint(
    person_id: UUID,
    payload: ResourcePersonNameUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    person = update_talent_name(db, person_id, payload.full_name)
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return serialize_with_contact_access(
        person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS,
        contacts_visible=can_view_talent_contacts(db, current_user),
    )


@router.patch(
    "/{person_id}/status", response_model=ResourcePersonDetailResponse,
    dependencies=talent_write_dependencies,
)
def update_talent_status_endpoint(
    person_id: UUID,
    payload: ResourcePersonStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    person = update_talent_status(db, person_id, payload.status)
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return serialize_with_contact_access(
        person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS,
        contacts_visible=can_view_talent_contacts(db, current_user),
    )


@router.delete(
    "/{person_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=talent_write_dependencies,
)
def delete_talent_endpoint(person_id: UUID, db: Session = Depends(get_db)):
    try:
        deleted = delete_talent(db, person_id)
    except TalentDeleteConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="人才档案不存在")


def create_recruitment_talent_endpoint(
    payload: ResourcePersonCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """招聘人才权限可新建主档与职业档案，不能借此授予专业项目能力。"""
    safe_payload = payload.model_copy(update={
        "capabilities": [],
        "written_profile": None,
        "interpretation_profile": None,
        "annotation_profile": None,
        "annotation_language_skills": [],
        "overall_score": None,
        "overall_rating": None,
        "cooperation_level": None,
        "cooperation_note": None,
        "punctuality_level": None,
        "punctuality_note": None,
        "audio_annotation_score": None,
        "audio_annotation_evaluation": None,
        "non_audio_annotation_score": None,
        "non_audio_annotation_evaluation": None,
        "collection_score": None,
        "collection_evaluation": None,
    })
    return create_talent_endpoint(
        safe_payload, db=db, current_user=current_user, idempotency_key=None,
    )


def update_recruitment_talent_endpoint(
    person_id: UUID,
    payload: ResourcePersonUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """招聘端编辑时保留原专业能力，能力只能由人才总库权限管理。"""
    contacts_visible = can_view_talent_contacts(db, current_user)
    if not contacts_visible:
        existing = get_talent(db, person_id)
        if not existing:
            raise HTTPException(status_code=404, detail="人才档案不存在")
        payload = preserve_contact_fields(payload, existing, RESOURCE_CONTACT_FIELDS)
    try:
        person = update_recruitment_talent(
            db,
            person_id,
            payload,
            check_contact_duplicates=contacts_visible,
        )
    except TalentDuplicateError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=_duplicate_error_detail(exc, contacts_visible=contacts_visible),
        )
    if not person:
        raise HTTPException(status_code=404, detail="人才档案不存在")
    return serialize_with_contact_access(
        person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS,
        contacts_visible=contacts_visible,
    )


# 招聘人才库复用同一份人员主档，但使用独立权限边界。
recruitment_router.add_api_route(
    "/", read_talents, methods=["GET"], response_model=List[ResourcePersonListResponse]
)
recruitment_router.add_api_route("/count", read_talent_count, methods=["GET"])
recruitment_router.add_api_route(
    "/duplicates", check_duplicates, methods=["GET"],
    response_model=DuplicateCheckResponse,
    dependencies=[Depends(require_super_admin)],
)
recruitment_router.add_api_route(
    "/", create_recruitment_talent_endpoint, methods=["POST"],
    response_model=ResourcePersonDetailResponse, status_code=status.HTTP_201_CREATED,
    dependencies=recruitment_write_dependencies,
)
recruitment_router.add_api_route(
    "/{person_id}", read_talent, methods=["GET"], response_model=ResourcePersonDetailResponse
)
recruitment_router.add_api_route(
    "/{person_id}/projects", read_talent_projects, methods=["GET"],
    response_model=List[TalentProjectHistoryResponse],
)
recruitment_router.add_api_route(
    "/{person_id}", update_recruitment_talent_endpoint, methods=["PUT"],
    response_model=ResourcePersonDetailResponse,
    dependencies=recruitment_write_dependencies,
)
recruitment_router.add_api_route(
    "/{person_id}/status", update_talent_status_endpoint, methods=["PATCH"],
    response_model=ResourcePersonDetailResponse,
    dependencies=recruitment_write_dependencies,
)
recruitment_router.add_api_route(
    "/{person_id}", delete_talent_endpoint, methods=["DELETE"],
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=recruitment_write_dependencies,
)
