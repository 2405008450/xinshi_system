"""项目存续期间的订单号及改号占用记录；删除后转入独立删除历史。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


PROJECT_ORDER_NO_TYPES = ("translation", "interpretation", "annotation", "recruitment")


class ProjectOrderNoReservation(Base):
    """项目改号时保留旧编号；项目删除时归档占用记录并释放号码。"""

    __tablename__ = "project_order_no_reservation"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="project_order_no_reservation_pkey"),
        ForeignKeyConstraint(
            ["assigned_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_project_order_no_reservation_actor",
        ),
        CheckConstraint(
            "project_type IN ('translation','interpretation','annotation','recruitment')",
            name="ck_project_order_no_reservation_type",
        ),
        UniqueConstraint(
            "project_type", "order_no_key",
            name="uq_project_order_no_reservation_type_key",
        ),
        Index(
            "ix_project_order_no_reservation_project",
            "project_type", "project_id", "assigned_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_type: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    order_no: Mapped[str] = mapped_column(String(80), nullable=False)
    order_no_key: Mapped[str] = mapped_column(String(80), nullable=False)
    assignment_source: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    assigned_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
