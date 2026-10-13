"""团队资源独立档案及持久审计，不参与个人资源统计。"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class TeamResource(Base):
    __tablename__ = "resource_team"
    __table_args__ = (
        CheckConstraint("team_type IN ('small_team','medium_large_company','small_medium_company')", name="ck_resource_team_type"),
        CheckConstraint("jsonb_typeof(resource_types) = 'array' AND jsonb_array_length(resource_types) BETWEEN 1 AND 5 AND resource_types <@ '[\"annotation\",\"interpretation\",\"written_translation\",\"full_time\",\"other\"]'::jsonb", name="ck_resource_team_resources"),
        CheckConstraint("NOT resource_types ? 'other' OR length(btrim(other_resource_description)) > 0", name="ck_resource_team_other"),
        CheckConstraint("revision > 0", name="ck_resource_team_revision"),
        Index("ix_resource_team_updated", "updated_at", "id"),
        Index("ix_resource_team_short_name", "short_name"),
        Index("ix_resource_team_full_name", "full_name"),
        Index("ix_resource_team_resources", "resource_types", postgresql_using="gin"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    team_type: Mapped[str] = mapped_column(String(40), nullable=False)
    introduction: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resource_types: Mapped[list] = mapped_column(JSONB, nullable=False)
    other_resource_description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    resource_situation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contacts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    contact_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
    contact_date: Mapped[date | None] = mapped_column(Date, index=True)
    follow_up_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
    created_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TeamResourceAudit(Base):
    __tablename__ = "resource_team_audit"
    __table_args__ = (Index("ix_resource_team_audit_entity_time", "team_id", "occurred_at"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # 不关联团队外键，删除档案后仍保留审计快照。
    team_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
