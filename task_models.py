"""个人任务、每日工作记录与日报模型。"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class NonProjectTaskRecurrence(Base):
    __tablename__ = "non_project_task_recurrence"
    __table_args__ = (
        ForeignKeyConstraint(["assigner_id"], ["app_user.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["assignee_id"], ["app_user.id"], ondelete="RESTRICT"),
        PrimaryKeyConstraint("id"),
        CheckConstraint(
            "frequency IN ('daily', 'workday', 'weekly', 'monthly')",
            name="ck_non_project_recurrence_frequency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assigner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assignee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    weekdays: Mapped[Optional[list]] = mapped_column(JSONB)
    month_day: Mapped[Optional[int]] = mapped_column(Integer)
    default_due_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    assigner = relationship("AppUser", foreign_keys=[assigner_id])
    assignee = relationship("AppUser", foreign_keys=[assignee_id])


class NonProjectTask(Base):
    __tablename__ = "non_project_task"
    __table_args__ = (
        ForeignKeyConstraint(["assigner_id"], ["app_user.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["assignee_id"], ["app_user.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["recurrence_template_id"],
            ["non_project_task_recurrence.id"],
            ondelete="SET NULL",
        ),
        PrimaryKeyConstraint("id"),
        UniqueConstraint(
            "recurrence_template_id",
            "occurrence_date",
            name="uq_non_project_task_recurrence_occurrence",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_non_project_task_status",
        ),
        Index("ix_non_project_task_assignee_status", "assignee_id", "status"),
        Index("ix_non_project_task_planned_completion", "planned_completion_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assigner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assignee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assigned_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    planned_completion_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    actual_completion_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    remark: Mapped[Optional[str]] = mapped_column(Text)
    recurrence_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    occurrence_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    source_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    assigner = relationship("AppUser", foreign_keys=[assigner_id])
    assignee = relationship("AppUser", foreign_keys=[assignee_id])
    recurrence = relationship("NonProjectTaskRecurrence")


class NonProjectTaskEvent(Base):
    __tablename__ = "non_project_task_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id"], ["non_project_task.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["operator_id"], ["app_user.id"], ondelete="SET NULL"),
        PrimaryKeyConstraint("id"),
        Index("ix_non_project_task_event_task_created", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[Optional[str]] = mapped_column(String(20))
    detail: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class WorkEntry(Base):
    __tablename__ = "work_entry"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["workflow_instance_id"], ["workflow_instance.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["project_responsibility_id"], ["project_workbench_responsibility.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["non_project_task_id"], ["non_project_task.id"], ondelete="CASCADE"
        ),
        PrimaryKeyConstraint("id"),
        CheckConstraint(
            "(CASE WHEN workflow_instance_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN project_responsibility_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN non_project_task_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_work_entry_exactly_one_source",
        ),
        CheckConstraint("duration_minutes >= 0", name="ck_work_entry_duration"),
        Index("ix_work_entry_user_date", "user_id", "work_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    work_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    workflow_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    project_responsibility_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    non_project_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    progress_content: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    result_content: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class DailyReport(Base):
    __tablename__ = "daily_report"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        PrimaryKeyConstraint("id"),
        UniqueConstraint("user_id", "report_date", name="uq_daily_report_user_date"),
        CheckConstraint(
            "status IN ('draft', 'finalized')", name="ck_daily_report_status"
        ),
        Index("ix_daily_report_user_date", "user_id", "report_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    report_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'draft'")
    )
    supplemental_note: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    finalized_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    user = relationship("AppUser")
    items: Mapped[list["DailyReportItem"]] = relationship(
        "DailyReportItem",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="DailyReportItem.sort_order",
    )


class DailyReportItem(Base):
    __tablename__ = "daily_report_item"
    __table_args__ = (
        ForeignKeyConstraint(["report_id"], ["daily_report.id"], ondelete="CASCADE"),
        PrimaryKeyConstraint("id"),
        CheckConstraint(
            "source_type IN ('project', 'non_project', 'manual')",
            name="ck_daily_report_item_source_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    progress_content: Mapped[str] = mapped_column(Text, nullable=False)
    result_content: Mapped[Optional[str]] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    display_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    report: Mapped["DailyReport"] = relationship("DailyReport", back_populates="items")
