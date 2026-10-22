"""逐条消息的实际阅读回执；与未读游标、收到确认相互独立。"""
from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now


class ChatMessageView(Base):
    __tablename__ = 'chat_message_view'
    __table_args__ = (Index('ix_chat_message_view_user', 'user_id', 'seen_at'),)
    conversation_kind = mapped_column(String(20), primary_key=True)
    conversation_id = mapped_column(Uuid, primary_key=True)
    message_id = mapped_column(String(64), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True)
    seen_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
