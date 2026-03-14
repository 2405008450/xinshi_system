from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    get_translation_project, get_translation_project_by_no, get_translation_projects,
    create_translation_project, update_translation_project, delete_translation_project
)
from schemas import TranslationProjectCreate, TranslationProjectUpdate, TranslationProjectResponse
from utils import generate_order_no
from routers.auth import get_current_user
from models import AppUser

router = APIRouter(prefix="/projects/translation", tags=["translation_projects"], dependencies=[Depends(get_current_user)])


@router.get("/next-order-no")
def get_next_order_no(db: Session = Depends(get_db)):
    """获取下一个订单号"""
    return {"orderNo": generate_order_no(db)}


@router.post("/", response_model=TranslationProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    project: TranslationProjectCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        project_to_create = project.model_copy(update={"created_by": current_user.id})
        return create_translation_project(db=db, project=project_to_create)
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "foreign key" in error_msg.lower() or "fk_" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Foreign key constraint violation: The referenced user (created_by) may not exist. {error_msg}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database integrity error: {error_msg}"
        )
    except DatabaseError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {error_msg}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/", response_model=List[TranslationProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    projects = get_translation_projects(
        db,
        skip=skip,
        limit=limit,
        created_by=created_by,
        project_name=project_name,
        order_no=order_no,
        project_status=project_status,
        client_short_name=client_short_name
    )
    return projects


@router.get("/{project_id}", response_model=TranslationProjectResponse)
def read_project(project_id: UUID, db: Session = Depends(get_db)):
    db_project = get_translation_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return db_project


@router.put("/{project_id}", response_model=TranslationProjectResponse)
def update_project_endpoint(
    project_id: UUID,
    project_update: TranslationProjectUpdate,
    db: Session = Depends(get_db)
):
    db_project = update_translation_project(db, project_id=project_id, project_update=project_update)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return db_project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(project_id: UUID, db: Session = Depends(get_db)):
    success = delete_translation_project(db, project_id=project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return None
