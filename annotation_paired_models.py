"""双人采标：订单隔离、成员版本与不可覆盖的操作历史。"""
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, Uuid, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from models import Base
from datetime import datetime
from business_time import BUSINESS_TIMEZONE


def business_now():
    return datetime.now(BUSINESS_TIMEZONE)


class PairedWorkspace(Base):
    __tablename__ = "annotation_paired_workspace"
    project_id = mapped_column(Uuid, ForeignKey("annotation_project.id", ondelete="CASCADE"), primary_key=True)
    allow_multiple_groups = mapped_column(Boolean, nullable=False, default=False)
    archived = mapped_column(Boolean, nullable=False, default=False)
    notes = mapped_column(JSONB, nullable=False, default=dict)
    revision = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedContact(Base):
    __tablename__ = "annotation_paired_contact"
    __table_args__ = (UniqueConstraint("project_id", "person_id", name="uq_paired_contact_person"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id = mapped_column(Uuid, ForeignKey("annotation_paired_workspace.project_id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = mapped_column(Uuid, ForeignKey("resource_person.id", ondelete="RESTRICT"), nullable=False)
    willingness = mapped_column(String(40), nullable=False, default="pending")
    data = mapped_column(JSONB, nullable=False, default=dict)
    revision = mapped_column(Integer, nullable=False, default=1)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedGroup(Base):
    __tablename__ = "annotation_paired_group"
    __table_args__ = (UniqueConstraint("project_id", "request_key", name="uq_paired_group_request"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id = mapped_column(Uuid, ForeignKey("annotation_paired_workspace.project_id", ondelete="CASCADE"), nullable=False, index=True)
    name = mapped_column(String(150), nullable=False)
    request_key = mapped_column(Uuid, nullable=False)
    request_hash = mapped_column(String(64), nullable=False, default="")
    archived = mapped_column(Boolean, nullable=False, default=False)
    revision = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedMembers(Base):
    __tablename__ = "annotation_paired_members"
    __table_args__ = (UniqueConstraint("group_id", "version", name="uq_paired_members_version"), CheckConstraint("person1_id <> person2_id", name="ck_paired_members_distinct"))
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    group_id = mapped_column(Uuid, ForeignKey("annotation_paired_group.id", ondelete="CASCADE"), index=True)
    version = mapped_column(Integer, nullable=False)
    person1_id = mapped_column(Uuid, ForeignKey("resource_person.id", ondelete="RESTRICT"), nullable=False)
    person2_id = mapped_column(Uuid, ForeignKey("resource_person.id", ondelete="RESTRICT"), nullable=False)
    reason = mapped_column(Text, nullable=False, default="")
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedTask(Base):
    """采集批次与标注任务使用同一任务接口，阶段分别管理。"""
    __tablename__ = "annotation_paired_task"
    __table_args__ = (
        UniqueConstraint("project_id", "request_key", name="uq_paired_task_request"),
        UniqueConstraint("source_task_id", name="uq_paired_task_source"),
        CheckConstraint("stage IN ('collection','annotation')", name="ck_paired_task_stage"),
        CheckConstraint("revision > 0", name="ck_paired_task_revision"),
    )
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id = mapped_column(Uuid, ForeignKey("annotation_paired_workspace.project_id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = mapped_column(Uuid, ForeignKey("annotation_paired_group.id", ondelete="RESTRICT"), nullable=False)
    members_id = mapped_column(Uuid, ForeignKey("annotation_paired_members.id", ondelete="RESTRICT"), nullable=False)
    source_task_id = mapped_column(Uuid, ForeignKey("annotation_paired_task.id", ondelete="RESTRICT"))
    request_key = mapped_column(Uuid, nullable=False)
    request_hash = mapped_column(String(64), nullable=False, default="")
    stage = mapped_column(String(20), nullable=False)
    name = mapped_column(String(200), nullable=False)
    status = mapped_column(String(30), nullable=False, default="pending")
    person_ids = mapped_column(JSONB, nullable=False, default=list)
    data = mapped_column(JSONB, nullable=False, default=dict)
    revision = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedRecord(Base):
    """当前阶段记录；修改前快照写入审计，不破坏节点ID。"""
    __tablename__ = "annotation_paired_record"
    __table_args__ = (UniqueConstraint("task_id", "request_key", name="uq_paired_record_request"), CheckConstraint("position > 0", name="ck_paired_record_position"))
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id = mapped_column(Uuid, ForeignKey("annotation_paired_task.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind = mapped_column(String(30), nullable=False)
    position = mapped_column(Integer, nullable=False)
    request_key = mapped_column(Uuid, nullable=False)
    request_hash = mapped_column(String(64), nullable=False, default="")
    title = mapped_column(String(200), nullable=False)
    data = mapped_column(JSONB, nullable=False, default=dict)
    person_ids = mapped_column(JSONB, nullable=False, default=list)
    revision = mapped_column(Integer, nullable=False, default=1)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedParticipant(Base):
    """保留任务历次参与人员的真实外键，防止自由安排的标注员被误删。"""
    __tablename__ = "annotation_paired_participant"
    task_id = mapped_column(Uuid, ForeignKey("annotation_paired_task.id", ondelete="CASCADE"), primary_key=True)
    person_id = mapped_column(Uuid, ForeignKey("resource_person.id", ondelete="RESTRICT"), primary_key=True)
    active = mapped_column(Boolean, nullable=False, default=True)


class PairedAudit(Base):
    __tablename__ = "annotation_paired_audit"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id = mapped_column(Uuid, ForeignKey("annotation_paired_workspace.project_id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = mapped_column(Uuid, nullable=False, index=True)
    action = mapped_column(String(40), nullable=False)
    before = mapped_column(JSONB, nullable=False, default=dict)
    after = mapped_column(JSONB, nullable=False, default=dict)
    actor_id = mapped_column(Uuid, ForeignKey("app_user.id"))
    actor_name = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class PairedAttachment(Base):
    __tablename__ = "annotation_paired_attachment"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    contact_id = mapped_column(Uuid, ForeignKey("annotation_paired_contact.id", ondelete="CASCADE"), nullable=False, index=True)
    name = mapped_column(String(255), nullable=False)
    content = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
