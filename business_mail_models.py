"""内部项目邮件组、发送快照与投递审计模型。"""

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
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import AppUser, Base


PROJECT_MAIL_TYPES = ("translation", "interpretation", "annotation", "recruitment")


class MailRecipientGroup(Base):
    __tablename__ = "mail_recipient_group"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="mail_recipient_group_pkey"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_mail_recipient_group_creator"),
        UniqueConstraint("name", name="uq_mail_recipient_group_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    members: Mapped[list["MailRecipientGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class MailRecipientGroupMember(Base):
    __tablename__ = "mail_recipient_group_member"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="mail_recipient_group_member_pkey"),
        ForeignKeyConstraint(["group_id"], ["mail_recipient_group.id"], ondelete="CASCADE", name="fk_mail_group_member_group"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT", name="fk_mail_group_member_user"),
        UniqueConstraint("group_id", "user_id", name="uq_mail_group_member_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    group: Mapped[MailRecipientGroup] = relationship(back_populates="members")
    user: Mapped[AppUser] = relationship(AppUser)


class ProjectMailPolicy(Base):
    __tablename__ = "project_mail_policy"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="project_mail_policy_pkey"),
        ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL", name="fk_project_mail_policy_updater"),
        UniqueConstraint("project_type", name="uq_project_mail_policy_type"),
        CheckConstraint(
            "project_type IN ('translation','interpretation','annotation','recruitment')",
            name="ck_project_mail_policy_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_type: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    groups: Mapped[list["ProjectMailPolicyGroup"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )


class ProjectMailPolicyGroup(Base):
    __tablename__ = "project_mail_policy_group"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="project_mail_policy_group_pkey"),
        ForeignKeyConstraint(["policy_id"], ["project_mail_policy.id"], ondelete="CASCADE", name="fk_project_mail_policy_group_policy"),
        ForeignKeyConstraint(["group_id"], ["mail_recipient_group.id"], ondelete="RESTRICT", name="fk_project_mail_policy_group_group"),
        UniqueConstraint("policy_id", "group_id", "recipient_type", name="uq_project_mail_policy_group"),
        CheckConstraint("recipient_type IN ('to','cc')", name="ck_project_mail_policy_recipient_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    policy_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(10), nullable=False)
    policy: Mapped[ProjectMailPolicy] = relationship(back_populates="groups")
    group: Mapped[MailRecipientGroup] = relationship(MailRecipientGroup)


class BusinessMail(Base):
    __tablename__ = "business_mail"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="business_mail_pkey"),
        ForeignKeyConstraint(["consultation_id"], ["consultation.id"], ondelete="SET NULL", name="fk_business_mail_consultation"),
        ForeignKeyConstraint(["translation_project_id"], ["translation_project.id"], ondelete="SET NULL", name="fk_business_mail_translation"),
        ForeignKeyConstraint(["interpretation_project_id"], ["interpretation_project.id"], ondelete="SET NULL", name="fk_business_mail_interpretation"),
        ForeignKeyConstraint(["annotation_project_id"], ["annotation_project.id"], ondelete="SET NULL", name="fk_business_mail_annotation"),
        ForeignKeyConstraint(["recruitment_project_id"], ["recruitment_project.id"], ondelete="SET NULL", name="fk_business_mail_recruitment"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_business_mail_creator"),
        UniqueConstraint("idempotency_key", name="uq_business_mail_idempotency"),
        CheckConstraint("status IN ('pending','sending','sent','failed')", name="ck_business_mail_status"),
        CheckConstraint("project_type IN ('translation','interpretation','annotation','recruitment')", name="ck_business_mail_project_type"),
        Index("ix_business_mail_consultation_created", "consultation_id", "created_at"),
        Index("ix_business_mail_project_created", "project_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    project_type: Mapped[str] = mapped_column(String(30), nullable=False)
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    interpretation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    annotation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    recruitment_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    subject: Mapped[str] = mapped_column(String(1000), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    smtp_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(20))
    send_error: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    send_attempted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    recipients: Mapped[list["BusinessMailRecipient"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["BusinessMailAttempt"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )


class BusinessMailRecipient(Base):
    __tablename__ = "business_mail_recipient"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="business_mail_recipient_pkey"),
        ForeignKeyConstraint(["mail_id"], ["business_mail.id"], ondelete="CASCADE", name="fk_business_mail_recipient_mail"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL", name="fk_business_mail_recipient_user"),
        UniqueConstraint("mail_id", "email_snapshot", name="uq_business_mail_recipient_email"),
        CheckConstraint("recipient_type IN ('to','cc')", name="ck_business_mail_recipient_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    mail_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    recipient_type: Mapped[str] = mapped_column(String(10), nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    mail: Mapped[BusinessMail] = relationship(back_populates="recipients")


class BusinessMailAttempt(Base):
    __tablename__ = "business_mail_attempt"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="business_mail_attempt_pkey"),
        ForeignKeyConstraint(["mail_id"], ["business_mail.id"], ondelete="CASCADE", name="fk_business_mail_attempt_mail"),
        ForeignKeyConstraint(["sender_user_id"], ["app_user.id"], ondelete="SET NULL", name="fk_business_mail_attempt_sender"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    mail_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sender_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sender_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255))
    sender_email_snapshot: Mapped[Optional[str]] = mapped_column(String(255))
    attempted_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(20))
    actual_recipients: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    error: Mapped[Optional[str]] = mapped_column(Text)
    mail: Mapped[BusinessMail] = relationship(back_populates="attempts")
