"""标注项目负责人变更日志模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Index, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class AnnotationManagerChangeLog(Base):
    """保存负责人变更快照，不依赖业务项目或用户继续存在。"""

    __tablename__ = "annotation_manager_change_log"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_manager_change_log_pkey"),
        UniqueConstraint(
            "source_request_id", "project_id", "manager_role",
            name="uq_annotation_manager_change_request_project_role",
        ),
        Index("ix_annotation_manager_change_project_time", "project_id", "changed_at"),
        Index("ix_annotation_manager_change_role_time", "manager_role", "changed_at"),
        Index("ix_annotation_manager_change_actor_time", "actor_user_id", "changed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    source_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    order_no: Mapped[str] = mapped_column(String(80), nullable=False)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    manager_role: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    previous_manager_name: Mapped[Optional[str]] = mapped_column(String(255))
    new_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    new_manager_name: Mapped[Optional[str]] = mapped_column(String(255))
    change_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    actor_username_snapshot: Mapped[Optional[str]] = mapped_column(String(100))
    actor_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255))
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
