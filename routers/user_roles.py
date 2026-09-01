import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    get_user_role, get_user_roles, get_user_roles_by_user, get_user_roles_by_role,
    get_user_role_by_user_and_role, create_user_role,
    delete_user_role, delete_user_role_by_user_and_role
)
from schemas import UserRoleCreate, UserRoleDetailResponse, UserRoleResponse
from routers.auth import require_permission

router = APIRouter(
    prefix="/user-roles",
    tags=["user-roles"],
    dependencies=[Depends(require_permission("system:user_roles:write"))],
)
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[UserRoleDetailResponse])
def read_user_roles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rows = get_user_roles(db, skip=skip, limit=limit)
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "role_id": row.role_id,
            "created_at": row.created_at,
            "username": row.user.username,
            "user_full_name": row.user.full_name,
            "role_name": row.role.role_name,
        }
        for row in rows
    ]


@router.post("/", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
def create_user_role_endpoint(user_role: UserRoleCreate, db: Session = Depends(get_db)):
    try:
        # 检查用户角色关联是否已存在
        db_user_role = get_user_role_by_user_and_role(
            db, user_id=user_role.user_id, role_id=user_role.role_id
        )
        if db_user_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户已拥有该角色"
            )
        return create_user_role(db=db, user_role=user_role)
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        logger.exception("保存用户角色时触发数据库约束")
        if "foreign key" in error_msg.lower() or "fk_" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户或角色不存在，请刷新后重试"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户角色数据不符合保存要求，请检查后重试"
        )
    except DatabaseError:
        db.rollback()
        logger.exception("保存用户角色时数据库异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户角色保存失败，请稍后重试"
        )
    except Exception:
        db.rollback()
        logger.exception("保存用户角色时发生未知异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户角色保存失败，请稍后重试"
        )


@router.get("/user/{user_id}", response_model=List[UserRoleResponse])
def read_user_roles_by_user(user_id: UUID, db: Session = Depends(get_db)):
    user_roles = get_user_roles_by_user(db, user_id=user_id)
    return user_roles


@router.get("/role/{role_id}", response_model=List[UserRoleResponse])
def read_user_roles_by_role(role_id: UUID, db: Session = Depends(get_db)):
    user_roles = get_user_roles_by_role(db, role_id=role_id)
    return user_roles


@router.get("/{user_role_id}", response_model=UserRoleResponse)
def read_user_role(user_role_id: UUID, db: Session = Depends(get_db)):
    db_user_role = get_user_role(db, user_role_id=user_role_id)
    if db_user_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户角色关联不存在"
        )
    return db_user_role


@router.delete("/{user_role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role_endpoint(user_role_id: UUID, db: Session = Depends(get_db)):
    success = delete_user_role(db, user_role_id=user_role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户角色关联不存在"
        )
    return None


@router.delete("/user/{user_id}/role/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role_by_user_and_role_endpoint(
    user_id: UUID,
    role_id: UUID,
    db: Session = Depends(get_db)
):
    success = delete_user_role_by_user_and_role(db, user_id=user_id, role_id=role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户角色关联不存在"
        )
    return None
