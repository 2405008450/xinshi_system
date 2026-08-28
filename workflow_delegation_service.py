"""临时代办关系的创建、展示、归还和结束。"""
from __future__ import annotations

import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models import AppUser
from permission_registry import ALL_PERMISSION
from permission_service import get_user_permission_codes
from project_roles import PROJECT_ROLE_NAME_BY_CODE, get_stage_role
from task_activity_service import record_task_activity
from workflow_models import (
    ProjectWorkbenchResponsibility,
    WorkflowHandoverItem,
    WorkflowHandoverRequest,
    WorkflowInstance,
    WorkflowTaskDelegation,
)


BUSINESS_TZ = ZoneInfo("Asia/Hong_Kong")


def _now() -> datetime.datetime:
    return datetime.datetime.now(BUSINESS_TZ).replace(tzinfo=None)


def delegated_source_ids(db: Session, original_assignee_id: UUID) -> tuple[set[UUID], set[UUID]]:
    rows = db.query(WorkflowTaskDelegation).filter(
        WorkflowTaskDelegation.original_assignee_id == original_assignee_id,
        WorkflowTaskDelegation.status == "active",
    ).all()
    return (
        {row.workflow_instance_id for row in rows if row.workflow_instance_id},
        {row.project_responsibility_id for row in rows if row.project_responsibility_id},
    )


def _display_user(user: AppUser | None) -> str:
    return (user.full_name or user.username) if user else "未知用户"


def permanent_handover_applies_to_current_item(item: dict, request: WorkflowHandoverRequest) -> bool:
    """判断永久交接历史是否仍属于当前阶段的任务。"""
    if item.get("assignment_type") == "role_pool" or item.get("group_assign_role"):
        return False
    current_assignee_id = item.get("current_assignee_id")
    return bool(current_assignee_id and current_assignee_id == request.target_user_id)


def _source_identity(item: WorkflowHandoverItem) -> tuple[str, str, dict]:
    if item.workflow_instance_id and item.workflow_instance:
        instance = item.workflow_instance
        if instance.sub_order_id and instance.sub_order:
            sub = instance.sub_order
            project = sub.parent_project
            return (
                (project.task_type or "项目任务") if project else "项目任务",
                sub.sub_project_name or (project.project_name if project else None) or sub.sub_order_no,
                {
                    "order_no": sub.sub_order_no,
                    "project_name": project.project_name if project else None,
                    "client_short_name": (
                        project.client.client_short_name if project and project.client else None
                    ),
                    "project_type": "translation",
                },
            )
        project = instance.translation_project
        return (
            (project.task_type or "项目任务") if project else "项目任务",
            (project.project_name or project.order_no) if project else "项目任务",
            {
                "order_no": project.order_no if project else None,
                "project_name": project.project_name if project else None,
                "client_short_name": project.client.client_short_name if project and project.client else None,
                "project_type": "translation",
            },
        )
    responsibility = item.project_responsibility
    project = responsibility.project if responsibility else None
    project_type = responsibility.project_type if responsibility else None
    return (
        PROJECT_ROLE_NAME_BY_CODE.get(responsibility.role_code, "项目任务") if responsibility else "项目任务",
        (project.project_name or project.order_no) if project else "项目任务",
        {
            "order_no": project.order_no if project else None,
            "project_name": project.project_name if project else None,
            "client_short_name": getattr(project, "client_short_name", None),
            "project_type": project_type,
            "responsibility_role_code": responsibility.role_code if responsibility else None,
        },
    )


def register_accepted_handover(db: Session, request: WorkflowHandoverRequest) -> list[WorkflowTaskDelegation]:
    """交接接受后建立临时代办关系，并给双方写入日报系统事件。"""
    requester_name = _display_user(request.requester)
    target_name = _display_user(request.target_user)
    now = _now()
    delegations: list[WorkflowTaskDelegation] = []
    for item in request.items or []:
        delegation = None
        if request.transfer_mode == "delegation":
            if request.delegation_end_at is None:
                raise ValueError("临时代办缺少计划结束时间")
            delegation = WorkflowTaskDelegation(
                handover_request_id=request.id,
                workflow_instance_id=item.workflow_instance_id,
                project_responsibility_id=item.project_responsibility_id,
                original_assignee_id=item.expected_assignee_id,
                delegate_assignee_id=request.target_user_id,
                planned_end_at=request.delegation_end_at,
                status="active",
                started_at=now,
            )
            db.add(delegation)
            db.flush()
            delegations.append(delegation)

        task_type, task_name, metadata = _source_identity(item)
        common = {
            "workflow_instance_id": item.workflow_instance_id,
            "project_responsibility_id": item.project_responsibility_id,
            "handover_request_id": request.id,
            "delegation_id": delegation.id if delegation else None,
            "task_type": task_type,
            "task_name": task_name,
            "display_metadata": {
                **metadata,
                "transfer_mode": request.transfer_mode,
                "original_assignee_name": requester_name,
                "current_assignee_name": target_name,
                "delegation_end_at": request.delegation_end_at.isoformat() if request.delegation_end_at else None,
            },
            "occurred_at": now,
        }
        record_task_activity(
            db,
            event_key=f"handover:{request.id}:{item.id}:out",
            user_id=request.requester_id,
            counterpart_user_id=request.target_user_id,
            event_type="handover_out",
            description=f"已将任务交接给{target_name}" if request.transfer_mode == "permanent" else f"已委托{target_name}临时代办任务",
            **common,
        )
        record_task_activity(
            db,
            event_key=f"handover:{request.id}:{item.id}:in",
            user_id=request.target_user_id,
            counterpart_user_id=request.requester_id,
            event_type="handover_in",
            description=f"已接收{requester_name}交接的任务" if request.transfer_mode == "permanent" else f"已接收{requester_name}委托的临时代办任务",
            **common,
        )
    return delegations


def enrich_work_items_with_delegation(
    db: Session, items: list[dict], current_user_id: UUID, *, include_all: bool = False
) -> list[dict]:
    workflow_ids = {item.get("workflow_instance_id") for item in items if item.get("workflow_instance_id")}
    responsibility_ids = {item.get("project_responsibility_id") for item in items if item.get("project_responsibility_id")}
    if not workflow_ids and not responsibility_ids:
        return items
    conditions = []
    if workflow_ids:
        conditions.append(WorkflowTaskDelegation.workflow_instance_id.in_(workflow_ids))
    if responsibility_ids:
        conditions.append(WorkflowTaskDelegation.project_responsibility_id.in_(responsibility_ids))
    rows = db.query(WorkflowTaskDelegation).options(
        joinedload(WorkflowTaskDelegation.original_assignee),
        joinedload(WorkflowTaskDelegation.delegate_assignee),
    ).filter(
        WorkflowTaskDelegation.status == "active",
        or_(*conditions),
    ).all()
    by_source = {
        ("workflow", row.workflow_instance_id) if row.workflow_instance_id else ("responsibility", row.project_responsibility_id): row
        for row in rows
    }
    permanent_items = db.query(WorkflowHandoverItem).options(
        joinedload(WorkflowHandoverItem.request).joinedload(WorkflowHandoverRequest.requester)
    ).join(
        WorkflowHandoverRequest,
        WorkflowHandoverRequest.id == WorkflowHandoverItem.request_id,
    ).filter(
        WorkflowHandoverRequest.status == "accepted",
        WorkflowHandoverRequest.transfer_mode == "permanent",
        or_(
            WorkflowHandoverItem.workflow_instance_id.in_(workflow_ids or {None}),
            WorkflowHandoverItem.project_responsibility_id.in_(responsibility_ids or {None}),
        ),
    ).order_by(WorkflowHandoverRequest.decided_at.desc()).all()
    previous_by_source = {}
    for history_item in permanent_items:
        history_key = (
            ("workflow", history_item.workflow_instance_id)
            if history_item.workflow_instance_id
            else ("responsibility", history_item.project_responsibility_id)
        )
        previous_by_source.setdefault(history_key, history_item.request)
    now = _now()
    for item in items:
        key = (
            ("workflow", item.get("workflow_instance_id"))
            if item.get("workflow_instance_id")
            else ("responsibility", item.get("project_responsibility_id"))
        )
        row = by_source.get(key)
        if not row:
            previous = previous_by_source.get(key)
            if previous and permanent_handover_applies_to_current_item(item, previous):
                item.update({
                    "transfer_mode": "permanent",
                    "original_assignee_id": previous.requester_id,
                    "original_assignee_name": _display_user(previous.requester),
                })
            else:
                item.setdefault("transfer_mode", None)
            continue
        item.update({
            "transfer_mode": "delegation",
            "delegation_id": row.id,
            "original_assignee_id": row.original_assignee_id,
            "original_assignee_name": _display_user(row.original_assignee),
            "delegation_end_at": row.planned_end_at,
            "delegation_overdue": row.planned_end_at < now,
        })
        if row.original_assignee_id == current_user_id and row.delegate_assignee_id != current_user_id:
            item["assignment_type"] = "delegated_out"
    return items


def _can_administer(db: Session, user_id: UUID) -> bool:
    return ALL_PERMISSION in get_user_permission_codes(db, user_id)


def return_delegations(
    db: Session,
    delegation_ids: list[UUID],
    operator: AppUser,
    note: str | None = None,
) -> dict:
    from crud import create_notifications_for_users, get_user_roles_with_role_names
    from leave_service import ensure_user_assignable
    from project_workbench_service import user_has_responsibility_role

    ids = list(dict.fromkeys(delegation_ids))
    rows = db.query(WorkflowTaskDelegation).options(
        joinedload(WorkflowTaskDelegation.original_assignee),
        joinedload(WorkflowTaskDelegation.delegate_assignee),
        joinedload(WorkflowTaskDelegation.workflow_instance),
        joinedload(WorkflowTaskDelegation.project_responsibility),
    ).filter(WorkflowTaskDelegation.id.in_(ids)).with_for_update().all()
    if len(rows) != len(ids):
        raise LookupError("部分临时代办记录不存在")
    is_admin = _can_administer(db, operator.id)
    now = _now()
    notifications = []
    for row in rows:
        if row.status != "active":
            raise LookupError("部分临时代办已经结束，请刷新后重试")
        if operator.id not in {row.original_assignee_id, row.delegate_assignee_id} and not is_admin:
            raise PermissionError("只有原负责人、当前代办人或超级管理员可以归还任务")
        original = row.original_assignee
        if not original or not original.is_active:
            raise ValueError("原负责人已停用，暂不能归还")
        ensure_user_assignable(db, original.id)

        if row.workflow_instance_id:
            source = row.workflow_instance
            if not source or source.current_stage_key == "completed":
                raise LookupError("任务已经完成，不能再执行归还")
            if source.current_assignee_id != row.delegate_assignee_id:
                raise LookupError("任务当前负责人已变化，不能按原代办关系归还")
            role_name = get_stage_role(source.current_stage_key)["role_name"]
            if role_name not in set(get_user_roles_with_role_names(db, original.id)):
                raise PermissionError(f"原负责人已不具备{role_name}角色")
            source.current_assignee_id = original.id
            source.updated_at = now
            item = WorkflowHandoverItem(
                workflow_instance_id=source.id,
                expected_assignee_id=original.id,
            )
            item.workflow_instance = source
        else:
            source = row.project_responsibility
            if not source or not source.project:
                raise LookupError("项目责任已经不存在")
            if source.assignee_id != row.delegate_assignee_id:
                raise LookupError("任务当前负责人已变化，不能按原代办关系归还")
            if not user_has_responsibility_role(db, original.id, source.role_code):
                raise PermissionError(f"原负责人已不具备{PROJECT_ROLE_NAME_BY_CODE[source.role_code]}角色")
            source.assignee_id = original.id
            source.updated_at = now
            item = WorkflowHandoverItem(
                project_responsibility_id=source.id,
                expected_assignee_id=original.id,
            )
            item.project_responsibility = source

        row.status = "returned"
        row.ended_at = now
        row.ended_by_id = operator.id
        row.end_note = (note or "").strip() or None
        task_type, task_name, metadata = _source_identity(item)
        original_name = _display_user(original)
        delegate_name = _display_user(row.delegate_assignee)
        common = {
            "workflow_instance_id": row.workflow_instance_id,
            "project_responsibility_id": row.project_responsibility_id,
            "handover_request_id": row.handover_request_id,
            "delegation_id": row.id,
            "task_type": task_type,
            "task_name": task_name,
            "display_metadata": {
                **metadata,
                "transfer_mode": "delegation",
                "original_assignee_name": original_name,
                "delegate_assignee_name": delegate_name,
            },
            "occurred_at": now,
        }
        record_task_activity(
            db,
            event_key=f"delegation:{row.id}:return_out",
            user_id=row.delegate_assignee_id,
            counterpart_user_id=row.original_assignee_id,
            event_type="return_out",
            description=f"已将临时代办任务归还给{original_name}",
            **common,
        )
        record_task_activity(
            db,
            event_key=f"delegation:{row.id}:return_in",
            user_id=row.original_assignee_id,
            counterpart_user_id=row.delegate_assignee_id,
            event_type="return_in",
            description=f"已收回由{delegate_name}代办的任务",
            **common,
        )
        notifications.extend(create_notifications_for_users(
            db,
            recipient_user_ids=list({row.original_assignee_id, row.delegate_assignee_id} - {operator.id}),
            title="临时代办任务已归还",
            content=f"任务“{task_name}”已归还给{original_name}。",
            notification_type="workflow_delegation_returned",
            commit=False,
        ))
    db.commit()
    return {
        "action": "return_delegation",
        "transferred_count": len(rows),
        "workflow_instance_ids": [row.workflow_instance_id for row in rows if row.workflow_instance_id],
        "project_responsibility_ids": [row.project_responsibility_id for row in rows if row.project_responsibility_id],
        "_notifications": notifications,
    }


def close_completed_delegations(db: Session) -> int:
    from project_workbench_service import is_active_project

    rows = db.query(WorkflowTaskDelegation).options(
        joinedload(WorkflowTaskDelegation.workflow_instance),
        joinedload(WorkflowTaskDelegation.project_responsibility),
    ).filter(WorkflowTaskDelegation.status == "active").all()
    changed = 0
    now = _now()
    for row in rows:
        completed = False
        if row.workflow_instance_id:
            completed = not row.workflow_instance or row.workflow_instance.current_stage_key == "completed"
        elif row.project_responsibility_id:
            responsibility = row.project_responsibility
            completed = (
                not responsibility
                or not responsibility.project
                or not is_active_project(responsibility.project_type, responsibility.project.project_status)
            )
        if completed:
            row.status = "completed"
            row.ended_at = now
            changed += 1
    if changed:
        db.commit()
    return changed


def notify_overdue_delegations(db: Session) -> int:
    """每条到期代办只生成一次提醒；到期不会改变当前负责人。"""
    from crud import create_notifications_for_users

    now = _now()
    rows = db.query(WorkflowTaskDelegation).filter(
        WorkflowTaskDelegation.status == "active",
        WorkflowTaskDelegation.planned_end_at < now,
        WorkflowTaskDelegation.overdue_notified_at.is_(None),
    ).with_for_update(skip_locked=True).all()
    for row in rows:
        create_notifications_for_users(
            db,
            recipient_user_ids=[row.original_assignee_id, row.delegate_assignee_id],
            title="临时代办已到期",
            content="临时代办任务已超过计划结束时间，当前仍由代办人负责，请及时确认是否归还。",
            notification_type="workflow_delegation_overdue",
            commit=False,
        )
        row.overdue_notified_at = now
    if rows:
        db.commit()
    return len(rows)
