"""项目操作审计写入与只读查询。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import AppUser
from project_audit_models import (
    PROJECT_AUDIT_OPERATIONS,
    PROJECT_AUDIT_TYPES,
    ProjectOperationAudit,
)


def _project_snapshot(project) -> dict:
    return jsonable_encoder({
        column.key: getattr(project, column.key, None)
        for column in project.__table__.columns
    })


def record_project_operation(
    db: Session,
    *,
    project_type: str,
    operation_type: str,
    project,
    actor_user_id: Optional[UUID],
    operation_source: str,
    previous_order_no: Optional[str] = None,
    change_reason: Optional[str] = None,
) -> ProjectOperationAudit:
    if project_type not in PROJECT_AUDIT_TYPES:
        raise ValueError("不支持的项目审计类型")
    if operation_type not in PROJECT_AUDIT_OPERATIONS:
        raise ValueError("不支持的项目审计操作")

    actor = db.get(AppUser, actor_user_id) if actor_user_id and hasattr(db, "get") else None
    row = ProjectOperationAudit(
        project_type=project_type,
        project_id=project.id,
        order_no=project.order_no,
        project_name=getattr(project, "project_name", None),
        operation_type=operation_type,
        operation_source=operation_source,
        actor_user_id=actor_user_id,
        actor_username_snapshot=getattr(actor, "username", None),
        actor_name_snapshot=getattr(actor, "full_name", None),
        previous_order_no=previous_order_no,
        change_reason=change_reason,
        project_snapshot=_project_snapshot(project),
    )
    db.add(row)
    return row


def list_project_operation_audits(
    db: Session,
    *,
    keyword: Optional[str] = None,
    project_type: Optional[str] = None,
    operation_type: Optional[str] = None,
    operator_keyword: Optional[str] = None,
    occurred_from: Optional[datetime] = None,
    occurred_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[ProjectOperationAudit], int]:
    query = db.query(ProjectOperationAudit)
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            ProjectOperationAudit.order_no.ilike(pattern),
            ProjectOperationAudit.previous_order_no.ilike(pattern),
            ProjectOperationAudit.project_name.ilike(pattern),
        ))
    if project_type:
        query = query.filter(ProjectOperationAudit.project_type == project_type)
    if operation_type:
        query = query.filter(ProjectOperationAudit.operation_type == operation_type)
    if operator_keyword and operator_keyword.strip():
        pattern = f"%{operator_keyword.strip()}%"
        query = query.filter(or_(
            ProjectOperationAudit.actor_name_snapshot.ilike(pattern),
            ProjectOperationAudit.actor_username_snapshot.ilike(pattern),
        ))
    if occurred_from:
        query = query.filter(ProjectOperationAudit.occurred_at >= occurred_from)
    if occurred_to:
        query = query.filter(ProjectOperationAudit.occurred_at <= occurred_to)
    total = query.count()
    rows = query.order_by(ProjectOperationAudit.occurred_at.desc(), ProjectOperationAudit.id.desc()).offset(skip).limit(limit).all()
    return rows, total
