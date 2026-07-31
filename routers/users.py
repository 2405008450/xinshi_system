from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_user, get_user_by_username, get_users, count_users,
    create_user, update_user, reset_user_password, delete_user
)
from schemas import AppUserCreate, AppUserUpdate, AppUserPasswordReset, AppUserResponse
from routers.auth import require_any_permission, require_permission, require_super_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("system:users:write"))])
def create_user_endpoint(user: AppUserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    return create_user(db=db, user=user)


@router.get("/", response_model=List[AppUserResponse], dependencies=[Depends(require_any_permission("system:users:read", "projects:read", "workflow:operate", "consultations:read", "finance:read", "tasks:assign"))])
def read_users(
    skip: int = 0,
    limit: int = 100,
    username: Optional[str] = Query(None),
    full_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    users = get_users(
        db,
        skip=skip,
        limit=limit,
        username=username,
        full_name=full_name
    )
    return users


@router.get("/count", dependencies=[Depends(require_any_permission("system:users:read", "projects:read", "workflow:operate", "consultations:read", "finance:read", "tasks:assign"))])
def read_user_count(
    username: Optional[str] = Query(None),
    full_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return {
        "total": count_users(
            db,
            username=username,
            full_name=full_name
        )
    }


@router.get("/{user_id}", response_model=AppUserResponse, dependencies=[Depends(require_any_permission("system:users:read", "projects:read", "workflow:operate", "consultations:read", "finance:read", "tasks:assign"))])
def read_user(user_id: UUID, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user


@router.put("/{user_id}", response_model=AppUserResponse, dependencies=[Depends(require_permission("system:users:write"))])
def update_user_endpoint(
    user_id: UUID,
    user_update: AppUserUpdate,
    db: Session = Depends(get_db)
):
    db_user = update_user(db, user_id=user_id, user_update=user_update)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password_endpoint(
    user_id: UUID,
    payload: AppUserPasswordReset,
    db: Session = Depends(get_db),
    _current_admin=Depends(require_super_admin),
):
    db_user = reset_user_password(db, user_id=user_id, new_password=payload.new_password)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("system:users:write"))])
def delete_user_endpoint(user_id: UUID, db: Session = Depends(get_db)):
    success = delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return None
