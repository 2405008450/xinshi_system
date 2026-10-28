"""开拓问题：逐记录授权、聊天来源验证、任务事务与审计。"""
from time import monotonic
from weakref import WeakKeyDictionary
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import inspect, or_, and_
from sqlalchemy.dialects.postgresql import insert
from fastapi.encoders import jsonable_encoder

from business_time import business_iso
from models import AppUser, ChatProjectMessage
from permission_service import user_has_permission
from resource_development_service import is_admin, can_delegate, active_user, check_revision
from resource_development_models import DevelopmentAudit
from resource_issue_models import DevelopmentIssue as Issue, DevelopmentIssueTask as Task, business_now
from resource_issue_models import DevelopmentIssueAudience as Audience
import resource_summary_service as summary_service

RESOURCE_PERMISSIONS = ("talents:read", "talents:write", "translators:read", "translators:write", "resource_development:delegate")


def resource_access(db, user):
    return any(user_has_permission(db, user.id, p) for p in RESOURCE_PERMISSIONS)


def can_collect(db, user):
    return can_delegate(db, user) or any(user_has_permission(db, user.id, p) for p in ("talents:write", "translators:write"))


_schema_cache = WeakKeyDictionary()


def schema_ready(bind):
    cached = _schema_cache.get(bind)
    if cached and monotonic() - cached[0] < 5:
        return cached[1]
    inspector = inspect(bind)
    ready = inspector.has_table(Issue.__tablename__) and inspector.has_table(Task.__tablename__)
    if ready:
        ready = {'topic_id', 'topic_path', 'client_request_id','summary_data'} <= {c['name'] for c in inspector.get_columns(Issue.__tablename__)} and inspector.has_table(Audience.__tablename__) and inspector.has_table('system_department')
    _schema_cache[bind] = (monotonic(), ready)
    return ready


def require_ready(db):
    if not schema_ready(db.get_bind()):
        raise HTTPException(503, "开拓问题尚未完成数据库迁移，请联系管理员")


def visible_query(db, user):
    q = db.query(Issue)
    if not can_delegate(db, user):
        assigned = db.query(Task.id).filter(Task.issue_id == Issue.id, Task.executor_id == user.id).exists()
        summary_member=db.query(Audience.issue_id).filter(Audience.issue_id==Issue.id,Audience.kind.in_(['follower','notify_user']),Audience.target_id==user.id).exists()
        legacy = or_(Issue.proposer_id == user.id, assigned, summary_member)
        from department_models import Department, DepartmentMember
        from department_utils import department_filter_values
        from organization_service import ready as memberships_ready
        primary_names = department_filter_values(user.department or '', db)
        department_ids = {item.id for item in db.query(Department).filter(Department.name.in_(primary_names))}
        if memberships_ready(db):
            department_ids.update(uid for uid, in db.query(DepartmentMember.department_id).filter(DepartmentMember.user_id == user.id))
        selected = [Issue.summary_data['view_user_ids'].as_string().contains(f'"{user.id}"')]
        selected.extend(Issue.summary_data['view_department_ids'].as_string().contains(f'"{uid}"') for uid in department_ids)
        scope = Issue.summary_data['view_all'].as_boolean()
        q = q.filter(or_(Issue.collected_by == user.id, scope.is_(True),
                         and_(scope.is_(False), or_(*selected)), and_(scope.is_(None), legacy)))
    return q


def capabilities(db, user):
    ready = schema_ready(db.get_bind())
    module = resource_access(db, user)
    collect = can_collect(db, user)
    associated = ready and visible_query(db, user).first() is not None
    return dict(ready=ready,summary_ready=ready, can_enter=module or associated, can_collect=collect and ready,
                can_manage=can_delegate(db, user), can_resource=module, user_id=str(user.id), user_name=user.full_name or user.username)


def get_issue(db, user, issue_id, *, lock=False):
    q = visible_query(db, user).filter(Issue.id == issue_id)
    if lock:
        q = q.with_for_update().populate_existing()
    row = q.first()
    if row is None:
        raise HTTPException(404, "开拓记录不存在或不可访问")
    return row


def can_edit(db, user, row):
    return can_delegate(db, user) or (can_collect(db, user) and user.id in (row.proposer_id, row.collected_by))


def can_delete(db, user, row):
    return is_admin(db, user) or (row.collected_by == user.id and can_collect(db, user))


def require_edit(db, user, row):
    if not can_edit(db, user, row):
        raise HTTPException(403, "没有维护此记录和安排任务的权限")


def source_preview(db, user, message_id, *, lock=False):
    q = db.query(ChatProjectMessage).filter(ChatProjectMessage.id == message_id)
    if lock:
        q = q.with_for_update().populate_existing()
    message = q.first()
    if message is None:
        raise HTTPException(404, "来源消息已删除或不存在")
    # 三种对话分别验证，私聊永远验证双方身份，管理员也不能旁路。
    if message.direct_conversation_id:
        from direct_chat_service import require_project
        conversation = require_project(db, message.direct_conversation_id, user)
        other_id = conversation.user_high_id if user.id == conversation.user_low_id else conversation.user_low_id
        other = db.get(AppUser, other_id)
        title = f"与{(other.full_name or other.username) if other else '已删除用户'}的私聊"
        kind, target = "direct", conversation.id
    elif message.annotation_project_id:
        from annotation_chat_service import require_project
        project = require_project(db, message.annotation_project_id, user)
        title = f"{project.order_no or ''} {project.project_name or ''} · 标注项目沟通".strip()
        kind, target = "annotation", project.id
    else:
        if not user_has_permission(db, user.id, "projects:read"):
            raise HTTPException(403, "没有访问原项目对话的权限")
        from routers.project_chat import _require_project
        from project_chat_crud import get_project_chat_settings
        project = _require_project(db, message.project_id)
        from chat_access_service import require_member
        require_member(db, 'translation', project.id, user)
        settings = get_project_chat_settings(db, project.id)
        if not settings or not settings.enabled:
            raise HTTPException(403, "原项目沟通未开启")
        title = f"{project.order_no or ''} {project.project_name or ''} · 笔译项目沟通".strip()
        kind, target = "translation", project.id
    if message.recalled_at:
        raise HTTPException(409, "来源消息已撤回")
    if message.message_type != "user" or not message.content.strip() or not message.sender_user_id:
        raise HTTPException(422, "只能收录有文字和提出人的普通聊天消息")
    from chat_topic_service import message_metadata
    topic = message_metadata(message, user.id)
    return dict(source_message_id=message.id, source_type=kind, source_conversation_id=target,
                topic_id=topic['topic_id'], topic_path=topic['topic_path'] or '',
                source_title=title[:500], source_content=message.content,
                proposer_id=message.sender_user_id, proposer_name=message.sender_name)


def snapshot(row):
    values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    for name in ("created_at", "updated_at"):
        values[name] = business_iso(values[name])
    return jsonable_encoder(values)


def audit(db, user, row, action, before=None):
    db.flush()
    db.add(DevelopmentAudit(entity_id=row.id, entity_type="issue_task" if isinstance(row, Task) else "issue",
                            actor_id=user.id, action=action, before=before or {}, after=snapshot(row),
                            created_at=business_now().replace(tzinfo=None)))


def tasks(db, row):
    return db.query(Task).filter(Task.issue_id == row.id).order_by(Task.created_at, Task.id).all()


def serialize(db, user, row, *, detail=False, children=None, authority=None, summary_info=None, discussion_source=None):
    result = snapshot(row)
    result.update(summary_info or summary_service.display_data(db,[row])[row.id])
    if children is None:
        children = tasks(db, row)
    if authority is None:
        authority = dict(manage=can_delegate(db, user), collect=can_collect(db, user), admin=is_admin(db, user))
    result.update(can_edit=authority['manage'] or (authority['collect'] and user.id in (row.proposer_id, row.collected_by)),
                  can_delete=authority['admin'] or (row.collected_by == user.id and authority['collect']),
                  task_count=len(children), executor_names=list(dict.fromkeys([*result.get('follower_names',[]),*[t.executor_name for t in children]])),
                  task_status_counts={status: sum(t.status == status for t in children)
                                      for status in ("pending", "in_progress", "completed", "cancelled")})
    if detail:
        result["tasks"] = [dict(snapshot(t), can_edit=result["can_edit"],
                                can_update_progress=result["can_edit"] or t.executor_id == user.id) for t in children]
    else:
        result.pop("source_content")
    result['can_update_progress']=result['can_edit'] or summary_service.progress_allowed(user,row)
    import discussion_issue_sources as discussion_sources
    if discussion_source is None:
        discussion_source = discussion_sources.for_issues(db,[row.id]).get(row.id)
    discussion_sources.decorate(result,discussion_source)
    return result


def create_issue(db, user, payload):
    if not can_collect(db, user):
        raise HTTPException(403, "没有开拓收录权限")
    discussion_source = None
    if payload.source_discussion_room_id:
        import discussion_issue_sources as discussion_sources
        from discussion_chat_models import DiscussionIssueSource
        if not discussion_sources.ready(db): raise HTTPException(503,'讨论分类保存尚未初始化')
        source = discussion_sources.preview(db,user,payload.source_discussion_room_id,payload.source_discussion_message_id,lock=True)
        existing_source = db.query(DiscussionIssueSource).filter_by(message_id=payload.source_discussion_message_id,category=payload.category).first()
        if existing_source:
            existing = visible_query(db,user).filter(Issue.id == existing_source.issue_id).first()
            if not existing: raise HTTPException(409,'该消息已保存，你没有查看权限')
            return dict(serialize(db,user,existing,detail=True),already_collected=True)
        # 既有来源枚举不做结构变更；真实讨论来源保存在独立关联表中。
        source['source_type'] = 'manual'
        discussion_source = DiscussionIssueSource(room_id=payload.source_discussion_room_id,
            message_id=payload.source_discussion_message_id,category=payload.category)
    elif payload.source_message_id:
        source = source_preview(db, user, payload.source_message_id, lock=True)
    else:
        source = dict(source_message_id=None, source_conversation_id=None, source_type='manual',
                      source_title='手工新增', source_content='', proposer_id=user.id,
                      proposer_name=user.full_name or user.username, topic_id=None, topic_path='')
    if 'topic_id' in payload.model_fields_set:
        if payload.topic_id and str(payload.topic_id) != str(source.get('topic_id')):
            from chat_topic_service import issue_topic
            source.update(issue_topic(db, payload.topic_id))
        elif not payload.topic_id:
            source.update(topic_id=None, topic_path='')
    issue_id = uuid4()
    now = business_now()
    values = dict(id=issue_id, **source, category=payload.category, content=payload.content, remarks=payload.remarks,
                  collected_by=user.id, collected_by_name=user.full_name or user.username, updated_by=user.id,
                  created_at=now, updated_at=now, revision=1,
                  client_request_id=payload.client_request_id if not payload.source_message_id and not discussion_source else None)
    inserted = db.execute(insert(Issue).values(**values).on_conflict_do_nothing().returning(Issue.id)).scalar_one_or_none()
    if inserted is None:
        if payload.source_message_id:
            existing = db.query(Issue).filter_by(source_message_id=payload.source_message_id, category=payload.category).one()
        else:
            existing = db.query(Issue).filter_by(collected_by=user.id, client_request_id=payload.client_request_id).one()
        accessible = visible_query(db, user).filter(Issue.id == existing.id).first()
        if not accessible:
            raise HTTPException(409, "该消息已按此类别收录，你没有查看该记录的权限")
        return dict(serialize(db, user, accessible, detail=True), already_collected=True)
    row = db.get(Issue, inserted)
    if discussion_source:
        discussion_source.issue_id = row.id
        db.add(discussion_source)
        db.flush()
    summary_service.write_summary(db,row,payload.summary)
    audit(db, user, row, "create")
    return dict(serialize(db, user, row, detail=True), already_collected=False)


def touch(db, user, row):
    row.updated_by, row.updated_at, row.revision = user.id, business_now(), row.revision + 1


def update_issue(db, user, issue_id, payload):
    row = get_issue(db, user, issue_id, lock=True)
    require_edit(db, user, row)
    check_revision(row, payload.revision)
    before = snapshot(row)
    row.content, row.remarks = payload.content, payload.remarks
    summary_service.write_summary(db,row,payload.summary)
    if 'topic_id' in payload.model_fields_set and payload.topic_id != row.topic_id:
        if payload.topic_id:
            from chat_topic_service import issue_topic
            for name, value in issue_topic(db, payload.topic_id).items():
                setattr(row, name, value)
        else:
            row.topic_id, row.topic_path = None, ''
    touch(db, user, row)
    audit(db, user, row, "update", before)
    return serialize(db, user, row, detail=True)


def write_task(db, user, issue_id, payload, task_id=None):
    row = get_issue(db, user, issue_id, lock=True)
    check_revision(row, payload.revision)
    manage = can_edit(db, user, row)
    task = db.query(Task).filter_by(id=task_id, issue_id=row.id).first() if task_id else None
    if task_id and task is None:
        raise HTTPException(404, "后续任务不存在")
    values = payload.model_dump(exclude_unset=True, exclude={"revision"})
    if not manage:
        if task is None or task.executor_id != user.id:
            raise HTTPException(403, "只能更新本人任务的进度")
        if set(values) - {"status", "progress", "completed_date"}:
            raise HTTPException(403, "执行人不能修改任务内容、日期或人员分配")
    before = snapshot(task) if task else {}
    if task is None:
        if not values.get("content") or not values.get("executor_id"):
            raise HTTPException(422, "请填写任务内容并选择执行人")
        task = Task(id=uuid4(), issue_id=row.id, created_by=user.id, updated_by=user.id,
                    created_at=business_now(), updated_at=business_now(), revision=1, status="pending", progress="", remarks="")
    if "executor_id" in values:
        executor = active_user(db, values["executor_id"])
        task.executor_name = executor.full_name or executor.username
    for name, value in values.items():
        setattr(task, name, value)
    today = business_now().date()
    if task.status == "completed":
        task.completed_date = task.completed_date or today
        if task.completed_date > today:
            raise HTTPException(422, "实际完成日期不能晚于香港时间当天")
    else:
        task.completed_date = None
    task.updated_by, task.updated_at = user.id, business_now()
    if not before:
        db.add(task)
    if before:
        task.revision += 1
    touch(db, user, row)
    audit(db, user, task, "update" if before else "create", before)
    return serialize(db, user, row, detail=True)


def delete_task(db, user, issue_id, task_id, revision):
    row = get_issue(db, user, issue_id, lock=True)
    require_edit(db, user, row)
    check_revision(row, revision)
    task = db.query(Task).filter_by(id=task_id, issue_id=row.id).first()
    if task is None:
        raise HTTPException(404, "后续任务不存在")
    audit(db, user, task, "delete", snapshot(task))
    db.delete(task)
    touch(db, user, row)
    db.flush()
    return serialize(db, user, row, detail=True)


def delete_issue(db, user, issue_id, revision):
    row = get_issue(db, user, issue_id, lock=True)
    if not can_delete(db, user, row):
        raise HTTPException(403, "只能删除本人收录的记录，删除他人记录需要管理员权限")
    check_revision(row, revision)
    for task in tasks(db, row):
        audit(db, user, task, "delete", snapshot(task))
    audit(db, user, row, "delete", snapshot(row))
    db.delete(row)
