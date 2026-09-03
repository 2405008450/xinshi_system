from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from interpretation_models import InterpretationLanguage, InterpretationProject
from interpretation_schemas import (
    InterpretationLanguageCreate,
    InterpretationLanguageResponse,
    InterpretationLanguageUpdate,
    InterpretationNamePreviewRequest,
    InterpretationNamePreviewResponse,
    InterpretationProjectCreate,
    InterpretationProjectDetailResponse,
    InterpretationProjectListResponse,
    InterpretationProjectStatusUpdate,
    InterpretationProjectUpdate,
)
from interpretation_service import (
    count_interpretation_projects,
    create_interpretation_project,
    delete_interpretation_project,
    get_interpretation_project,
    get_interpretation_projects,
    preview_interpretation_project_name,
    update_interpretation_project,
    update_interpretation_project_status,
)
from models import AppUser
from inline_text_update import TextFieldRule, TextFieldUpdate, apply_text_field_update
from routers.auth import get_current_user, require_any_permission, require_module_access
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters


router = APIRouter(
    prefix="/projects/interpretation",
    tags=["interpretation_projects"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)

INTERPRETATION_TEXT_FIELDS = {
    "project_name": TextFieldRule(max_length=500),
    "task_description": TextFieldRule(),
    "customer_budget": TextFieldRule(max_length=500),
    "contact_name": TextFieldRule(max_length=255),
    "customer_order_no": TextFieldRule(max_length=150),
    "interpreter_special_requirements": TextFieldRule(),
    "interpreter_height_requirement": TextFieldRule(max_length=100),
    "interpreter_appearance_requirement": TextFieldRule(max_length=255),
    "interpreter_dress_requirement": TextFieldRule(max_length=255),
    "interpretation_domain": TextFieldRule(),
    "interpretation_content": TextFieldRule(),
    "file_path": TextFieldRule(managed_path=True),
    "quotation_path": TextFieldRule(managed_path=True),
    "contract_path": TextFieldRule(managed_path=True),
    "client_rating_note": TextFieldRule(),
    "social_post_request": TextFieldRule(),
    "resource_request": TextFieldRule(),
    "remarks": TextFieldRule(),
    "email_subject_preview": TextFieldRule(),
}

INTERPRETATION_FILTER_FIELDS = {
    "order_no", "project_name", "project_types", "task_description", "current_client_manager",
    "project_status", "client_short_name", "client_code", "client_full_name", "client_domain",
    "manager_contact", "contact_name", "customer_order_no", "scheduled_date", "locations",
    "language_id", "customer_budget", "customer_consultation_time", "customer_confirmation_time",
    "interpretation_domain", "interpretation_content", "required_interpreter_count",
    "required_interpreter_gender", "required_interpretation_level", "interpreter_special_requirements",
    "interpreter_height_requirement", "interpreter_appearance_requirement", "interpreter_dress_requirement",
    "translator_id", "client_rating", "client_rating_note", "remarks", "created_at", "updated_at",
}


def _field_filters(raw: Optional[str]):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, INTERPRETATION_FILTER_FIELDS)
    ranges = {"scheduled_date", "required_interpreter_count", "customer_consultation_time", "customer_confirmation_time", "created_at", "updated_at"}
    enums = {"project_types", "project_status", "language_id", "translator_id", "client_rating"}
    ensure_filter_operators(value, {field: ({"between"} if field in ranges else {"in"} if field in enums else {"contains"}) for field in INTERPRETATION_FILTER_FIELDS})
    return value


def _filters(
    keyword=None,
    project_status=None,
    project_type=None,
    scheduled_date_start=None,
    scheduled_date_end=None,
    translator_id=None,
    client_id=None,
    sub_client_id=None,
    language_id=None,
    field_filters=None,
):
    return dict(
        keyword=keyword,
        project_status=project_status,
        project_type=project_type,
        scheduled_date_start=scheduled_date_start,
        scheduled_date_end=scheduled_date_end,
        translator_id=translator_id,
        client_id=client_id,
        sub_client_id=sub_client_id,
        language_id=language_id,
        field_filters=field_filters,
    )


@router.get("/", response_model=List[InterpretationProjectListResponse])
def read_projects(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    project_type: Optional[str] = None,
    scheduled_date_start: Optional[date] = None,
    scheduled_date_end: Optional[date] = None,
    translator_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    language_id: Optional[UUID] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_interpretation_projects(
        db, skip=skip, limit=limit,
        **_filters(keyword, project_status, project_type, scheduled_date_start, scheduled_date_end, translator_id, client_id, sub_client_id, language_id, _field_filters(field_filters)),
    )


@router.get("/count")
def read_project_count(
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    project_type: Optional[str] = None,
    scheduled_date_start: Optional[date] = None,
    scheduled_date_end: Optional[date] = None,
    translator_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    language_id: Optional[UUID] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return {"total": count_interpretation_projects(
        db, **_filters(keyword, project_status, project_type, scheduled_date_start, scheduled_date_end, translator_id, client_id, sub_client_id, language_id, _field_filters(field_filters))
    )}


@router.get("/languages", response_model=List[InterpretationLanguageResponse])
def read_languages(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(InterpretationLanguage)
    if not include_inactive:
        query = query.filter(InterpretationLanguage.is_active.is_(True))
    return query.order_by(
        InterpretationLanguage.is_custom.asc(), InterpretationLanguage.label.asc()
    ).all()


@router.post(
    "/languages",
    response_model=InterpretationLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def create_language(
    payload: InterpretationLanguageCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    existing = db.query(InterpretationLanguage).filter(
        func.lower(InterpretationLanguage.label) == payload.label.lower()
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="该语种已存在")
    language = InterpretationLanguage(
        label=payload.label, is_custom=True, created_by=current_user.id
    )
    db.add(language)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该语种已存在")
    db.refresh(language)
    return language


@router.patch(
    "/languages/{language_id}",
    response_model=InterpretationLanguageResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_language(
    language_id: UUID,
    payload: InterpretationLanguageUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    language = db.query(InterpretationLanguage).filter(
        InterpretationLanguage.id == language_id
    ).first()
    if not language:
        raise HTTPException(status_code=404, detail="语种不存在")
    if not language.is_custom:
        raise HTTPException(status_code=400, detail="系统预置语种不可修改或停用")
    if payload.label is not None and payload.label != language.label:
        existing = db.query(InterpretationLanguage).filter(
            func.lower(func.trim(InterpretationLanguage.label)) == payload.label.lower(),
            InterpretationLanguage.id != language_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="该语种已存在")
        language.label = payload.label
    if payload.is_active is not None:
        language.is_active = payload.is_active
    language.updated_by = current_user.id
    language.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该语种已存在")
    db.refresh(language)
    return language


@router.post("/name-preview", response_model=InterpretationNamePreviewResponse)
def preview_name(payload: InterpretationNamePreviewRequest, db: Session = Depends(get_db)):
    try:
        return {"project_name": preview_interpretation_project_name(db, payload)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/", response_model=InterpretationProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def create_project(
    payload: InterpretationProjectCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(InterpretationProject).filter(
            InterpretationProject.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_interpretation_project(db, existing.id)
    try:
        return create_interpretation_project(
            db, payload, current_user.id, idempotency_key=idempotency_key,
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(InterpretationProject).filter(
                InterpretationProject.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_interpretation_project(db, existing.id)
        raise HTTPException(status_code=409, detail="口译项目创建冲突，请刷新后重试")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{project_id}", response_model=InterpretationProjectDetailResponse)
def read_project(project_id: UUID, db: Session = Depends(get_db)):
    project = get_interpretation_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="口译项目不存在")
    return project


@router.put(
    "/{project_id}", response_model=InterpretationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project(
    project_id: UUID,
    payload: InterpretationProjectUpdate,
    db: Session = Depends(get_db),
):
    try:
        project = update_interpretation_project(db, project_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if not project:
        raise HTTPException(status_code=404, detail="口译项目不存在")
    return project


@router.patch(
    "/{project_id}/text-field", response_model=InterpretationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_text_field(
    project_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
):
    project = db.get(InterpretationProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="口译项目不存在")
    try:
        changed = apply_text_field_update(project, payload, INTERPRETATION_TEXT_FIELDS)
        if changed:
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_interpretation_project(db, project_id)


@router.patch(
    "/{project_id}/status", response_model=InterpretationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_status(
    project_id: UUID,
    payload: InterpretationProjectStatusUpdate,
    db: Session = Depends(get_db),
):
    project = update_interpretation_project_status(db, project_id, payload.project_status)
    if not project:
        raise HTTPException(status_code=404, detail="口译项目不存在")
    return project


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def delete_project(
    project_id: UUID, db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        if not delete_interpretation_project(db, project_id, actor_user_id=current_user.id):
            raise HTTPException(status_code=404, detail="口译项目不存在")
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="无法删除该口译项目：仍被资源需求等业务数据引用，请先处理关联记录")
    return None
