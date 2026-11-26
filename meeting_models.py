"""会议安排与逐人回执；业务时间为UTC+8实际时刻。"""
from uuid import uuid4
from sqlalchemy import Integer, String, Text, DateTime, Uuid, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now


class Meeting(Base):
    __tablename__ = 'meeting_arrangement'
    number = mapped_column(Integer, primary_key=True, autoincrement=True)
    id = mapped_column(Uuid, nullable=False, unique=True, default=uuid4)
    client_id = mapped_column(Uuid, nullable=False, unique=True)
    organizer_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False, index=True)
    topic = mapped_column(String(500), nullable=False)
    meeting_type = mapped_column(String(30), nullable=False)
    location = mapped_column(String(80), nullable=False)
    start_at = mapped_column(DateTime(timezone=True), nullable=False)
    end_at = mapped_column(DateTime(timezone=True), nullable=False)
    selection = mapped_column(JSON, nullable=False)
    association = mapped_column(JSON, nullable=False)
    note = mapped_column(Text, nullable=False, default='')
    agendas = mapped_column(JSON, nullable=False, default=list)
    actual_start_at = mapped_column(DateTime(timezone=True))
    actual_end_at = mapped_column(DateTime(timezone=True))
    actual_user_ids = mapped_column(JSON, nullable=False, default=list)
    confirmed_at = mapped_column(DateTime(timezone=True))
    record_content = mapped_column(Text, nullable=False, default='')
    record_version = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (Index('ix_meeting_start', 'start_at'), CheckConstraint('end_at > start_at', name='ck_meeting_time'),)


class MeetingParticipant(Base):
    __tablename__ = 'meeting_participant'
    meeting_id = mapped_column(Uuid, ForeignKey('meeting_arrangement.id', ondelete='CASCADE'), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id'), primary_key=True)
    name = mapped_column(String(200), nullable=False)
    response = mapped_column(String(20), nullable=False, default='pending')
    reason = mapped_column(Text, nullable=False, default='')
    responded_at = mapped_column(DateTime(timezone=True))
    response_version = mapped_column(Integer, nullable=False, default=0)
    organizer_seen_version = mapped_column(Integer, nullable=False, default=0)
    __table_args__ = (Index('ix_meeting_participant_user', 'user_id', 'response'),
                     CheckConstraint("response IN ('pending','attending','declined')", name='ck_meeting_response'),)


class MeetingActionTask(Base):
    __tablename__ = 'meeting_action_task'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    client_id = mapped_column(Uuid, nullable=False)
    meeting_id = mapped_column(Uuid, ForeignKey('meeting_arrangement.id', ondelete='CASCADE'), nullable=False, index=True)
    assignee_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False, index=True)
    arranger_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    category = mapped_column(String(20), nullable=False)
    content = mapped_column(Text, nullable=False)
    project = mapped_column(JSON, nullable=False, default=dict)
    due_at = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    status = mapped_column(String(20), nullable=False, default='pending')
    completed_at = mapped_column(DateTime(timezone=True))
    revision = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (Index('uq_meeting_action_client_person', 'client_id', 'assignee_id', unique=True),
                     CheckConstraint("category IN ('project','non_project')", name='ck_meeting_action_category'),
                     CheckConstraint("status IN ('pending','in_progress','completed')", name='ck_meeting_action_status'))
