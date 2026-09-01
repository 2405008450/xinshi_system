from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crypto_utils import CredentialCryptoConfigurationError
from database import get_db
from daily_report_mail_models import UserMailAccount
from crud import (
    get_user, get_user_by_email, get_user_by_username, get_users, count_users,
    create_user, update_user, reset_user_password, delete_user
)
from schemas import AppUserCreate, AppUserUpdate, AppUserPasswordReset, AppUserResponse
from mail_account_schemas import MailAccountStatus, MailAccountWrite
from mail_service import MailConfigurationError, MailDeliveryError
from routers.auth import require_any_permission, require_permission, require_super_admin
from leave_service import assignment_disabled_reason, get_active_leave_map
from user_mail_account_service import (
    delete_mail_account,
    save_mail_account,
    serialize_mail_account,
    verify_mail_account,
)

router = APIRouter(prefix="/users", tags=["users"])


EMAIL_ALREADY_BOUND_DETAIL = "该邮箱已被其他用户绑定，请使用其他邮箱"


def _mail_account_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, MailDeliveryError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, (MailConfigurationError, CredentialCryptoConfigurationError, ValueError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="发件邮箱配置处理失败，请检查服务日志",
    )


def _serialize_user(user, account: Optional[UserMailAccount] = None, leave=None) -> dict:
    email_matches = bool(
        account
        and user.email
        and account.email_snapshot.casefold() == user.email.strip().casefold()
    )
    mail_verified = bool(account and account.is_verified and email_matches)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "is_active": user.is_active,
        "department": user.department,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "mail_account_bound": account is not None,
        "mail_account_verified": mail_verified,
        "mail_account_verified_at": account.verified_at if mail_verified else None,
        "is_on_leave": leave is not None,
        "leave_start": leave.start_date if leave else None,
        "leave_end": leave.end_date if leave else None,
        "assignment_disabled_reason": assignment_disabled_reason(leave),
    }


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
            detail="用户名已存在"
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
    limit: int = Query(100, ge=1, le=500),
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
    user_ids = [user.id for user in users]
    account_map = {
        account.user_id: account
        for account in db.query(UserMailAccount).filter(UserMailAccount.user_id.in_(user_ids)).all()
    } if user_ids else {}
    leave_map = get_active_leave_map(db, user_ids) if include_leave_status else {}
    return [
        _serialize_user(user, account_map.get(user.id), leave_map.get(user.id))
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
            detail="用户不存在"
        )
    account = db.query(UserMailAccount).filter(UserMailAccount.user_id == user_id).first()
    return _serialize_user(db_user, account)


@router.get(
    "/{user_id}/mail-account",
    response_model=MailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def read_user_mail_account(user_id: UUID, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return serialize_mail_account(db, db_user)


@router.put(
    "/{user_id}/mail-account",
    response_model=MailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def save_user_mail_account(
    user_id: UUID,
    payload: MailAccountWrite,
    db: Session = Depends(get_db),
):
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    try:
        save_mail_account(db, db_user, payload.authorization_code)
        return verify_mail_account(db, db_user)
    except Exception as exc:
        db.rollback()
        raise _mail_account_exception(exc) from exc


@router.post(
    "/{user_id}/mail-account/verify",
    response_model=MailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def verify_user_mail_account(user_id: UUID, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    try:
        return verify_mail_account(db, db_user)
    except Exception as exc:
        db.rollback()
        raise _mail_account_exception(exc) from exc


@router.delete(
    "/{user_id}/mail-account",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def delete_user_mail_account(user_id: UUID, db: Session = Depends(get_db)):
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    delete_mail_account(db, db_user)


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
    existing_user = get_user(db, user_id=user_id)
    previous_email = (existing_user.email or "").strip().casefold() if existing_user else ""
    try:
        db_user = update_user(db, user_id=user_id, user_update=user_update)
    except IntegrityError as exc:
        db.rollback()
        _raise_user_integrity_error(exc)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    current_email = (db_user.email or "").strip().casefold()
    if previous_email != current_email:
        account = db.query(UserMailAccount).filter(UserMailAccount.user_id == user_id).first()
        if account:
            account.is_verified = False
            account.verified_at = None
            db.commit()
            db.refresh(db_user)
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
            detail="用户不存在"
        )
    return None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("system:users:write"))])
def delete_user_endpoint(user_id: UUID, db: Session = Depends(get_db)):
    success = delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return None
