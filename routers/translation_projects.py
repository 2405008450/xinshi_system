import logging
from typing import List, Literal, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    count_translation_projects, get_translation_project, get_translation_project_by_no, get_translation_projects,
    create_translation_project, update_translation_project, delete_translation_project
)
from schemas import TranslationProjectCreate, TranslationProjectUpdate, TranslationProjectResponse
from utils import generate_order_no
from language_catalog import get_searchable_language_variants
from routers.auth import get_current_user, require_module_access
from models import AppUser, TranslationProject
from inline_text_update import TextFieldRule, TextFieldUpdate, apply_text_field_update
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters

router = APIRouter(prefix="/projects/translation", tags=["translation_projects"], dependencies=[Depends(require_module_access("projects:read", "projects:write"))])
logger = logging.getLogger(__name__)

TRANSLATION_TEXT_FIELDS = {
    "project_name": TextFieldRule(max_length=255, required=True),
    "email_subject_preview": TextFieldRule(),
    "task_type": TextFieldRule(max_length=50),
    "service_content": TextFieldRule(max_length=255),
    "customer_order_no": TextFieldRule(max_length=100),
    "file_type_secondary": TextFieldRule(max_length=100),
    "project_contract_type": TextFieldRule(max_length=100),
    "project_contract_status": TextFieldRule(max_length=100),
    "quotation_status": TextFieldRule(max_length=100),
    "quotation_path": TextFieldRule(managed_path=True),
    "customer_requirement_professional": TextFieldRule(),
    "customer_requirement_special": TextFieldRule(),
    "client_feedback": TextFieldRule(),
}

TRANSLATION_FILTER_FIELDS = {
    "order_no", "project_name", "service_content", "task_type", "client_short_name",
    "client_code", "customer_order_no", "project_manager_id", "client_manager",
    "manager_contact", "project_status", "file_type_secondary", "project_contract_type",
    "project_contract_status", "quotation_required", "quotation_status",
    "customer_requirement_professional", "customer_requirement_special", "language_pair",
    "priority", "word_count", "word_count_dimension", "word_count_metric_type", "customer_reception_time", "customer_deadline_time",
    "sent_to_client_time", "major_project_manager_confirmation", "translator_id", "translator_name",
    "translator_assignment_time", "translator_delivery_progress", "pre_review_qc_progress",
    "review1_progress", "review2_progress", "post_review_qc_progress", "layout_progress",
    "consolidation_progress", "client_feedback", "created_at", "updated_at",
    "project_specialist_name", "project_assistant_name", "layout_specialist_name",
    "project_file_translation_domain_level1", "project_file_translation_domain_level2",
    "project_file_type_level1", "project_file_type_level2", "project_file_format",
    "project_file_attribute_level1", "project_file_attribute_level2",
    "project_file_attribute_level3", "project_file_difficulty", "pm_confirmed_by",
}


def _field_filters(raw: Optional[str]):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, TRANSLATION_FILTER_FIELDS)
    ranges = {"word_count", "customer_reception_time", "customer_deadline_time", "sent_to_client_time", "translator_assignment_time", "created_at", "updated_at", "translator_delivery_progress", "pre_review_qc_progress", "review1_progress", "review2_progress", "post_review_qc_progress", "layout_progress", "consolidation_progress"}
    enums = {"service_content", "task_type", "project_manager_id", "project_status", "priority", "translator_id", "pm_confirmed_by", "word_count_dimension", "word_count_metric_type"}
    booleans = {"quotation_required"}
    ensure_filter_operators(value, {field: ({"between"} if field in ranges else {"in"} if field in enums else {"eq"} if field in booleans else {"contains"}) for field in TRANSLATION_FILTER_FIELDS})
    return value


@router.get("/next-order-no")
def get_next_order_no(db: Session = Depends(get_db)):
    """获取下一个订单号"""
    return {"orderNo": generate_order_no(db)}


@router.get("/language-variants")
def get_language_variants():
    """返回可搜索的受控语种及地区变体。"""
    return get_searchable_language_variants()


@router.post("/", response_model=TranslationProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    project: TranslationProjectCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(TranslationProject).filter(
            TranslationProject.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_translation_project(db, existing.id)
    try:
        project_to_create = project.model_copy(update={"created_by": current_user.id})
        return create_translation_project(
            db=db, project=project_to_create, idempotency_key=idempotency_key,
        )
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        if idempotency_key:
            existing = db.query(TranslationProject).filter(
                TranslationProject.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_translation_project(db, existing.id)
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        logger.exception("创建笔译项目时触发数据库约束")
        if "foreign key" in error_msg.lower() or "fk_" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="关联用户不存在或已失效，请刷新后重试"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目数据不符合保存要求，请检查后重试"
        )
    except DatabaseError:
        db.rollback()
        logger.exception("创建笔译项目时数据库异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="项目保存失败，请稍后重试"
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        db.rollback()
        logger.exception("创建笔译项目时发生未知异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="项目保存失败，请稍后重试"
        )


@router.get("/count")
def read_project_count(
    keyword: Optional[str] = None,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None,
    task_type: Optional[str] = None,
    service_content: Optional[str] = None,
    priority: Optional[str] = None,
    project_manager_id: Optional[UUID] = None,
    customer_deadline_date_start: Optional[date] = None,
    customer_deadline_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return {
        "total": count_translation_projects(
            db,
            keyword=keyword,
            created_by=created_by,
            project_name=project_name,
            order_no=order_no,
            project_status=project_status,
            client_short_name=client_short_name,
            task_type=task_type,
            service_content=service_content,
            priority=priority,
            project_manager_id=project_manager_id,
            customer_deadline_date_start=customer_deadline_date_start,
            customer_deadline_date_end=customer_deadline_date_end,
            created_date_start=created_date_start,
            created_date_end=created_date_end,
            field_filters=_field_filters(field_filters),
        )
    }


@router.get("/", response_model=List[TranslationProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None,
    task_type: Optional[str] = None,
    service_content: Optional[str] = None,
    priority: Optional[str] = None,
    project_manager_id: Optional[UUID] = None,
    customer_deadline_date_start: Optional[date] = None,
    customer_deadline_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    sort: Optional[Literal[
        "order_no_desc",
        "unfinished_first_order_no_desc",
        "customer_deadline_time_asc",
        "translator_return_time_asc",
    ]] = None,
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    projects = get_translation_projects(
        db,
        skip=skip,
        limit=limit,
        keyword=keyword,
        created_by=created_by,
        project_name=project_name,
        order_no=order_no,
        project_status=project_status,
        client_short_name=client_short_name,
        task_type=task_type,
        service_content=service_content,
        priority=priority,
        project_manager_id=project_manager_id,
        customer_deadline_date_start=customer_deadline_date_start,
        customer_deadline_date_end=customer_deadline_date_end,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        field_filters=_field_filters(field_filters),
        sort=sort,
    )
    return projects


@router.get("/{project_id}", response_model=TranslationProjectResponse)
def read_project(project_id: UUID, db: Session = Depends(get_db)):
    db_project = get_translation_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔译项目不存在"
        )
    return db_project


@router.put("/{project_id}", response_model=TranslationProjectResponse)
def update_project_endpoint(
    project_id: UUID,
    project_update: TranslationProjectUpdate,
    db: Session = Depends(get_db)
):
    try:
        db_project = update_translation_project(db, project_id=project_id, project_update=project_update)
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔译项目不存在"
        )
    return db_project


@router.patch("/{project_id}/text-field", response_model=TranslationProjectResponse)
def update_project_text_field(
    project_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
):
    project = db.get(TranslationProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="笔译项目不存在")
    try:
        changed = apply_text_field_update(project, payload, TRANSLATION_TEXT_FIELDS)
        if changed:
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_translation_project(db, project_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(
    project_id: UUID, db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        success = delete_translation_project(
            db, project_id=project_id, actor_user_id=current_user.id,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="无法删除该笔译项目：仍被资源需求等业务数据引用，请先处理关联记录",
        )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔译项目不存在"
        )
    return None
