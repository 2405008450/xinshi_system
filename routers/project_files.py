from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    get_project_file, get_project_files_by_project, get_project_files,
    create_project_file, update_project_file, delete_project_file
)
from schemas import ProjectFileCreate, ProjectFileUpdate, ProjectFileResponse

router = APIRouter(prefix="/project-files", tags=["project-files"])


@router.post("/", response_model=ProjectFileResponse, status_code=status.HTTP_201_CREATED)
def create_project_file_endpoint(project_file: ProjectFileCreate, db: Session = Depends(get_db)):
    try:
        return create_project_file(db=db, project_file=project_file)
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "foreign key" in error_msg.lower() or "fk_" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Foreign key constraint violation. Project or User may not exist: {error_msg}"
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


@router.get("/", response_model=List[ProjectFileResponse])
def read_project_files(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    files = get_project_files(db, skip=skip, limit=limit)
    return files


@router.get("/project/{project_id}", response_model=List[ProjectFileResponse])
def read_project_files_by_project(
    project_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    files = get_project_files_by_project(db, project_id=project_id, skip=skip, limit=limit)
    return files


@router.get("/{file_id}", response_model=ProjectFileResponse)
def read_project_file(file_id: UUID, db: Session = Depends(get_db)):
    db_file = get_project_file(db, file_id=file_id)
    if db_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project file not found"
        )
    return db_file


@router.put("/{file_id}", response_model=ProjectFileResponse)
def update_project_file_endpoint(
    file_id: UUID,
    file_update: ProjectFileUpdate,
    db: Session = Depends(get_db)
):
    db_file = update_project_file(db, file_id=file_id, file_update=file_update)
    if db_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project file not found"
        )
    return db_file


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_file_endpoint(file_id: UUID, db: Session = Depends(get_db)):
    success = delete_project_file(db, file_id=file_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project file not found"
        )
    return None
