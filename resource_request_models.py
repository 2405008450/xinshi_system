"""跨业务资源需求数据库模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint,
    SmallInteger, String, Text, UniqueConstraint, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class ResourceRequest(Base):
    __tablename__ = "resource_request"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="resource_request_pkey"),
        UniqueConstraint("request_no", name="uq_resource_request_no"),
        ForeignKeyConstraint(["annotation_project_id"], ["annotation_project.id"], ondelete="RESTRICT", name="fk_resource_request_annotation"),
        ForeignKeyConstraint(["recruitment_project_id"], ["recruitment_project.id"], ondelete="RESTRICT", name="fk_resource_request_recruitment"),
        ForeignKeyConstraint(["interpretation_project_id"], ["interpretation_project.id"], ondelete="RESTRICT", name="fk_resource_request_interpretation"),
        ForeignKeyConstraint(["translation_project_id"], ["translation_project.id"], ondelete="RESTRICT", name="fk_resource_request_translation"),
        ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="RESTRICT", name="fk_resource_request_client"),
        ForeignKeyConstraint(["sub_client_id"], ["sub_client.id"], ondelete="SET NULL", name="fk_resource_request_sub_client"),
        ForeignKeyConstraint(["requested_by"], ["app_user.id"], ondelete="SET NULL", name="fk_resource_request_requester"),
        ForeignKeyConstraint(["owner_id"], ["app_user.id"], ondelete="SET NULL", name="fk_resource_request_owner"),
        CheckConstraint("source_type IN ('annotation','recruitment','interpretation','translation','other')", name="ck_resource_request_source_type"),
        CheckConstraint("request_category IN ('annotation_trial','annotation_formal','recruitment','interpretation','translation','other')", name="ck_resource_request_category"),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_resource_request_progress"),
        CheckConstraint("priority IN ('high','medium','low')", name="ck_resource_request_priority"),
        CheckConstraint("request_status IN ('draft','submitted','in_progress','fulfilled','cancelled')", name="ck_resource_request_status"),
        CheckConstraint("completed_at IS NULL OR completed_at >= requested_at", name="ck_resource_request_completed_at"),
        CheckConstraint("(source_type='annotation' AND annotation_project_id IS NOT NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NULL) OR (source_type='recruitment' AND annotation_project_id IS NULL AND recruitment_project_id IS NOT NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NULL) OR (source_type='interpretation' AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NOT NULL AND translation_project_id IS NULL AND other_source_name IS NULL) OR (source_type='translation' AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NOT NULL AND other_source_name IS NULL) OR (source_type='other' AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NOT NULL)", name="ck_resource_request_source_xor"),
        CheckConstraint("(source_type='annotation' AND request_category IN ('annotation_trial','annotation_formal')) OR (source_type=request_category)", name="ck_resource_request_category_source"),
        Index("ix_resource_request_status_priority", "request_status", "priority", text("requested_at DESC")),
        Index("ix_resource_request_source", "source_type", text("requested_at DESC")),
        Index("ix_resource_request_client", "client_id"),
        Index("ix_resource_request_owner_status", "owner_id", "request_status"),
        Index("ix_resource_request_annotation", "annotation_project_id", postgresql_where=text("annotation_project_id IS NOT NULL")),
        Index("ix_resource_request_recruitment", "recruitment_project_id", postgresql_where=text("recruitment_project_id IS NOT NULL")),
        Index("ix_resource_request_interpretation", "interpretation_project_id", postgresql_where=text("interpretation_project_id IS NOT NULL")),
        Index("ix_resource_request_translation", "translation_project_id", postgresql_where=text("translation_project_id IS NOT NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    request_no: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    request_category: Mapped[str] = mapped_column(String(30), nullable=False)
    annotation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    recruitment_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    interpretation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    other_source_name: Mapped[Optional[str]] = mapped_column(String(500))
    source_project_types_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    source_order_no_snapshot: Mapped[Optional[str]] = mapped_column(String(80))
    source_project_name_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    source_status_snapshot: Mapped[Optional[str]] = mapped_column(String(50))
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    client_code_snapshot: Mapped[Optional[str]] = mapped_column(String(60))
    client_short_name_snapshot: Mapped[Optional[str]] = mapped_column(String(100))
    request_detail: Mapped[str] = mapped_column(Text, nullable=False)
    progress_percent: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    priority: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'medium'"))
    request_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'submitted'"))
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    items = relationship("ResourceRequestItem", back_populates="request", cascade="all, delete-orphan", order_by="ResourceRequestItem.sequence_no")
    progress_logs = relationship("ResourceRequestProgressLog", back_populates="request", cascade="all, delete-orphan", order_by="ResourceRequestProgressLog.changed_at")


class ResourceRequestItem(Base):
    __tablename__ = "resource_request_item"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="resource_request_item_pkey"),
        ForeignKeyConstraint(["request_id"], ["resource_request.id"], ondelete="CASCADE", name="fk_resource_request_item_request"),
        ForeignKeyConstraint(["source_language_id"], ["interpretation_language.id"], ondelete="RESTRICT", name="fk_resource_request_item_source_language"),
        ForeignKeyConstraint(["target_language_id"], ["interpretation_language.id"], ondelete="RESTRICT", name="fk_resource_request_item_target_language"),
        UniqueConstraint("request_id", "sequence_no", name="uq_resource_request_item_sequence"),
        CheckConstraint("sequence_no > 0", name="ck_resource_request_item_sequence"),
        CheckConstraint("required_count IS NULL OR required_count > 0", name="ck_resource_request_item_count"),
        CheckConstraint("target_language_id IS NULL OR (source_language_id IS NOT NULL AND source_language_id <> target_language_id)", name="ck_resource_request_item_languages"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    target_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    required_count: Mapped[Optional[int]] = mapped_column(Integer)
    requirement_detail: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    request = relationship("ResourceRequest", back_populates="items")


class ResourceRequestProgressLog(Base):
    __tablename__ = "resource_request_progress_log"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="resource_request_progress_log_pkey"),
        ForeignKeyConstraint(["request_id"], ["resource_request.id"], ondelete="CASCADE", name="fk_resource_request_progress_request"),
        ForeignKeyConstraint(["changed_by"], ["app_user.id"], ondelete="SET NULL", name="fk_resource_request_progress_user"),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_resource_request_progress_log_percent"),
        Index("ix_resource_request_progress_timeline", "request_id", text("changed_at DESC")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    progress_percent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    progress_note: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    changed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    request = relationship("ResourceRequest", back_populates="progress_logs")
