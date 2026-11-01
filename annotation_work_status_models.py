"""标注项目每日安排、分时汇报与提醒去重；新表不改变现有项目状态枚举。"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.types import Uuid
from models import Base


class AnnotationWorkDay(Base):
    __tablename__ = 'annotation_work_day'
    __table_args__ = (
        UniqueConstraint('user_id', 'project_id', 'work_date', name='uq_annotation_work_day'),
        CheckConstraint("arrangement_status IN ('in_progress','not_today')", name='ck_annotation_work_day_status'),
    )
    id = Column(Uuid, primary_key=True)
    user_id = Column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(Uuid, ForeignKey('annotation_project.id', ondelete='CASCADE'), nullable=False)
    work_date = Column(Date, nullable=False)
    arrangement_status = Column(String(20), nullable=False)
    remaining_time = Column(String(20))
    entered_at = Column(DateTime(timezone=True))
    revision = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class AnnotationWorkSubmission(Base):
    __tablename__ = 'annotation_work_submission'
    __table_args__ = (
        UniqueConstraint('work_day_id', 'slot', name='uq_annotation_work_submission_slot'),
        CheckConstraint('cumulative_minutes > 0 AND cumulative_minutes <= 1440', name='ck_annotation_work_submission_minutes'),
        CheckConstraint("slot IN ('11','15','18','21','end_shift')", name='ck_annotation_work_submission_slot'),
    )
    id = Column(Uuid, primary_key=True)
    work_day_id = Column(Uuid, ForeignKey('annotation_work_day.id', ondelete='CASCADE'), nullable=False)
    slot = Column(String(20), nullable=False)
    progress_note = Column(Text, nullable=False)
    cumulative_minutes = Column(Integer, nullable=False)
    arrangement_status = Column(String(20), nullable=False)
    remaining_time = Column(String(20), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)


class AnnotationWorkReminder(Base):
    __tablename__ = 'annotation_work_reminder'
    __table_args__ = (UniqueConstraint('user_id', 'work_date', 'slot', name='uq_annotation_work_reminder'),)
    id = Column(Uuid, primary_key=True)
    user_id = Column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False)
    work_date = Column(Date, nullable=False)
    slot = Column(String(20), nullable=False)
    reminded_at = Column(DateTime(timezone=True), nullable=False)


class AnnotationWorkAvailability(Base):
    __tablename__ = 'annotation_work_availability'
    __table_args__ = (
        UniqueConstraint('user_id', 'work_date', 'slot', name='uq_annotation_work_availability'),
        CheckConstraint("slot IN ('11','15','18','21','end_shift')", name='ck_annotation_work_availability_slot'),
        CheckConstraint("(is_idle = false AND expected_idle_time IS NULL) OR (is_idle = true AND expected_idle_time IN ('undetermined','under_30','30_60','1_2h','2_5h'))", name='ck_annotation_work_availability_estimate'),
    )
    id = Column(Uuid, primary_key=True)
    user_id = Column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False)
    work_date = Column(Date, nullable=False)
    slot = Column(String(20), nullable=False)
    is_idle = Column(Boolean, nullable=False)
    expected_idle_time = Column(String(20))
    revision = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
