"""项目新增、删除操作的持久审计模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, PrimaryKeyConstraint, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


PROJECT_AUDIT_TYPES = ("translation", "interpretation", "annotation", "recruitment")
PROJECT_AUDIT_OPERATIONS = ("create", "delete")


class ProjectOperationAudit(Base):
    __tablename__ = "project_operation_audit"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="project_operation_audit_pkey"),
        ForeignKeyConstraint(
            ["actor_user_id"], ["app_user.id"], ondelete="SET NULL",
            name="fk_project_operation_audit_actor",
        ),
        CheckConstraint(
            "project_type IN ('translation','interpretation','annotation','recruitment')",
            name="ck_project_operation_audit_type",
        ),
        CheckConstraint(
            "operation_type IN ('create','delete')",
            name="ck_project_operation_audit_operation",
        ),
        Index("ix_project_operation_audit_order_time", "order_no", "occurred_at"),
        Index("ix_project_operation_audit_type_time", "project_type", "occurred_at"),
        Index("ix_project_operation_audit_actor_time", "actor_user_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_type: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    order_no: Mapped[str] = mapped_column(String(80), nullable=False)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    operation_source: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    actor_username_snapshot: Mapped[Optional[str]] = mapped_column(String(100))
    actor_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255))
    project_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
