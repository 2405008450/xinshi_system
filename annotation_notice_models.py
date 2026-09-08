"""标注须知数据库模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import AppUser, Base


class AnnotationNoticeSection(Base):
    """标注业务知识库中的两级自定义栏目。"""

    __tablename__ = "annotation_notice_section"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_notice_section_pkey"),
        ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_annotation_notice_section_updated_by",
        ),
        ForeignKeyConstraint(
            ["parent_id"], ["annotation_notice_section.id"], ondelete="RESTRICT",
            name="fk_annotation_notice_section_parent_id",
        ),
        Index("ix_annotation_notice_section_parent_order", "parent_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    section_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    has_content: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    content_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    structure_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    editor: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[updated_by])
