"""个人工作日报邮箱配置、收件策略与投递审计模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from business_mail_models import MailRecipientGroup
from models import AppUser, Base


class UserMailProfile(Base):
    """用户可维护的邮件展示资料；与 SMTP 敏感凭据分开保存。"""

    __tablename__ = "user_mail_profile"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="user_mail_profile_pkey"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE", name="fk_user_mail_profile_user"),
        ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL", name="fk_user_mail_profile_updater"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    recipient_display_name: Mapped[Optional[str]] = mapped_column(String(255))
    signature_html: Mapped[Optional[str]] = mapped_column(Text)
    signature_text: Mapped[Optional[str]] = mapped_column(Text)
    signature_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class UserMailAccount(Base):
    __tablename__ = "user_mail_account"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="user_mail_account_pkey"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE", name="fk_user_mail_account_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    authorization_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_key_version: Mapped[str] = mapped_column(String(50), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped[AppUser] = relationship(AppUser)


class DailyReportMailPolicy(Base):
    __tablename__ = "daily_report_mail_policy"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="daily_report_mail_policy_pkey"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE", name="fk_daily_report_mail_policy_user"),
        ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL", name="fk_daily_report_mail_policy_updater"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped[AppUser] = relationship(AppUser, foreign_keys=[user_id])
    groups: Mapped[list["DailyReportMailPolicyGroup"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )


class DailyReportMailPolicyGroup(Base):
    __tablename__ = "daily_report_mail_policy_group"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="daily_report_mail_policy_group_pkey"),
        ForeignKeyConstraint(["user_id"], ["daily_report_mail_policy.user_id"], ondelete="CASCADE", name="fk_daily_report_mail_policy_group_policy"),
        ForeignKeyConstraint(["group_id"], ["mail_recipient_group.id"], ondelete="RESTRICT", name="fk_daily_report_mail_policy_group_group"),
        UniqueConstraint("user_id", "group_id", "recipient_type", name="uq_daily_report_mail_policy_group"),
        CheckConstraint("recipient_type IN ('to','cc')", name="ck_daily_report_mail_policy_group_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(10), nullable=False)

    policy: Mapped[DailyReportMailPolicy] = relationship(back_populates="groups")
    group: Mapped[MailRecipientGroup] = relationship(MailRecipientGroup)


class DailyReportMailDelivery(Base):
    __tablename__ = "daily_report_mail_delivery"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="daily_report_mail_delivery_pkey"),
        ForeignKeyConstraint(["report_id"], ["daily_report.id"], ondelete="RESTRICT", name="fk_daily_report_mail_delivery_report"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL", name="fk_daily_report_mail_delivery_user"),
        UniqueConstraint("idempotency_key", name="uq_daily_report_mail_delivery_idempotency"),
        CheckConstraint("status IN ('pending','sending','sent','failed')", name="ck_daily_report_mail_delivery_status"),
        Index("ix_daily_report_mail_delivery_report_created", "report_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sender_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(1000), nullable=False)
    body_rows: Mapped[list] = mapped_column(JSONB, nullable=False)
    supplemental_note: Mapped[Optional[str]] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    smtp_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(20))
    send_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    send_attempted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    recipients: Mapped[list["DailyReportMailRecipient"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["DailyReportMailAttempt"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan"
    )


class DailyReportMailRecipient(Base):
    __tablename__ = "daily_report_mail_recipient"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="daily_report_mail_recipient_pkey"),
        ForeignKeyConstraint(["delivery_id"], ["daily_report_mail_delivery.id"], ondelete="CASCADE", name="fk_daily_report_mail_recipient_delivery"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL", name="fk_daily_report_mail_recipient_user"),
        UniqueConstraint("delivery_id", "email_snapshot", name="uq_daily_report_mail_recipient_email"),
        CheckConstraint("recipient_type IN ('to','cc')", name="ck_daily_report_mail_recipient_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    delivery_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    recipient_type: Mapped[str] = mapped_column(String(10), nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)

    delivery: Mapped[DailyReportMailDelivery] = relationship(back_populates="recipients")


class DailyReportMailAttempt(Base):
    __tablename__ = "daily_report_mail_attempt"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="daily_report_mail_attempt_pkey"),
        ForeignKeyConstraint(["delivery_id"], ["daily_report_mail_delivery.id"], ondelete="CASCADE", name="fk_daily_report_mail_attempt_delivery"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    delivery_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    attempted_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(20))
    actual_recipients: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    error: Mapped[Optional[str]] = mapped_column(Text)

    delivery: Mapped[DailyReportMailDelivery] = relationship(back_populates="attempts")
