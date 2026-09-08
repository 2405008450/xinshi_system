"""标注项目比较组 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from annotation_comparison_schemas import (
    AnnotationComparisonGroupCreate,
    AnnotationComparisonGroupDetailResponse,
    AnnotationComparisonGroupListResponse,
    AnnotationComparisonGroupUpdate,
)
from annotation_comparison_service import (
    count_comparison_groups,
    create_comparison_group,
    delete_comparison_group,
    get_comparison_group,
    list_comparison_groups,
    update_comparison_group,
)
from database import get_db
from models import AppUser
from pagination_schemas import PageResponse
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/projects/annotation-comparisons",
    tags=["annotation_project_comparisons"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)
write_permission = [Depends(require_any_permission("projects:write"))]


@router.get("/page", response_model=PageResponse[AnnotationComparisonGroupListResponse])
def read_comparison_group_page(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=150),
    db: Session = Depends(get_db),
):
    items = list_comparison_groups(db, skip=skip, limit=limit, keyword=keyword)
    return {
        "items": items,
        "total": count_comparison_groups(db, keyword=keyword),
    }


@router.post(
    "", response_model=AnnotationComparisonGroupDetailResponse,
    status_code=status.HTTP_201_CREATED, dependencies=write_permission,
)
def create_group(
    payload: AnnotationComparisonGroupCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return create_comparison_group(db, payload, current_user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="比较组创建冲突，请刷新后重试") from exc


@router.get("/{group_id}", response_model=AnnotationComparisonGroupDetailResponse)
def read_group(group_id: UUID, db: Session = Depends(get_db)):
    row = get_comparison_group(db, group_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目比较组不存在")
    return row


@router.patch(
    "/{group_id}", response_model=AnnotationComparisonGroupDetailResponse,
    dependencies=write_permission,
)
def edit_group(
    group_id: UUID,
    payload: AnnotationComparisonGroupUpdate,
    db: Session = Depends(get_db),
):
    try:
        row = update_comparison_group(db, group_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="项目比较组不存在")
    return row


@router.delete(
    "/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=write_permission,
)
def remove_group(group_id: UUID, db: Session = Depends(get_db)):
    if not delete_comparison_group(db, group_id):
        raise HTTPException(status_code=404, detail="项目比较组不存在")
    return None
