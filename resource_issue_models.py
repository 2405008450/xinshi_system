"""开拓问题及独立的后续任务；聊天删除不级联删除已收录的业务快照。"""
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, text, JSON
from sqlalchemy.orm import mapped_column
from models import Base
from chat_topic_models import ChatTopic  # 注册主题表，支持独立导入模型后的元数据解析。
from business_time import business_now as local_now, BUSINESS_TIMEZONE


def business_now():
    """新表使用带时区的实际时刻，不依赖数据库会话时区解释无时区值。"""
    return local_now().replace(tzinfo=BUSINESS_TIMEZONE)


class DevelopmentIssue(Base):
    __tablename__ = "resource_development_issue"
    __table_args__ = (
        UniqueConstraint("source_message_id", "category", name="uq_development_issue_source_category"),
        CheckConstraint("category IN ('arrangement','request','idea','decision','execution','problem','risk','standard')", name="ck_development_issue_category"),
        CheckConstraint("source_type IN ('translation','annotation','direct','manual')", name="ck_development_issue_source_type"),
        Index("ix_development_issue_created", "created_at", "id"),
        Index('uq_issue_manual_request', 'collected_by', 'client_request_id', unique=True,
              postgresql_where=text('client_request_id IS NOT NULL')),
    )
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    category = mapped_column(String(20), nullable=False)
    content = mapped_column(Text, nullable=False)
    remarks = mapped_column(Text, nullable=False, default="")
    summary_data = mapped_column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
    source_message_id = mapped_column(Uuid)
    topic_id = mapped_column(Uuid, ForeignKey('chat_topic.id'), index=True)
    topic_path = mapped_column(String(200), nullable=False, default='')
    client_request_id = mapped_column(Uuid)
    source_type = mapped_column(String(20), nullable=False)
    source_conversation_id = mapped_column(Uuid)
    source_title = mapped_column(String(500), nullable=False)
    source_content = mapped_column(Text, nullable=False)
    proposer_id = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
    proposer_name = mapped_column(String(255), nullable=False)
    collected_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False, index=True)
    collected_by_name = mapped_column(String(255), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
    revision = mapped_column(Integer, nullable=False, default=1)


class DevelopmentIssueAudience(Base):
    __tablename__ = 'resource_issue_audience'
    issue_id = mapped_column(Uuid, ForeignKey('resource_development_issue.id',ondelete='CASCADE'), primary_key=True)
    kind = mapped_column(String(24),primary_key=True)
    target_id = mapped_column(Uuid,primary_key=True)
    __table_args__ = (CheckConstraint("kind IN ('follower','notify_user','notify_department')",name='ck_issue_audience_kind'),Index('ix_issue_audience_target','kind','target_id','issue_id'))


class DevelopmentIssueTask(Base):
    __tablename__ = "resource_development_issue_task"
    __table_args__ = (
        CheckConstraint("status IN ('pending','in_progress','completed','cancelled')", name="ck_development_issue_task_status"),
        CheckConstraint("(status = 'completed') = (completed_date IS NOT NULL)", name="ck_development_issue_task_completion"),
        Index("ix_development_issue_task_executor", "executor_id", "issue_id"),
        Index("ix_development_issue_task_filter", "issue_id", "status", "planned_date"),
    )
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    issue_id = mapped_column(Uuid, ForeignKey("resource_development_issue.id", ondelete="CASCADE"), nullable=False, index=True)
    content = mapped_column(Text, nullable=False)
    executor_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    executor_name = mapped_column(String(255), nullable=False)
    planned_date = mapped_column(Date)
    status = mapped_column(String(20), nullable=False, default="pending")
    progress = mapped_column(Text, nullable=False, default="")
    completed_date = mapped_column(Date)
    remarks = mapped_column(Text, nullable=False, default="")
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
    revision = mapped_column(Integer, nullable=False, default=1)
