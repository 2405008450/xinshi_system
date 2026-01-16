from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_user, get_user_by_username, get_users,
    create_user, update_user, delete_user
)
from schemas import AppUserCreate, AppUserUpdate, AppUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(user: AppUserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    return create_user(db=db, user=user)


@router.get("/", response_model=List[AppUserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=AppUserResponse)
def read_user(user_id: UUID, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user


@router.put("/{user_id}", response_model=AppUserResponse)
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_endpoint(user_id: UUID, db: Session = Depends(get_db)):
    success = delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return None
