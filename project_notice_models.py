"""笔译、口译和招聘项目的独立须知栏目与附件。"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import AppUser, Base


class ProjectNoticeSection(Base):
    __tablename__ = "project_notice_section"
    __table_args__ = (
        CheckConstraint("module IN ('translation', 'interpretation', 'recruitment')", name="ck_project_notice_module"),
        UniqueConstraint("module", "id", name="uq_project_notice_module_id"),
        ForeignKeyConstraint(["module", "parent_id"], ["project_notice_section.module", "project_notice_section.id"], ondelete="RESTRICT"),
        Index("ix_project_notice_module_parent_order", "module", "parent_id", "sort_order"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(20), nullable=False)
    section_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    has_content: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    structure_updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    editor: Mapped[AppUser | None] = relationship(AppUser, foreign_keys=[updated_by])


class ProjectNoticeAttachment(Base):
    __tablename__ = "project_notice_attachment"
    __table_args__ = (CheckConstraint("file_size > 0 AND file_size <= 20971520", name="ck_project_notice_attachment_size"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("project_notice_section.id"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploader: Mapped[AppUser | None] = relationship(AppUser, foreign_keys=[uploaded_by])
