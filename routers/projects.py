from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    get_project, get_project_by_no, get_projects,
    create_project, update_project, delete_project
)
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(project: ProjectCreate, db: Session = Depends(get_db)):
    try:
        # 检查项目编号是否已存在
        db_project = get_project_by_no(db, project_no=project.project_no)
        if db_project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project number already exists"
            )
        return create_project(db=db, project=project)
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


@router.get("/", response_model=List[ProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    created_by: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    projects = get_projects(db, skip=skip, limit=limit, created_by=created_by)
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(project_id: UUID, db: Session = Depends(get_db)):
    db_project = get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return db_project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project_endpoint(
    project_id: UUID,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db)
):
    db_project = update_project(db, project_id=project_id, project_update=project_update)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return db_project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(project_id: UUID, db: Session = Depends(get_db)):
    success = delete_project(db, project_id=project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return None
