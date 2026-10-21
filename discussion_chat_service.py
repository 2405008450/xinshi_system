"""资源讨论权限、独立消息、稳定分页及幂等发送。"""
from datetime import timedelta
from uuid import UUID
from search_matching import keyword_contains
from fastapi import HTTPException
from sqlalchemy import and_, func, inspect, or_, text
from business_time import business_iso
from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryFolder as Folder, category_now
from chat_session_category_service import BUILTIN_FOLDERS, folder_schema_ready
from discussion_chat_models import DiscussionMember as Member, DiscussionMessage as Message
from models import AppUser, Role, RolePermission, UserRole
from notification_ws import broadcast_to_users
from permission_registry import SUPER_ROLE_NAMES
from permission_service import get_user_permission_codes, user_has_permission

RESOURCE_ROOT = next(row['id'] for row in BUILTIN_FOLDERS if row['ruleKey'] == 'resource')
VIEW_PERMISSIONS = ('talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate')


def can_view(db, user):
    if not user or not user.is_active:
        return False
    if (user.username or '').casefold() == 'jimmy':
        return True
    permissions = set(get_user_permission_codes(db, user.id))
    return '*' in permissions or bool(permissions.intersection(VIEW_PERMISSIONS))


def schema_ready(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(table.__tablename__) for table in (Member, Message))


def room_specs(db):
    rows = [dict(id=row['id'], name=row['name']) for row in BUILTIN_FOLDERS if row['parentKey'] == RESOURCE_ROOT]
    if folder_schema_ready(db):
        existing = {row['id'] for row in rows}
        rows.extend(dict(id=str(row.id), name=row.name) for row in db.query(Category).join(Folder).filter(
            Category.active.is_(True), Folder.parent_key == RESOURCE_ROOT).order_by(Category.created_at, Category.id)
                    if str(row.id) not in existing)
    return rows


def require_room(db, user, room_id, *, storage=True):
    if not can_view(db, user):
        raise HTTPException(403, '没有资源讨论访问权限')
    row = next((row for row in room_specs(db) if row['id'] == str(room_id)), None)
    if row is None:
        raise HTTPException(404, '讨论会话不存在或已停用')
    if storage and not schema_ready(db):
        raise HTTPException(503, '讨论会话暂未启用，请联系系统管理员')
    return row


def publish(db):
    ids = [uid for uid, in db.query(AppUser.id).outerjoin(UserRole, UserRole.user_id == AppUser.id).outerjoin(
        Role, Role.id == UserRole.role_id).outerjoin(RolePermission, RolePermission.role_id == Role.id).filter(
        AppUser.is_active.is_(True), or_(func.lower(AppUser.username) == 'jimmy', Role.role_name.in_(SUPER_ROLE_NAMES),
        RolePermission.permission_code.in_((*VIEW_PERMISSIONS, '*')))).distinct()]
    broadcast_to_users(ids, {'type': 'chat_sessions_changed'})


def catalog(db, user):
    if not can_view(db, user):
        return []
    rooms = room_specs(db)
    ready = schema_ready(db)
    members = {str(row.room_id): row for row in db.query(Member).filter_by(user_id=user.id)} if ready else {}
    latest = {}
    unread = {}
    if ready:
        ids = [UUID(row['id']) for row in rooms]
        maxima = db.query(Message.room_id, func.max(Message.id).label('last_id')).filter(Message.room_id.in_(ids)).group_by(Message.room_id).subquery()
        latest = {str(row.room_id): row for row in db.query(Message).join(maxima, Message.id == maxima.c.last_id)}
        baselines = [and_(Message.room_id == UUID(row['id']), Message.id > (members[row['id']].last_read_id if row['id'] in members else 0)) for row in rooms]
        unread = {str(room): count for room, count in db.query(Message.room_id, func.count(Message.id)).filter(
            or_(*baselines), Message.sender_id != user.id, Message.recalled_at.is_(None)).group_by(Message.room_id)} if baselines else {}
    rows = []
    for room in rooms:
        mid = room['id']; member = members.get(mid); last = latest.get(mid)
        rows.append(dict(key=f'discussion:{mid}', kind='discussion', project_id=mid, title=room['name'],
            subtitle='资源开拓讨论', storage_ready=ready, pinned=bool(member and member.pinned),
            starred=bool(member and member.starred), unread=unread.get(mid, 0), mention_unread=0,
            last_message=dict(id=str(last.id), sender_name=last.sender_name, preview='消息已撤回' if last.recalled_at else last.content[:140],
                              created_at=business_iso(last.created_at)) if last else None))
    return rows


def serialize(db, row, user, *, admin=None, replies=None):
    reply = (replies.get(row.reply_to_id) if replies is not None else db.get(Message, row.reply_to_id)) if row.reply_to_id else None
    if admin is None:
        admin = user_has_permission(db, user.id, '*')
    now = category_now()
    created = row.created_at
    if created.tzinfo is None:
        from business_time import BUSINESS_TIMEZONE
        created = created.replace(tzinfo=BUSINESS_TIMEZONE)
    return dict(id=str(row.id), sequence_no=str(row.id), sender_user_id=str(row.sender_id), sender_name=row.sender_name,
        content='' if row.recalled_at else row.content, created_at=business_iso(row.created_at),
        recalled_at=business_iso(row.recalled_at), can_recall=not row.recalled_at and (
            admin or (row.sender_id == user.id and now <= created + timedelta(hours=24))),
        reply=dict(id=str(reply.id), sender_name=reply.sender_name, content='消息已撤回' if reply.recalled_at else reply.content[:200])
              if reply and not row.recalled_at and reply.room_id == row.room_id else None)


def messages(db, user, room_id, before=None, after=None, limit=50, keyword=''):
    require_room(db, user, room_id)
    query = db.query(Message).filter_by(room_id=room_id)
    if keyword.strip():
        query = query.filter(Message.recalled_at.is_(None), keyword_contains(Message.content, keyword))
    if before is not None:
        query = query.filter(Message.id < before)
    if after is not None:
        query = query.filter(Message.id > after)
    rows = query.order_by(Message.id.asc() if after is not None else Message.id.desc()).limit(limit + 1).all()
    more = len(rows) > limit
    rows = rows[:limit]
    if after is None:
        rows.reverse()
    reply_ids = {row.reply_to_id for row in rows if row.reply_to_id}
    replies = {row.id: row for row in db.query(Message).filter(Message.id.in_(reply_ids), Message.room_id == room_id)} if reply_ids else {}
    admin = user_has_permission(db, user.id, '*')
    return dict(items=[serialize(db, row, user, admin=admin, replies=replies) for row in rows], has_more=more)


def send(db, user, room_id, payload):
    require_room(db, user, room_id)
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:room)'), {'room': room_id.int & ((1 << 63) - 1)})
    row = db.query(Message).filter_by(room_id=room_id, sender_id=user.id, client_message_id=payload.client_message_id).first()
    if row:
        return serialize(db, row, user)
    if payload.reply_to_id is not None:
        reply = db.get(Message, payload.reply_to_id)
        if not reply or reply.room_id != room_id or reply.recalled_at:
            raise HTTPException(422, '引用消息不属于当前讨论或已撤回')
    row = Message(room_id=room_id, sender_id=user.id, sender_name=user.full_name or user.username,
        client_message_id=payload.client_message_id, content=payload.content, reply_to_id=payload.reply_to_id)
    db.add(row); db.commit(); db.refresh(row)
    publish(db)
    return serialize(db, row, user)


def preferences(db, user, room_id, payload):
    require_room(db, user, room_id)
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(Member).values(room_id=room_id, user_id=user.id, last_read_id=0, pinned=False, starred=False).on_conflict_do_nothing())
    row = db.query(Member).filter_by(room_id=room_id, user_id=user.id).with_for_update().first()
    for field in ('pinned', 'starred'):
        if getattr(payload, field) is not None:
            setattr(row, field, getattr(payload, field))
    if payload.read_message_id is not None:
        message = db.get(Message, payload.read_message_id)
        if not message or message.room_id != room_id:
            raise HTTPException(422, '阅读消息不属于当前讨论')
        row.last_read_id = max(row.last_read_id, message.id)
    elif payload.mark_read:
        row.last_read_id = max(row.last_read_id, db.query(func.max(Message.id)).filter_by(room_id=room_id).scalar() or 0)
    db.commit(); publish(db)
    return dict(last_read_id=str(row.last_read_id), pinned=row.pinned, starred=row.starred)
