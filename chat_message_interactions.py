"""消息引用与真实阅读回执；全部入口遵守当前会话参与人边界。"""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import inspect
from models import AppUser, ChatProjectMessage, ChatDirectMember
from discussion_chat_models import DiscussionMessage
from chat_access_service import MEMBERS, member_ids
from chat_message_view_models import ChatMessageView
from chat_time import api_time, now


def scope(db, kind, conversation_id, user):
    if kind == 'direct':
        import direct_chat_service
        direct_chat_service.require_project(db, conversation_id, user)
        recipients = {uid for uid, in db.query(ChatDirectMember.user_id).filter_by(conversation_id=conversation_id)}
    elif kind in MEMBERS:
        from routers.chat_sessions import _require_participant_scope
        _require_participant_scope(db, user, kind, conversation_id)
        recipients = member_ids(db, kind, conversation_id)
    else:
        raise HTTPException(404, '会话不存在')
    recipients = {uid for uid, in db.query(AppUser.id).filter(AppUser.id.in_(recipients), AppUser.is_active.is_(True))}
    if kind == 'discussion':
        return db.query(DiscussionMessage).filter_by(room_id=conversation_id), DiscussionMessage, recipients
    field = {'annotation': ChatProjectMessage.annotation_project_id, 'translation': ChatProjectMessage.project_id, 'direct': ChatProjectMessage.direct_conversation_id}[kind]
    return db.query(ChatProjectMessage).filter(field == conversation_id), ChatProjectMessage, recipients


def message_ids(kind, values):
    try:
        return list(dict.fromkeys(int(value) if kind == 'discussion' else UUID(str(value)) for value in values))
    except (ValueError, TypeError):
        raise HTTPException(400, '消息编号无效')


def sender_id(message, kind):
    return message.sender_id if kind == 'discussion' else message.sender_user_id


def brief(message, kind):
    recalled = bool(message.recalled_at)
    return api_time(dict(id=str(message.id), sender_user_id=sender_id(message, kind), sender_name=message.sender_name,
        content='消息已撤回' if recalled else message.content or '[附件]', created_at=message.created_at,
        recalled_at=message.recalled_at))


def ready(db):
    return inspect(db.connection()).has_table(ChatMessageView.__tablename__)


def stats(db, kind, conversation_id, user, values):
    query, model, recipients = scope(db, kind, conversation_id, user)
    ids = message_ids(kind, values)
    rows = query.filter(model.id.in_(ids)).all()
    if len(rows) != len(ids):
        raise HTTPException(404, '消息不属于当前会话')
    available = ready(db)
    names = {person.id: person.full_name or person.username for person in db.query(AppUser).filter(AppUser.id.in_(recipients))}
    views = db.query(ChatMessageView).filter_by(conversation_kind=kind, conversation_id=conversation_id).filter(
        ChatMessageView.message_id.in_([str(value) for value in ids]), ChatMessageView.user_id.in_(recipients)).all() if available and ids else []
    reply_field = model.reply_to_id if kind == 'discussion' else model.reply_to_message_id
    replies = query.filter(reply_field.in_(ids), model.recalled_at.is_(None)).all() if ids else []
    grouped = {}
    for reply in replies:
        parent = str(reply.reply_to_id if kind == 'discussion' else reply.reply_to_message_id)
        grouped.setdefault(parent, []).append(reply)
    result = []
    for row in rows:
        mid, author = str(row.id), sender_id(row, kind)
        seen = [view for view in views if view.message_id == mid and view.user_id != author]
        quoted = grouped.get(mid, []) if not row.recalled_at else []
        reply_users = {str(sender_id(reply, kind)): reply.sender_name for reply in quoted}
        own = author == user.id
        result.append(dict(message_id=mid, reply_count=len(quoted), has_replied=str(user.id) in reply_users,
            reply_users=[dict(id=uid, name=name) for uid, name in reply_users.items()],
            seen_count=len(seen) if own and available and not row.recalled_at else None,
            recipient_count=len(recipients - {author}) if own else None,
            seen_users=[dict(id=view.user_id, name=names[view.user_id], seen_at=api_time(view.seen_at)) for view in seen] if own and not row.recalled_at else []))
    return dict(views_available=available, items=result)


def mark_views(db, kind, conversation_id, user, values):
    query, model, recipients = scope(db, kind, conversation_id, user)
    if not ready(db):
        raise HTTPException(503, '阅读回执尚未启用')
    ids = message_ids(kind, values)
    rows = query.filter(model.id.in_(ids)).all()
    if len(rows) != len(ids):
        raise HTTPException(404, '消息不属于当前会话')
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    for row in rows:
        if row.recalled_at or sender_id(row, kind) == user.id:
            continue
        db.execute(insert(ChatMessageView).values(conversation_kind=kind, conversation_id=conversation_id,
            message_id=str(row.id), user_id=user.id, seen_at=now()).on_conflict_do_nothing())
    db.commit()
    from notification_ws import broadcast_to_users
    broadcast_to_users(list(recipients), dict(type='chat_message_interactions', projectType=kind,
        projectId=str(conversation_id), messageIds=[str(value) for value in ids]))
    return dict(message_ids=[str(value) for value in ids])


def references(db, kind, conversation_id, user, message_id, offset=0, limit=30):
    query, model, _ = scope(db, kind, conversation_id, user)
    mid = message_ids(kind, [message_id])[0]
    original = query.filter(model.id == mid).first()
    if not original:
        raise HTTPException(404, '消息不属于当前会话')
    field = model.reply_to_id if kind == 'discussion' else model.reply_to_message_id
    replies = query.filter(field == mid, model.recalled_at.is_(None)).order_by(model.created_at, model.id)
    if original.recalled_at:
        return dict(original=brief(original, kind), items=[], total=0, has_more=False)
    total = replies.count()
    rows = replies.offset(offset).limit(limit).all()
    return dict(original=brief(original, kind), items=[brief(row, kind) for row in rows], total=total, has_more=offset + len(rows) < total)
