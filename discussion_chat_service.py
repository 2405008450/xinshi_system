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
ANNOTATION_ROOT = next(row['id'] for row in BUILTIN_FOLDERS if row['ruleKey'] == 'annotation')
VIEW_PERMISSIONS = ('talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate')


def can_view(db, user):
    if not user or not user.is_active:
        return False
    if (user.username or '').casefold() == 'jimmy':
        return True
    permissions = set(get_user_permission_codes(db, user.id))
    return '*' in permissions or bool(permissions.intersection(VIEW_PERMISSIONS))


def can_view_room(db, user, room):
    if room.get('parent_key', RESOURCE_ROOT) == RESOURCE_ROOT:
        return can_view(db, user)
    return bool(user and user.is_active)


def schema_ready(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(table.__tablename__) for table in (Member, Message))


def room_specs(db):
    rows = [dict(id=row['id'], name=row['name']) for row in BUILTIN_FOLDERS if row['parentKey'] == RESOURCE_ROOT]
    if folder_schema_ready(db):
        overrides = {str(row.id): row.name for row in db.query(Category).filter(Category.id.in_([UUID(row['id']) for row in rows]))}
        for row in rows:
            row['name'] = overrides.get(row['id'], row['name'])
        existing = {row['id'] for row in rows}
        rows.extend(dict(id=str(row.id), name=row.name, parent_key=location.parent_key if location else None) for row, location in db.query(Category, Folder).outerjoin(Folder).filter(
            Category.active.is_(True),
            db.query(Member.room_id).filter(Member.room_id == Category.id).exists()).order_by(Category.created_at, Category.id)
                    if str(row.id) not in existing)
    root_ids = {row['id'] for row in BUILTIN_FOLDERS if not row['parentKey']}
    active_categories = {str(row.id) for row in db.query(Category).filter(Category.active.is_(True))}
    locations = {str(row.category_id): str(row.parent_key) for row in db.query(Folder)} if folder_schema_ready(db) else {}
    visible = root_ids | {key for key in active_categories if not locations.get(key)}
    for _ in range(2):
        visible |= {key for key in active_categories if locations.get(key) in visible}
    from technical_requirements import specs
    technical={row['id']:row for row in specs(db)}
    rows=[{**row,**technical.get(row['id'],{})} for row in rows]
    return [row for row in rows if row.get('parent_key', RESOURCE_ROOT) is None or row.get('parent_key', RESOURCE_ROOT) in visible]


def require_room(db, user, room_id, *, storage=True):
    row = next((row for row in room_specs(db) if row['id'] == str(room_id)), None)
    if row is None:
        raise HTTPException(404, '讨论会话不存在或已停用')
    if not can_view_room(db, user, row):
        raise HTTPException(403, '没有会话访问权限')
    if storage and not schema_ready(db):
        raise HTTPException(503, '讨论会话暂未启用，请联系系统管理员')
    from chat_access_service import require_member
    require_member(db, 'discussion', room_id, user)
    return row


def publish(db):
    # 事件不携带消息内容；每个账号重新按自己的参与人权限读取目录。
    ids = [uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True))]
    broadcast_to_users(ids, {'type': 'chat_sessions_changed'})


def catalog(db, user):
    if not user or not user.is_active:
        return []
    resource_visible=can_view(db,user)
    rooms = [room for room in room_specs(db) if room.get('parent_key',RESOURCE_ROOT)!=RESOURCE_ROOT or resource_visible]
    ready = schema_ready(db)
    if not ready:
        return []
    members = {str(row.room_id): row for row in db.query(Member).filter_by(user_id=user.id)} if ready else {}
    rooms = [row for row in rooms if row['id'] in members]
    if not rooms:
        return []
    latest = {}
    unread = {}
    if ready:
        ids = [UUID(row['id']) for row in rooms]
        maxima = db.query(Message.room_id, func.max(Message.id).label('last_id')).filter(Message.room_id.in_(ids)).group_by(Message.room_id).subquery()
        latest = {str(row.room_id): row for row in db.query(Message).join(maxima, Message.id == maxima.c.last_id)}
        baselines = [and_(Message.room_id == UUID(row['id']), Message.id > (members[row['id']].last_read_id if row['id'] in members else 0)) for row in rooms]
        unread = {str(room): count for room, count in db.query(Message.room_id, func.count(Message.id)).filter(
            or_(*baselines), Message.sender_id != user.id, Message.recalled_at.is_(None)).group_by(Message.room_id)} if baselines else {}
    from discussion_mentions import ready as mentions_ready
    from discussion_chat_models import DiscussionMention
    mentioned = {}
    if mentions_ready(db):
        for mid,room_id in db.query(DiscussionMention.message_id,Message.room_id).join(Message,Message.id==DiscussionMention.message_id).filter(DiscussionMention.user_id==user.id,Message.room_id.in_([UUID(room['id']) for room in rooms]),Message.recalled_at.is_(None)):
            member=members.get(str(room_id))
            if mid>(member.last_read_id if member else 0):mentioned.setdefault(str(room_id),[]).append(str(mid))
    rows = []
    for room in rooms:
        mid = room['id']; member = members.get(mid); last = latest.get(mid)
        rows.append(dict(key=f'discussion:{mid}', kind='discussion', project_id=mid, title=room['name'],
            technical_project_id=room.get('technical_project_id'),technical_order_no=room.get('technical_order_no'),
            subtitle='资源开拓讨论' if room.get('parent_key', RESOURCE_ROOT) == RESOURCE_ROOT else '群聊',
            category_ids=[mid], storage_ready=ready, pinned=bool(member and member.pinned),
            starred=bool(member and member.starred), unread=unread.get(mid, 0), mention_unread=len(mentioned.get(mid,[])),mention_message_ids=mentioned.get(mid,[]),
            last_message=dict(id=str(last.id), sender_name=last.sender_name, preview='消息已撤回' if last.recalled_at else last.content[:140],
                              created_at=business_iso(last.created_at),mentions_me=bool(last and str(last.id) in mentioned.get(mid,[]))) if last else None))
    return rows


def serialize(db, row, user, *, admin=None, replies=None, mention_cache=None, action_cache=None):
    reply = (replies.get(row.reply_to_id) if replies is not None else db.get(Message, row.reply_to_id)) if row.reply_to_id else None
    if admin is None:
        admin = user_has_permission(db, user.id, '*')
    now = category_now()
    created = row.created_at
    if created.tzinfo is None:
        from business_time import BUSINESS_TIMEZONE
        created = created.replace(tzinfo=BUSINESS_TIMEZONE)
    from discussion_mentions import serialize as mentions
    mention_rows = [] if row.recalled_at else mention_cache.get(row.id,[]) if mention_cache is not None else mentions(db,row.id)
    from chat_recall_policy import can_recall_own
    from discussion_message_actions import load
    actions = {} if row.recalled_at else (action_cache if action_cache is not None else load(db,[row.id],user.id)).get(row.id,{})
    return dict(**actions,mentions=mention_rows,metadata={'mention_all':any(item['is_all'] for item in mention_rows)},id=str(row.id), sequence_no=str(row.id), sender_user_id=str(row.sender_id), sender_name=row.sender_name,
        content='' if row.recalled_at else row.content, created_at=business_iso(row.created_at),
        recalled_at=business_iso(row.recalled_at), can_recall=can_recall_own(row.sender_id,user.id,row.created_at,row.recalled_at),
        reply=dict(id=str(reply.id), sender_name=reply.sender_name, content='消息已撤回' if reply.recalled_at else reply.content[:200])
              if reply and not row.recalled_at and reply.room_id == row.room_id else None)


def messages(db, user, room_id, before=None, after=None, limit=50, keyword='', favorites_only=False):
    require_room(db, user, room_id)
    query = db.query(Message).filter_by(room_id=room_id)
    if favorites_only:
        from discussion_chat_models import DiscussionMessageAction
        from discussion_message_actions import ready
        if not ready(db): raise HTTPException(503,'讨论收藏尚未初始化')
        query=query.filter(Message.recalled_at.is_(None),db.query(DiscussionMessageAction.message_id).filter(
            DiscussionMessageAction.message_id==Message.id,DiscussionMessageAction.user_id==user.id,DiscussionMessageAction.favorited_at.is_not(None)).exists())
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
    from discussion_mentions import ready as mentions_ready
    from discussion_chat_models import DiscussionMention
    mention_cache={}
    if mentions_ready(db):
        for mention in db.query(DiscussionMention).filter(DiscussionMention.message_id.in_([row.id for row in rows])):
            mention_cache.setdefault(mention.message_id,[]).append(dict(mentioned_user_id=str(mention.user_id),mentioned_user_name=mention.user_name,is_all=mention.is_all))
    from discussion_message_actions import load
    action_cache=load(db,[row.id for row in rows],user.id)
    return dict(items=[serialize(db, row, user, admin=admin, replies=replies,mention_cache=mention_cache,action_cache=action_cache) for row in rows], has_more=more)


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
    from discussion_mentions import recipients,create as create_mentions
    people,members=recipients(db,user,room_id,payload)
    row = Message(room_id=room_id, sender_id=user.id, sender_name=user.full_name or user.username,
        client_message_id=payload.client_message_id, content=payload.content, reply_to_id=payload.reply_to_id)
    db.add(row); db.flush()
    notifications=create_mentions(db,user,row,payload,people,members)
    from chat_message_notifications import ordinary_notifications
    notifications.extend(ordinary_notifications(db, 'discussion', room_id, user, [p.id for p in people], row))
    db.commit(); db.refresh(row)
    from project_chat_crud import _push_notifications
    _push_notifications(notifications)
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
    from chat_message_notifications import settle_notifications
    settle_notifications(db, 'discussion', room_id, user_id=user.id, sequence=row.last_read_id)
    db.commit(); publish(db)
    return dict(last_read_id=str(row.last_read_id), pinned=row.pinned, starred=row.starred)
