"""资源需求发圈／发帖批次及独立回执。"""
import uuid
from sqlalchemy import String, DateTime, ForeignKey, Uuid, JSON, Index, Text, Integer
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now


class ResourceRequestDispatch(Base):
    __tablename__ = 'resource_request_dispatch'
    id = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id = mapped_column(Uuid, ForeignKey('resource_request.id', ondelete='RESTRICT'), nullable=False, index=True)
    sender_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='RESTRICT'), nullable=False, index=True)
    kind = mapped_column(String(16), nullable=False)
    idempotency_key = mapped_column(String(128), nullable=False, unique=True)
    snapshot = mapped_column(JSON, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class ResourceRequestDispatchRecipient(Base):
    __tablename__ = 'resource_request_dispatch_recipient'
    dispatch_id = mapped_column(Uuid, ForeignKey('resource_request_dispatch.id', ondelete='CASCADE'), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='RESTRICT'), primary_key=True)
    received_at = mapped_column(DateTime(timezone=True))
    processed_at = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index('ix_resource_dispatch_recipient_user', 'user_id', 'dispatch_id'),)


class ResourceRequestExecutionReply(Base):
    """每次执行回复独立保存平台名称快照，渠道后续改名或删除不改历史回执。"""
    __tablename__ = 'resource_request_execution_reply'
    id = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dispatch_id = mapped_column(Uuid, ForeignKey('resource_request_dispatch.id', ondelete='RESTRICT'), nullable=False, index=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='RESTRICT'), nullable=False)
    platforms = mapped_column(JSON, nullable=False)
    content = mapped_column(Text, nullable=False, default='')
    idempotency_key = mapped_column(String(128), nullable=False, unique=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class ResourceRequestDispatchDefault(Base):
    __tablename__ = 'resource_request_dispatch_default'
    kind = mapped_column(String(16),primary_key=True)
    # NULL 使用初始规则；显式 [] 表示管理员清空默认名单。
    user_ids = mapped_column(JSON,nullable=True)
    revision = mapped_column(Integer,nullable=False,default=1)
    updated_by = mapped_column(Uuid,ForeignKey('app_user.id'),nullable=True)
    updated_at = mapped_column(DateTime(timezone=True),nullable=False,default=now)
