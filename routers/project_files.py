from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    count_project_files, count_project_files_by_project, get_project_file,
    get_project_files_by_project, get_project_files,
    create_project_file, update_project_file, delete_project_file
)
from models import ProjectFile
from schemas import ProjectFileCreate, ProjectFileUpdate, ProjectFileResponse
from routers.auth import require_module_access

router = APIRouter(prefix="/project-files", tags=["project-files"], dependencies=[Depends(require_module_access("project_files:read", "project_files:write"))])


@router.post("/", response_model=ProjectFileResponse, status_code=status.HTTP_201_CREATED)
def create_project_file_endpoint(project_file: ProjectFileCreate, db: Session = Depends(get_db)):
    existing = db.query(ProjectFile).filter(
        ProjectFile.translation_project_id == project_file.translation_project_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该项目已存在文件记录，请直接编辑现有记录"
        )
    try:
        return create_project_file(db=db, project_file=project_file)
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "foreign key" in error_msg.lower() or "fk_" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"项目或用户不存在：{error_msg}"
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据库约束错误：{error_msg}")
    except DatabaseError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库错误：{error_msg}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"未知错误：{str(e)}")


@router.get("/", response_model=List[ProjectFileResponse])
def read_project_files(
    skip: int = 0,
    limit: int = 100,
    order_no: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return get_project_files(db, skip=skip, limit=limit, order_no=order_no)


@router.get("/project/{project_id}", response_model=List[ProjectFileResponse])
def read_project_files_by_project(
    project_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return get_project_files_by_project(db, translation_project_id=project_id, skip=skip, limit=limit)


@router.get("/project/{project_id}/count")
def read_project_file_count_by_project(project_id: UUID, db: Session = Depends(get_db)):
    return {"total": count_project_files_by_project(db, translation_project_id=project_id)}


@router.get("/count")
def read_project_file_count(
    order_no: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return {"total": count_project_files(db, order_no=order_no)}


@router.get("/{file_id}", response_model=ProjectFileResponse)
def read_project_file(file_id: UUID, db: Session = Depends(get_db)):
    db_file = get_project_file(db, file_id=file_id)
    if db_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件记录不存在")
    return db_file


@router.put("/{file_id}", response_model=ProjectFileResponse)
def update_project_file_endpoint(
    file_id: UUID,
    file_update: ProjectFileUpdate,
    db: Session = Depends(get_db)
):
    try:
        db_file = update_project_file(db, file_id=file_id, file_update=file_update)
        if db_file is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件记录不存在")
        return db_file
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据库约束错误：{error_msg}")
    except DatabaseError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库错误：{error_msg}")


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_file_endpoint(file_id: UUID, db: Session = Depends(get_db)):
    success = delete_project_file(db, file_id=file_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件记录不存在")
    return None
