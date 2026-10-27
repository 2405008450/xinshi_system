"""资源讨论独立会话；不将讨论伪装为业务项目或私聊。"""
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import mapped_column
from models import Base
from chat_session_category_models import category_now


class DiscussionMessageAction(Base):
    __tablename__ = 'chat_discussion_message_action'
    message_id = mapped_column(BigInteger, ForeignKey('chat_discussion_message.id', ondelete='CASCADE'), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True)
    user_name = mapped_column(String(255), nullable=False)
    favorited_at = mapped_column(DateTime(timezone=True))
    acknowledged_at = mapped_column(DateTime(timezone=True))


class DiscussionIssueSource(Base):
    __tablename__ = 'chat_discussion_issue_source'
    __table_args__ = (UniqueConstraint('message_id', 'category', name='uq_discussion_issue_category'),)
    issue_id = mapped_column(Uuid, ForeignKey('resource_development_issue.id', ondelete='CASCADE'), primary_key=True)
    room_id = mapped_column(Uuid, nullable=False, index=True)
    message_id = mapped_column(BigInteger, ForeignKey('chat_discussion_message.id', ondelete='RESTRICT'), nullable=False)
    category = mapped_column(String(20), nullable=False)


class DiscussionMessage(Base):
    __tablename__ = 'chat_discussion_message'
    __table_args__ = (
        UniqueConstraint('room_id', 'sender_id', 'client_message_id', name='uq_discussion_client_message'),
        Index('ix_discussion_room_message', 'room_id', 'id'),
    )
    id = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), Identity(), primary_key=True)
    room_id = mapped_column(Uuid, nullable=False)
    sender_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    sender_name = mapped_column(String(255), nullable=False)
    client_message_id = mapped_column(Uuid, nullable=False)
    content = mapped_column(Text, nullable=False)
    reply_to_id = mapped_column(BigInteger, ForeignKey('chat_discussion_message.id'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=category_now)
    recalled_at = mapped_column(DateTime(timezone=True))


class DiscussionMember(Base):
    __tablename__ = 'chat_discussion_member'
    room_id = mapped_column(Uuid, primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id'), primary_key=True)
    last_read_id = mapped_column(BigInteger, nullable=False, default=0)
    pinned = mapped_column(Boolean, nullable=False, default=False)
    starred = mapped_column(Boolean, nullable=False, default=False)


class DiscussionMention(Base):
    """显式的讨论提及关系；纯文本 @ 不产生提醒。"""
    __tablename__ = 'chat_discussion_mention'
    __table_args__ = (Index('ix_discussion_mention_user_message', 'user_id', 'message_id'),)
    message_id = mapped_column(BigInteger, ForeignKey('chat_discussion_message.id', ondelete='CASCADE'), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True)
    user_name = mapped_column(String(255), nullable=False)
    is_all = mapped_column(Boolean, nullable=False, default=False)
    notification_id = mapped_column(Uuid, ForeignKey('app_notification.id', ondelete='SET NULL'), unique=True)
