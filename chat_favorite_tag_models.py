"""共享标签目录及各账号的消息收藏标签。"""
from uuid import uuid4
from sqlalchemy import String, DateTime, Uuid, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import mapped_column
from models import Base
from business_time import business_now


class ChatFavoriteTag(Base):
    __tablename__='chat_favorite_tag'
    id=mapped_column(Uuid,primary_key=True,default=uuid4)
    name=mapped_column(String(60),nullable=False)
    name_key=mapped_column(String(120),nullable=False)
    color=mapped_column(String(7),nullable=False)
    created_by=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=business_now)
    __table_args__=(UniqueConstraint('name_key',name='uq_chat_favorite_tag_name_key'),)


class ChatFavoriteMessageTag(Base):
    __tablename__='chat_favorite_message_tag'
    user_id=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='CASCADE'),primary_key=True)
    conversation_kind=mapped_column(String(20),primary_key=True)
    conversation_id=mapped_column(Uuid,primary_key=True)
    message_id=mapped_column(String(40),primary_key=True)
    tag_id=mapped_column(Uuid,ForeignKey('chat_favorite_tag.id',ondelete='CASCADE'),primary_key=True)
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=business_now)
    __table_args__=(Index('ix_chat_favorite_message_tag_user_tag','user_id','tag_id'),
        CheckConstraint("conversation_kind IN ('annotation','translation','direct','discussion')",name='ck_chat_favorite_tag_kind'))
