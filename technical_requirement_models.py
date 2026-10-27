from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, BigInteger
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now


class TechnicalRoom(Base):
    __tablename__ = 'annotation_technical_room'
    project_id = mapped_column(Uuid, ForeignKey('annotation_project.id',ondelete='CASCADE'), primary_key=True)
    room_id = mapped_column(Uuid, ForeignKey('chat_session_category.id',ondelete='RESTRICT'), unique=True, nullable=False, default=uuid4)
    requirements = mapped_column(Text, nullable=False, default='')
    revision = mapped_column(Integer, nullable=False, default=1)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class TechnicalAppend(Base):
    __tablename__ = 'annotation_technical_append'
    __table_args__ = (UniqueConstraint('room_id','request_id',name='uq_technical_append_request'),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    room_id = mapped_column(Uuid, ForeignKey('annotation_technical_room.room_id',ondelete='CASCADE'), nullable=False)
    request_id = mapped_column(Uuid, nullable=False)
    message_id = mapped_column(BigInteger, ForeignKey('chat_discussion_message.id',ondelete='RESTRICT'), nullable=False)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
