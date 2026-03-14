"""
工作流 CRUD 操作
包含阶段定义、难度过滤逻辑、推进/打回/初始化等核心业务方法
"""
from typing import Optional, List
from uuid import UUID

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


from sqlalchemy import or_
from crud import get_user_roles_with_role_names

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

def init_workflow(db: Session, project_id: UUID) -> WorkflowInstance:
    """为项目创建工作流实例，并写入"进入接稿"的初始日志"""
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
        description='进入接稿（客户专员）',
        note='系统自动初始化',
    )
    db.add(log)
    db.commit()
    db.refresh(instance)
    return instance


# ========== 请假校验 ==========

import datetime as _dt


def _check_on_leave(db: Session, user_id: UUID):
    """检查用户当前是否在请假，是则抛出 ValueError 阻止派发"""
    now = _dt.datetime.now()
    leave = db.query(EmployeeLeave).filter(
        EmployeeLeave.employee_id == user_id,
        EmployeeLeave.start_date <= now,
        EmployeeLeave.end_date >= now,
    ).first()
    if leave:
        raise ValueError(
            f"该用户（{leave.employee_name}）当前处于请假中"
            f"（{leave.start_date.strftime('%Y-%m-%d %H:%M')} ~ {leave.end_date.strftime('%Y-%m-%d %H:%M')}），无法指派任务"
        )


# ========== 设定难度 ==========

import re

def _sync_stage_data_to_project(db: Session, project_id: UUID, stage_data: dict):
    if not stage_data:
        return
    project = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
    if not project:
        return
    
    def to_snake(name):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    for k, v in stage_data.items():
        snake_k = to_snake(k)
        if hasattr(project, snake_k):
            if isinstance(v, str) and v.strip() == '':
                if 'time' in snake_k or 'date' in snake_k:
                    setattr(project, snake_k, None)
                    continue
            setattr(project, snake_k, v)


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
    """客户专员设定难度，推进到下一阶段（支持指定个人或同组指派）"""
    if not next_assignee_id and not group_assign_role:
        raise ValueError("Must specify either next_assignee_id or group_assign_role")

    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")
    if instance.current_stage_key != 'reception':
        raise ValueError("Can only set difficulty at reception stage")

    # 保存当前阶段数据
    current_notes = dict(instance.stage_notes or {})
    current_notes['reception'] = note or '（无备注）'
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    if stage_data:
        current_data['reception'] = stage_data
        _sync_stage_data_to_project(db, project_id, stage_data)
    instance.stage_data = current_data

    # 设置难度
    instance.difficulty = difficulty
    instance.file_editable = file_editable

    # 确定下一阶段
    steps = get_effective_stages(difficulty, file_editable)
    if len(steps) < 2:
        raise ValueError("No next stage available")
    next_stage = steps[1]

    if next_assignee_id:
        # 指定个人：校验是否请假
        _check_on_leave(db, next_assignee_id)
        next_user = db.query(AppUser).filter(AppUser.id == next_assignee_id).first()
        next_user_name = (next_user.full_name or next_user.username) if next_user else ''
        assign_desc = f"指定负责人：{next_user_name}"
        instance.current_assignee_id = next_assignee_id
        instance.group_assign_role = None
    else:
        # 同组指派
        assign_desc = f"同组指派给「{group_assign_role}」组"
        next_assignee_id = None
        instance.current_assignee_id = None
        instance.group_assign_role = group_assign_role

    # 写入日志
    log = WorkflowLog(
        workflow_instance_id=instance.id,
        operator_id=operator_id,
        from_stage='reception',
        to_stage=next_stage['key'],
        direction='forward',
        description=f"确认难度为「{difficulty}」，进入{next_stage['title']}，{assign_desc}",
        note=note,
        next_assignee_id=next_assignee_id,
    )
    db.add(log)

    # 推进
    instance.current_stage_key = next_stage['key']
    instance.project_status = 'in_progress'

    db.commit()
    db.refresh(instance)
    return instance


# ========== 阶段推进 ==========

def transition_forward(
    db: Session,
    project_id: UUID,
    next_assignee_id: Optional[UUID] = None,
    group_assign_role: Optional[str] = None,
    operator_id: Optional[UUID] = None,
    note: Optional[str] = None,
    stage_data: Optional[dict] = None,
) -> WorkflowInstance:
    """完成当前阶段，推进到下一阶段（支持指定个人或同组指派）"""
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")

    steps = get_effective_stages(instance.difficulty, instance.file_editable)
    current_idx = next((i for i, s in enumerate(steps) if s['key'] == instance.current_stage_key), -1)
    if current_idx < 0:
        raise ValueError(f"Current stage '{instance.current_stage_key}' not found in effective stages")

    # 保存当前阶段数据
    current_notes = dict(instance.stage_notes or {})
    current_notes[instance.current_stage_key] = note or '（无备注）'
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    if stage_data:
        current_data[instance.current_stage_key] = stage_data
        _sync_stage_data_to_project(db, project_id, stage_data)
    instance.stage_data = current_data

    current_stage_info = STAGE_BY_KEY.get(instance.current_stage_key, {})
    next_idx = current_idx + 1

    if next_idx >= len(steps):
        # 已是最后一步 → 完成
        instance.current_stage_key = 'completed'
        instance.current_assignee_id = None
        instance.group_assign_role = None
        instance.project_status = 'completed'

        log = WorkflowLog(
            workflow_instance_id=instance.id,
            operator_id=operator_id,
            from_stage=current_stage_info.get('key', ''),
            to_stage='completed',
            direction='forward',
            description=f"从「{current_stage_info.get('title', '')}」进入「完成」",
            note=note,
        )
        db.add(log)
    else:
        next_stage = steps[next_idx]

        if next_stage['key'] == 'completed':
            description = f"从「{current_stage_info.get('title', '')}」进入「完成」"
            instance.project_status = 'completed'
            instance.current_assignee_id = None
            instance.group_assign_role = None
            log_next_assignee_id = None
        elif next_assignee_id:
            # 指定个人
            _check_on_leave(db, next_assignee_id)
            next_user = db.query(AppUser).filter(AppUser.id == next_assignee_id).first()
            next_user_name = (next_user.full_name or next_user.username) if next_user else ''
            description = f"从「{current_stage_info.get('title', '')}」进入「{next_stage['title']}」，指定负责人：{next_user_name}"
            instance.current_assignee_id = next_assignee_id
            instance.group_assign_role = None
            log_next_assignee_id = next_assignee_id
        elif group_assign_role:
            # 同组指派
            description = f"从「{current_stage_info.get('title', '')}」进入「{next_stage['title']}」，同组指派给「{group_assign_role}」组"
            instance.current_assignee_id = None
            instance.group_assign_role = group_assign_role
            log_next_assignee_id = None
        else:
            raise ValueError("Must specify next_assignee_id or group_assign_role for non-completed stages")

        log = WorkflowLog(
            workflow_instance_id=instance.id,
            operator_id=operator_id,
            from_stage=instance.current_stage_key,
            to_stage=next_stage['key'],
            direction='forward',
            description=description,
            note=note,
            next_assignee_id=log_next_assignee_id,
        )
        db.add(log)
        instance.current_stage_key = next_stage['key']

    db.commit()
    db.refresh(instance)
    return instance


# ========== 打回 ==========

def rollback(
    db: Session,
    project_id: UUID,
    steps: int = 1,
    to_start: bool = False,
    note: str = '',
    operator_id: Optional[UUID] = None,
) -> WorkflowInstance:
    """打回操作"""
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise ValueError("Workflow not initialized for this project")

    effective = get_effective_stages(instance.difficulty, instance.file_editable)
    current_idx = next((i for i, s in enumerate(effective) if s['key'] == instance.current_stage_key), -1)
    if current_idx <= 0:
        raise ValueError("Cannot rollback from the first stage")

    target_idx = 0 if to_start else max(0, current_idx - steps)
    target = effective[target_idx]
    current_stage_info = STAGE_BY_KEY.get(instance.current_stage_key, {})

    description = (
        f"打回至初始节点「{target['title']}」" if to_start
        else f"打回至「{target['title']}」"
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
        # 打回到中间环节时，清除指派信息，让重新指派
        instance.current_assignee_id = None
        instance.group_assign_role = None

    # 清除目标阶段的旧备注和数据，允许重新填写
    current_notes = dict(instance.stage_notes or {})
    current_notes.pop(target['key'], None)
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    current_data.pop(target['key'], None)
    instance.stage_data = current_data

    db.commit()
    db.refresh(instance)
    return instance


# ========== 更新阶段进度数据 ==========

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
