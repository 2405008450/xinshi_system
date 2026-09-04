"""非笔译项目接入统一工作台所需的责任、展示和转交适配。"""
from __future__ import annotations

import datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from annotation_models import AnnotationProject
from interpretation_models import InterpretationProject
from recruitment_models import RecruitmentProject
from models import AppUser
from project_roles import PROJECT_ROLE_NAME_BY_CODE
from workflow_models import ProjectWorkbenchResponsibility


PROJECT_TYPES = ('interpretation', 'annotation', 'recruitment')
RESPONSIBILITY_ROLE_CODES = ('project_manager', 'project_specialist', 'project_assistant')
PROJECT_TYPE_LABELS = {
    'translation': '笔译项目',
    'interpretation': '口译项目',
    'annotation': '标注项目',
    'recruitment': '招聘项目',
}
PROJECT_DETAIL_ROUTES = {
    'translation': 'TranslationProjectDetails',
    'interpretation': 'InterpretationProjectDetails',
    'annotation': 'AnnotationProjectDetails',
    'recruitment': 'RecruitmentProjectDetails',
}
ACTIVE_STATUSES = {
    'interpretation': {'initial_follow_up', 'in_progress'},
    'annotation': {
        'initial_consultation', 'resource_sourcing', 'trial_preparation',
        'trial_in_progress', 'trial_passed', 'trial_partially_passed',
        'project_in_progress',
    },
}

# 工作台只承载仍需处理的项目。笔译状态较多且会继续扩展，因此使用终态黑名单；
# 其他项目类型已有收敛的状态机，继续使用上面的活跃状态白名单。
TRANSLATION_INACTIVE_STATUSES = frozenset({
    'sent_to_client',
    'client_feedback',
    'feedback_sent_to_client',
    'completed',
    'terminated',
    'cancelled',
    'partially_cancelled',
})


def is_active_project(project_type: str, status: Optional[str]) -> bool:
    value = (status or '').strip()
    if project_type == 'translation':
        return value not in TRANSLATION_INACTIVE_STATUSES
    if project_type == 'recruitment':
        return value not in {'closed', 'cancelled'}
    return value in ACTIVE_STATUSES.get(project_type, set())


def _project_fk_name(project_type: str) -> str:
    if project_type not in PROJECT_TYPES:
        raise ValueError('不支持的工作台项目类型')
    return f'{project_type}_project_id'


def get_project(db: Session, project_type: str, project_id: UUID):
    model = {
        'interpretation': InterpretationProject,
        'annotation': AnnotationProject,
        'recruitment': RecruitmentProject,
    }.get(project_type)
    if not model:
        raise ValueError('不支持的工作台项目类型')
    return db.query(model).filter(model.id == project_id).first()


def ensure_project_responsibilities(
    db: Session,
    project_type: str,
    project_id: UUID,
    assignments: Optional[dict[str, Optional[UUID]]] = None,
) -> list[ProjectWorkbenchResponsibility]:
    """幂等补齐三个内部角色；传 assignments 时同步负责人。"""
    project = get_project(db, project_type, project_id)
    if not project:
        raise LookupError('项目不存在')
    fk_name = _project_fk_name(project_type)
    rows = db.query(ProjectWorkbenchResponsibility).filter(
        getattr(ProjectWorkbenchResponsibility, fk_name) == project_id
    ).all()
    by_role = {row.role_code: row for row in rows}
    now = datetime.datetime.utcnow()
    for role_code in RESPONSIBILITY_ROLE_CODES:
        row = by_role.get(role_code)
        if not row:
            row = ProjectWorkbenchResponsibility(
                **{fk_name: project_id},
                role_code=role_code,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            rows.append(row)
            by_role[role_code] = row
        if assignments is not None and role_code in assignments:
            row.assignee_id = assignments[role_code]
            row.updated_at = now
    db.flush()
    return rows


def ensure_active_project_responsibilities(
    db: Session,
    project_type: str,
    project_id: UUID,
    status: Optional[str],
    assignments: Optional[dict[str, Optional[UUID]]] = None,
) -> list[ProjectWorkbenchResponsibility]:
    if not is_active_project(project_type, status):
        if hasattr(db, 'query'):
            cancel_pending_project_handovers(db, project_type, project_id, reason='项目已离开工作台活跃范围')
        return []
    # 服务层测试会使用仅实现 add/commit 的轻量会话替身；正式 SQLAlchemy Session 均提供 query。
    if not hasattr(db, 'query'):
        return []
    return ensure_project_responsibilities(db, project_type, project_id, assignments)


def cancel_pending_project_handovers(
    db: Session,
    project_type: str,
    project_id: UUID,
    *,
    reason: str = '项目已删除',
) -> None:
    """项目结束或删除前，使关联的待确认交接失效，避免留下不可处理的空申请。"""
    from workflow_models import (
        ProjectManagerHandoverItem,
        ProjectManagerHandoverRequest,
        WorkflowHandoverItem,
        WorkflowHandoverRequest,
        WorkflowInstance,
    )

    now = datetime.datetime.utcnow()
    if project_type == 'translation':
        instance_ids = [
            value for (value,) in db.query(WorkflowInstance.id).filter(
                WorkflowInstance.translation_project_id == project_id
            ).all()
        ]
        workflow_request_ids = [
            value for (value,) in db.query(WorkflowHandoverItem.request_id).filter(
                WorkflowHandoverItem.workflow_instance_id.in_(instance_ids)
            ).all()
        ] if instance_ids else []
        manager_request_ids = [
            value for (value,) in db.query(ProjectManagerHandoverItem.request_id).filter(
                ProjectManagerHandoverItem.translation_project_id == project_id
            ).all()
        ]
    else:
        fk_name = _project_fk_name(project_type)
        responsibility_ids = [
            value for (value,) in db.query(ProjectWorkbenchResponsibility.id).filter(
                getattr(ProjectWorkbenchResponsibility, fk_name) == project_id
            ).all()
        ]
        if not responsibility_ids:
            return
        workflow_request_ids = [
            value for (value,) in db.query(WorkflowHandoverItem.request_id).filter(
                WorkflowHandoverItem.project_responsibility_id.in_(responsibility_ids)
            ).all()
        ]
        manager_request_ids = [
            value for (value,) in db.query(ProjectManagerHandoverItem.request_id).filter(
                ProjectManagerHandoverItem.project_responsibility_id.in_(responsibility_ids)
            ).all()
        ]
    if workflow_request_ids:
        db.query(WorkflowHandoverRequest).filter(
            WorkflowHandoverRequest.id.in_(workflow_request_ids),
            WorkflowHandoverRequest.status == 'pending',
        ).update({
            WorkflowHandoverRequest.status: 'rejected',
            WorkflowHandoverRequest.decision_note: reason,
            WorkflowHandoverRequest.decided_at: now,
        }, synchronize_session=False)
    if manager_request_ids:
        db.query(ProjectManagerHandoverRequest).filter(
            ProjectManagerHandoverRequest.id.in_(manager_request_ids),
            ProjectManagerHandoverRequest.status == 'pending',
        ).update({
            ProjectManagerHandoverRequest.status: 'rejected',
            ProjectManagerHandoverRequest.decision_note: reason,
            ProjectManagerHandoverRequest.decided_at: now,
        }, synchronize_session=False)


def role_assignments_for_project(db: Session, project_type: str, project_id: UUID) -> list[dict]:
    fk_name = _project_fk_name(project_type)
    rows = db.query(ProjectWorkbenchResponsibility).options(
        joinedload(ProjectWorkbenchResponsibility.assignee)
    ).filter(getattr(ProjectWorkbenchResponsibility, fk_name) == project_id).all()
    by_role = {row.role_code: row for row in rows}
    result = []
    for role_code in RESPONSIBILITY_ROLE_CODES:
        row = by_role.get(role_code)
        user = row.assignee if row else None
        result.append({
            'role_code': role_code,
            'role_name': PROJECT_ROLE_NAME_BY_CODE[role_code],
            'assignee_id': row.assignee_id if row else None,
            'assignee_name': (user.full_name or user.username) if user else None,
            'assignment_type': 'direct' if row and row.assignee_id else 'role_pool',
        })
    return result


def assignment_map_from_payload(values: Optional[Iterable]) -> Optional[dict[str, Optional[UUID]]]:
    if values is None:
        return None
    result: dict[str, Optional[UUID]] = {}
    for item in values:
        data = item.model_dump() if hasattr(item, 'model_dump') else dict(item)
        role_code = data.get('role_code')
        if role_code not in RESPONSIBILITY_ROLE_CODES:
            raise ValueError('不支持的内部项目角色')
        result[role_code] = data.get('assignee_id')
    return result


def validate_assignment_map(db: Session, assignments: Optional[dict[str, Optional[UUID]]]) -> None:
    if assignments is None:
        return
    from crud import get_user_roles_with_role_names
    from leave_service import ensure_user_assignable
    for role_code, user_id in assignments.items():
        if role_code not in RESPONSIBILITY_ROLE_CODES:
            raise ValueError('不支持的内部项目角色')
        if user_id is None:
            continue
        user = db.query(AppUser).filter(AppUser.id == user_id, AppUser.is_active == True).first()
        if not user:
            raise ValueError('所选内部负责人不存在或已停用')
        if PROJECT_ROLE_NAME_BY_CODE[role_code] not in set(get_user_roles_with_role_names(db, user_id)):
            raise ValueError(f'所选用户不具备{PROJECT_ROLE_NAME_BY_CODE[role_code]}角色')
        ensure_user_assignable(db, user_id)


def _responsibility_project_type(row: ProjectWorkbenchResponsibility) -> str:
    return row.project_type


def _client(project):
    return getattr(project, 'sub_client', None) or getattr(project, 'client', None)


def _deadline(project_type: str, project):
    if project_type == 'interpretation':
        ranges = list(getattr(project, 'time_ranges', None) or [])
        return max((item.scheduled_end for item in ranges), default=None)
    if project_type == 'recruitment' and project.target_onboard_type != 'anytime' and project.target_onboard_date:
        return datetime.datetime.combine(project.target_onboard_date, datetime.time.max.replace(microsecond=0))
    return None


def _language_pair(project_type: str, project) -> Optional[str]:
    if project_type == 'interpretation':
        return project.language_directions_display
    if project_type == 'annotation':
        return project.language_items_display
    values = [item.label for item in (getattr(project, 'language_directions', None) or [])]
    return '；'.join(value for value in values if value) or None


def _load_responsibilities(db: Session):
    return db.query(ProjectWorkbenchResponsibility).options(
        joinedload(ProjectWorkbenchResponsibility.assignee),
        joinedload(ProjectWorkbenchResponsibility.interpretation_project)
        .selectinload(InterpretationProject.time_ranges),
        joinedload(ProjectWorkbenchResponsibility.interpretation_project)
        .selectinload(InterpretationProject.language_directions),
        joinedload(ProjectWorkbenchResponsibility.interpretation_project)
        .joinedload(InterpretationProject.client),
        joinedload(ProjectWorkbenchResponsibility.interpretation_project)
        .joinedload(InterpretationProject.sub_client),
        joinedload(ProjectWorkbenchResponsibility.annotation_project)
        .selectinload(AnnotationProject.language_items),
        joinedload(ProjectWorkbenchResponsibility.annotation_project)
        .joinedload(AnnotationProject.client),
        joinedload(ProjectWorkbenchResponsibility.annotation_project)
        .joinedload(AnnotationProject.sub_client),
        joinedload(ProjectWorkbenchResponsibility.recruitment_project)
        .selectinload(RecruitmentProject.language_directions),
        joinedload(ProjectWorkbenchResponsibility.recruitment_project)
        .joinedload(RecruitmentProject.client),
        joinedload(ProjectWorkbenchResponsibility.recruitment_project)
        .joinedload(RecruitmentProject.sub_client),
    )


def serialize_responsibility(
    db: Session,
    row: ProjectWorkbenchResponsibility,
    *,
    assignment_type: Optional[str] = None,
) -> dict:
    project_type = _responsibility_project_type(row)
    project = row.project
    client = _client(project)
    assignee = row.assignee
    role_name = PROJECT_ROLE_NAME_BY_CODE[row.role_code]
    return {
        'workflow_instance_id': None,
        'translation_project_id': None,
        'project_responsibility_id': row.id,
        'source_kind': 'project_responsibility',
        'project_type': project_type,
        'project_type_label': PROJECT_TYPE_LABELS[project_type],
        'project_id': project.id,
        'detail_route_name': PROJECT_DETAIL_ROUTES[project_type],
        'sub_order_id': None,
        'order_no': project.order_no,
        'project_name': project.project_name or project.order_no,
        'task_type': PROJECT_TYPE_LABELS[project_type],
        'task_kind': 'project_responsibility',
        'consultation_id': getattr(project, 'consultation_id', None),
        'sub_project_name': None,
        'client_name': getattr(project, 'client_full_name', None) or getattr(project, 'client_name', None) or (client.client_name if client else ''),
        'client_short_name': getattr(project, 'client_short_name', None) or (client.client_short_name if client else ''),
        'current_stage_key': row.role_code,
        'current_stage_role_code': row.role_code,
        'current_stage_role_name': role_name,
        'current_assignee_id': row.assignee_id,
        'current_assignee_name': (assignee.full_name or assignee.username) if assignee else None,
        'group_assign_role': None if row.assignee_id else role_name,
        'assignment_type': assignment_type or ('direct' if row.assignee_id else 'role_pool'),
        'difficulty': None,
        'project_status': project.project_status,
        'customer_deadline_time': _deadline(project_type, project),
        'language_pair': _language_pair(project_type, project),
        'entity_type': 'project',
        'role_assignments': role_assignments_for_project(db, project_type, project.id),
        'project_manager_id': None,
        'project_manager_name': None,
    }


def get_responsibility_tasks(db: Session, user_id: UUID, roles: set[str], *, include_all: bool = False) -> list[dict]:
    role_codes = {
        code for code, name in PROJECT_ROLE_NAME_BY_CODE.items()
        if name in roles and code in {'project_specialist', 'project_assistant'}
    }
    query = _load_responsibilities(db).filter(
        ProjectWorkbenchResponsibility.role_code.in_(['project_specialist', 'project_assistant'])
    )
    if not include_all:
        from workflow_delegation_service import delegated_source_ids
        _, delegated_responsibility_ids = delegated_source_ids(db, user_id)
        if not role_codes and not delegated_responsibility_ids:
            return []
        responsibility_scope = [
            ProjectWorkbenchResponsibility.assignee_id == user_id,
            ProjectWorkbenchResponsibility.assignee_id.is_(None),
        ]
        if delegated_responsibility_ids:
            responsibility_scope.append(
                ProjectWorkbenchResponsibility.id.in_(delegated_responsibility_ids)
            )
        query = query.filter(
            or_(
                ProjectWorkbenchResponsibility.role_code.in_(role_codes),
                ProjectWorkbenchResponsibility.id.in_(delegated_responsibility_ids or {None}),
            ),
            or_(*responsibility_scope),
        )
    result = []
    for row in query.all():
        project = row.project
        if not project or not is_active_project(row.project_type, project.project_status):
            continue
        assignment_type = 'overview' if include_all and row.assignee_id != user_id else None
        result.append(serialize_responsibility(db, row, assignment_type=assignment_type))
    return result


def get_management_responsibilities(db: Session, user_id: UUID, *, include_all: bool = False) -> list[dict]:
    query = _load_responsibilities(db).filter(
        ProjectWorkbenchResponsibility.role_code == 'project_manager'
    )
    if not include_all:
        query = query.filter(or_(
            ProjectWorkbenchResponsibility.assignee_id == user_id,
            ProjectWorkbenchResponsibility.assignee_id.is_(None),
        ))
    result = []
    for row in query.all():
        if not row.project or not is_active_project(row.project_type, row.project.project_status):
            continue
        item = serialize_responsibility(db, row)
        item['project_manager_id'] = row.assignee_id
        item['project_manager_name'] = item['current_assignee_name']
        result.append(item)
    return result


def get_responsibilities_by_ids(db: Session, ids: Iterable[UUID], *, lock: bool = False) -> list[ProjectWorkbenchResponsibility]:
    unique_ids = list(dict.fromkeys(ids))
    query = _load_responsibilities(db).filter(ProjectWorkbenchResponsibility.id.in_(unique_ids))
    if lock:
        query = query.with_for_update(of=ProjectWorkbenchResponsibility)
    rows = query.all()
    if len(rows) != len(unique_ids):
        raise LookupError('部分项目责任不存在')
    return rows


def get_manager_responsibilities_by_refs(
    db: Session,
    project_refs: Iterable[dict],
    *,
    lock: bool = False,
) -> list[ProjectWorkbenchResponsibility]:
    refs = []
    for value in project_refs:
        data = value.model_dump() if hasattr(value, 'model_dump') else dict(value)
        if data.get('project_type') == 'translation':
            continue
        refs.append((data.get('project_type'), data.get('project_id')))
    if not refs:
        return []
    conditions = []
    for project_type, project_id in refs:
        conditions.append(
            getattr(ProjectWorkbenchResponsibility, _project_fk_name(project_type)) == project_id
        )
    query = _load_responsibilities(db).filter(
        ProjectWorkbenchResponsibility.role_code == 'project_manager',
        or_(*conditions),
    )
    if lock:
        query = query.with_for_update(of=ProjectWorkbenchResponsibility)
    rows = query.all()
    if len(rows) != len(set(refs)):
        raise LookupError('部分管理项目不存在或尚未接入工作台')
    return rows


def ensure_same_responsibility_role(rows: list[ProjectWorkbenchResponsibility]) -> str:
    if not rows:
        raise ValueError('请至少选择一项任务')
    roles = {row.role_code for row in rows}
    if len(roles) != 1:
        raise ValueError('一次只能处理同一角色类型的任务，请按角色分别操作')
    return next(iter(roles))


def user_has_responsibility_role(db: Session, user_id: UUID, role_code: str) -> bool:
    from crud import get_user_roles_with_role_names
    return PROJECT_ROLE_NAME_BY_CODE.get(role_code) in set(get_user_roles_with_role_names(db, user_id))


def get_transferable_responsibility_tasks(
    db: Session,
    user_id: UUID,
    roles: set[str],
    *,
    owner_user_id: Optional[UUID] = None,
    keyword: Optional[str] = None,
) -> list[dict]:
    from workflow_models import WorkflowHandoverItem, WorkflowHandoverRequest
    role_codes = {
        code for code in ('project_specialist', 'project_assistant')
        if PROJECT_ROLE_NAME_BY_CODE[code] in roles
    }
    if not role_codes:
        return []
    query = _load_responsibilities(db).filter(
        ProjectWorkbenchResponsibility.role_code.in_(role_codes),
        ProjectWorkbenchResponsibility.assignee_id.is_not(None),
        ProjectWorkbenchResponsibility.assignee_id != user_id,
        ~ProjectWorkbenchResponsibility.id.in_(
            db.query(WorkflowHandoverItem.project_responsibility_id)
            .join(WorkflowHandoverRequest, WorkflowHandoverRequest.id == WorkflowHandoverItem.request_id)
            .filter(
                WorkflowHandoverRequest.status == 'pending',
                WorkflowHandoverItem.project_responsibility_id.is_not(None),
            )
        ),
    )
    if owner_user_id:
        query = query.filter(ProjectWorkbenchResponsibility.assignee_id == owner_user_id)
    normalized = (keyword or '').strip().casefold()
    result = []
    for row in query.all():
        if not row.project or not is_active_project(row.project_type, row.project.project_status):
            continue
        item = serialize_responsibility(db, row, assignment_type='direct')
        if normalized:
            haystack = ' '.join(str(item.get(key) or '') for key in (
                'order_no', 'project_name', 'client_name', 'client_short_name',
                'current_assignee_name', 'project_type_label',
            )).casefold()
            if normalized not in haystack:
                continue
        result.append(item)
    return result


def eligible_users_for_responsibilities(db: Session, rows: list[ProjectWorkbenchResponsibility]) -> list[AppUser]:
    role_code = ensure_same_responsibility_role(rows)
    role_name = PROJECT_ROLE_NAME_BY_CODE[role_code]
    from crud import get_user_roles_with_role_names
    return [
        user for user in db.query(AppUser).filter(AppUser.is_active == True).order_by(AppUser.full_name, AppUser.username).all()
        if role_name in set(get_user_roles_with_role_names(db, user.id))
    ]


def claim_role_pool_responsibilities(
    db: Session,
    operator: AppUser,
    responsibility_ids: list[UUID],
    *,
    commit: bool = True,
) -> dict:
    from leave_service import ensure_user_assignable
    rows = get_responsibilities_by_ids(db, responsibility_ids, lock=True)
    ensure_user_assignable(db, operator.id)
    for row in rows:
        if row.assignee_id is not None:
            raise LookupError('部分任务已被其他用户认领，请刷新后重试')
        if not row.project or not is_active_project(row.project_type, row.project.project_status):
            raise LookupError('部分项目已不在工作台活跃范围')
        if not user_has_responsibility_role(db, operator.id, row.role_code):
            raise PermissionError('当前用户不具备部分角色池任务所需角色')
        row.assignee_id = operator.id
        row.updated_at = datetime.datetime.utcnow()
    if commit:
        db.commit()
    return {
        'action': 'role_pool_claim',
        'transferred_count': len(rows),
        'workflow_instance_ids': [],
        'project_responsibility_ids': [row.id for row in rows],
    }


def transfer_responsibilities(
    db: Session,
    operator: AppUser,
    responsibility_ids: list[UUID],
    *,
    action: str,
    target_user_id: Optional[UUID] = None,
    expected_assignee_ids: Optional[dict[UUID, UUID]] = None,
    commit: bool = True,
) -> dict:
    from crud import create_notifications_for_users
    from leave_service import ensure_user_assignable
    if action not in {'handover', 'claim'}:
        raise ValueError('不支持的交接类型')
    rows = get_responsibilities_by_ids(db, responsibility_ids, lock=True)
    role_code = ensure_same_responsibility_role(rows)
    expected_assignee_ids = expected_assignee_ids or {}
    if any(expected_assignee_ids.get(row.id) != row.assignee_id for row in rows):
        raise LookupError('部分任务负责人已发生变化，请刷新后重试')
    if action == 'handover':
        if any(row.assignee_id != operator.id for row in rows):
            raise PermissionError('只能交接当前用户直接负责的任务')
        if not target_user_id or target_user_id == operator.id:
            raise ValueError('请选择其他接收人')
        target_id = target_user_id
    else:
        if any(not row.assignee_id or row.assignee_id == operator.id for row in rows):
            raise PermissionError('只能继承其他用户直接负责的任务')
        target_id = operator.id
    target = db.query(AppUser).filter(AppUser.id == target_id, AppUser.is_active == True).first()
    if not target:
        raise ValueError('接收用户不存在或已停用')
    ensure_user_assignable(db, target.id)
    if not user_has_responsibility_role(db, target.id, role_code):
        raise PermissionError('接收用户不具备任务所需角色')
    source_ids = {row.assignee_id for row in rows if row.assignee_id}
    now = datetime.datetime.utcnow()
    for row in rows:
        if not row.project or not is_active_project(row.project_type, row.project.project_status):
            raise LookupError('部分项目已不在工作台活跃范围')
        row.assignee_id = target.id
        row.updated_at = now
    recipients = [target.id] if action == 'handover' else [value for value in source_ids if value != operator.id]
    first = rows[0]
    notifications = create_notifications_for_users(
        db,
        recipient_user_ids=recipients,
        title='项目任务交接' if action == 'handover' else '项目任务已被继承',
        content=f'已更新 {len(rows)} 项{PROJECT_ROLE_NAME_BY_CODE[role_code]}责任。',
        notification_type=f'workflow_{action}',
        related_project_type=first.project_type,
        related_entity_id=first.project_id,
        commit=False,
    )
    if commit:
        db.commit()
    return {
        'action': action,
        'transferred_count': len(rows),
        'workflow_instance_ids': [],
        'project_responsibility_ids': [row.id for row in rows],
        '_notifications': notifications,
    }
