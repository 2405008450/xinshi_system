"""独立于消息主题的团队会话分类。"""
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import mapped_column
from models import Base
from business_time import BUSINESS_TIMEZONE, business_now


def category_now():
    return business_now().replace(tzinfo=BUSINESS_TIMEZONE)


class ChatSessionCategory(Base):
    __tablename__ = 'chat_session_category'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    name = mapped_column(String(80), nullable=False)
    active = mapped_column(Boolean, nullable=False, default=True)
    revision = mapped_column(Integer, nullable=False, default=1)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=category_now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=category_now)


class ChatSessionCategoryLink(Base):
    __tablename__ = 'chat_session_category_link'
    __table_args__ = (
        CheckConstraint('num_nonnulls(project_id, annotation_project_id, direct_conversation_id) = 1', name='ck_session_category_one_target'),
        Index('uq_session_category_translation', 'category_id', 'project_id', unique=True, postgresql_where=text('project_id IS NOT NULL')),
        Index('uq_session_category_annotation', 'category_id', 'annotation_project_id', unique=True, postgresql_where=text('annotation_project_id IS NOT NULL')),
        Index('uq_session_category_direct', 'category_id', 'direct_conversation_id', unique=True, postgresql_where=text('direct_conversation_id IS NOT NULL')),
    )
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    category_id = mapped_column(Uuid, ForeignKey('chat_session_category.id'), nullable=False)
    project_id = mapped_column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'))
    annotation_project_id = mapped_column(Uuid, ForeignKey('annotation_project.id', ondelete='CASCADE'))
    direct_conversation_id = mapped_column(Uuid, ForeignKey('chat_direct_conversation.id', ondelete='CASCADE'))
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=category_now)
