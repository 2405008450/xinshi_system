"""人才概览企微大群、人数登记与不可覆盖的操作历史。"""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class ManagementFields:
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    operator_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TalentOverviewLanguageManagement(ManagementFields, Base):
    __tablename__ = "talent_overview_language_management"
    overview_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_overview_management_revision"),)


class TalentOverviewWecomGroup(ManagementFields, Base):
    __tablename__ = "talent_overview_wecom_group"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    overview_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_built: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    built_date: Mapped[date | None] = mapped_column(Date)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_overview_wecom_group_revision"),
        CheckConstraint("is_built OR built_date IS NULL", name="ck_overview_wecom_group_built_date"),
        Index("ix_overview_wecom_group_language", "overview_key", "archived"),
    )


class TalentOverviewWecomCount(Base):
    __tablename__ = "talent_overview_wecom_count"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("talent_overview_wecom_group.id"), nullable=False)
    statistics_date: Mapped[date] = mapped_column(Date, nullable=False)
    people_count: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    voided_by_name: Mapped[str | None] = mapped_column(String(255))
    void_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("people_count >= 0", name="ck_overview_wecom_count_nonnegative"),
        Index("ix_overview_wecom_count_latest", "group_id", "statistics_date", "id"),
    )


class TalentOverviewManagementAudit(Base):
    __tablename__ = "talent_overview_management_audit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    overview_key: Mapped[str] = mapped_column(String(80), nullable=False)
    group_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("talent_overview_wecom_group.id"))
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    before: Mapped[dict] = mapped_column(JSONB, nullable=False)
    after: Mapped[dict] = mapped_column(JSONB, nullable=False)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("ix_overview_management_audit_language", "overview_key", "id"),
        Index("ix_overview_management_audit_group", "group_id", "id"),
    )
