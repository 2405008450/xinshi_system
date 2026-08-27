"""标注运营第三阶段数据库模型。"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, Integer,
    Numeric, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


STATUS_VALUES_SQL = (
    "'initial_consultation','consultation_no_result','resource_sourcing',"
    "'resource_sourcing_cancelled','trial_preparation','trial_in_progress',"
    "'trial_passed','trial_failed','trial_partially_passed','project_in_progress',"
    "'sent_to_client','client_feedback','cancelled','partially_cancelled'"
)


class AnnotationProjectStatusHistory(Base):
    __tablename__ = "annotation_project_status_history"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_status_history_pkey"),
        ForeignKeyConstraint(["project_id"], ["annotation_project.id"], ondelete="CASCADE", name="fk_annotation_status_history_project"),
        ForeignKeyConstraint(["changed_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_status_history_user"),
        CheckConstraint(f"from_status IS NULL OR from_status IN ({STATUS_VALUES_SQL})", name="ck_annotation_status_history_from"),
        CheckConstraint(f"to_status IN ({STATUS_VALUES_SQL})", name="ck_annotation_status_history_to"),
        Index("ix_annotation_status_history_timeline", "project_id", text("effective_on DESC"), text("changed_at DESC")),
        Index("ix_annotation_status_history_status_date", "to_status", "effective_on"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    changed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    change_note: Mapped[Optional[str]] = mapped_column(Text)


class AnnotationPlatform(Base):
    __tablename__ = "annotation_platform"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_platform_pkey"),
        ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="RESTRICT", name="fk_annotation_platform_client"),
        ForeignKeyConstraint(["sub_client_id"], ["sub_client.id"], ondelete="SET NULL", name="fk_annotation_platform_sub_client"),
        ForeignKeyConstraint(["origin_project_id"], ["annotation_project.id"], ondelete="SET NULL", name="fk_annotation_platform_origin_project"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_platform_creator"),
        UniqueConstraint("client_id", "sequence_no", name="uq_annotation_platform_client_sequence"),
        CheckConstraint("sequence_no > 0", name="ck_annotation_platform_sequence"),
        Index("uq_annotation_platform_client_url", "client_id", "platform_url_normalized", unique=True, postgresql_nulls_not_distinct=True),
        Index("ix_annotation_platform_client_sequence", "client_id", "sequence_no"),
        Index("ix_annotation_platform_normalized_url", "platform_url_normalized"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    origin_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    platform_name: Mapped[Optional[str]] = mapped_column(String(150))
    platform_url: Mapped[str] = mapped_column(Text, nullable=False)
    platform_url_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    login_notes: Mapped[Optional[str]] = mapped_column(Text)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    accounts = relationship("AnnotationPlatformAccount", back_populates="platform", cascade="all, delete-orphan")


class AnnotationPlatformAccount(Base):
    __tablename__ = "annotation_platform_account"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_platform_account_pkey"),
        ForeignKeyConstraint(["platform_id"], ["annotation_platform.id"], ondelete="CASCADE", name="fk_annotation_account_platform"),
        ForeignKeyConstraint(["parent_account_id"], ["annotation_platform_account.id"], ondelete="SET NULL", name="fk_annotation_account_parent"),
        ForeignKeyConstraint(["owner_id"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_account_owner"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_account_creator"),
        UniqueConstraint("platform_id", "login_account_normalized", name="uq_annotation_account_login_normalized"),
        UniqueConstraint("platform_id", "sequence_no", name="uq_annotation_account_sequence"),
        CheckConstraint("parent_account_id IS NULL OR parent_account_id <> id", name="ck_annotation_account_parent"),
        CheckConstraint("sequence_no > 0", name="ck_annotation_account_sequence"),
        CheckConstraint("account_status IN ('available','assigned','suspended','banned','retired')", name="ck_annotation_account_status"),
        CheckConstraint("registration_status IN ('unregistered','registering','registered','registration_failed','disabled','not_required')", name="ck_annotation_account_registration_status"),
        CheckConstraint("account_source IN ('client_provided','self_registered','annotator_owned')", name="ck_annotation_account_source"),
        CheckConstraint("registration_status <> 'registered' OR (login_account IS NOT NULL AND password IS NOT NULL)", name="ck_annotation_account_registered_credential"),
        Index("ix_annotation_account_platform_status", "platform_id", "account_status"),
        Index("ix_annotation_account_registration_status", "registration_status"),
        Index("ix_annotation_account_owner", "owner_id"),
        Index("ix_annotation_account_expires_on", "expires_on", postgresql_where=text("expires_on IS NOT NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    platform_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    parent_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    nickname: Mapped[Optional[str]] = mapped_column(String(255))
    login_account: Mapped[Optional[str]] = mapped_column(Text)
    login_account_normalized: Mapped[Optional[str]] = mapped_column(Text)
    password: Mapped[Optional[str]] = mapped_column(Text)
    account_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'available'"))
    registration_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'unregistered'"))
    account_source: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'client_provided'"))
    expires_on: Mapped[Optional[datetime.date]] = mapped_column(Date)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    password_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    platform = relationship("AnnotationPlatform", back_populates="accounts")
    owner = relationship("AppUser", foreign_keys=[owner_id])
    parent_account = relationship("AnnotationPlatformAccount", remote_side=[id], back_populates="backup_accounts")
    backup_accounts = relationship("AnnotationPlatformAccount", back_populates="parent_account")
    assignments = relationship("AnnotationAccountAssignment", back_populates="account", cascade="all, delete-orphan")
    password_history = relationship("AnnotationAccountPasswordHistory", back_populates="account", cascade="all, delete-orphan")
    access_logs = relationship("AnnotationCredentialAccessLog", back_populates="account", cascade="all, delete-orphan")


class AnnotationAccountAssignment(Base):
    __tablename__ = "annotation_account_assignment"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_account_assignment_pkey"),
        ForeignKeyConstraint(["account_id"], ["annotation_platform_account.id"], ondelete="CASCADE", name="fk_annotation_assignment_account"),
        ForeignKeyConstraint(["person_id"], ["resource_person.id"], ondelete="RESTRICT", name="fk_annotation_assignment_person"),
        ForeignKeyConstraint(["project_id"], ["annotation_project.id"], ondelete="SET NULL", name="fk_annotation_assignment_project"),
        ForeignKeyConstraint(["assigned_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_assignment_user"),
        CheckConstraint("released_on IS NULL OR released_on >= assigned_on", name="ck_annotation_assignment_dates"),
        CheckConstraint("release_reason IS NULL OR release_reason IN ('project_completed','person_left','account_banned','reassigned','other')", name="ck_annotation_assignment_release_reason"),
        Index("uq_annotation_assignment_active", "account_id", unique=True, postgresql_where=text("released_on IS NULL")),
        Index("ix_annotation_assignment_person_active", "person_id", "released_on"),
        Index("ix_annotation_assignment_project", "project_id"),
        Index("ix_annotation_assignment_timeline", "account_id", text("assigned_on DESC")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # 人员可空：账号可以先绑定项目和适用语言，之后再分配标注员。
    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    assigned_on: Mapped[datetime.date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    released_on: Mapped[Optional[datetime.date]] = mapped_column(Date)
    release_reason: Mapped[Optional[str]] = mapped_column(String(30))
    assignment_note: Mapped[Optional[str]] = mapped_column(Text)
    # 项目账号表的扩展列属于本次项目分配，账号释放后仍随履历保留。
    custom_values: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    account = relationship("AnnotationPlatformAccount", back_populates="assignments")
    person = relationship("ResourcePerson")
    project = relationship("AnnotationProject")
    languages = relationship("AnnotationAccountAssignmentLanguage", cascade="all, delete-orphan")


class AnnotationAccountAssignmentLanguage(Base):
    __tablename__ = "annotation_account_assignment_language"
    __table_args__ = (
        PrimaryKeyConstraint("assignment_id", "language_item_id", name="annotation_account_assignment_language_pkey"),
        ForeignKeyConstraint(["assignment_id"], ["annotation_account_assignment.id"], ondelete="CASCADE", name="fk_annotation_assignment_language_assignment"),
        ForeignKeyConstraint(["language_item_id"], ["annotation_project_language_item.id"], ondelete="RESTRICT", name="fk_annotation_assignment_language_item"),
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    language_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    language_item = relationship("AnnotationProjectLanguageItem")


class AnnotationAccountPasswordHistory(Base):
    __tablename__ = "annotation_account_password_history"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_account_password_history_pkey"),
        ForeignKeyConstraint(["account_id"], ["annotation_platform_account.id"], ondelete="CASCADE", name="fk_annotation_password_history_account"),
        ForeignKeyConstraint(["changed_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_password_history_user"),
        Index("ix_annotation_password_history_timeline", "account_id", text("replaced_at DESC")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    replaced_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    account = relationship("AnnotationPlatformAccount", back_populates="password_history")


class AnnotationCredentialAccessLog(Base):
    __tablename__ = "annotation_credential_access_log"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_credential_access_log_pkey"),
        ForeignKeyConstraint(["account_id"], ["annotation_platform_account.id"], ondelete="CASCADE", name="fk_annotation_access_log_account"),
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_access_log_user"),
        Index("ix_annotation_access_log_account_timeline", "account_id", text("accessed_at DESC")),
        Index("ix_annotation_access_log_user_timeline", "user_id", text("accessed_at DESC")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    accessed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    access_reason: Mapped[Optional[str]] = mapped_column(Text)
    client_ip: Mapped[Optional[str]] = mapped_column(String(64))
    account = relationship("AnnotationPlatformAccount", back_populates="access_logs")


class AnnotationTrialRecord(Base):
    __tablename__ = "annotation_trial_record"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_trial_record_pkey"),
        ForeignKeyConstraint(["project_id"], ["annotation_project.id"], ondelete="CASCADE", name="fk_annotation_trial_project"),
        ForeignKeyConstraint(["person_id"], ["resource_person.id"], ondelete="RESTRICT", name="fk_annotation_trial_person"),
        ForeignKeyConstraint(["platform_account_id"], ["annotation_platform_account.id"], ondelete="SET NULL", name="fk_annotation_trial_account"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_trial_creator"),
        UniqueConstraint("project_id", "person_id", "round_no", name="uq_annotation_trial_person_round"),
        UniqueConstraint("project_id", "round_no", "sequence_no", name="uq_annotation_trial_sequence"),
        CheckConstraint("round_no > 0 AND sequence_no > 0", name="ck_annotation_trial_sequence"),
        CheckConstraint("trial_status IN ('pending','in_progress','submitted','reviewing','completed','cancelled')", name="ck_annotation_trial_status"),
        CheckConstraint("trial_result IS NULL OR trial_result IN ('passed','failed','partially_passed','withdrawn')", name="ck_annotation_trial_result"),
        Index("ix_annotation_trial_project_status", "project_id", "trial_status"),
        Index("ix_annotation_trial_person", "person_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    platform_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    willingness_text: Mapped[Optional[str]] = mapped_column(Text)
    trial_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'pending'"))
    trial_result: Mapped[Optional[str]] = mapped_column(String(30))
    result_note: Mapped[Optional[str]] = mapped_column(Text)
    custom_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class AnnotationAssigneeRate(Base):
    __tablename__ = "annotation_assignee_rate"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_assignee_rate_pkey"),
        ForeignKeyConstraint(["assignee_id"], ["annotation_project_assignee.id"], ondelete="CASCADE", name="fk_annotation_rate_assignee"),
        UniqueConstraint("assignee_id", name="uq_annotation_rate_assignee"),
        CheckConstraint("amount > 0", name="ck_annotation_rate_amount"),
        CheckConstraint("unit IN ('item','second','minute','hour')", name="ck_annotation_rate_unit"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    assignee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    assignee = relationship("AnnotationProjectAssignee", back_populates="rate")


class AnnotationCustomFieldDefinition(Base):
    __tablename__ = "annotation_custom_field_definition"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_custom_field_definition_pkey"),
        ForeignKeyConstraint(["project_id"], ["annotation_project.id"], ondelete="CASCADE", name="fk_annotation_custom_field_project"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_annotation_custom_field_creator"),
        CheckConstraint("table_code IN ('project','account','trial','assignment','account_assignment')", name="ck_annotation_custom_field_table"),
        CheckConstraint("data_type IN ('text','number','date','datetime','boolean','single_select','multi_select','url')", name="ck_annotation_custom_field_type"),
        CheckConstraint("sequence_no > 0", name="ck_annotation_custom_field_sequence"),
        CheckConstraint(
            "(table_code IN ('project','account') AND project_id IS NULL) OR "
            "(table_code IN ('trial','assignment','account_assignment') AND project_id IS NOT NULL)",
            name="ck_annotation_custom_field_scope",
        ),
        Index("uq_annotation_custom_field_scope_key", "project_id", "table_code", "field_key", unique=True, postgresql_nulls_not_distinct=True),
        Index("ix_annotation_custom_field_sequence", "project_id", "table_code", "sequence_no"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    table_code: Mapped[str] = mapped_column(String(30), nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    field_label: Mapped[str] = mapped_column(String(150), nullable=False)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
