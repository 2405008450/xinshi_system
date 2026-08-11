"""
工作流 CRUD 操作
包含阶段定义、难度过滤逻辑、推进/打回/初始化等核心业务方法
"""
from decimal import Decimal
import datetime
from typing import Optional, List
import uuid as _uuid
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, Uuid, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from workflow_models import (
    ProjectManagerHandoverItem,
    ProjectManagerHandoverRequest,
    WorkflowHandoverAttachment,
    WorkflowHandoverItem,
    WorkflowHandoverRequest,
    WorkflowInstance,
    WorkflowLog,
)
from models import ChatProjectAttachment, TranslationProject, TranslationSubOrder, AppUser, Client, EmployeeLeave, ProjectRoleAssignment
from leave_service import ensure_user_assignable
from project_roles import (
    PROJECT_ROLE_NAME_BY_CODE,
    ROLE_NAME_BY_CODE,
    get_stage_role,
)


# ========== 阶段定义（与前端 ALL_STAGES 保持一致） ==========

ALL_STAGES = [
    {'key': 'reception',           'title': '客户专员',   'role': '客户专员', 'role_code': 'customer_specialist'},
    {'key': 'layout_assign',       'title': '排版指派',   'role': '排版专员', 'role_code': 'layout_specialist'},
    {'key': 'project_manager',     'title': '项目经理',   'role': '项目经理', 'role_code': 'project_manager'},
    {'key': 'project_specialist',  'title': '项目专员',   'role': '项目专员', 'role_code': 'project_specialist'},
    {'key': 'project_assistant',   'title': '项目助理',   'role': '项目助理', 'role_code': 'project_assistant'},
    {'key': 'review',              'title': '译审',       'role': '译审', 'role_code': 'reviewer'},
    {'key': 'special_qc',          'title': '专检',       'role': '项目专员', 'role_code': 'project_specialist'},
    {'key': 'layout',              'title': '排版',       'role': '排版专员', 'role_code': 'layout_specialist'},
    {'key': 'completed',           'title': '完成',       'role': '-', 'role_code': 'completed'},
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


def get_workflow_by_sub_order(db: Session, sub_order_id: UUID) -> Optional[WorkflowInstance]:
    return db.query(WorkflowInstance)\
        .filter(WorkflowInstance.sub_order_id == sub_order_id)\
        .first()


def get_workflow_by_id(db: Session, instance_id: UUID) -> Optional[WorkflowInstance]:
    return db.query(WorkflowInstance)\
        .filter(WorkflowInstance.id == instance_id)\
        .first()


def _get_instance(db: Session, project_id: Optional[UUID] = None, sub_order_id: Optional[UUID] = None) -> Optional[WorkflowInstance]:
    """统一查询：按 project_id 或 sub_order_id 获取工作流实例"""
    if project_id:
        return get_workflow_by_project(db, project_id)
    if sub_order_id:
        return get_workflow_by_sub_order(db, sub_order_id)
    return None


from crud import (
    create_notifications_for_users,
    ensure_finance_record_for_project,
    get_user_roles_with_role_names,
    get_users_by_role_names,
)
from notification_ws import dispatch_personal_message

def get_my_tasks(db: Session, user_id: UUID, *, include_all: bool = False) -> list:
    """查询未完成的工作流实例；超级管理员可按需查看全部执行任务。"""
    roles = get_user_roles_with_role_names(db, user_id)
    can_view_all = include_all and not set(roles).isdisjoint(SUPER_TRANSFER_ROLES)
    is_customer_specialist = '客户专员' in roles
    group_filters = [WorkflowInstance.group_assign_role == role for role in roles] if roles else []

    if can_view_all:
        scope_conditions = []
    else:
        if is_customer_specialist:
            base_conditions = [
                WorkflowInstance.current_assignee_id == user_id,
                (WorkflowInstance.current_stage_key == 'reception') & (WorkflowInstance.difficulty == None),
            ]
        else:
            base_conditions = [WorkflowInstance.current_assignee_id == user_id]
        filter_cond = or_(*base_conditions, *group_filters) if group_filters else or_(*base_conditions)
        scope_conditions = [filter_cond]

    # 查询母订单工作流
    proj_query = db.query(WorkflowInstance, TranslationProject, Client)\
        .join(TranslationProject, WorkflowInstance.translation_project_id == TranslationProject.id)\
        .outerjoin(Client, TranslationProject.client_id == Client.id)\
        .filter(*scope_conditions, WorkflowInstance.current_stage_key != 'completed',
                WorkflowInstance.translation_project_id != None)
    proj_results = proj_query.all()

    # 查询子订单工作流
    sub_query = db.query(WorkflowInstance, TranslationSubOrder, TranslationProject, Client)\
        .join(TranslationSubOrder, WorkflowInstance.sub_order_id == TranslationSubOrder.id)\
        .join(TranslationProject, TranslationSubOrder.parent_project_id == TranslationProject.id)\
        .outerjoin(Client, TranslationProject.client_id == Client.id)\
        .filter(*scope_conditions, WorkflowInstance.current_stage_key != 'completed',
                WorkflowInstance.sub_order_id != None)
    sub_results = sub_query.all()

    tasks = []
    for wf, proj, client in proj_results:
        stage_role = get_stage_role(wf.current_stage_key)
        tasks.append({
            'workflow_instance_id': wf.id,
            'translation_project_id': proj.id,
            'sub_order_id': None,
            'order_no': proj.order_no,
            'project_name': proj.project_name,
            'task_type': proj.task_type or '项目任务',
            'consultation_id': proj.consultation_id,
            'sub_project_name': None,
            'client_name': client.client_name if client else '',
            'client_short_name': client.client_short_name if client else '',
            'current_stage_key': wf.current_stage_key,
            'current_stage_role_code': stage_role['role_code'],
            'current_stage_role_name': stage_role['role_name'],
            'current_assignee_id': wf.current_assignee_id,
            'current_assignee_name': (
                (wf.current_assignee.full_name or wf.current_assignee.username)
                if wf.current_assignee else None
            ),
            'group_assign_role': wf.group_assign_role,
            'assignment_type': (
                'direct' if wf.current_assignee_id == user_id
                else 'overview' if can_view_all
                else 'role_pool'
            ),
            'difficulty': wf.difficulty,
            'project_status': wf.project_status,
            'customer_deadline_time': proj.customer_deadline_time,
            'language_pair': proj.language_pair,
            'entity_type': 'project',
            'role_assignments': proj.role_assignments,
        })

    for wf, sub, proj, client in sub_results:
        stage_role = get_stage_role(wf.current_stage_key)
        tasks.append({
            'workflow_instance_id': wf.id,
            'translation_project_id': proj.id,
            'sub_order_id': sub.id,
            'order_no': sub.sub_order_no,
            'project_name': proj.project_name,
            'task_type': proj.task_type or '项目任务',
            'consultation_id': proj.consultation_id,
            'sub_project_name': sub.sub_project_name,
            'client_name': client.client_name if client else '',
            'client_short_name': client.client_short_name if client else '',
            'current_stage_key': wf.current_stage_key,
            'current_stage_role_code': stage_role['role_code'],
            'current_stage_role_name': stage_role['role_name'],
            'current_assignee_id': wf.current_assignee_id,
            'current_assignee_name': (
                (wf.current_assignee.full_name or wf.current_assignee.username)
                if wf.current_assignee else None
            ),
            'group_assign_role': wf.group_assign_role,
            'assignment_type': (
                'direct' if wf.current_assignee_id == user_id
                else 'overview' if can_view_all
                else 'role_pool'
            ),
            'difficulty': wf.difficulty,
            'project_status': wf.project_status,
            'customer_deadline_time': sub.customer_deadline_time,
            'language_pair': sub.language_pair,
            'entity_type': 'suborder',
            'role_assignments': proj.role_assignments,
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


SUPER_TRANSFER_ROLES = {'admin', '超级管理员'}
HANDOVER_TYPE_LABELS = {
    'daily_shift': '每日班次交接',
    'weekend_holiday': '周末/节假日交接',
    'leave_time_off': '请假调休交接',
    'other': '其他',
}


def _required_stage_roles(stage_key: str) -> set[str]:
    role_name = get_stage_role(stage_key)['role_name']
    return {role_name} if role_name and role_name != '-' else set()


def _user_can_take_stage(user_roles: set[str], stage_key: str) -> bool:
    required = _required_stage_roles(stage_key)
    return bool(required and not user_roles.isdisjoint(required))


def _ensure_same_stage_role(instances: list[WorkflowInstance]) -> dict[str, str]:
    if not instances:
        raise ValueError('请至少选择一项任务')
    roles = {
        get_stage_role(instance.current_stage_key)['role_code']: get_stage_role(instance.current_stage_key)
        for instance in instances
    }
    if len(roles) != 1:
        raise ValueError('一次只能交接同一角色类型的任务，请按角色分别操作')
    return next(iter(roles.values()))


def _workflow_query_with_task_details(db: Session):
    return db.query(WorkflowInstance).options(
        joinedload(WorkflowInstance.current_assignee),
        joinedload(WorkflowInstance.translation_project).joinedload(TranslationProject.client),
        joinedload(WorkflowInstance.sub_order)
        .joinedload(TranslationSubOrder.parent_project)
        .joinedload(TranslationProject.client),
    )


def _serialize_transfer_task(instance: WorkflowInstance) -> dict:
    assignee = instance.current_assignee
    assignee_name = (assignee.full_name or assignee.username) if assignee else None
    stage_role = get_stage_role(instance.current_stage_key)
    if instance.sub_order_id and instance.sub_order:
        sub = instance.sub_order
        project = sub.parent_project
        client = project.client if project else None
        return {
            'workflow_instance_id': instance.id,
            'translation_project_id': project.id if project else None,
            'sub_order_id': sub.id,
            'order_no': sub.sub_order_no,
            'project_name': project.project_name if project else '',
            'task_type': (project.task_type or '项目任务') if project else '项目任务',
            'consultation_id': project.consultation_id if project else None,
            'sub_project_name': sub.sub_project_name,
            'client_name': client.client_name if client else '',
            'client_short_name': client.client_short_name if client else '',
            'current_stage_key': instance.current_stage_key,
            'current_stage_role_code': stage_role['role_code'],
            'current_stage_role_name': stage_role['role_name'],
            'current_assignee_id': instance.current_assignee_id,
            'current_assignee_name': assignee_name,
            'group_assign_role': instance.group_assign_role,
            'assignment_type': 'direct',
            'difficulty': instance.difficulty,
            'project_status': instance.project_status,
            'customer_deadline_time': sub.customer_deadline_time,
            'language_pair': sub.language_pair,
            'entity_type': 'suborder',
            'role_assignments': project.role_assignments if project else [],
        }
    project = instance.translation_project
    client = project.client if project else None
    return {
        'workflow_instance_id': instance.id,
        'translation_project_id': project.id if project else None,
        'sub_order_id': None,
        'order_no': project.order_no if project else '',
        'project_name': project.project_name if project else '',
        'task_type': (project.task_type or '项目任务') if project else '项目任务',
        'consultation_id': project.consultation_id if project else None,
        'sub_project_name': None,
        'client_name': client.client_name if client else '',
        'client_short_name': client.client_short_name if client else '',
        'current_stage_key': instance.current_stage_key,
        'current_stage_role_code': stage_role['role_code'],
        'current_stage_role_name': stage_role['role_name'],
        'current_assignee_id': instance.current_assignee_id,
        'current_assignee_name': assignee_name,
        'group_assign_role': instance.group_assign_role,
        'assignment_type': 'direct',
        'difficulty': instance.difficulty,
        'project_status': instance.project_status,
        'customer_deadline_time': project.customer_deadline_time if project else None,
        'language_pair': project.language_pair if project else None,
        'entity_type': 'project',
        'role_assignments': project.role_assignments if project else [],
    }


def get_transferable_tasks(
    db: Session,
    user_id: UUID,
    owner_user_id: Optional[UUID] = None,
    keyword: Optional[str] = None,
) -> list[dict]:
    user_roles = set(get_user_roles_with_role_names(db, user_id))
    query = _workflow_query_with_task_details(db).filter(
        WorkflowInstance.current_assignee_id != None,
        WorkflowInstance.current_assignee_id != user_id,
        WorkflowInstance.current_stage_key != 'completed',
        ~WorkflowInstance.id.in_(
            db.query(WorkflowHandoverItem.workflow_instance_id)
            .join(WorkflowHandoverRequest, WorkflowHandoverRequest.id == WorkflowHandoverItem.request_id)
            .filter(WorkflowHandoverRequest.status == 'pending')
        ),
    )
    if owner_user_id:
        query = query.filter(WorkflowInstance.current_assignee_id == owner_user_id)

    normalized_keyword = (keyword or '').strip().casefold()
    result = []
    for instance in query.all():
        if not _user_can_take_stage(user_roles, instance.current_stage_key):
            continue
        item = _serialize_transfer_task(instance)
        if normalized_keyword:
            haystack = ' '.join(str(item.get(key) or '') for key in (
                'order_no', 'project_name', 'sub_project_name', 'client_name',
                'client_short_name', 'current_assignee_name',
            )).casefold()
            if normalized_keyword not in haystack:
                continue
        result.append(item)
    return result


def get_eligible_transfer_users(db: Session, workflow_instance_ids: list[UUID]) -> list[AppUser]:
    unique_ids = list(dict.fromkeys(workflow_instance_ids))
    instances = (
        db.query(WorkflowInstance)
        .filter(
            WorkflowInstance.id.in_(unique_ids),
            WorkflowInstance.current_assignee_id != None,
            WorkflowInstance.current_stage_key != 'completed',
        )
        .all()
    )
    if len(instances) != len(unique_ids):
        raise ValueError('部分任务不存在、已完成或不是直接分配任务')
    _ensure_same_stage_role(instances)

    eligible = []
    for user in db.query(AppUser).filter(AppUser.is_active == True).order_by(AppUser.full_name, AppUser.username).all():
        roles = set(get_user_roles_with_role_names(db, user.id))
        if all(_user_can_take_stage(roles, instance.current_stage_key) for instance in instances):
            eligible.append(user)
    return eligible


def create_handover_request(
    db: Session,
    requester: AppUser,
    workflow_instance_ids: list[UUID],
    target_user_id: UUID,
    handover_type: str,
    reason_detail: Optional[str] = None,
    content: str = '',
    content_json: Optional[dict] = None,
    attachment_ids: Optional[list[UUID]] = None,
) -> WorkflowHandoverRequest:
    if handover_type == 'other' and not (reason_detail or '').strip():
        raise ValueError('选择“其他”时必须填写交接原因')
    unique_ids = list(dict.fromkeys(workflow_instance_ids))
    instances = (
        db.query(WorkflowInstance)
        .filter(WorkflowInstance.id.in_(unique_ids))
        .with_for_update()
        .all()
    )
    if len(instances) != len(unique_ids):
        raise LookupError('部分任务不存在')
    _ensure_same_stage_role(instances)
    if any(
        instance.current_assignee_id != requester.id or instance.current_stage_key == 'completed'
        for instance in instances
    ):
        raise PermissionError('只能交接当前用户直接负责的未完成任务')
    if target_user_id == requester.id:
        raise ValueError('请选择其他接收人')

    target = db.query(AppUser).filter(AppUser.id == target_user_id, AppUser.is_active == True).first()
    if target is None:
        raise ValueError('接收用户不存在或已停用')
    ensure_user_assignable(db, target.id)
    target_roles = set(get_user_roles_with_role_names(db, target.id))
    if any(not _user_can_take_stage(target_roles, instance.current_stage_key) for instance in instances):
        raise PermissionError('接收用户不具备部分任务当前阶段所需角色')

    existing_pending = (
        db.query(WorkflowHandoverItem.id)
        .join(WorkflowHandoverRequest, WorkflowHandoverRequest.id == WorkflowHandoverItem.request_id)
        .filter(
            WorkflowHandoverItem.workflow_instance_id.in_(unique_ids),
            WorkflowHandoverRequest.status == 'pending',
        )
        .first()
    )
    if existing_pending:
        raise LookupError('部分任务已有待确认交接，请勿重复提交')

    attachment_ids = list(dict.fromkeys(attachment_ids or []))
    attachments = []
    if attachment_ids:
        attachments = (
            db.query(ChatProjectAttachment)
            .filter(
                ChatProjectAttachment.id.in_(attachment_ids),
                ChatProjectAttachment.uploaded_by == requester.id,
            )
            .all()
        )
        if len(attachments) != len(attachment_ids):
            raise ValueError('部分图片不存在或不属于当前用户')

    from project_chat_crud import normalize_rich_text_json, rich_text_to_plain
    normalized_content_json = normalize_rich_text_json(content_json)
    normalized_content = (content or '').strip()
    if normalized_content_json:
        normalized_content = rich_text_to_plain(normalized_content_json) or normalized_content

    request = WorkflowHandoverRequest(
        requester_id=requester.id,
        target_user_id=target.id,
        handover_type=handover_type,
        reason_detail=(reason_detail or '').strip() or None,
        content=normalized_content[:10000],
        content_json=normalized_content_json,
        status='pending',
    )
    db.add(request)
    db.flush()
    db.add_all(
        WorkflowHandoverItem(
            request_id=request.id,
            workflow_instance_id=instance.id,
            expected_assignee_id=requester.id,
        )
        for instance in instances
    )
    db.add_all(
        WorkflowHandoverAttachment(request_id=request.id, attachment_id=attachment.id)
        for attachment in attachments
    )

    first_instance = instances[0]
    related_project_id = first_instance.translation_project_id
    if first_instance.sub_order_id:
        sub = db.query(TranslationSubOrder).filter(TranslationSubOrder.id == first_instance.sub_order_id).first()
        related_project_id = sub.parent_project_id if sub else None
    requester_name = requester.full_name or requester.username
    notifications = create_notifications_for_users(
        db,
        recipient_user_ids=[target.id],
        title='待确认的项目交接',
        content=f'{requester_name} 向你发起了 {len(instances)} 项任务交接，请进入“工作台”确认接收。',
        notification_type='workflow_handover_pending',
        related_project_id=related_project_id,
        commit=False,
    )
    db.commit()
    db.refresh(request)
    _push_notifications(notifications)
    return request


def list_incoming_handover_requests(
    db: Session,
    target_user_id: UUID,
    status_filter: str = 'pending',
) -> list[WorkflowHandoverRequest]:
    return (
        db.query(WorkflowHandoverRequest)
        .options(
            joinedload(WorkflowHandoverRequest.requester),
            joinedload(WorkflowHandoverRequest.target_user),
            selectinload(WorkflowHandoverRequest.items)
            .selectinload(WorkflowHandoverItem.workflow_instance)
            .joinedload(WorkflowInstance.current_assignee),
            selectinload(WorkflowHandoverRequest.attachment_links)
            .joinedload(WorkflowHandoverAttachment.attachment),
        )
        .filter(
            WorkflowHandoverRequest.target_user_id == target_user_id,
            WorkflowHandoverRequest.status == status_filter,
        )
        .order_by(WorkflowHandoverRequest.created_at.desc())
        .all()
    )


def serialize_handover_request(request: WorkflowHandoverRequest) -> dict:
    requester_name = (
        request.requester.full_name or request.requester.username
        if request.requester else None
    )
    target_name = (
        request.target_user.full_name or request.target_user.username
        if request.target_user else None
    )
    tasks = []
    for item in request.items or []:
        instance = item.workflow_instance
        if instance is None:
            continue
        # 查询列表已加载负责人；项目关系在此按需加载，保持响应与“我的任务”一致。
        tasks.append(_serialize_transfer_task(instance))
    attachments = [
        {
            'id': link.attachment.id,
            'original_name': link.attachment.original_name,
            'content_type': link.attachment.content_type,
            'file_size': link.attachment.file_size,
        }
        for link in (request.attachment_links or [])
        if link.attachment
    ]
    return {
        'id': request.id,
        'requester_id': request.requester_id,
        'requester_name': requester_name,
        'target_user_id': request.target_user_id,
        'target_user_name': target_name,
        'handover_type': request.handover_type,
        'reason_detail': request.reason_detail,
        'content': request.content,
        'content_json': request.content_json,
        'status': request.status,
        'decision_note': request.decision_note,
        'created_at': request.created_at,
        'decided_at': request.decided_at,
        'tasks': tasks,
        'attachments': attachments,
    }


def serialize_managed_project(project: TranslationProject) -> dict:
    selected_client = project.sub_client or project.client
    workflow = project.workflow_instance
    current_assignee = workflow.current_assignee if workflow else None
    stage_role = get_stage_role(workflow.current_stage_key) if workflow else {
        'role_code': None,
        'role_name': None,
    }
    return {
        'translation_project_id': project.id,
        'order_no': project.order_no,
        'project_name': project.project_name,
        'task_type': project.task_type or '项目任务',
        'client_short_name': selected_client.client_short_name if selected_client else None,
        'project_status': project.project_status,
        'difficulty': workflow.difficulty if workflow else None,
        'language_pair': project.language_pair,
        'customer_deadline_time': project.customer_deadline_time,
        'current_assignee_id': workflow.current_assignee_id if workflow else None,
        'current_assignee_name': (
            (current_assignee.full_name or current_assignee.username)
            if current_assignee else None
        ),
        'group_assign_role': workflow.group_assign_role if workflow else None,
        'current_stage_role_code': stage_role['role_code'],
        'current_stage_role_name': stage_role['role_name'],
        'role_assignments': project.role_assignments,
        'project_manager_id': project.project_manager_id,
        'project_manager_name': project.project_manager_name,
    }


def get_management_projects(db: Session, current_user: AppUser) -> list[dict]:
    """返回当前项目经理负责或可承接的项目；超级管理员可查看全部管理归属。"""
    roles = set(get_user_roles_with_role_names(db, current_user.id))
    is_super = bool(roles & SUPER_TRANSFER_ROLES)
    if '项目经理' not in roles and not is_super:
        return []

    query = (
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.client),
            selectinload(TranslationProject.sub_client),
            selectinload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .selectinload(ProjectRoleAssignment.assignee),
            selectinload(TranslationProject.workflow_instance)
            .selectinload(WorkflowInstance.current_assignee),
        )
        .filter(
            func.coalesce(TranslationProject.project_status, '').notin_(
                ['completed', 'terminated', 'cancelled', 'partially_cancelled']
            )
        )
    )
    if not is_super:
        query = query.filter(
            or_(
                TranslationProject.project_manager_id == current_user.id,
                TranslationProject.project_manager_id.is_(None),
            )
        )

    return [
        serialize_managed_project(project)
        for project in query.order_by(
            TranslationProject.customer_deadline_time.asc().nullslast(),
            TranslationProject.created_at.desc(),
        ).all()
    ]


def get_project_manager_candidates(
    db: Session,
    current_user_id: UUID,
    include_current: bool = False,
) -> list[AppUser]:
    """仅返回可作为管理主负责人的启用项目经理。"""
    return sorted(
        (
            user for user in get_users_by_role_names(db, ['项目经理'])
            if include_current or user.id != current_user_id
        ),
        key=lambda user: ((user.full_name or '').casefold(), user.username.casefold()),
    )


def get_project_role_candidates(db: Session, role_code: str) -> list[AppUser]:
    """按稳定角色编码返回启用用户，不接受前端传入任意角色名称。"""
    role_name = ROLE_NAME_BY_CODE.get(role_code)
    if not role_name:
        raise ValueError('不支持的项目角色编码')
    return sorted(
        get_users_by_role_names(db, [role_name]),
        key=lambda user: ((user.full_name or '').casefold(), user.username.casefold()),
    )


def claim_management_projects(
    db: Session,
    current_user: AppUser,
    translation_project_ids: list[UUID],
) -> list[TranslationProject]:
    """项目经理直接承接尚未绑定管理主负责人的项目。"""
    roles = set(get_user_roles_with_role_names(db, current_user.id))
    if '项目经理' not in roles:
        raise PermissionError('只有项目经理可以自主承接未绑定的管理项目')
    ensure_user_assignable(db, current_user.id)

    unique_ids = list(dict.fromkeys(translation_project_ids))
    if not unique_ids:
        raise ValueError('请至少选择一个需要承接的管理项目')

    projects = (
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.client),
            selectinload(TranslationProject.sub_client),
            selectinload(TranslationProject.project_manager),
        )
        .filter(
            TranslationProject.id.in_(unique_ids),
            func.coalesce(TranslationProject.project_status, '').notin_(
                ['completed', 'terminated', 'cancelled', 'partially_cancelled']
            ),
        )
        .with_for_update()
        .all()
    )
    if len(projects) != len(unique_ids):
        raise LookupError('部分管理项目不存在或已不再允许承接')
    if any(project.project_manager_id is not None for project in projects):
        raise LookupError('部分项目已被其他项目经理承接，请刷新后重试')

    pending_project_ids = {
        row.translation_project_id
        for row in (
            db.query(ProjectManagerHandoverItem.translation_project_id)
            .join(
                ProjectManagerHandoverRequest,
                ProjectManagerHandoverRequest.id == ProjectManagerHandoverItem.request_id,
            )
            .filter(
                ProjectManagerHandoverRequest.status == 'pending',
                ProjectManagerHandoverItem.translation_project_id.in_(unique_ids),
            )
            .all()
        )
    }
    if pending_project_ids:
        raise LookupError('部分项目已有待确认的管理层交接，暂不能自主承接')

    for project in projects:
        project.project_manager_id = current_user.id

    db.commit()
    for project in projects:
        db.refresh(project)
    return projects


def create_project_manager_handover(
    db: Session,
    requester: AppUser,
    translation_project_ids: list[UUID],
    target_manager_id: UUID,
    reason: Optional[str] = None,
    note: Optional[str] = None,
) -> ProjectManagerHandoverRequest:
    """发起管理层项目归属交接，不改变执行工作流当前处理人。"""
    requester_roles = set(get_user_roles_with_role_names(db, requester.id))
    is_super = bool(requester_roles & SUPER_TRANSFER_ROLES)
    if '项目经理' not in requester_roles and not is_super:
        raise PermissionError('只有项目经理或超级管理员可以发起管理层项目交接')
    if target_manager_id == requester.id:
        raise ValueError('请选择其他项目经理作为接收人')

    target = db.query(AppUser).filter(
        AppUser.id == target_manager_id,
        AppUser.is_active == True,
    ).first()
    if not target or '项目经理' not in get_user_roles_with_role_names(db, target.id):
        raise ValueError('接收人必须是启用中的项目经理')
    ensure_user_assignable(db, target.id)

    unique_ids = list(dict.fromkeys(translation_project_ids))
    if not unique_ids:
        raise ValueError('请至少选择一个需要交接的管理项目')
    projects = (
        db.query(TranslationProject)
        .filter(TranslationProject.id.in_(unique_ids))
        .with_for_update()
        .all()
    )
    if len(projects) != len(unique_ids):
        raise LookupError('部分管理项目不存在')
    if not is_super and any(project.project_manager_id != requester.id for project in projects):
        raise PermissionError('只能交接当前用户作为管理主负责人的项目')

    pending_project_ids = {
        row.translation_project_id
        for row in (
            db.query(ProjectManagerHandoverItem.translation_project_id)
            .join(
                ProjectManagerHandoverRequest,
                ProjectManagerHandoverRequest.id == ProjectManagerHandoverItem.request_id,
            )
            .filter(
                ProjectManagerHandoverRequest.status == 'pending',
                ProjectManagerHandoverItem.translation_project_id.in_(unique_ids),
            )
            .all()
        )
    }
    if pending_project_ids:
        raise LookupError('部分项目已有待确认的管理层交接，请勿重复提交')

    request = ProjectManagerHandoverRequest(
        requester_id=requester.id,
        target_manager_id=target.id,
        reason=(reason or '').strip() or None,
        note=(note or '').strip() or None,
    )
    db.add(request)
    db.flush()
    db.add_all(
        ProjectManagerHandoverItem(
            request_id=request.id,
            translation_project_id=project.id,
            expected_manager_id=project.project_manager_id,
        )
        for project in projects
    )

    requester_name = requester.full_name or requester.username
    notifications = create_notifications_for_users(
        db,
        recipient_user_ids=[target.id],
        title='待确认的管理层项目交接',
        content=f'{requester_name} 向你发起了 {len(projects)} 个项目的管理主负责人交接。',
        notification_type='project_manager_handover_pending',
        related_project_id=projects[0].id if projects else None,
        commit=False,
    )
    db.commit()
    db.refresh(request)
    _push_notifications(notifications)
    return request


def list_incoming_project_manager_handovers(
    db: Session,
    target_manager_id: UUID,
    status_filter: str = 'pending',
) -> list[ProjectManagerHandoverRequest]:
    return (
        db.query(ProjectManagerHandoverRequest)
        .options(
            joinedload(ProjectManagerHandoverRequest.requester),
            joinedload(ProjectManagerHandoverRequest.target_manager),
            selectinload(ProjectManagerHandoverRequest.items)
            .joinedload(ProjectManagerHandoverItem.project),
        )
        .filter(
            ProjectManagerHandoverRequest.target_manager_id == target_manager_id,
            ProjectManagerHandoverRequest.status == status_filter,
        )
        .order_by(ProjectManagerHandoverRequest.created_at.desc())
        .all()
    )


def serialize_project_manager_handover(request: ProjectManagerHandoverRequest) -> dict:
    requester_name = (
        request.requester.full_name or request.requester.username
        if request.requester else None
    )
    target_name = (
        request.target_manager.full_name or request.target_manager.username
        if request.target_manager else None
    )
    return {
        'id': request.id,
        'requester_id': request.requester_id,
        'requester_name': requester_name,
        'target_manager_id': request.target_manager_id,
        'target_manager_name': target_name,
        'reason': request.reason,
        'note': request.note,
        'status': request.status,
        'decision_note': request.decision_note,
        'created_at': request.created_at,
        'decided_at': request.decided_at,
        'projects': [
            serialize_managed_project(item.project)
            for item in (request.items or [])
            if item.project
        ],
    }


def decide_project_manager_handover(
    db: Session,
    request_id: UUID,
    current_user: AppUser,
    decision: str,
    decision_note: Optional[str] = None,
) -> ProjectManagerHandoverRequest:
    if decision not in {'accept', 'reject'}:
        raise ValueError('不支持的管理层交接处理类型')
    request = (
        db.query(ProjectManagerHandoverRequest)
        .options(
            joinedload(ProjectManagerHandoverRequest.requester),
            joinedload(ProjectManagerHandoverRequest.target_manager),
            selectinload(ProjectManagerHandoverRequest.items)
            .joinedload(ProjectManagerHandoverItem.project),
        )
        .filter(ProjectManagerHandoverRequest.id == request_id)
        # joinedload 会为申请人和接收人生成 LEFT OUTER JOIN。PostgreSQL 不允许
        # 对外连接的可空侧执行 FOR UPDATE，因此这里只锁定交接申请主表。
        .with_for_update(of=ProjectManagerHandoverRequest)
        .first()
    )
    if not request:
        raise LookupError('管理层交接申请不存在')
    if request.target_manager_id != current_user.id:
        raise PermissionError('只能处理发给当前用户的管理层交接')
    if request.status != 'pending':
        raise LookupError('该管理层交接申请已处理')

    if decision == 'accept':
        ensure_user_assignable(db, current_user.id)
        if '项目经理' not in get_user_roles_with_role_names(db, current_user.id):
            raise PermissionError('当前用户已不具备项目经理角色，不能接收管理层项目归属')
        item_project_ids = [
            item.translation_project_id
            for item in (request.items or [])
        ]
        locked_projects = {
            project.id: project
            for project in (
                db.query(TranslationProject)
                .filter(TranslationProject.id.in_(item_project_ids))
                .with_for_update()
                .all()
            )
        }
        for item in request.items or []:
            project = locked_projects.get(item.translation_project_id)
            if not project:
                raise LookupError('交接申请中的项目已不存在')
            if project.project_manager_id != item.expected_manager_id:
                raise LookupError('部分项目的管理主负责人已变化，请拒绝后重新发起')
        for item in request.items or []:
            locked_projects[item.translation_project_id].project_manager_id = current_user.id
        request.status = 'accepted'
    else:
        request.status = 'rejected'

    request.decision_note = (decision_note or '').strip() or None
    request.decided_by = current_user.id
    request.decided_at = datetime.datetime.now()

    current_name = current_user.full_name or current_user.username
    notifications = []
    if request.requester_id:
        notifications = create_notifications_for_users(
            db,
            recipient_user_ids=[request.requester_id],
            title='管理层项目交接已确认' if decision == 'accept' else '管理层项目交接已拒绝',
            content=(
                f'{current_name} 已确认接收 {len(request.items or [])} 个项目的管理主负责人归属。'
                if decision == 'accept'
                else f'{current_name} 拒绝了管理层项目交接。'
            ),
            notification_type=f'project_manager_handover_{request.status}',
            related_project_id=(
                request.items[0].translation_project_id
                if request.items else None
            ),
            commit=False,
        )
    db.commit()
    db.refresh(request)
    _push_notifications(notifications)
    return request


def transfer_workflow_tasks(
    db: Session,
    operator: AppUser,
    workflow_instance_ids: list[UUID],
    action: str,
    target_user_id: Optional[UUID] = None,
    content: str = '',
    content_json: Optional[dict] = None,
    attachment_ids: Optional[list[UUID]] = None,
    expected_assignee_ids: Optional[dict[UUID, UUID]] = None,
    commit: bool = True,
) -> dict:
    if action not in {'handover', 'claim'}:
        raise ValueError('不支持的交接类型')
    unique_ids = list(dict.fromkeys(workflow_instance_ids))
    instances = (
        db.query(WorkflowInstance)
        .filter(WorkflowInstance.id.in_(unique_ids))
        .with_for_update()
        .all()
    )
    if len(instances) != len(unique_ids):
        raise LookupError('部分任务不存在或已发生变化')

    if action == 'handover':
        _ensure_same_stage_role(instances)
        expected_assignee_ids = expected_assignee_ids or {}
        if expected_assignee_ids and any(
            expected_assignee_ids.get(instance.id) != instance.current_assignee_id
            for instance in instances
        ):
            raise LookupError('部分任务负责人已发生变化，请刷新后重新发起交接')
        if any(instance.current_assignee_id != operator.id for instance in instances):
            raise PermissionError('只能交接当前用户直接负责的任务')
        if not target_user_id or target_user_id == operator.id:
            raise ValueError('请选择其他接收人')
        target_id = target_user_id
    else:
        pending_handover = (
            db.query(WorkflowHandoverItem.id)
            .join(WorkflowHandoverRequest, WorkflowHandoverRequest.id == WorkflowHandoverItem.request_id)
            .filter(
                WorkflowHandoverItem.workflow_instance_id.in_(unique_ids),
                WorkflowHandoverRequest.status == 'pending',
            )
            .first()
        )
        if pending_handover:
            raise LookupError('部分任务正在等待交接确认，暂不能自行继承')
        expected_assignee_ids = expected_assignee_ids or {}
        if any(
            expected_assignee_ids.get(instance.id) != instance.current_assignee_id
            for instance in instances
        ):
            raise LookupError('部分任务负责人已发生变化，请刷新后重试')
        if any(
            not instance.current_assignee_id or instance.current_assignee_id == operator.id
            for instance in instances
        ):
            raise PermissionError('只能继承其他用户直接负责的任务')
        target_id = operator.id

    if any(instance.current_stage_key == 'completed' for instance in instances):
        raise LookupError('已完成任务不能交接或继承')

    target = db.query(AppUser).filter(AppUser.id == target_id, AppUser.is_active == True).first()
    if target is None:
        raise ValueError('接收用户不存在或已停用')
    ensure_user_assignable(db, target.id)
    target_roles = set(get_user_roles_with_role_names(db, target.id))
    if any(not _user_can_take_stage(target_roles, instance.current_stage_key) for instance in instances):
        raise PermissionError('接收用户不具备部分任务当前阶段所需角色')

    operator_name = operator.full_name or operator.username
    target_name = target.full_name or target.username
    plain_note = (content or '').strip()
    grouped: dict[UUID, dict] = {}

    for instance in instances:
        source = instance.current_assignee
        source_name = (source.full_name or source.username) if source else '未知用户'
        project = instance.translation_project
        task_name = project.project_name if project else ''
        order_no = project.order_no if project else ''
        project_id = instance.translation_project_id
        if instance.sub_order_id and instance.sub_order:
            sub = instance.sub_order
            project = sub.parent_project
            project_id = sub.parent_project_id
            order_no = sub.sub_order_no
            task_name = sub.sub_project_name or project.project_name
        if project_id is None:
            raise LookupError('任务未关联有效项目')

        description = (
            f'{operator_name} 将任务从 {source_name} 交接给 {target_name}'
            if action == 'handover'
            else f'{target_name} 从 {source_name} 处继承任务'
        )
        db.add(WorkflowLog(
            workflow_instance_id=instance.id,
            operator_id=operator.id,
            from_stage=instance.current_stage_key,
            to_stage=instance.current_stage_key,
            direction=action,
            description=f'{description}：{order_no} / {task_name}',
            note=plain_note,
            next_assignee_id=target.id,
        ))
        instance.current_assignee_id = target.id
        instance.group_assign_role = None
        instance.updated_at = _dt.datetime.utcnow()
        grouped.setdefault(project_id, {'project': project, 'tasks': [], 'sources': set()})
        grouped[project_id]['tasks'].append({
            'workflow_instance_id': str(instance.id),
            'order_no': order_no,
            'task_name': task_name,
            'entity_type': 'suborder' if instance.sub_order_id else 'project',
            'from_user_id': str(source.id) if source else None,
            'from_user_name': source_name,
            'to_user_id': str(target.id),
            'to_user_name': target_name,
        })
        if source:
            grouped[project_id]['sources'].add(source.id)

    default_content = (
        f'{operator_name} 已将所选任务交接给 {target_name}'
        if action == 'handover'
        else f'{target_name} 已自行继承所选任务'
    )
    message_content = plain_note or default_content
    notifications = []
    from project_chat_crud import create_project_chat_message

    for project_id, group in grouped.items():
        project = group['project']
        task_summary = '、'.join(item['order_no'] for item in group['tasks'])
        create_project_chat_message(
            db,
            project_id=project_id,
            sender=operator,
            content=message_content,
            content_json=content_json,
            attachment_ids=attachment_ids,
            message_type=action,
            event_data={
                'action': action,
                'operator_id': str(operator.id),
                'operator_name': operator_name,
                'tasks': group['tasks'],
            },
            bypass_enabled=True,
            commit=False,
            notify=False,
        )
        recipients = [target.id] if action == 'handover' else list(group['sources'])
        recipients = [recipient for recipient in recipients if recipient != operator.id]
        if recipients:
            notifications.extend(create_notifications_for_users(
                db,
                recipient_user_ids=recipients,
                title='项目任务交接' if action == 'handover' else '项目任务已被继承',
                content=f'{project.order_no} / {project.project_name}：{task_summary}。{message_content[:120]}',
                notification_type=f'workflow_{action}',
                related_project_id=project_id,
                commit=False,
            ))

    result = {
        'action': action,
        'transferred_count': len(instances),
        'workflow_instance_ids': unique_ids,
    }
    if commit:
        db.commit()
        _push_notifications(notifications)
    else:
        db.flush()
        result['_notifications'] = notifications
    return result


def claim_role_pool_tasks(
    db: Session,
    operator: AppUser,
    workflow_instance_ids: list[UUID],
) -> dict:
    """将当前用户有权处理的无人负责角色池任务直接绑定给本人。"""
    unique_ids = list(dict.fromkeys(workflow_instance_ids))
    if not unique_ids:
        raise ValueError('请至少选择一个角色池任务')

    ensure_user_assignable(db, operator.id)
    operator_roles = set(get_user_roles_with_role_names(db, operator.id))
    instances = (
        db.query(WorkflowInstance)
        .filter(WorkflowInstance.id.in_(unique_ids))
        .with_for_update()
        .all()
    )
    if len(instances) != len(unique_ids):
        raise LookupError('部分角色池任务不存在或已发生变化')

    def can_claim(instance: WorkflowInstance) -> bool:
        if instance.current_assignee_id is not None or instance.current_stage_key == 'completed':
            return False
        if instance.group_assign_role:
            return (
                instance.group_assign_role in operator_roles
                and _user_can_take_stage(operator_roles, instance.current_stage_key)
            )
        # 客户专员接单阶段的兼容角色池：历史数据可能尚未写入 group_assign_role。
        return (
            '客户专员' in operator_roles
            and instance.current_stage_key == 'reception'
            and instance.difficulty is None
        )

    if any(not can_claim(instance) for instance in instances):
        raise PermissionError('部分任务已被承接，或当前用户不具备对应角色池权限')

    operator_name = operator.full_name or operator.username
    for instance in instances:
        pool_name = instance.group_assign_role or '客户专员'
        db.add(WorkflowLog(
            workflow_instance_id=instance.id,
            operator_id=operator.id,
            from_stage=instance.current_stage_key,
            to_stage=instance.current_stage_key,
            direction='claim_pool',
            description=f'{operator_name} 从“{pool_name}”角色池自主承接任务',
            next_assignee_id=operator.id,
        ))
        instance.current_assignee_id = operator.id
        instance.group_assign_role = None
        instance.updated_at = _dt.datetime.utcnow()

    db.commit()
    return {
        'action': 'role_pool_claim',
        'transferred_count': len(instances),
        'workflow_instance_ids': unique_ids,
    }


def decide_handover_request(
    db: Session,
    request_id: UUID,
    target_user: AppUser,
    decision: str,
    note: Optional[str] = None,
) -> WorkflowHandoverRequest:
    if decision not in {'accept', 'reject'}:
        raise ValueError('不支持的处理方式')
    request = (
        db.query(WorkflowHandoverRequest)
        .filter(WorkflowHandoverRequest.id == request_id)
        .with_for_update()
        .first()
    )
    if request is None:
        raise LookupError('交接申请不存在')
    if request.target_user_id != target_user.id:
        raise PermissionError('只能处理发给当前用户的交接申请')
    if request.status != 'pending':
        raise LookupError('该交接申请已处理')

    notifications = []
    if decision == 'accept':
        ensure_user_assignable(db, target_user.id)
        items = db.query(WorkflowHandoverItem).filter(WorkflowHandoverItem.request_id == request.id).all()
        if not items:
            raise LookupError('交接申请中没有有效任务')
        requester = db.query(AppUser).filter(AppUser.id == request.requester_id).first()
        if requester is None:
            raise LookupError('原负责人不存在，无法完成交接')
        attachment_ids = [
            row[0]
            for row in db.query(WorkflowHandoverAttachment.attachment_id)
            .filter(WorkflowHandoverAttachment.request_id == request.id)
            .all()
        ]
        reason_label = HANDOVER_TYPE_LABELS.get(request.handover_type, request.handover_type)
        if request.handover_type == 'other' and request.reason_detail:
            reason_label = f'{reason_label}：{request.reason_detail}'
        reason_text = f'交接类型：{reason_label}'
        combined_content = f'{reason_text}\n{request.content}'.strip()
        existing_nodes = list((request.content_json or {}).get('content') or [])
        combined_content_json = {
            'type': 'doc',
            'content': [
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': reason_text, 'marks': [{'type': 'bold'}]}]},
                *existing_nodes,
            ],
        }
        result = transfer_workflow_tasks(
            db,
            operator=requester,
            workflow_instance_ids=[item.workflow_instance_id for item in items],
            action='handover',
            target_user_id=target_user.id,
            content=combined_content,
            content_json=combined_content_json,
            attachment_ids=attachment_ids,
            expected_assignee_ids={
                item.workflow_instance_id: item.expected_assignee_id
                for item in items
            },
            commit=False,
        )
        notifications.extend(result.pop('_notifications', []))
        request.status = 'accepted'
    else:
        request.status = 'rejected'

    request.decision_note = (note or '').strip() or None
    request.decided_by = target_user.id
    request.decided_at = _dt.datetime.utcnow()
    target_name = target_user.full_name or target_user.username
    if request.requester_id:
        notifications.extend(create_notifications_for_users(
            db,
            recipient_user_ids=[request.requester_id],
            title='交接已确认' if decision == 'accept' else '交接已拒绝',
            content=(
                f'{target_name} 已确认接收你发起的任务交接。'
                if decision == 'accept'
                else f'{target_name} 拒绝了你发起的任务交接。'
            ),
            notification_type=f'workflow_handover_{request.status}',
            commit=False,
        ))
    db.commit()
    db.refresh(request)
    _push_notifications(notifications)
    return request


def _get_assignment_recipients(db: Session, next_assignee_id: Optional[UUID], group_assign_role: Optional[str]) -> list[UUID]:
    if next_assignee_id:
        return [next_assignee_id]
    if group_assign_role:
        return [user.id for user in get_users_by_role_names(db, [group_assign_role])]
    return []


def _notify_assignment(
    db: Session,
    project_id: Optional[UUID],
    stage_key: str,
    next_assignee_id: Optional[UUID],
    group_assign_role: Optional[str],
    action: str,
    sub_order_id: Optional[UUID] = None,
) -> None:
    recipients = _get_assignment_recipients(db, next_assignee_id, group_assign_role)
    if not recipients:
        return

    stage_info = STAGE_BY_KEY.get(stage_key, {})
    stage_title = stage_info.get('title') or stage_key
    title = 'Workflow Task Updated'

    if sub_order_id:
        sub = db.query(TranslationSubOrder).filter(TranslationSubOrder.id == sub_order_id).first()
        if not sub:
            return
        order_no = sub.sub_order_no
        name = sub.sub_project_name or order_no
        related_project_id = sub.parent_project_id
    else:
        project = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
        if not project:
            return
        order_no = project.order_no
        name = project.project_name
        related_project_id = project.id

    if action == 'assigned':
        content = f'{order_no} / {name} has entered {stage_title}. Please handle it.'
        notification_type = 'workflow_assign'
    else:
        content = f'{order_no} / {name} was rolled back to {stage_title}. Please review it.'
        notification_type = 'workflow_rollback'

    notifications = create_notifications_for_users(
        db,
        recipient_user_ids=recipients,
        title=title,
        content=content,
        notification_type=notification_type,
        related_project_id=related_project_id,
        commit=True,
    )
    _push_notifications(notifications)


def init_workflow(
    db: Session,
    project_id: Optional[UUID] = None,
    sub_order_id: Optional[UUID] = None,
    commit: bool = True,
) -> WorkflowInstance:
    if not project_id and not sub_order_id:
        raise ValueError("Must specify either project_id or sub_order_id")

    existing = _get_instance(db, project_id=project_id, sub_order_id=sub_order_id)
    if existing:
        return existing

    instance = WorkflowInstance(
        translation_project_id=project_id,
        sub_order_id=sub_order_id,
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
    if commit:
        db.commit()
        db.refresh(instance)
    else:
        db.flush()
    return instance


import datetime as _dt


def _check_on_leave(db: Session, user_id: UUID):
    ensure_user_assignable(db, user_id)


def _get_parent_project_for_workflow(
    db: Session,
    project_id: Optional[UUID],
    sub_order_id: Optional[UUID],
) -> Optional[TranslationProject]:
    target_project_id = project_id
    if sub_order_id:
        sub_order = db.query(TranslationSubOrder).filter(
            TranslationSubOrder.id == sub_order_id
        ).first()
        target_project_id = sub_order.parent_project_id if sub_order else None
    if not target_project_id:
        return None
    return (
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .selectinload(ProjectRoleAssignment.assignee),
        )
        .filter(TranslationProject.id == target_project_id)
        .first()
    )


def _configured_project_role_assignee_id(
    project: Optional[TranslationProject], role_code: str
) -> Optional[UUID]:
    if not project:
        return None
    if role_code == 'project_manager':
        return project.project_manager_id
    for assignment in project.project_role_assignments or []:
        if assignment.role_code == role_code:
            return assignment.assignee_id
    return None


def _validate_stage_assignee(db: Session, user_id: UUID, stage_key: str) -> AppUser:
    user = db.query(AppUser).filter(
        AppUser.id == user_id,
        AppUser.is_active == True,
    ).first()
    if not user:
        raise ValueError('下一环节负责人不存在或已停用')
    roles = set(get_user_roles_with_role_names(db, user.id))
    if not _user_can_take_stage(roles, stage_key):
        role_name = get_stage_role(stage_key)['role_name']
        raise ValueError(f'下一环节负责人必须拥有“{role_name}”角色')
    ensure_user_assignable(db, user.id)
    return user


def _resolve_stage_assignment(
    db: Session,
    *,
    stage_key: str,
    project_id: Optional[UUID],
    sub_order_id: Optional[UUID],
    next_assignee_id: Optional[UUID],
    group_assign_role: Optional[str],
) -> tuple[Optional[UUID], Optional[str]]:
    """显式选择优先；未选择时使用项目固定角色，否则进入准确角色池。"""
    stage_role = get_stage_role(stage_key)
    role_name = stage_role['role_name']
    if next_assignee_id:
        _validate_stage_assignee(db, next_assignee_id, stage_key)
        return next_assignee_id, None
    if group_assign_role:
        if group_assign_role != role_name:
            raise ValueError(f'下一环节只能指派给“{role_name}”角色池')
        return None, role_name

    project = _get_parent_project_for_workflow(db, project_id, sub_order_id)
    configured_id = _configured_project_role_assignee_id(
        project, stage_role['role_code']
    )
    if configured_id:
        try:
            _validate_stage_assignee(db, configured_id, stage_key)
            return configured_id, None
        except ValueError:
            # 固定负责人停用、失去角色或请假时，安全回退到对应角色池。
            pass
    return None, role_name if role_name != '-' else None


import re

def _sync_stage_data_to_project(db: Session, project_id: Optional[UUID], stage_data: dict, sub_order_id: Optional[UUID] = None):
    if not stage_data:
        return
    if sub_order_id:
        project = db.query(TranslationSubOrder).filter(TranslationSubOrder.id == sub_order_id).first()
    else:
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
    project_id: Optional[UUID] = None,
    difficulty: str = '',
    file_editable: bool = True,
    next_assignee_id: Optional[UUID] = None,
    group_assign_role: Optional[str] = None,
    operator_id: Optional[UUID] = None,
    note: Optional[str] = None,
    stage_data: Optional[dict] = None,
    sub_order_id: Optional[UUID] = None,
) -> WorkflowInstance:
    instance = _get_instance(db, project_id=project_id, sub_order_id=sub_order_id)
    if not instance:
        raise ValueError("Workflow not initialized")
    if instance.current_stage_key != 'reception':
        raise ValueError("Can only set difficulty at reception stage")

    current_notes = dict(instance.stage_notes or {})
    current_notes['reception'] = note or ''
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    if stage_data:
        current_data['reception'] = stage_data
        _sync_stage_data_to_project(db, project_id, stage_data, sub_order_id=sub_order_id)
    instance.stage_data = current_data

    instance.difficulty = difficulty
    instance.file_editable = file_editable

    steps = get_effective_stages(difficulty, file_editable)
    if len(steps) < 2:
        raise ValueError("No next stage available")
    next_stage = steps[1]

    next_assignee_id, group_assign_role = _resolve_stage_assignment(
        db,
        stage_key=next_stage['key'],
        project_id=project_id,
        sub_order_id=sub_order_id,
        next_assignee_id=next_assignee_id,
        group_assign_role=group_assign_role,
    )

    if next_assignee_id:
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
    _notify_assignment(db, project_id, next_stage['key'], next_assignee_id, group_assign_role, 'assigned', sub_order_id=sub_order_id)
    return instance


def transition_forward(
    db: Session,
    project_id: Optional[UUID] = None,
    next_assignee_id: Optional[UUID] = None,
    group_assign_role: Optional[str] = None,
    operator_id: Optional[UUID] = None,
    note: Optional[str] = None,
    stage_data: Optional[dict] = None,
    sub_order_id: Optional[UUID] = None,
) -> WorkflowInstance:
    instance = _get_instance(db, project_id=project_id, sub_order_id=sub_order_id)
    if not instance:
        raise ValueError("Workflow not initialized")

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
        _sync_stage_data_to_project(db, project_id, stage_data, sub_order_id=sub_order_id)
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
        if project_id:
            ensure_finance_record_for_project(db, project_id=project_id, edited_by=operator_id)
        db.refresh(instance)
        return instance

    next_stage = steps[next_idx]
    if next_stage['key'] != 'completed':
        next_assignee_id, group_assign_role = _resolve_stage_assignment(
            db,
            stage_key=next_stage['key'],
            project_id=project_id,
            sub_order_id=sub_order_id,
            next_assignee_id=next_assignee_id,
            group_assign_role=group_assign_role,
        )
    if next_stage['key'] == 'completed':
        description = f"Moved from {current_stage_info.get('key', current_stage_key)} to completed."
        instance.project_status = 'completed'
        instance.current_assignee_id = None
        instance.group_assign_role = None
        log_next_assignee_id = None
    elif next_assignee_id:
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
    if next_stage['key'] == 'completed' and project_id:
        ensure_finance_record_for_project(db, project_id=project_id, edited_by=operator_id)
    db.refresh(instance)
    if notify_stage_key:
        _notify_assignment(db, project_id, notify_stage_key, notify_next_assignee_id, notify_group_assign_role, 'assigned', sub_order_id=sub_order_id)
    return instance


def rollback(
    db: Session,
    project_id: Optional[UUID] = None,
    steps: int = 1,
    to_start: bool = False,
    note: str = '',
    operator_id: Optional[UUID] = None,
    sub_order_id: Optional[UUID] = None,
) -> WorkflowInstance:
    instance = _get_instance(db, project_id=project_id, sub_order_id=sub_order_id)
    if not instance:
        raise ValueError("Workflow not initialized")

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
    rollback_assignee_id, rollback_group_role = _resolve_stage_assignment(
        db,
        stage_key=target['key'],
        project_id=project_id,
        sub_order_id=sub_order_id,
        next_assignee_id=None,
        group_assign_role=None,
    )

    log = WorkflowLog(
        workflow_instance_id=instance.id,
        operator_id=operator_id,
        from_stage=instance.current_stage_key,
        to_stage=target['key'],
        direction='rollback',
        description=description,
        note=note,
        next_assignee_id=rollback_assignee_id,
    )
    db.add(log)

    instance.current_stage_key = target['key']
    instance.current_assignee_id = rollback_assignee_id
    instance.group_assign_role = rollback_group_role
    if target['key'] == 'reception':
        instance.project_status = 'pending'
        instance.difficulty = None
        instance.file_editable = None

    current_notes = dict(instance.stage_notes or {})
    current_notes.pop(target['key'], None)
    instance.stage_notes = current_notes

    current_data = dict(instance.stage_data or {})
    current_data.pop(target['key'], None)
    instance.stage_data = current_data

    db.commit()
    db.refresh(instance)

    _notify_assignment(
        db,
        project_id,
        target['key'],
        rollback_assignee_id,
        rollback_group_role,
        'rollback',
        sub_order_id=sub_order_id,
    )
    return instance


def update_stage_data(
    db: Session,
    project_id: Optional[UUID] = None,
    stage_data: dict = None,
    sub_order_id: Optional[UUID] = None,
) -> WorkflowInstance:
    """暂存当前阶段的进度表单数据"""
    instance = _get_instance(db, project_id=project_id, sub_order_id=sub_order_id)
    if not instance:
        raise ValueError("Workflow not initialized")

    current_data = dict(instance.stage_data or {})
    current_data[instance.current_stage_key] = stage_data or {}
    instance.stage_data = current_data

    _sync_stage_data_to_project(db, project_id, stage_data or {}, sub_order_id=sub_order_id)

    db.commit()
    db.refresh(instance)
    return instance
