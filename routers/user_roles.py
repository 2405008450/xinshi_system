from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DatabaseError

from database import get_db
from crud import (
    get_user_role, get_user_roles_by_user, get_user_roles_by_role,
    get_user_role_by_user_and_role, create_user_role,
    delete_user_role, delete_user_role_by_user_and_role
)
from schemas import UserRoleCreate, UserRoleResponse

router = APIRouter(prefix="/user-roles", tags=["user-roles"])


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
                detail="User role already exists"
            )
        return create_user_role(db=db, user_role=user_role)
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "foreign key" in error_msg.lower() or "fk_" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Foreign key constraint violation. User or Role may not exist: {error_msg}"
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
            detail="User role not found"
        )
    return db_user_role


@router.delete("/{user_role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role_endpoint(user_role_id: UUID, db: Session = Depends(get_db)):
    success = delete_user_role(db, user_role_id=user_role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User role not found"
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
            detail="User role not found"
        )
    return None
