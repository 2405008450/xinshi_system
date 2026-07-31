"""稿件安排模块的数据模型。"""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class ManuscriptDispatch(Base):
    """一次针对母订单或子订单的派稿批次。"""

    __tablename__ = "manuscript_dispatch"
    __table_args__ = (
        ForeignKeyConstraint(
            ["translation_project_id"],
            ["translation_project.id"],
            ondelete="CASCADE",
            name="fk_manuscript_dispatch_project",
        ),
        ForeignKeyConstraint(
            ["sub_order_id"],
            ["translation_sub_order.id"],
            ondelete="CASCADE",
            name="fk_manuscript_dispatch_sub_order",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            ondelete="SET NULL",
            name="fk_manuscript_dispatch_creator",
        ),
        PrimaryKeyConstraint("id", name="manuscript_dispatch_pkey"),
        CheckConstraint(
            "(entity_type = 'project' AND sub_order_id IS NULL) OR "
            "(entity_type = 'suborder' AND sub_order_id IS NOT NULL)",
            name="ck_manuscript_dispatch_entity",
        ),
        CheckConstraint(
            "status IN ('draft', 'ready', 'partially_sent', 'sent', 'cancelled')",
            name="ck_manuscript_dispatch_status",
        ),
        Index(
            "ix_manuscript_dispatch_project_status",
            "translation_project_id",
            "status",
        ),
        Index(
            "ix_manuscript_dispatch_order_created",
            "order_no_snapshot",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sub_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    order_no_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    project_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    cancelled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    previous_order_status: Mapped[Optional[str]] = mapped_column(String(50))

    arrangements: Mapped[list["ManuscriptArrangement"]] = relationship(
        "ManuscriptArrangement",
        back_populates="dispatch",
        cascade="all, delete-orphan",
        order_by="ManuscriptArrangement.created_at",
    )


class ManuscriptArrangement(Base):
    """派稿批次中的单个译员分配明细及独立邮件投递记录。"""

    __tablename__ = "manuscript_arrangement"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dispatch_id"],
            ["manuscript_dispatch.id"],
            ondelete="CASCADE",
            name="fk_manuscript_arrangement_dispatch",
        ),
        ForeignKeyConstraint(
            ["translation_project_id"],
            ["translation_project.id"],
            ondelete="CASCADE",
            name="fk_manuscript_arrangement_project",
        ),
        ForeignKeyConstraint(
            ["sub_order_id"],
            ["translation_sub_order.id"],
            ondelete="CASCADE",
            name="fk_manuscript_arrangement_sub_order",
        ),
        ForeignKeyConstraint(
            ["translator_id"],
            ["translator.id"],
            ondelete="RESTRICT",
            name="fk_manuscript_arrangement_translator",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            ondelete="SET NULL",
            name="fk_manuscript_arrangement_creator",
        ),
        PrimaryKeyConstraint("id", name="manuscript_arrangement_pkey"),
        UniqueConstraint(
            "dispatch_id",
            "translator_id",
            name="uq_manuscript_arrangement_dispatch_translator",
        ),
        CheckConstraint(
            "entity_type IN ('project', 'suborder')",
            name="ck_manuscript_arrangement_entity_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'ready', 'sent', 'failed', 'cancelled')",
            name="ck_manuscript_arrangement_status",
        ),
        CheckConstraint(
            "planned_word_count IS NULL OR planned_word_count >= 0",
            name="ck_manuscript_arrangement_planned_words",
        ),
        CheckConstraint(
            "actual_word_count IS NULL OR actual_word_count >= 0",
            name="ck_manuscript_arrangement_actual_words",
        ),
        Index(
            "ix_manuscript_arrangement_project_status",
            "translation_project_id",
            "status",
        ),
        Index(
            "ix_manuscript_arrangement_translator_status",
            "translator_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    dispatch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sub_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translator_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    order_no_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    project_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    translator_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    cooperation_type_snapshot: Mapped[Optional[str]] = mapped_column(String(50))
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255))

    planned_word_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    actual_word_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    word_count_type: Mapped[Optional[str]] = mapped_column(String(50))
    translation_scope: Mapped[Optional[str]] = mapped_column(Text)
    settlement_method: Mapped[Optional[str]] = mapped_column(String(30))
    custom_settlement_method: Mapped[Optional[str]] = mapped_column(String(100))
    translator_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    translator_total_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))

    # 兼容旧接口；新批次的最终交稿时间由 final 类型节点同步到这里。
    planned_delivery_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    manuscript_source_path: Mapped[Optional[str]] = mapped_column(Text)
    email_subject: Mapped[Optional[str]] = mapped_column(String(500))
    email_body: Mapped[Optional[str]] = mapped_column(Text)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    send_attempted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    delivery_recipient: Mapped[Optional[str]] = mapped_column(String(255))
    delivery_mode: Mapped[Optional[str]] = mapped_column(String(20))
    smtp_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    send_error: Mapped[Optional[str]] = mapped_column(Text)

    dispatch: Mapped[Optional[ManuscriptDispatch]] = relationship(
        "ManuscriptDispatch",
        back_populates="arrangements",
    )
    milestones: Mapped[list["ManuscriptDeliveryMilestone"]] = relationship(
        "ManuscriptDeliveryMilestone",
        back_populates="arrangement",
        cascade="all, delete-orphan",
        order_by="ManuscriptDeliveryMilestone.sequence_no",
    )


class ManuscriptDeliveryMilestone(Base):
    """单个译员的阶段或全稿预定交付节点。"""

    __tablename__ = "manuscript_delivery_milestone"
    __table_args__ = (
        ForeignKeyConstraint(
            ["arrangement_id"],
            ["manuscript_arrangement.id"],
            ondelete="CASCADE",
            name="fk_manuscript_milestone_arrangement",
        ),
        PrimaryKeyConstraint("id", name="manuscript_delivery_milestone_pkey"),
        UniqueConstraint(
            "arrangement_id",
            "sequence_no",
            name="uq_manuscript_milestone_sequence",
        ),
        CheckConstraint(
            "milestone_type IN ('phase', 'final')",
            name="ck_manuscript_milestone_type",
        ),
        CheckConstraint(
            "sequence_no >= 1",
            name="ck_manuscript_milestone_sequence",
        ),
        Index(
            "ix_manuscript_milestone_planned_at",
            "planned_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    arrangement_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    milestone_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    arrangement: Mapped[ManuscriptArrangement] = relationship(
        "ManuscriptArrangement",
        back_populates="milestones",
    )
