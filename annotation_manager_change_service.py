"""标注项目负责人变更日志写入与查询。"""

from __future__ import annotations
from search_matching import keyword_ilike, keyword_or

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from annotation_manager_change_models import AnnotationManagerChangeLog
from models import AppUser
from annotation_progress_time import business_datetime, business_now


def active_annotation_manager_users(db: Session) -> list[AppUser]:
    """标注项目职责可分配给所有启用账号，与账号角色、请假状态无关。"""
    return db.query(AppUser).filter(AppUser.is_active.is_(True)).order_by(
        AppUser.full_name, AppUser.username, AppUser.id,
    ).all()


def attach_manager_assignment_history(db: Session, projects) -> None:
    """一次读取当前页的历史，清空后再次添加也不能冒充首次分配。"""
    if not projects:
        return
    history = set(db.query(
        AnnotationManagerChangeLog.project_id, AnnotationManagerChangeLog.manager_role,
    ).filter(AnnotationManagerChangeLog.project_id.in_([p.id for p in projects])).distinct().all())
    for project in projects:
        project.manager_assignment_history = {
            'client_manager': bool(project.client_manager_id) or (project.id, 'client_manager') in history,
            'project_manager': any(
                r.role_code == 'project_manager' and r.assignee_id
                for r in project.workbench_responsibilities
            ) or (project.id, 'project_manager') in history,
        }


def validate_manager_change_reason(project, previous_client, previous_managers, new_client, new_managers, reason):
    """客户经理任何调整均需原因；项目经理仍保留首次分配免原因规则。"""
    normalized = (reason or '').strip()
    if len(normalized) > 500:
        raise ValueError('调整原因不能超过500字')
    history = getattr(project, 'manager_assignment_history', {})
    needs_reason = (
        previous_client != new_client
    ) or (
        set(previous_managers) != set(new_managers)
        and (bool(previous_managers) or history.get('project_manager', False))
    )
    if needs_reason and not normalized:
        raise ValueError('请填写负责人调整原因')
    return normalized or '首次分配'


def _user_snapshot(db: Session, user_id: Optional[UUID]) -> tuple[Optional[str], Optional[str]]:
    if not user_id:
        return None, None
    # 部分服务层单元测试使用轻量会话替身；正式运行只从真实 Session 取用户快照。
    if not isinstance(db, Session):
        return None, None
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        return None, None
    return user.username, user.full_name or user.username


def record_annotation_manager_change(
    db: Session,
    *,
    project,
    manager_role: str,
    previous_manager_id: Optional[UUID],
    new_manager_id: Optional[UUID],
    change_mode: str,
    actor_user_id: Optional[UUID],
    reason: Optional[str] = None,
    source_request_id: Optional[UUID] = None,
) -> Optional[AnnotationManagerChangeLog]:
    """负责人确实变化时写入一条不可依赖当前关联数据的快照。"""
    if previous_manager_id == new_manager_id:
        return None
    _previous_username, previous_name = _user_snapshot(db, previous_manager_id)
    _new_username, new_name = _user_snapshot(db, new_manager_id)
    actor_username, actor_name = _user_snapshot(db, actor_user_id)
    row = AnnotationManagerChangeLog(
        source_request_id=source_request_id,
        project_id=project.id,
        order_no=getattr(project, "order_no", None) or str(project.id),
        project_name=getattr(project, "project_name", None),
        manager_role=manager_role,
        previous_manager_id=previous_manager_id,
        previous_manager_name=previous_name,
        new_manager_id=new_manager_id,
        new_manager_name=new_name,
        change_mode=change_mode,
        reason=(reason or "").strip() or None,
        actor_user_id=actor_user_id,
        actor_username_snapshot=actor_username,
        actor_name_snapshot=actor_name,
        changed_at=business_now(),
    )
    add = getattr(db, "add", None)
    if callable(add):
        add(row)
    return row


def list_annotation_manager_changes(
    db: Session,
    *,
    keyword: Optional[str] = None,
    manager_role: Optional[str] = None,
    change_mode: Optional[str] = None,
    project_id: Optional[UUID] = None,
    changed_from: Optional[datetime] = None,
    changed_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AnnotationManagerChangeLog], int]:
    query = db.query(AnnotationManagerChangeLog)
    normalized = (keyword or "").strip()
    if normalized:
        pattern = f"%{normalized}%"
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(AnnotationManagerChangeLog.order_no, _search_part),
            keyword_ilike(AnnotationManagerChangeLog.project_name, _search_part),
            keyword_ilike(AnnotationManagerChangeLog.previous_manager_name, _search_part),
            keyword_ilike(AnnotationManagerChangeLog.new_manager_name, _search_part),
            keyword_ilike(AnnotationManagerChangeLog.actor_name_snapshot, _search_part),
            keyword_ilike(AnnotationManagerChangeLog.actor_username_snapshot, _search_part),
            keyword_ilike(AnnotationManagerChangeLog.reason, _search_part),
        ), pattern))
    if manager_role:
        query = query.filter(AnnotationManagerChangeLog.manager_role == manager_role)
    if change_mode:
        query = query.filter(AnnotationManagerChangeLog.change_mode == change_mode)
    if project_id:
        query = query.filter(AnnotationManagerChangeLog.project_id == project_id)
    if changed_from:
        query = query.filter(AnnotationManagerChangeLog.changed_at >= business_datetime(changed_from))
    if changed_to:
        query = query.filter(AnnotationManagerChangeLog.changed_at <= business_datetime(changed_to))
    total = query.count()
    rows = query.order_by(
        AnnotationManagerChangeLog.changed_at.desc(),
        AnnotationManagerChangeLog.id.desc(),
    ).offset(skip).limit(limit).all()
    return rows, total
