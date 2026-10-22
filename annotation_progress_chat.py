"""标注进度的共享默认提及名单，以及同事务同步到对应订单会话。"""
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy import Integer, JSON, DateTime, ForeignKey, Uuid, inspect
from sqlalchemy.orm import mapped_column
from fastapi import HTTPException
from models import Base, AppUser, AnnotationChatMember, ChatProjectMessage
from annotation_progress_time import business_now


class ProgressMentionDefaults(Base):
    __tablename__ = 'annotation_progress_mention_defaults'
    id = mapped_column(Integer, primary_key=True)
    user_ids = mapped_column(JSON, nullable=False, default=list)
    department_ids = mapped_column(JSON, nullable=False, default=list)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


class MentionSelection(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    department_ids: list[UUID] = Field(default_factory=list, max_length=500)


class ProgressChatDelivery(MentionSelection):
    send_to_chat: bool = False


def options(db, user, scope='progress'):
    import annotation_chat_service as chat
    from department_service import catalog
    from department_service import alias_map
    from department_utils import normalize_department
    from permission_service import user_has_permission
    if not chat.can_view(db, user):
        raise HTTPException(403, '没有项目沟通权限')
    ready = inspect(db.connection()).has_table(ProgressMentionDefaults.__tablename__)
    row = db.get(ProgressMentionDefaults, 2 if scope=='creation' else 1) if ready else None
    departments = catalog(db, user)['items']
    department_ids = {d['name']: str(d['id']) for d in departments}
    aliases = alias_map(db)
    from organization_service import directory
    membership_ids = {p['id']: [d['id'] for d in p['departments']] for p in directory(db,user)['people']}
    automatic=[u.id for u in chat.eligible_users(db) if (u.full_name or '').strip()=='赵震锋'] if scope=='creation' and row is None else []
    return dict(ready=ready, supports_creation=True, can_manage=user_has_permission(db, user.id, 'projects:write'), current_user_id=str(user.id),
                user_ids=row.user_ids if row else [], department_ids=row.department_ids if row else [], automatic_user_ids=automatic,
                users=[dict(id=u.id, name=u.full_name or u.username, department_ids=membership_ids.get(str(u.id), []),
                    department_id=department_ids.get(aliases.get((u.department or '').strip(),normalize_department(u.department or '')), '')) for u in chat.eligible_users(db)],
                departments=departments)


def resolve_users(db, selection, sender=None):
    import annotation_chat_service as chat
    from department_models import Department
    from department_service import alias_map
    from department_utils import normalize_department
    eligible = {u.id: u for u in chat.eligible_users(db)}
    selected = set(selection.user_ids)
    if not selected <= eligible.keys():
        raise HTTPException(422, '部分人员已停用或没有项目沟通权限，请重新选择')
    departments = db.query(Department).filter(Department.id.in_(selection.department_ids)).all() if selection.department_ids else []
    if len(departments) != len(set(selection.department_ids)):
        raise HTTPException(422, '部分部门不存在，请重新选择')
    names = {row.name for row in departments}
    aliases = alias_map(db) if names else {}
    from organization_service import department_condition
    if names:
        selected.update(uid for uid, in db.query(AppUser.id).filter(AppUser.id.in_(eligible), department_condition(db, names)))
    if sender:
        selected.discard(sender.id)
    return sorted(selected, key=str)


def save_defaults(db, user, selection, scope='progress'):
    from permission_service import user_has_permission
    if not user_has_permission(db, user.id, 'projects:write'):
        raise HTTPException(403, '没有修改默认@名单的权限')
    if not options(db, user)['ready']:
        raise HTTPException(503, '默认@配置尚未初始化，请联系管理员')
    resolve_users(db, selection)
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(646227451908632)'))
    row = db.get(ProgressMentionDefaults, 2 if scope=='creation' else 1)
    if row is None:
        row = ProgressMentionDefaults(id=2 if scope=='creation' else 1)
        db.add(row)
    row.user_ids = sorted({str(uid) for uid in selection.user_ids})
    row.department_ids = sorted({str(uid) for uid in selection.department_ids})
    row.updated_by = user.id
    row.updated_at = business_now()
    db.commit()
    return options(db, user, scope)


def enqueue(db, project_id, user_id, delivery, *, track, note, effective_on, attachment_ids=None, content_json=None):
    if not delivery or not delivery.send_to_chat:
        return
    import annotation_chat_service as chat
    from schemas import AnnotationProjectChatMessageCreate
    from chat_default_participant_service import default_user_ids
    user = db.get(AppUser, user_id)
    chat.require_project_record(db, project_id, user, lock=True)
    ids = resolve_users(db, delivery, user)
    exists = db.query(AnnotationChatMember.user_id).filter_by(project_id=project_id).first()
    if exists or db.query(ChatProjectMessage.id).filter_by(annotation_project_id=project_id).first():
        chat.require_project(db, project_id, user)
    else:
        eligible={u.id for u in chat.eligible_users(db)}
        for uid in (set(default_user_ids(db)) | {user.id}) & eligible:
            chat.add_member(db, project_id, uid)
    class ProgressMessage(AnnotationProjectChatMessageCreate):
        content: str = Field(default='', max_length=100000 if track=='creation' else 10000)
        mentioned_user_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    payload = ProgressMessage(content=note.strip(), mentioned_user_ids=ids, attachment_ids=attachment_ids or [])
    message=chat.send_message(db, project_id, user, payload, commit=False, max_mentions=2000)
    if content_json:message.content_json=content_json;db.flush()


def after_commit(db):
    import annotation_chat_service as chat
    from project_chat_crud import _push_notifications
    for project_id, user_id, message_id, notifications in db.info.pop('progress_chat_events', []):
        _push_notifications(notifications)
        chat.publish(db, project_id, 'message', message_id)
        chat.notify_state(user_id, project_id)
