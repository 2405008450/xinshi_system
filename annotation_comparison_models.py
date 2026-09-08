"""标注项目比较组数据库模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from annotation_models import AnnotationProject
from models import AppUser, Base


class AnnotationProjectComparisonGroup(Base):
    __tablename__ = "annotation_project_comparison_group"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_comparison_group_pkey"),
        ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_annotation_comparison_group_creator",
        ),
        Index("ix_annotation_comparison_group_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    creator: Mapped[Optional[AppUser]] = relationship(AppUser)
    members: Mapped[list["AnnotationProjectComparisonMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="AnnotationProjectComparisonMember.sequence_no",
    )

    @property
    def created_by_name(self) -> Optional[str]:
        if not self.creator:
            return None
        return self.creator.full_name or self.creator.username


class AnnotationProjectComparisonMember(Base):
    __tablename__ = "annotation_project_comparison_member"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_comparison_member_pkey"),
        ForeignKeyConstraint(
            ["group_id"], ["annotation_project_comparison_group.id"],
            ondelete="CASCADE", name="fk_annotation_comparison_member_group",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["annotation_project.id"],
            ondelete="CASCADE", name="fk_annotation_comparison_member_project",
        ),
        UniqueConstraint(
            "group_id", "project_id", name="uq_annotation_comparison_member_project"
        ),
        UniqueConstraint(
            "group_id", "sequence_no", name="uq_annotation_comparison_member_sequence"
        ),
        CheckConstraint(
            "sequence_no >= 1 AND sequence_no <= 10",
            name="ck_annotation_comparison_member_sequence",
        ),
        Index("ix_annotation_comparison_member_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)

    group: Mapped[AnnotationProjectComparisonGroup] = relationship(back_populates="members")
    project: Mapped[AnnotationProject] = relationship(AnnotationProject)
