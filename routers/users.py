from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_user, get_user_by_email, get_user_by_username, get_users, count_users,
    create_user, update_user, reset_user_password, delete_user
)
from schemas import AppUserCreate, AppUserUpdate, AppUserPasswordReset, AppUserResponse
from routers.auth import require_any_permission, require_permission, require_super_admin
from leave_service import assignment_disabled_reason, get_active_leave_map

router = APIRouter(prefix="/users", tags=["users"])


EMAIL_ALREADY_BOUND_DETAIL = "该邮箱已被其他用户绑定，请使用其他邮箱"


def _raise_user_integrity_error(exc: IntegrityError) -> None:
    constraint_name = getattr(getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", None)
    if constraint_name == "uq_app_user_email_normalized":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=EMAIL_ALREADY_BOUND_DETAIL) from exc
    if constraint_name == "app_user_username_key":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在") from exc
    raise exc


@router.post("/", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("system:users:write"))])
def create_user_endpoint(user: AppUserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=EMAIL_ALREADY_BOUND_DETAIL,
        )
    try:
        return create_user(db=db, user=user)
    except IntegrityError as exc:
        db.rollback()
        _raise_user_integrity_error(exc)


@router.get("/", response_model=List[AppUserResponse], dependencies=[Depends(require_any_permission("system:users:read", "system:mail_settings:read", "projects:read", "workflow:operate", "consultations:read", "finance:read", "tasks:assign"))])
def read_users(
    skip: int = 0,
    limit: int = 100,
    username: Optional[str] = Query(None),
    full_name: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    include_leave_status: bool = Query(False),
    db: Session = Depends(get_db)
):
    users = get_users(
        db,
        skip=skip,
        limit=limit,
        username=username,
        full_name=full_name,
        department=department,
    )
    if not include_leave_status:
        return users
    leave_map = get_active_leave_map(db, [user.id for user in users])
    return [
        {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
            "department": user.department,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "is_on_leave": user.id in leave_map,
            "leave_start": leave_map[user.id].start_date if user.id in leave_map else None,
            "leave_end": leave_map[user.id].end_date if user.id in leave_map else None,
            "assignment_disabled_reason": assignment_disabled_reason(leave_map.get(user.id)),
        }
        for user in users
    ]


@router.get("/count", dependencies=[Depends(require_any_permission("system:users:read", "projects:read", "workflow:operate", "consultations:read", "finance:read", "tasks:assign"))])
def read_user_count(
    username: Optional[str] = Query(None),
    full_name: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return {
        "total": count_users(
            db,
            username=username,
            full_name=full_name,
            department=department,
        )
    }


@router.get("/email-availability", dependencies=[Depends(require_permission("system:users:write"))])
def check_user_email_availability(
    email: EmailStr = Query(...),
    exclude_user_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
):
    return {
        "available": get_user_by_email(
            db,
            str(email),
            exclude_user_id=exclude_user_id,
        ) is None
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
    if "email" in user_update.model_fields_set and get_user_by_email(
        db,
        user_update.email,
        exclude_user_id=user_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=EMAIL_ALREADY_BOUND_DETAIL,
        )
    try:
        db_user = update_user(db, user_id=user_id, user_update=user_update)
    except IntegrityError as exc:
        db.rollback()
        _raise_user_integrity_error(exc)
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
