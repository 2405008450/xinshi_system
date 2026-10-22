"""跨账号共用的标注会话默认参与人；不在运行时创建表。"""
from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import mapped_column
from models import Base
from business_time import business_now


class AnnotationChatDefaultParticipant(Base):
    __tablename__ = 'annotation_chat_default_participant'
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)
