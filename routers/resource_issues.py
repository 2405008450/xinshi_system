"""独立认证路由；关联人员无资源模块权限时也能访问本人记录。"""
from search_matching import keyword_ilike, keyword_or
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser
from routers.auth import get_current_user
import resource_issue_service as service
from resource_issue_models import DevelopmentIssue as Issue, DevelopmentIssueTask as Task
from resource_issue_schemas import IssueCategory, IssueTaskStatus, IssueCreate, IssueUpdate, IssueTaskWrite

router = APIRouter(prefix="/resource-development/issues", tags=["resource_issues"])


def user(user: AppUser = Depends(get_current_user)):
    if not user.is_active:
        raise HTTPException(403, "账号已停用")
    return user


def ready(db: Session = Depends(get_db)):
    service.require_ready(db)
    return db


@router.get("/access")
def access(db: Session = Depends(get_db), actor=Depends(user)):
    return service.capabilities(db, actor)


@router.get("/options")
def options(db=Depends(ready), actor=Depends(user)):
    caps = service.capabilities(db, actor)
    if not caps["can_enter"]:
        raise HTTPException(403, "没有开拓问题访问权限")
    people = [{"id": str(u.id), "name": u.full_name or u.username}
              for u in db.query(AppUser).filter(AppUser.is_active.is_(True)).order_by(AppUser.full_name, AppUser.id)]
    return dict(caps, users=people)


@router.get("/source/{message_id}")
def source(message_id: UUID, db=Depends(ready), actor=Depends(user)):
    if not service.can_collect(db, actor):
        raise HTTPException(403, "没有开拓收录权限")
    return service.source_preview(db, actor, message_id)


@router.get("")
def listing(keyword: str | None = Query(None, max_length=255), category: IssueCategory | None = None,
            topic_id: UUID | None = None,
            proposer_id: UUID | None = None, executor_id: UUID | None = None, status: IssueTaskStatus | None = None,
            planned_start: date | None = None, planned_end: date | None = None,
            skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db=Depends(ready), actor=Depends(user)):
    if planned_start and planned_end and planned_start > planned_end:
        raise HTTPException(422, "预定完成日期范围无效")
    q = service.visible_query(db, actor)
    if category:
        q = q.filter(Issue.category == category)
    if topic_id:
        from chat_topic_service import descendant_ids
        q = q.filter(Issue.topic_id.in_(descendant_ids(db, topic_id)))
    if proposer_id:
        q = q.filter(Issue.proposer_id == proposer_id)
    conditions = [Task.issue_id == Issue.id]
    if executor_id:
        conditions.append(Task.executor_id == executor_id)
    if status:
        conditions.append(Task.status == status)
    if planned_start:
        conditions.append(Task.planned_date >= planned_start)
    if planned_end:
        conditions.append(Task.planned_date <= planned_end)
    if len(conditions) > 1:
        q = q.filter(db.query(Task.id).filter(*conditions).exists())
    if keyword and keyword.strip():
        escaped = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        def match_part(part):
            def contains(column):
                return keyword_ilike(column, part, escape="\\")
            task_match = db.query(Task.id).filter(Task.issue_id == Issue.id, or_(*[
                contains(c) for c in (Task.content, Task.progress, Task.remarks, Task.executor_name)])).exists()
            return or_(*[contains(c) for c in (Issue.content, Issue.remarks, Issue.source_title, Issue.proposer_name)], task_match)
        q = q.filter(keyword_or(match_part, pattern))
    total = q.count()
    rows = q.order_by(Issue.created_at.desc(), Issue.id.desc()).offset(skip).limit(limit).all()
    # 一次加载当页任务和权限，避免每行重复查询远程业务数据库。
    grouped = {row.id: [] for row in rows}
    if grouped:
        for task in db.query(Task).filter(Task.issue_id.in_(grouped)).order_by(Task.created_at, Task.id):
            grouped[task.issue_id].append(task)
    authority = dict(manage=service.can_delegate(db, actor), collect=service.can_collect(db, actor), admin=service.is_admin(db, actor))
    return {"items": [service.serialize(db, actor, row, children=grouped[row.id], authority=authority) for row in rows], "total": total}


@router.post("")
def create(payload: IssueCreate, db=Depends(ready), actor=Depends(user)):
    result = service.create_issue(db, actor, payload)
    db.commit()
    return result


@router.get("/{issue_id}/source")
def locate_source(issue_id: UUID, db=Depends(ready), actor=Depends(user)):
    row = service.get_issue(db, actor, issue_id)
    if not row.source_message_id:
        return {'available': False, 'reason': '手工新增事项没有来源聊天消息'}
    try:
        source = service.source_preview(db, actor, row.source_message_id)
    except HTTPException as error:
        return {"available": False, "reason": error.detail}
    return dict(source, available=True)


@router.get("/{issue_id}")
def detail(issue_id: UUID, db=Depends(ready), actor=Depends(user)):
    return service.serialize(db, actor, service.get_issue(db, actor, issue_id), detail=True)


@router.put("/{issue_id}")
def update(issue_id: UUID, payload: IssueUpdate, db=Depends(ready), actor=Depends(user)):
    result = service.update_issue(db, actor, issue_id, payload)
    db.commit()
    return result


@router.delete("/{issue_id}")
def delete(issue_id: UUID, revision: int = Query(..., ge=1), db=Depends(ready), actor=Depends(user)):
    service.delete_issue(db, actor, issue_id, revision)
    db.commit()
    return {"deleted": True}


@router.post("/{issue_id}/tasks")
def add_task(issue_id: UUID, payload: IssueTaskWrite, db=Depends(ready), actor=Depends(user)):
    result = service.write_task(db, actor, issue_id, payload)
    db.commit()
    return result


@router.patch("/{issue_id}/tasks/{task_id}")
def edit_task(issue_id: UUID, task_id: UUID, payload: IssueTaskWrite, db=Depends(ready), actor=Depends(user)):
    result = service.write_task(db, actor, issue_id, payload, task_id)
    db.commit()
    return result


@router.delete("/{issue_id}/tasks/{task_id}")
def remove_task(issue_id: UUID, task_id: UUID, revision: int = Query(..., ge=1), db=Depends(ready), actor=Depends(user)):
    result = service.delete_task(db, actor, issue_id, task_id, revision)
    db.commit()
    return result
