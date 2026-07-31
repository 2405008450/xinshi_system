"""
工作流模型：WorkflowInstance（工作流实例）和 WorkflowLog（操作日志）
"""
from typing import Optional
import datetime
import uuid

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class WorkflowInstance(Base):
    """工作流实例表 —— 每个笔译项目或子订单对应一条记录，记录当前流转状态"""
    __tablename__ = 'workflow_instance'
    __table_args__ = (
        ForeignKeyConstraint(
            ['translation_project_id'], ['translation_project.id'],
            ondelete='CASCADE', name='fk_wf_instance_project'
        ),
        ForeignKeyConstraint(
            ['sub_order_id'], ['translation_sub_order.id'],
            ondelete='CASCADE', name='fk_wf_instance_suborder'
        ),
        ForeignKeyConstraint(
            ['current_assignee_id'], ['app_user.id'],
            ondelete='SET NULL', name='fk_wf_instance_assignee'
        ),
        PrimaryKeyConstraint('id', name='workflow_instance_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    translation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    sub_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20))          # simple / normal / complex
    file_editable: Mapped[Optional[bool]] = mapped_column()                # 文件是否可编辑
    current_stage_key: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'reception'"))
    current_assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    group_assign_role: Mapped[Optional[str]] = mapped_column(String(50))   # 同组指派时存储目标角色名
    project_status: Mapped[Optional[str]] = mapped_column(String(30), server_default=text("'pending'"))
    stage_notes: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    stage_data: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    # Relationships
    translation_project = relationship('TranslationProject', back_populates='workflow_instance', foreign_keys=[translation_project_id])
    sub_order = relationship('TranslationSubOrder', back_populates='workflow_instance', foreign_keys=[sub_order_id])
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


class WorkflowHandoverRequest(Base):
    __tablename__ = 'workflow_handover_request'
    __table_args__ = (
        ForeignKeyConstraint(['requester_id'], ['app_user.id'], ondelete='SET NULL', name='fk_wf_handover_requester'),
        ForeignKeyConstraint(['target_user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_wf_handover_target'),
        ForeignKeyConstraint(['decided_by'], ['app_user.id'], ondelete='SET NULL', name='fk_wf_handover_decider'),
        PrimaryKeyConstraint('id', name='workflow_handover_request_pkey'),
        Index('ix_wf_handover_target_status', 'target_user_id', 'status'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    requester_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    target_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    handover_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_detail: Mapped[Optional[str]] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    content_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    decision_note: Mapped[Optional[str]] = mapped_column(String(500))
    decided_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    decided_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    requester = relationship('AppUser', foreign_keys=[requester_id])
    target_user = relationship('AppUser', foreign_keys=[target_user_id])
    decider = relationship('AppUser', foreign_keys=[decided_by])
    items: Mapped[list['WorkflowHandoverItem']] = relationship(
        'WorkflowHandoverItem',
        back_populates='request',
        cascade='all, delete-orphan',
    )
    attachment_links: Mapped[list['WorkflowHandoverAttachment']] = relationship(
        'WorkflowHandoverAttachment',
        back_populates='request',
        cascade='all, delete-orphan',
    )


class WorkflowHandoverItem(Base):
    __tablename__ = 'workflow_handover_item'
    __table_args__ = (
        ForeignKeyConstraint(['request_id'], ['workflow_handover_request.id'], ondelete='CASCADE', name='fk_wf_handover_item_request'),
        ForeignKeyConstraint(['workflow_instance_id'], ['workflow_instance.id'], ondelete='CASCADE', name='fk_wf_handover_item_instance'),
        ForeignKeyConstraint(['expected_assignee_id'], ['app_user.id'], ondelete='SET NULL', name='fk_wf_handover_item_assignee'),
        PrimaryKeyConstraint('id', name='workflow_handover_item_pkey'),
        UniqueConstraint('request_id', 'workflow_instance_id', name='uq_wf_handover_item'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    expected_assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    request: Mapped['WorkflowHandoverRequest'] = relationship('WorkflowHandoverRequest', back_populates='items')
    workflow_instance: Mapped['WorkflowInstance'] = relationship('WorkflowInstance')


class WorkflowHandoverAttachment(Base):
    __tablename__ = 'workflow_handover_attachment'
    __table_args__ = (
        ForeignKeyConstraint(['request_id'], ['workflow_handover_request.id'], ondelete='CASCADE', name='fk_wf_handover_attachment_request'),
        ForeignKeyConstraint(['attachment_id'], ['chat_project_attachment.id'], ondelete='CASCADE', name='fk_wf_handover_attachment_file'),
        PrimaryKeyConstraint('id', name='workflow_handover_attachment_pkey'),
        UniqueConstraint('request_id', 'attachment_id', name='uq_wf_handover_attachment'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    attachment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    request: Mapped['WorkflowHandoverRequest'] = relationship('WorkflowHandoverRequest', back_populates='attachment_links')
    attachment = relationship('ChatProjectAttachment')


class ProjectManagerHandoverRequest(Base):
    """项目管理主负责人交接；与执行阶段任务交接独立。"""
    __tablename__ = 'project_manager_handover_request'
    __table_args__ = (
        ForeignKeyConstraint(['requester_id'], ['app_user.id'], ondelete='SET NULL', name='fk_pm_handover_requester'),
        ForeignKeyConstraint(['target_manager_id'], ['app_user.id'], ondelete='CASCADE', name='fk_pm_handover_target'),
        ForeignKeyConstraint(['decided_by'], ['app_user.id'], ondelete='SET NULL', name='fk_pm_handover_decider'),
        PrimaryKeyConstraint('id', name='project_manager_handover_request_pkey'),
        Index('ix_pm_handover_target_status', 'target_manager_id', 'status'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    requester_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    target_manager_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    note: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    decision_note: Mapped[Optional[str]] = mapped_column(String(500))
    decided_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    decided_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    requester = relationship('AppUser', foreign_keys=[requester_id])
    target_manager = relationship('AppUser', foreign_keys=[target_manager_id])
    decider = relationship('AppUser', foreign_keys=[decided_by])
    items: Mapped[list['ProjectManagerHandoverItem']] = relationship(
        'ProjectManagerHandoverItem',
        back_populates='request',
        cascade='all, delete-orphan',
    )


class ProjectManagerHandoverItem(Base):
    __tablename__ = 'project_manager_handover_item'
    __table_args__ = (
        ForeignKeyConstraint(['request_id'], ['project_manager_handover_request.id'], ondelete='CASCADE', name='fk_pm_handover_item_request'),
        ForeignKeyConstraint(['translation_project_id'], ['translation_project.id'], ondelete='CASCADE', name='fk_pm_handover_item_project'),
        ForeignKeyConstraint(['expected_manager_id'], ['app_user.id'], ondelete='SET NULL', name='fk_pm_handover_item_expected'),
        PrimaryKeyConstraint('id', name='project_manager_handover_item_pkey'),
        UniqueConstraint('request_id', 'translation_project_id', name='uq_pm_handover_item'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    expected_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    request: Mapped['ProjectManagerHandoverRequest'] = relationship(
        'ProjectManagerHandoverRequest',
        back_populates='items',
    )
    project = relationship('TranslationProject')
    expected_manager = relationship('AppUser', foreign_keys=[expected_manager_id])
