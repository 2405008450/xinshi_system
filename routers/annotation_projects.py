"""标注项目 API。"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from annotation_schemas import (
    AnnotationNamePreviewRequest,
    AnnotationNamePreviewResponse,
    AnnotationProjectCreate,
    AnnotationProjectDetailResponse,
    AnnotationProjectListResponse,
    AnnotationProjectStatusUpdate,
    AnnotationProjectUpdate,
)
from annotation_service import (
    count_annotation_projects,
    create_annotation_project,
    delete_annotation_project,
    get_annotation_project,
    get_annotation_projects,
    preview_annotation_project_name,
    update_annotation_project,
    update_annotation_project_status,
)
from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/projects/annotation",
    tags=["annotation_projects"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)


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
    )


@router.get("/", response_model=List[AnnotationProjectListResponse])
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
    )
    return get_annotation_projects(db, skip=skip, limit=limit, **filters)


@router.get("/count")
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
    )
    return {"total": count_annotation_projects(db, **filters)}


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
):
    try:
        return create_annotation_project(db, payload, current_user.id)
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
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    try:
        if not delete_annotation_project(db, project_id):
            raise HTTPException(status_code=404, detail="标注项目不存在")
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="无法删除该标注项目：仍被资源需求等业务数据引用，请先处理关联记录")
    return None
