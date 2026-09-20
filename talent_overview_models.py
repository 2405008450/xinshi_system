"""人才概览可编辑快照模型。"""

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, SmallInteger, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class TalentOverviewSnapshot(Base):
    """全系统共享的一份人才概览二维表快照。"""

    __tablename__ = "talent_overview_snapshot"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="talent_overview_snapshot_pkey"),
        CheckConstraint("id = 1", name="ck_talent_overview_snapshot_singleton"),
        CheckConstraint("revision >= 1", name="ck_talent_overview_snapshot_revision"),
        ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_talent_overview_snapshot_updated_by",
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
