"""多维字数统计数据模型。"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKeyConstraint, Index, PrimaryKeyConstraint, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class WordCountMetric(Base):
    """项目、子订单或译员安排下的单个字数统计单元格。"""

    __tablename__ = "word_count_metric"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["translation_project.id"], ondelete="CASCADE", name="fk_word_count_metric_project"),
        ForeignKeyConstraint(["sub_order_id"], ["translation_sub_order.id"], ondelete="CASCADE", name="fk_word_count_metric_sub_order"),
        ForeignKeyConstraint(["arrangement_id"], ["manuscript_arrangement.id"], ondelete="CASCADE", name="fk_word_count_metric_arrangement"),
        ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL", name="fk_word_count_metric_updated_by"),
        PrimaryKeyConstraint("id", name="word_count_metric_pkey"),
        CheckConstraint(
            "num_nonnulls(project_id, sub_order_id, arrangement_id) = 1",
            name="ck_word_count_metric_single_owner",
        ),
        CheckConstraint(
            "metric_type IN ('words', 'characters_no_spaces', 'cjk_chars_korean_words', 'foreign_words')",
            name="ck_word_count_metric_type",
        ),
        CheckConstraint(
            "dimension IN ('company', 'customer', 'translator_estimate', 'planned', 'actual')",
            name="ck_word_count_metric_dimension",
        ),
        CheckConstraint("count_value >= 0", name="ck_word_count_metric_nonnegative"),
        CheckConstraint(
            "((arrangement_id IS NOT NULL AND dimension IN ('planned', 'actual')) OR "
            "(arrangement_id IS NULL AND dimension IN ('company', 'customer', 'translator_estimate')))",
            name="ck_word_count_metric_owner_dimension",
        ),
        Index(
            "uq_word_count_metric_project_dimension_type",
            "project_id",
            "dimension",
            "metric_type",
            unique=True,
            postgresql_where=text("project_id IS NOT NULL"),
        ),
        Index(
            "uq_word_count_metric_sub_order_dimension_type",
            "sub_order_id",
            "dimension",
            "metric_type",
            unique=True,
            postgresql_where=text("sub_order_id IS NOT NULL"),
        ),
        Index(
            "uq_word_count_metric_arrangement_dimension_type",
            "arrangement_id",
            "dimension",
            "metric_type",
            unique=True,
            postgresql_where=text("arrangement_id IS NOT NULL"),
        ),
        Index("ix_word_count_metric_sub_order_id", "sub_order_id"),
        Index("ix_word_count_metric_arrangement_id", "arrangement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    arrangement_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    count_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
