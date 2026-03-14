"""
工作流 CRUD 操作
包含阶段定义、难度过滤逻辑、推进/打回/初始化等核心业务方法
"""
from decimal import Decimal
from typing import Optional, List
import uuid as _uuid
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, Uuid, or_
from sqlalchemy.orm import Session

from workflow_models import WorkflowInstance, WorkflowLog
from models import TranslationProject, AppUser, Client, EmployeeLeave


# ========== 阶段定义（与前端 ALL_STAGES 保持一致） ==========

ALL_STAGES = [
    {'key': 'reception',           'title': '客户专员',   'role': '客户专员'},
    {'key': 'layout_assign',       'title': '排版指派',   'role': '排版专员'},
    {'key': 'project_manager',     'title': '项目经理',   'role': '项目经理'},
    {'key': 'project_specialist',  'title': '项目专员',   'role': '项目专员'},
    {'key': 'project_assistant',   'title': '项目助理',   'role': '项目助理'},
    {'key': 'review',              'title': '译审',       'role': '译审'},
    {'key': 'special_qc',          'title': '专检',       'role': '项目专员'},
    {'key': 'layout',              'title': '排版',       'role': '排版专员'},
    {'key': 'completed',           'title': '完成',       'role': '-'},
]

STAGE_BY_KEY = {s['key']: s for s in ALL_STAGES}


def get_effective_stages(difficulty: Optional[str], file_editable: Optional[bool] = True) -> list:
    """根据难度和文件是否可编辑返回实际流转阶段列表"""
    if not difficulty:
        return [ALL_STAGES[0]]  # 仅返回 reception

    steps = list(ALL_STAGES)

    # 文件可编辑时，去掉排版指派
    if file_editable is not False:
        steps = [s for s in steps if s['key'] != 'layout_assign']

    if difficulty == 'simple':
        # 简单：跳过 项目经理、项目专员、译审
        return [s for s in steps if s['key'] not in ('project_manager', 'project_specialist', 'review')]
    elif difficulty == 'normal':
        # 普通：跳过 译审
        return [s for s in steps if s['key'] != 'review']
    else:
        # 复杂：全流程
        return steps


# ========== 查询 ==========

def get_workflow_by_project(db: Session, project_id: UUID) -> Optional[WorkflowInstance]:
    return db.query(WorkflowInstance)\
        .filter(WorkflowInstance.translation_project_id == project_id)\
        .first()


def get_workflow_by_id(db: Session, instance_id: UUID) -> Optional[WorkflowInstance]:
    return db.query(WorkflowInstance)\
        .filter(WorkflowInstance.id == instance_id)\
        .first()


from crud import (
    create_notifications_for_users,
    ensure_finance_record_for_project,
    get_user_roles_with_role_names,
    get_users_by_role_names,
)
from notification_ws import dispatch_personal_message

def get_my_tasks(db: Session, user_id: UUID) -> list:
    """查询当前用户作为负责人（或同组指派）且未完成的工作流实例，返回带项目信息的列表"""
    roles = get_user_roles_with_role_names(db, user_id)
    is_customer_specialist = '客户专员' in roles

    query = db.query(WorkflowInstance, TranslationProject, Client)\
        .join(TranslationProject, WorkflowInstance.translation_project_id == TranslationProject.id)\
        .outerjoin(Client, TranslationProject.client_id == Client.id)

    # 构造"同组指派"匹配条件：group_assign_role 与该用户的任意角色匹配
    group_filters = [WorkflowInstance.group_assign_role == role for role in roles] if roles else []

    if is_customer_specialist:
        base_conditions = [
            WorkflowInstance.current_assignee_id == user_id,
            (WorkflowInstance.current_stage_key == 'reception') & (WorkflowInstance.difficulty == None),
        ]
    else:
        base_conditions = [
            WorkflowInstance.current_assignee_id == user_id,
        ]

    if group_filters:
        query = query.filter(
            or_(*base_conditions, *group_filters),
            WorkflowInstance.current_stage_key != 'completed'
        )
    else:
        query = query.filter(
            or_(*base_conditions),
            WorkflowInstance.current_stage_key != 'completed'
        )
        
    results = query.all()

    tasks = []
    for wf, proj, client in results:
        tasks.append({
            'workflow_instance_id': wf.id,
            'translation_project_id': proj.id,
            'order_no': proj.order_no,
            'project_name': proj.project_name,
            'client_short_name': client.client_short_name if client else '',
            'current_stage_key': wf.current_stage_key,
            'difficulty': wf.difficulty,
            'project_status': wf.project_status,
            'customer_deadline_time': proj.customer_deadline_time,
            'language_pair': proj.language_pair,
        })
    return tasks


# ========== 初始化 ==========

def _serialize_notification(notification) -> dict:
    return {
        'id': str(notification.id),
        'title': notification.title,
        'content': notification.content,
        'notification_type': notification.notification_type,
        'is_read': notification.is_read,
        'related_project_id': str(notification.related_project_id) if notification.related_project_id else None,
        'created_at': notification.created_at.isoformat() if notification.created_at else None,
    }


def _push_notifications(notifications: list) -> None:
    for notification in notifications:
        dispatch_personal_message(
            notification.recipient_user_id,
            {
                'type': 'notification',
                'notification': _serialize_notification(notification),
            },
        )


def _get_assignment_recipients(db: Session, next_assignee_id: Optional[UUID], group_assign_role: Optional[str]) -> list[UUID]:
    if next_assignee_id:
        return [next_assignee_id]
    if group_assign_role:
        return [user.id for user in get_users_by_role_names(db, [group_assign_role])]
    return []


def _notify_assignment(
    db: Session,
    project_id: UUID,
    stage_key: str,
    next_assignee_id: Optional[UUID],
    group_assign_role: Optional[str],
    action: str,
) -> None:
    recipients = _get_assignment_recipients(db, next_assignee_id, group_assign_role)
    if not recipients:
        return

    project = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
    if not project:
        return

    stage_info = STAGE_BY_KEY.get(stage_key, {})
    stage_title = stage_info.get('title') or stage_key
    title = 'Workflow Task Updated'
    if action == 'assigned':
        content = f'Project {project.order_no} / {project.project_name} has entered {stage_title}. Please handle it.'
        notification_type = 'workflow_assign'
    else:
        content = f'Project {project.order_no} / {project.project_name} was rolled back to {stage_title}. Please review it.'
        notification_type = 'workflow_rollback'

    notifications = create_notifications_for_users(
        db,
        recipient_user_ids=recipients,
        title=title,
        content=content,
        notification_type=notification_type,
        related_project_id=project.id,
        commit=True,
    )
    _push_notifications(notifications)


def init_workflow(db: Session, project_id: UUID) -> WorkflowInstance:
    existing = get_workflow_by_project(db, project_id)
    if existing:
        return existing

    instance = WorkflowInstance(
        translation_project_id=project_id,
        current_stage_key='reception',
        project_status='pending',
        stage_notes={},
        stage_data={},
    )
    db.add(instance)
    db.flush()

    log = WorkflowLog(
        workflow_instance_id=instance.id,
        from_stage='',
        to_stage='reception',
        direction='forward',
        description='Workflow initialized at reception stage.',
        note='System initialization',
    )
    db.add(log)
    db.commit()
    db.refresh(instance)
    return instance


import datetime as _dt


def _check_on_leave(db: Session, user_id: UUID):
    now = _dt.datetime.now()
    leave = db.query(EmployeeLeave).filter(
        EmployeeLeave.employee_id == user_id,
        EmployeeLeave.start_date <= now,
        EmployeeLeave.end_date >= now,
    ).first()
    if leave:
        raise ValueError(
            f"The selected user {leave.employee_name} is currently on leave "
            f"({leave.start_date.strftime('%Y-%m-%d %H:%M')} ~ {leave.end_date.strftime('%Y-%m-%d %H:%M')})."
        )


import re

def _sync_stage_data_to_project(db: Session, project_id: UUID, stage_data: dict):
    if not stage_data:
        return
    project = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
    if not project:
        return

    def to_snake(name):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    def parse_datetime(value: str):
        normalized = value.replace('Z', '+00:00')
        return _dt.datetime.fromisoformat(normalized)

    def parse_date(value: str):
        return _dt.date.fromisoformat(value)

    for key, value in stage_data.items():
        field_name = to_snake(key)
        if not hasattr(project, field_name):
            continue

        column = project.__table__.columns.get(field_name)
        column_type = type(column.type) if column is not None else None

        if isinstance(value, str):
            stripped = value.strip()
            if stripped == '':
                if column is None or column.nullable:
                    setattr(project, field_name, None)
                continue
            value = stripped

        try:
            if column_type in (BigInteger, Integer):
                value = int(value)
            elif column_type is Numeric:
                value = Decimal(str(value))
            elif column_type is Boolean:
                if isinstance(value, str):
                    value = value.lower() in ('1', 'true', 'yes', 'on')
                else:
                    value = bool(value)
            elif column_type is Uuid and isinstance(value, str):
                value = _uuid.UUID(value)
            elif column_type is DateTime and isinstance(value, str):
                value = parse_datetime(value)
            elif column_type is Date and isinstance(value, str):
                value = parse_date(value)
        except (ValueError, TypeError):
            if column is not None and column.nullable:
                value = None
            else:
                continue

        setattr(project, field_name, value)


def set_difficulty(
    db: Session,
    project_id: UUID,
    difficulty: str,
    file_editable: bool,
    next_assignee_id: Optional[UUID] = None,
    group_assign_role: Optional[str] = None,
    operator_id: Optional[UUID] = None,
    note: Optional[str] = None,
    stage_data: Optional[dict] = None,
) -> WorkflowInstance:
    if not next_assignee_id and not group_assign_role:
        raise ValueError("Must specify either next_assignee_id or group_assign_role")

    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")
    if instance.current_stage_key != 'reception':
        raise ValueError("Can only set difficulty at reception stage")

    current_notes = dict(instance.stage_notes or {})
    current_notes['reception'] = note or ''
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    if stage_data:
        current_data['reception'] = stage_data
        _sync_stage_data_to_project(db, project_id, stage_data)
    instance.stage_data = current_data

    instance.difficulty = difficulty
    instance.file_editable = file_editable

    steps = get_effective_stages(difficulty, file_editable)
    if len(steps) < 2:
        raise ValueError("No next stage available")
    next_stage = steps[1]

    if next_assignee_id:
        _check_on_leave(db, next_assignee_id)
        next_user = db.query(AppUser).filter(AppUser.id == next_assignee_id).first()
        next_user_name = (next_user.full_name or next_user.username) if next_user else str(next_assignee_id)
        assign_desc = f"Assigned to {next_user_name}"
        instance.current_assignee_id = next_assignee_id
        instance.group_assign_role = None
    else:
        assign_desc = f"Assigned to role group {group_assign_role}"
        instance.current_assignee_id = None
        instance.group_assign_role = group_assign_role

    log = WorkflowLog(
        workflow_instance_id=instance.id,
        operator_id=operator_id,
        from_stage='reception',
        to_stage=next_stage['key'],
        direction='forward',
        description=f"Difficulty set to {difficulty}; moved to {next_stage['key']}. {assign_desc}.",
        note=note,
        next_assignee_id=next_assignee_id,
    )
    db.add(log)

    instance.current_stage_key = next_stage['key']
    instance.project_status = 'in_progress'

    db.commit()
    db.refresh(instance)
    _notify_assignment(db, project_id, next_stage['key'], next_assignee_id, group_assign_role, 'assigned')
    return instance


def transition_forward(
    db: Session,
    project_id: UUID,
    next_assignee_id: Optional[UUID] = None,
    group_assign_role: Optional[str] = None,
    operator_id: Optional[UUID] = None,
    note: Optional[str] = None,
    stage_data: Optional[dict] = None,
) -> WorkflowInstance:
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")

    steps = get_effective_stages(instance.difficulty, instance.file_editable)
    current_idx = next((i for i, s in enumerate(steps) if s['key'] == instance.current_stage_key), -1)
    if current_idx < 0:
        raise ValueError(f"Current stage '{instance.current_stage_key}' not found in effective stages")

    current_stage_key = instance.current_stage_key
    current_notes = dict(instance.stage_notes or {})
    current_notes[current_stage_key] = note or ''
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    if stage_data:
        current_data[current_stage_key] = stage_data
        _sync_stage_data_to_project(db, project_id, stage_data)
    instance.stage_data = current_data

    current_stage_info = STAGE_BY_KEY.get(current_stage_key, {})
    next_idx = current_idx + 1
    notify_stage_key = None
    notify_next_assignee_id = None
    notify_group_assign_role = None

    if next_idx >= len(steps):
        instance.current_stage_key = 'completed'
        instance.current_assignee_id = None
        instance.group_assign_role = None
        instance.project_status = 'completed'
        log = WorkflowLog(
            workflow_instance_id=instance.id,
            operator_id=operator_id,
            from_stage=current_stage_key,
            to_stage='completed',
            direction='forward',
            description=f"Moved from {current_stage_info.get('key', current_stage_key)} to completed.",
            note=note,
        )
        db.add(log)
        db.commit()
        ensure_finance_record_for_project(db, project_id=project_id, edited_by=operator_id)
        db.refresh(instance)
        return instance

    next_stage = steps[next_idx]
    if next_stage['key'] == 'completed':
        description = f"Moved from {current_stage_info.get('key', current_stage_key)} to completed."
        instance.project_status = 'completed'
        instance.current_assignee_id = None
        instance.group_assign_role = None
        log_next_assignee_id = None
    elif next_assignee_id:
        _check_on_leave(db, next_assignee_id)
        next_user = db.query(AppUser).filter(AppUser.id == next_assignee_id).first()
        next_user_name = (next_user.full_name or next_user.username) if next_user else str(next_assignee_id)
        description = f"Moved from {current_stage_info.get('key', current_stage_key)} to {next_stage['key']}, assigned to {next_user_name}."
        instance.current_assignee_id = next_assignee_id
        instance.group_assign_role = None
        log_next_assignee_id = next_assignee_id
        notify_stage_key = next_stage['key']
        notify_next_assignee_id = next_assignee_id
    elif group_assign_role:
        description = f"Moved from {current_stage_info.get('key', current_stage_key)} to {next_stage['key']}, assigned to role group {group_assign_role}."
        instance.current_assignee_id = None
        instance.group_assign_role = group_assign_role
        log_next_assignee_id = None
        notify_stage_key = next_stage['key']
        notify_group_assign_role = group_assign_role
    else:
        raise ValueError("Must specify next_assignee_id or group_assign_role for non-completed stages")

    log = WorkflowLog(
        workflow_instance_id=instance.id,
        operator_id=operator_id,
        from_stage=current_stage_key,
        to_stage=next_stage['key'],
        direction='forward',
        description=description,
        note=note,
        next_assignee_id=log_next_assignee_id,
    )
    db.add(log)
    instance.current_stage_key = next_stage['key']

    db.commit()
    if next_stage['key'] == 'completed':
        ensure_finance_record_for_project(db, project_id=project_id, edited_by=operator_id)
    db.refresh(instance)
    if notify_stage_key:
        _notify_assignment(db, project_id, notify_stage_key, notify_next_assignee_id, notify_group_assign_role, 'assigned')
    return instance


def rollback(
    db: Session,
    project_id: UUID,
    steps: int = 1,
    to_start: bool = False,
    note: str = '',
    operator_id: Optional[UUID] = None,
) -> WorkflowInstance:
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")

    effective = get_effective_stages(instance.difficulty, instance.file_editable)
    current_idx = next((i for i, s in enumerate(effective) if s['key'] == instance.current_stage_key), -1)
    if current_idx <= 0:
        raise ValueError("Cannot rollback from the first stage")

    target_idx = 0 if to_start else max(0, current_idx - steps)
    target = effective[target_idx]
    description = (
        f"Rolled back to start stage {target['key']}." if to_start
        else f"Rolled back to {target['key']}."
    )

    log = WorkflowLog(
        workflow_instance_id=instance.id,
        operator_id=operator_id,
        from_stage=instance.current_stage_key,
        to_stage=target['key'],
        direction='rollback',
        description=description,
        note=note,
    )
    db.add(log)

    instance.current_stage_key = target['key']
    if target['key'] == 'reception':
        instance.current_assignee_id = None
        instance.group_assign_role = None
        instance.project_status = 'pending'
        instance.difficulty = None
        instance.file_editable = None
    else:
        instance.current_assignee_id = None
        instance.group_assign_role = None

    current_notes = dict(instance.stage_notes or {})
    current_notes.pop(target['key'], None)
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    current_data.pop(target['key'], None)
    instance.stage_data = current_data

    db.commit()
    db.refresh(instance)

    target_role = STAGE_BY_KEY.get(target['key'], {}).get('role')
    if target_role and target_role != '-':
        _notify_assignment(db, project_id, target['key'], None, target_role, 'rollback')
    return instance


def update_stage_data(
    db: Session,
    project_id: UUID,
    stage_data: dict,
) -> WorkflowInstance:
    """暂存当前阶段的进度表单数据"""
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")

    current_data = dict(instance.stage_data or {})
    current_data[instance.current_stage_key] = stage_data
    instance.stage_data = current_data
    
    _sync_stage_data_to_project(db, project_id, stage_data)

    db.commit()
    db.refresh(instance)
    return instance
