"""
工作流模型：WorkflowInstance（工作流实例）和 WorkflowLog（操作日志）
"""
from typing import Optional
import datetime
import uuid

from sqlalchemy import DateTime, ForeignKeyConstraint, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class WorkflowInstance(Base):
    """工作流实例表 —— 每个笔译项目对应一条记录，记录当前流转状态"""
    __tablename__ = 'workflow_instance'
    __table_args__ = (
        ForeignKeyConstraint(
            ['translation_project_id'], ['translation_project.id'],
            ondelete='CASCADE', name='fk_wf_instance_project'
        ),
        ForeignKeyConstraint(
            ['current_assignee_id'], ['app_user.id'],
            ondelete='SET NULL', name='fk_wf_instance_assignee'
        ),
        PrimaryKeyConstraint('id', name='workflow_instance_pkey'),
        UniqueConstraint('translation_project_id', name='uq_wf_instance_project')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20))          # simple / normal / complex
    file_editable: Mapped[Optional[bool]] = mapped_column()                # 文件是否可编辑
    current_stage_key: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'reception'"))
    current_assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    project_status: Mapped[Optional[str]] = mapped_column(String(30), server_default=text("'pending'"))
    stage_notes: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    stage_data: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    # Relationships
    translation_project = relationship('TranslationProject', back_populates='workflow_instance')
    current_assignee = relationship('AppUser', foreign_keys=[current_assignee_id])
    logs: Mapped[list['WorkflowLog']] = relationship('WorkflowLog', back_populates='workflow_instance', cascade='all, delete-orphan', order_by='WorkflowLog.created_at')


class WorkflowLog(Base):
    """操作日志表 —— 记录每一次推进/打回"""
    __tablename__ = 'workflow_log'
    __table_args__ = (
        ForeignKeyConstraint(
            ['workflow_instance_id'], ['workflow_instance.id'],
            ondelete='CASCADE', name='fk_wf_log_instance'
        ),
        ForeignKeyConstraint(
            ['operator_id'], ['app_user.id'],
            ondelete='SET NULL', name='fk_wf_log_operator'
        ),
        ForeignKeyConstraint(
            ['next_assignee_id'], ['app_user.id'],
            ondelete='SET NULL', name='fk_wf_log_next_assignee'
        ),
        PrimaryKeyConstraint('id', name='workflow_log_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    from_stage: Mapped[Optional[str]] = mapped_column(String(50))
    to_stage: Mapped[Optional[str]] = mapped_column(String(50))
    direction: Mapped[Optional[str]] = mapped_column(String(20))           # forward / rollback
    description: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    next_assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    # Relationships
    workflow_instance: Mapped['WorkflowInstance'] = relationship('WorkflowInstance', back_populates='logs')
    operator = relationship('AppUser', foreign_keys=[operator_id])
    next_assignee = relationship('AppUser', foreign_keys=[next_assignee_id])
