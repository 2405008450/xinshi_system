"""分类和检索均使用原会话权限，不根据主题扩展数据可见范围。"""
from time import monotonic
from weakref import WeakKeyDictionary
from fastapi import HTTPException
from sqlalchemy import inspect, or_
from sqlalchemy.orm import object_session
from models import AppUser, ChatDirectConversation, ChatProjectEnabled, ChatProjectMessage, TranslationProject
from annotation_models import AnnotationProject
from permission_service import user_has_permission
from business_time import business_iso
from chat_topic_models import ChatTopic as Topic, ChatMessageTopic as Link, ChatTopicAudit, topic_now

_ready = WeakKeyDictionary()


def schema_ready(db):
    bind = db.get_bind()
    cached = _ready.get(bind)
    if cached and monotonic() - cached[0] < 5:
        return cached[1]
    inspector = inspect(bind)
    result = all(inspector.has_table(name) for name in ('chat_topic', 'chat_message_topic', 'chat_topic_audit'))
    _ready[bind] = monotonic(), result
    return result


def require_ready(db):
    if not schema_ready(db):
        raise HTTPException(503, '讨论主题尚未完成数据库迁移，请联系管理员')


def capabilities(db, user):
    return dict(ready=schema_ready(db), can_manage=user_has_permission(db, user.id, 'chat_topics:manage'),
                can_classify_others=user_has_permission(db, user.id, 'chat_topics:classify'))


def topic_rows(db):
    return db.query(Topic).order_by(Topic.sort_order, Topic.name, Topic.id).all()


def topic_path(row, rows):
    parent = rows.get(row.parent_id)
    return f'{parent.name} / {row.name}' if parent else row.name


def serialize_topic(row, rows):
    parent = rows.get(row.parent_id)
    return dict(id=str(row.id), parent_id=str(row.parent_id) if row.parent_id else None,
                builtin_key=row.builtin_key, kind=row.kind, name=row.name, description=row.description,
                sort_order=row.sort_order, active=row.active, selectable=row.kind == 'topic' and row.active and (not parent or parent.active),
                path=topic_path(row, rows), revision=row.revision, updated_at=business_iso(row.updated_at))


def get_topic(db, topic_id, *, selecting=False):
    row = db.get(Topic, topic_id)
    if not row or row.kind != 'topic':
        raise HTTPException(422, '讨论主题不存在或不能用于分类')
    parent = db.get(Topic, row.parent_id) if row.parent_id else None
    if selecting and (not row.active or (parent and not parent.active)):
        raise HTTPException(409, '讨论主题已停用，请重新选择')
    return row


def descendant_ids(db, topic_id):
    row = get_topic(db, topic_id)
    return [row.id] + [value for value, in db.query(Topic.id).filter(Topic.parent_id == row.id)]


def filter_topic(db, query, topic_id):
    require_ready(db)
    return query.filter(ChatProjectMessage.id.in_(db.query(Link.message_id).filter(Link.topic_id.in_(descendant_ids(db, topic_id)))))


def visible_messages(db, user):
    """SQL 层过滤后才统计和分页；管理员也不能越过私聊双方边界。"""
    direct = db.query(ChatDirectConversation.id).filter(or_(ChatDirectConversation.user_low_id == user.id,
                                                          ChatDirectConversation.user_high_id == user.id))
    clauses = [ChatProjectMessage.direct_conversation_id.in_(direct)]
    if user_has_permission(db, user.id, 'projects:read'):
        clauses += [ChatProjectMessage.annotation_project_id.in_(db.query(AnnotationProject.id)),
                    ChatProjectMessage.project_id.in_(db.query(TranslationProject.id).join(ChatProjectEnabled,
                        ChatProjectEnabled.project_id == TranslationProject.id).filter(ChatProjectEnabled.enabled.is_(True)))]
    return db.query(ChatProjectMessage).filter(or_(*clauses), ChatProjectMessage.recalled_at.is_(None),
                                             ChatProjectMessage.message_type == 'user')


def require_message(db, user, message_id, *, lock=False):
    query = visible_messages(db, user).filter(ChatProjectMessage.id == message_id)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, '消息不存在、已撤回或不可访问')
    return row


def audit(db, user, entity_id, action, before, after):
    db.add(ChatTopicAudit(entity_id=entity_id, actor_id=user.id, action=action, before=before, after=after))


def notify_menu_changed(db):
    from notification_ws import broadcast_to_users
    broadcast_to_users([uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True))], {'type': 'chat_topics_changed'})


def set_message_topic(db, user, message, topic_id, revision=None):
    require_ready(db)
    if message.sender_user_id != user.id and not user_has_permission(db, user.id, 'chat_topics:classify'):
        raise HTTPException(403, '只能修改本人消息的讨论主题')
    link = db.get(Link, message.id, populate_existing=True)
    current = link.revision if link else 0
    if revision is not None and revision != current:
        raise HTTPException(409, '消息分类已被其他人修改，请重新加载')
    if topic_id:
        get_topic(db, topic_id, selecting=True)
    before = dict(topic_id=str(link.topic_id) if link and link.topic_id else None, revision=current)
    if not link:
        link = Link(message_id=message.id, updated_by=user.id)
        db.add(link)
    link.topic_id, link.updated_by, link.updated_at, link.revision = topic_id, user.id, topic_now(), current + 1
    after = dict(topic_id=str(topic_id) if topic_id else None, revision=link.revision)
    audit(db, user, message.id, 'message.classify', before, after)
    db.flush()
    db.info.pop('chat_topic_metadata', None)


def message_metadata(message, user_id):
    db = object_session(message)
    empty = dict(topic_id=None, topic_path=None, topic_revision=0, can_classify=False)
    if not db or not schema_ready(db) or message.recalled_at:
        return empty
    cache = db.info.setdefault('chat_topic_metadata', {})
    key = str(user_id)
    if key not in cache:
        cache[key] = {}
    values = cache[key]
    if message.id not in values:
        # 一次载入当前结果集的分类，避免逐条查询消息关联。
        ids = [obj.id for obj in db.identity_map.values() if isinstance(obj, ChatProjectMessage) and obj.id not in values]
        rows = {row.id: row for row in topic_rows(db)}
        links = {link.message_id: link for link in db.query(Link).filter(Link.message_id.in_(ids))}
        manager = bool(user_id and user_has_permission(db, user_id, 'chat_topics:classify'))
        for obj in list(db.identity_map.values()):
            if isinstance(obj, ChatProjectMessage) and obj.id in ids:
                link = links.get(obj.id)
                topic = rows.get(link.topic_id) if link else None
                values[obj.id] = dict(topic_id=str(topic.id) if topic else None,
                    topic_path=topic_path(topic, rows) if topic else None, topic_revision=link.revision if link else 0,
                    can_classify=obj.message_type == 'user' and not obj.recalled_at and (obj.sender_user_id == user_id or manager))
    return values.get(message.id, empty)


def issue_topic(db, topic_id):
    row = get_topic(db, topic_id, selecting=True)
    rows = {value.id: value for value in topic_rows(db)}
    return dict(topic_id=row.id, topic_path=topic_path(row, rows))


def search(db, user, topic_id, scope, conversation_type, conversation_id, keyword, before, limit):
    query = filter_topic(db, visible_messages(db, user), topic_id)
    if scope == 'current':
        if not conversation_id or conversation_type not in ('translation', 'annotation', 'direct'):
            raise HTTPException(422, '请先选择当前会话')
        column = {'translation': ChatProjectMessage.project_id, 'annotation': ChatProjectMessage.annotation_project_id,
                  'direct': ChatProjectMessage.direct_conversation_id}[conversation_type]
        query = query.filter(column == conversation_id)
    if keyword.strip():
        escaped = keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(ChatProjectMessage.content.ilike(f'%{escaped}%', escape='\\'))
    total = query.count()
    if before:
        query = query.filter(ChatProjectMessage.sequence_no < before)
    rows = query.order_by(ChatProjectMessage.sequence_no.desc()).limit(limit + 1).all()
    more, rows = len(rows) > limit, rows[:limit]
    # 提前批量读取来源标题，不泄露未经过过滤的会话。
    annotations = {p.id: p for p in db.query(AnnotationProject).filter(AnnotationProject.id.in_([m.annotation_project_id for m in rows if m.annotation_project_id]))}
    translations = {p.id: p for p in db.query(TranslationProject).filter(TranslationProject.id.in_([m.project_id for m in rows if m.project_id]))}
    directs = {p.id: p for p in db.query(ChatDirectConversation).filter(ChatDirectConversation.id.in_([m.direct_conversation_id for m in rows if m.direct_conversation_id]))}
    people = {p.id: p for p in db.query(AppUser).filter(AppUser.id.in_([uid for p in directs.values() for uid in (p.user_low_id, p.user_high_id)]))}
    items = []
    for row in rows:
        if row.direct_conversation_id:
            conversation = directs[row.direct_conversation_id]
            person = people.get(conversation.user_high_id if user.id == conversation.user_low_id else conversation.user_low_id)
            kind, target, title = 'direct', conversation.id, f'与{(person.full_name or person.username) if person else "已删除用户"}的私聊'
        else:
            kind = 'annotation' if row.annotation_project_id else 'translation'
            project = (annotations if kind == 'annotation' else translations)[row.annotation_project_id or row.project_id]
            target, title = project.id, f'{project.order_no or ""} {project.project_name or ""}'.strip()
        items.append(dict(id=str(row.id), conversation_type=kind, conversation_id=str(target), source_title=title,
                          sender_name=row.sender_name, created_at=business_iso(row.created_at), content=row.content,
                          **message_metadata(row, user.id)))
    return dict(items=items, total=total, next_before=rows[-1].sequence_no if more and rows else None)
