"""标注项目 API。"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from annotation_schemas import (
    AnnotationNamePreviewRequest,
    AnnotationNamePreviewResponse,
    AnnotationProjectCreate,
    AnnotationProjectDetailResponse,
    AnnotationProjectListResponse,
    AnnotationProjectManagersUpdate,
    AnnotationProjectOrderNoUpdate,
    AnnotationProjectPriorityUpdate,
    AnnotationProjectStatusUpdate,
    AnnotationProjectUpdate,
)
from annotation_service import (
    AnnotationProjectDeleteConflict,
    AnnotationOrderNoConflict,
    count_annotation_projects,
    create_annotation_project,
    delete_annotation_project,
    get_annotation_project,
    get_annotation_projects,
    preview_annotation_project_name,
    update_annotation_project,
    update_annotation_project_managers,
    update_annotation_project_order_no,
    update_annotation_project_priority,
    update_annotation_project_status,
)
from database import get_db
from annotation_models import AnnotationProject
from annotation_ops_models import AnnotationCustomFieldDefinition
from pagination_schemas import PageResponse, resolve_page_total
from annotation_custom_field_service import validate_custom_values
from concurrency import assert_fresh
from inline_text_update import (
    TextFieldRule,
    TextFieldUpdate,
    apply_text_field_update,
    normalize_text_value,
)
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access, require_permission
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters


router = APIRouter(
    prefix="/projects/annotation",
    tags=["annotation_projects"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)


ANNOTATION_TEXT_FIELDS = {
    "language_region": TextFieldRule(max_length=255),
    "project_name": TextFieldRule(max_length=500),
    "task_description": TextFieldRule(),
    "potential_demand": TextFieldRule(),
    "contact_name": TextFieldRule(max_length=255),
    "customer_order_no": TextFieldRule(max_length=150),
    "email_subject_preview": TextFieldRule(max_length=1000),
    "project_path": TextFieldRule(managed_path=True),
    "quotation_path": TextFieldRule(managed_path=True),
    "contract_path": TextFieldRule(managed_path=True),
}

ANNOTATION_FILTER_FIELDS = {
    "order_no", "project_name", "project_types", "task_description", "project_status", "priority",
    "client_short_name", "client_code", "client_full_name", "contact_name", "customer_order_no",
    "language_id", "language_region", "potential_demand", "has_customer_price", "customer_price",
    "assignee_person_id", "task_dispatched_at", "task_submitted_at", "client_manager_id",
    "project_manager_id",
    "customer_consultation_time", "customer_confirmation_time", "created_at", "updated_at",
}


def _field_filters(raw: Optional[str], db: Session):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, ANNOTATION_FILTER_FIELDS, allow_custom=True)
    ranges = {"customer_price", "task_dispatched_at", "task_submitted_at", "customer_consultation_time", "customer_confirmation_time", "created_at", "updated_at"}
    enums = {
        "project_types", "project_status", "priority", "language_id", "assignee_person_id",
        "client_manager_id", "project_manager_id",
    }
    booleans = {"has_customer_price"}
    ensure_filter_operators(value, {field: ({"between"} if field in ranges else {"in"} if field in enums else {"eq"} if field in booleans else {"contains"}) for field in ANNOTATION_FILTER_FIELDS}, allow_custom=True)
    for key, descriptor in value.items():
        if not key.startswith("custom:"):
            continue
        try:
            field_id = UUID(key.split(":", 1)[1])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="动态筛选字段 ID 无效") from exc
        definition = db.query(AnnotationCustomFieldDefinition).filter(
            AnnotationCustomFieldDefinition.id == field_id,
            AnnotationCustomFieldDefinition.table_code == "project",
            AnnotationCustomFieldDefinition.is_active.is_(True),
        ).first()
        if not definition or definition.data_type in {"image", "url"}:
            raise HTTPException(status_code=422, detail="动态筛选字段不存在或不支持筛选")
        allowed_operator = {
            "number": "between", "date": "between", "datetime": "between",
            "boolean": "eq", "single_select": "in", "multi_select": "in",
        }.get(definition.data_type, "contains")
        if descriptor.get("op") != allowed_operator:
            raise HTTPException(status_code=422, detail=f"动态字段 {definition.field_label} 不支持该操作符")
        descriptor["data_type"] = definition.data_type
    return value


def _filters(
    keyword=None,
    project_status=None,
    project_type=None,
    language_id=None,
    client_manager_id=None,
    dispatched_date_start=None,
    dispatched_date_end=None,
    submitted_date_start=None,
    submitted_date_end=None,
    client_id=None,
    sub_client_id=None,
    assignee_person_id=None,
    created_date_start=None,
    created_date_end=None,
    consultation_date_start=None,
    consultation_date_end=None,
    confirmation_date_start=None,
    confirmation_date_end=None,
    field_filters=None,
):
    return dict(
        keyword=keyword,
        project_status=project_status,
        project_type=project_type,
        language_id=language_id,
        client_manager_id=client_manager_id,
        dispatched_date_start=dispatched_date_start,
        dispatched_date_end=dispatched_date_end,
        submitted_date_start=submitted_date_start,
        submitted_date_end=submitted_date_end,
        client_id=client_id,
        sub_client_id=sub_client_id,
        assignee_person_id=assignee_person_id,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        confirmation_date_start=confirmation_date_start,
        confirmation_date_end=confirmation_date_end,
        field_filters=field_filters,
    )


@router.get("/", response_model=List[AnnotationProjectListResponse], deprecated=True)
def read_projects(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    project_type: Optional[str] = None,
    language_id: Optional[UUID] = None,
    client_manager_id: Optional[UUID] = None,
    dispatched_date_start: Optional[date] = None,
    dispatched_date_end: Optional[date] = None,
    submitted_date_start: Optional[date] = None,
    submitted_date_end: Optional[date] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    assignee_person_id: Optional[UUID] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    confirmation_date_start: Optional[date] = None,
    confirmation_date_end: Optional[date] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = _filters(
        keyword=keyword,
        project_status=project_status,
        project_type=project_type,
        language_id=language_id,
        client_manager_id=client_manager_id,
        dispatched_date_start=dispatched_date_start,
        dispatched_date_end=dispatched_date_end,
        submitted_date_start=submitted_date_start,
        submitted_date_end=submitted_date_end,
        client_id=client_id,
        sub_client_id=sub_client_id,
        assignee_person_id=assignee_person_id,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        confirmation_date_start=confirmation_date_start,
        confirmation_date_end=confirmation_date_end,
        field_filters=_field_filters(field_filters, db),
    )
    return get_annotation_projects(db, skip=skip, limit=limit, **filters)


@router.get("/count", deprecated=True)
def read_project_count(
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    project_type: Optional[str] = None,
    language_id: Optional[UUID] = None,
    client_manager_id: Optional[UUID] = None,
    dispatched_date_start: Optional[date] = None,
    dispatched_date_end: Optional[date] = None,
    submitted_date_start: Optional[date] = None,
    submitted_date_end: Optional[date] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    assignee_person_id: Optional[UUID] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    confirmation_date_start: Optional[date] = None,
    confirmation_date_end: Optional[date] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = _filters(
        keyword=keyword,
        project_status=project_status,
        project_type=project_type,
        language_id=language_id,
        client_manager_id=client_manager_id,
        dispatched_date_start=dispatched_date_start,
        dispatched_date_end=dispatched_date_end,
        submitted_date_start=submitted_date_start,
        submitted_date_end=submitted_date_end,
        client_id=client_id,
        sub_client_id=sub_client_id,
        assignee_person_id=assignee_person_id,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        confirmation_date_start=confirmation_date_start,
        confirmation_date_end=confirmation_date_end,
        field_filters=_field_filters(field_filters, db),
    )
    return {"total": count_annotation_projects(db, **filters)}


@router.get("/page", response_model=PageResponse[AnnotationProjectListResponse])
def read_project_page(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    project_type: Optional[str] = None,
    language_id: Optional[UUID] = None,
    client_manager_id: Optional[UUID] = None,
    dispatched_date_start: Optional[date] = None,
    dispatched_date_end: Optional[date] = None,
    submitted_date_start: Optional[date] = None,
    submitted_date_end: Optional[date] = None,
    client_id: Optional[UUID] = None,
    sub_client_id: Optional[UUID] = None,
    assignee_person_id: Optional[UUID] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    confirmation_date_start: Optional[date] = None,
    confirmation_date_end: Optional[date] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = _filters(
        keyword=keyword, project_status=project_status,
        project_type=project_type, language_id=language_id,
        client_manager_id=client_manager_id,
        dispatched_date_start=dispatched_date_start,
        dispatched_date_end=dispatched_date_end,
        submitted_date_start=submitted_date_start,
        submitted_date_end=submitted_date_end, client_id=client_id,
        sub_client_id=sub_client_id, assignee_person_id=assignee_person_id,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        confirmation_date_start=confirmation_date_start,
        confirmation_date_end=confirmation_date_end,
        field_filters=_field_filters(field_filters, db),
    )
    items = get_annotation_projects(db, skip=skip, limit=limit, **filters)
    return {
        "items": items,
        "total": resolve_page_total(
            items, skip, lambda: count_annotation_projects(db, **filters),
        ),
    }


@router.post("/name-preview", response_model=AnnotationNamePreviewResponse)
def preview_name(payload: AnnotationNamePreviewRequest, db: Session = Depends(get_db)):
    try:
        return {"project_name": preview_annotation_project_name(db, payload)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/", response_model=AnnotationProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def create_project(
    payload: AnnotationProjectCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(AnnotationProject).filter(
            AnnotationProject.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_annotation_project(db, existing.id)
    try:
        return create_annotation_project(
            db, payload, current_user.id, idempotency_key=idempotency_key,
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(AnnotationProject).filter(
                AnnotationProject.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_annotation_project(db, existing.id)
        raise HTTPException(status_code=409, detail="标注项目创建冲突，请刷新后重试")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{project_id}", response_model=AnnotationProjectDetailResponse)
def read_project(project_id: UUID, db: Session = Depends(get_db)):
    project = get_annotation_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    return project


@router.put(
    "/{project_id}", response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project(
    project_id: UUID,
    payload: AnnotationProjectUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        project = update_annotation_project(db, project_id, payload, current_user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    return project


@router.patch(
    "/{project_id}/text-field", response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_text_field(
    project_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
):
    project = db.get(AnnotationProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    try:
        changed = apply_text_field_update(project, payload, ANNOTATION_TEXT_FIELDS)
        if changed:
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return get_annotation_project(db, project_id)


@router.patch(
    "/{project_id}/custom-fields/{field_id}/text",
    response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_custom_text_field(
    project_id: UUID,
    field_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    project = db.get(AnnotationProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    definition = db.get(AnnotationCustomFieldDefinition, field_id)
    if (
        not definition
        or definition.table_code != "project"
        or definition.project_id is not None
        or definition.data_type != "text"
        or not definition.is_active
    ):
        raise HTTPException(status_code=400, detail="该动态字段不支持快捷编辑")
    if payload.field != definition.field_key:
        raise HTTPException(status_code=400, detail="动态字段键与接口地址不一致")
    try:
        assert_fresh(project, payload.expected_updated_at)
        value = normalize_text_value(
            payload.value,
            TextFieldRule(required=definition.is_required),
        )
        values = dict(project.custom_values or {})
        values[str(field_id)] = value
        normalized = validate_custom_values(
            db,
            "project",
            None,
            values,
            project.custom_values,
            current_user.id,
        )
        if normalized != (project.custom_values or {}):
            project.custom_values = normalized
            project.updated_at = datetime.now()
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return get_annotation_project(db, project_id)


@router.patch(
    "/{project_id}/priority", response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_priority(
    project_id: UUID,
    payload: AnnotationProjectPriorityUpdate,
    db: Session = Depends(get_db),
):
    project = update_annotation_project_priority(db, project_id, payload.priority)
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    return project


@router.patch(
    "/{project_id}/managers", response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_managers(
    project_id: UUID,
    payload: AnnotationProjectManagersUpdate,
    db: Session = Depends(get_db),
):
    try:
        project = update_annotation_project_managers(
            db,
            project_id,
            payload.client_manager_id,
            payload.project_manager_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    return project


@router.patch(
    "/{project_id}/order-no",
    response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_permission("projects:order_no:write"))],
)
def update_project_order_no(
    project_id: UUID,
    payload: AnnotationProjectOrderNoUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        project = update_annotation_project_order_no(
            db,
            project_id,
            payload.new_order_no,
            payload.reason,
            payload.expected_updated_at,
            current_user.id,
        )
    except AnnotationOrderNoConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"订单号 {payload.new_order_no} 已被当前或历史标注项目使用",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
    return project


@router.patch(
    "/{project_id}/status", response_model=AnnotationProjectDetailResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def update_project_status(
    project_id: UUID,
    payload: AnnotationProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    project = update_annotation_project_status(
        db,
        project_id,
        payload.project_status,
        payload.effective_on,
        payload.change_note,
        current_user.id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="标注项目不存在")
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
        if not delete_annotation_project(db, project_id, actor_user_id=current_user.id):
            raise HTTPException(status_code=404, detail="标注项目不存在")
    except AnnotationProjectDeleteConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="无法删除该标注项目：仍有未识别的业务数据引用，请联系管理员检查关联记录")
    return None
