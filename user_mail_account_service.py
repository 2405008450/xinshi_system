"""用户个人 SMTP 凭据的保存、验证与发件配置服务。"""

from __future__ import annotations

import datetime
import os
from dataclasses import replace
from typing import Optional
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from crypto_utils import decrypt_credential, encrypt_credential
from daily_report_mail_models import UserMailAccount
from mail_service import (
    MailConfigurationError,
    SmtpSettings,
    verify_smtp_settings,
)
from models import AppUser


PROJECT_MAIL_SENDER_MODES = {"system", "personal"}


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def display_user(user: AppUser) -> str:
    return (user.full_name or user.username or "").strip()


def valid_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def get_mail_account(db: Session, user_id: UUID) -> Optional[UserMailAccount]:
    return db.query(UserMailAccount).filter(UserMailAccount.user_id == user_id).first()


def serialize_mail_account(db: Session, user: AppUser) -> dict:
    account = get_mail_account(db, user.id)
    current_email = valid_email(user.email)
    email_matches = bool(
        account
        and current_email
        and account.email_snapshot.casefold() == current_email.casefold()
    )
    return {
        "email": current_email,
        "is_bound": bool(account),
        "is_verified": bool(account and account.is_verified and email_matches),
        "verified_at": account.verified_at if account else None,
        "updated_at": account.updated_at if account else None,
    }


def save_mail_account(db: Session, user: AppUser, authorization_code: str) -> dict:
    email = valid_email(user.email)
    if not email:
        raise ValueError("当前用户尚未绑定有效企业邮箱，请联系管理员完善用户邮箱")
    code = authorization_code.strip()
    if not code:
        raise ValueError("SMTP 授权码或专用密码不能为空")
    ciphertext, version = encrypt_credential(code)
    account = get_mail_account(db, user.id)
    if not account:
        account = UserMailAccount(
            user_id=user.id,
            email_snapshot=email,
            authorization_ciphertext=ciphertext,
            encryption_key_version=version,
        )
        db.add(account)
    else:
        account.email_snapshot = email
        account.authorization_ciphertext = ciphertext
        account.encryption_key_version = version
    account.is_verified = False
    account.verified_at = None
    account.updated_at = _now()
    db.commit()
    return serialize_mail_account(db, user)


def delete_mail_account(db: Session, user: AppUser) -> None:
    account = get_mail_account(db, user.id)
    if account:
        db.delete(account)
        db.commit()


def personal_smtp_settings(
    db: Session,
    user: AppUser,
    *,
    require_verified: bool = True,
) -> SmtpSettings:
    email = valid_email(user.email)
    if not email:
        raise MailConfigurationError("当前用户没有有效企业邮箱")
    account = get_mail_account(db, user.id)
    if not account:
        raise MailConfigurationError("尚未绑定个人邮箱 SMTP 授权码或专用密码")
    if account.email_snapshot.casefold() != email.casefold():
        raise MailConfigurationError("用户邮箱已变更，请重新绑定个人邮箱 SMTP 凭据")
    if require_verified and not account.is_verified:
        raise MailConfigurationError("个人邮箱 SMTP 授权尚未验证")
    authorization_code = decrypt_credential(
        account.authorization_ciphertext,
        account.encryption_key_version,
    )
    base = SmtpSettings.from_env()
    settings = replace(
        base,
        username=email,
        password=authorization_code,
        sender_email=email,
        sender_name=display_user(user),
        reply_to=email,
    )
    settings.validate()
    return settings


def verify_mail_account(db: Session, user: AppUser) -> dict:
    settings = personal_smtp_settings(db, user, require_verified=False)
    verify_smtp_settings(settings)
    account = get_mail_account(db, user.id)
    account.is_verified = True
    account.verified_at = _now()
    account.updated_at = account.verified_at
    db.commit()
    return serialize_mail_account(db, user)


def project_mail_sender_mode() -> str:
    mode = os.getenv("PROJECT_MAIL_SENDER_MODE", "system").strip().lower()
    if mode not in PROJECT_MAIL_SENDER_MODES:
        raise MailConfigurationError(
            "PROJECT_MAIL_SENDER_MODE 只能是 system 或 personal"
        )
    return mode


def resolve_project_sender(db: Session, user: AppUser) -> tuple[SmtpSettings, dict]:
    """返回项目邮件使用的 SMTP 配置和可安全展示的发件人信息。"""
    mode = project_mail_sender_mode()
    if mode == "personal":
        settings = personal_smtp_settings(db, user)
        return settings, {
            "sender_mode": mode,
            "sender_name": settings.sender_name,
            "sender_email": settings.sender_email,
            "sender_verified": True,
        }

    settings = SmtpSettings.from_env()
    settings.validate()
    return settings, {
        "sender_mode": mode,
        "sender_name": settings.sender_name,
        "sender_email": settings.sender_email,
        "sender_verified": True,
    }
