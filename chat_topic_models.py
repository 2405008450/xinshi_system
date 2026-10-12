"""团队讨论主题、消息分类及独立审计。"""
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import mapped_column
from models import Base
from business_time import BUSINESS_TIMEZONE, business_now


def topic_now():
    return business_now().replace(tzinfo=BUSINESS_TIMEZONE)


class ChatTopic(Base):
    __tablename__ = 'chat_topic'
    __table_args__ = (CheckConstraint("kind IN ('topic','annotation')"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    parent_id = mapped_column(Uuid, ForeignKey('chat_topic.id'))
    builtin_key = mapped_column(String(60), unique=True)
    kind = mapped_column(String(20), nullable=False, default='topic')
    name = mapped_column(String(80), nullable=False)
    description = mapped_column(String(500), nullable=False, default='')
    sort_order = mapped_column(Integer, nullable=False, default=0)
    active = mapped_column(Boolean, nullable=False, default=True)
    revision = mapped_column(Integer, nullable=False, default=1)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=topic_now)


class ChatMessageTopic(Base):
    __tablename__ = 'chat_message_topic'
    __table_args__ = (Index('ix_chat_message_topic_topic', 'topic_id', 'message_id'),)
    message_id = mapped_column(Uuid, ForeignKey('chat_project_message.id', ondelete='CASCADE'), primary_key=True)
    topic_id = mapped_column(Uuid, ForeignKey('chat_topic.id'))
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=topic_now)
    revision = mapped_column(Integer, nullable=False, default=1)


class ChatTopicAudit(Base):
    __tablename__ = 'chat_topic_audit'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_id = mapped_column(Uuid, nullable=False)
    actor_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    action = mapped_column(String(40), nullable=False)
    before = mapped_column(JSON, nullable=False, default=dict)
    after = mapped_column(JSON, nullable=False, default=dict)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=topic_now)
