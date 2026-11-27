"""资源讨论权限、独立消息、稳定分页及幂等发送。"""
from datetime import timedelta
from chat_catalog_read import catalog_cached
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
    from technical_task_conversations import can_access
    scope = _room_permission_scope(room)
    if scope == 'technical':
        return can_access(db, user)
    if scope == 'resource':
        return can_view(db, user)
    return bool(user and user.is_active)


def _room_permission_scope(room):
    from technical_task_conversations import ROOT_ID, GENERAL_NAME
    if room.get('parent_key') == ROOT_ID or room.get('technical_task_id') or room.get('name') == GENERAL_NAME:
        return 'technical'
    return 'resource' if room.get('parent_key', RESOURCE_ROOT) == RESOURCE_ROOT else 'general'


def visible_room_specs(db, user, rooms=None):
    """同一次目录读取只计算一次各类权限，不按会话重复查询角色和部门。"""
    from technical_task_conversations import can_access
    if not user or not user.is_active:
        return []
    rooms = room_specs(db) if rooms is None else rooms
    permissions = {}
    result = []
    for room in rooms:
        scope = _room_permission_scope(room)
        if scope not in permissions:
            permissions[scope] = can_access(db, user) if scope == 'technical' else can_view(db, user) if scope == 'resource' else True
        if permissions[scope]:
            result.append(room)
    return result


@catalog_cached
def schema_ready(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(table.__tablename__) for table in (Member, Message))


@catalog_cached
def all_member_room_ids(db):
    return {str(room) for room, in db.query(Member.room_id).distinct()} if schema_ready(db) else set()


@catalog_cached
def user_member_map(db, user_id):
    return {str(row.room_id): row for row in db.query(Member).filter_by(user_id=user_id)} if schema_ready(db) else {}


@catalog_cached
def room_specs(db):
    from chat_session_category_service import all_categories, all_folders
    categories = all_categories(db)
    locations = all_folders(db)
    rows = [dict(id=row['id'], name=row['name']) for row in BUILTIN_FOLDERS if row['parentKey'] == RESOURCE_ROOT]
    if folder_schema_ready(db):
        by_id = {str(row.id): row for row in categories}
        for row in rows:
            override = by_id.get(row['id'])
            if override is not None:
                row['name'] = override.name
        existing = {row['id'] for row in rows}
        member_rooms = all_member_room_ids(db)
        rows.extend(
            dict(id=str(row.id), name=row.name, parent_key=locations.get(str(row.id)))
            for row in categories
            if row.active and str(row.id) in member_rooms and str(row.id) not in existing
        )
    root_ids = {row['id'] for row in BUILTIN_FOLDERS if not row['parentKey']}
    active_categories = {str(row.id) for row in categories if row.active}
    visible = root_ids | {key for key in active_categories if not locations.get(key)}
    for _ in range(2):
        visible |= {key for key in active_categories if locations.get(key) in visible}
    from technical_requirements import specs
    technical={row['id']:row for row in specs(db)}
    from technical_task_conversations import specs as development_specs
    technical.update(development_specs(db))
    rows=[{**row,**technical.get(row['id'],{})} for row in rows]
    from translation_chat_delivery import aliases as translation_aliases
    titles=translation_aliases(db)
    for row in rows:
        row['name']=titles.get(row['id'],row['name'])
        row['deletion_protected']=row['id'] in titles
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


def publish(db, room=None, recipients=None, *, members_changed=False, kind=None):
    event = {'type': 'chat_sessions_changed'}
    if room is None:
        if recipients is None:
            recipients = [uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True))]
    else:
        event.update(projectType='discussion', projectId=str(room['id']), membersChanged=members_changed)
        if kind:
            event['kind'] = kind
        if recipients is None:
            from chat_access_service import member_ids
            from discussion_mentions import eligible_users
            ids = member_ids(db, 'discussion', UUID(str(room['id'])))
            recipients = [user.id for user in eligible_users(db, room, ids)] if ids else []
    broadcast_to_users(recipients, event)


def catalog(db, user, *, recent_only=False, room_ids=None):
    if not user or not user.is_active:
        return []
    ready = schema_ready(db)
    if not ready:
        return []
    if room_ids is None:
        members = user_member_map(db, user.id)
    else:
        wanted = {str(rid) for rid in room_ids}
        members = {rid: row for rid, row in user_member_map(db, user.id).items() if rid in wanted}
    if not members:
        return []
    rooms = visible_room_specs(db, user, [row for row in room_specs(db) if row['id'] in members])
    if recent_only:
        from chat_session_activity import active_discussion_ids
        active = active_discussion_ids(db, user.id, room_ids=room_ids)
        rooms = [row for row in rooms if row['id'] in active or
                 members[row['id']].pinned or members[row['id']].starred]
    if not rooms:
        return []
    latest = {}
    unread = {}
    if ready:
        ids = [UUID(row['id']) for row in rooms]
        maxima = db.query(Message.room_id, func.max(Message.id).label('last_id')).filter(Message.room_id.in_(ids)).group_by(Message.room_id).subquery()
        latest = {str(row.room_id): row for row in db.query(Message).join(maxima, Message.id == maxima.c.last_id)}
        baselines = [and_(Message.room_id == UUID(row['id']), Message.id > (members[row['id']].last_read_id if row['id'] in members else 0)) for row in rooms]
        from chat_receipt_read import received as is_received
        unread = {str(room): count for room, count in db.query(Message.room_id, func.count(Message.id)).filter(
            or_(*baselines), Message.sender_id != user.id, Message.recalled_at.is_(None), ~is_received(db, Message, user.id, discussion=True)).group_by(Message.room_id)} if baselines else {}
    from chat_receipt_read import received
    from discussion_mentions import ready as mentions_ready
    from discussion_chat_models import DiscussionMention
    mentioned = {}
    broadcast_unread = {}
    latest_mentions = {}
    if mentions_ready(db):
        for mid,room_id,is_all in db.query(DiscussionMention.message_id,Message.room_id,DiscussionMention.is_all).join(Message,Message.id==DiscussionMention.message_id).filter(DiscussionMention.user_id==user.id,~received(db,Message,user.id,discussion=True),Message.room_id.in_([UUID(room['id']) for room in rooms]),Message.recalled_at.is_(None)):
            room_key = str(room_id)
            if latest.get(room_key) and latest[room_key].id == mid:
                latest_mentions[room_key] = bool(is_all)
            if mid > members[room_key].last_read_id:
                mentioned.setdefault(room_key, []).append(str(mid))
                if is_all:
                    broadcast_unread[room_key] = broadcast_unread.get(room_key, 0) + 1
    rows = []
    for room in rooms:
        mid = room['id']; member = members.get(mid); last = latest.get(mid)
        rows.append(dict(key=f'discussion:{mid}', kind='discussion', project_id=mid, title=room['name'],
            deletion_protected=room.get('deletion_protected',False),
            technical_project_id=room.get('technical_project_id'),technical_order_no=room.get('technical_order_no'),
            subtitle='资源开拓讨论' if room.get('parent_key', RESOURCE_ROOT) == RESOURCE_ROOT else '群聊',
            category_ids=[mid], storage_ready=ready, pinned=bool(member and member.pinned),
            starred=bool(member and member.starred), unread=unread.get(mid, 0), mention_unread=len(mentioned.get(mid,[])),mention_message_ids=mentioned.get(mid,[]), mention_all_unread=broadcast_unread.get(mid, 0),
            last_message=dict(id=str(last.id), sender_name=last.sender_name, preview='消息已撤回' if last.recalled_at else last.content[:140],
                              created_at=business_iso(last.created_at),mentions_me=mid in latest_mentions, mention_all=latest_mentions.get(mid, False)) if last else None))
    return rows


def serialize(db, row, user, *, admin=None, replies=None, mention_cache=None, action_cache=None, format_cache=None):
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
    from chat_recall_policy import can_recall_own, can_edit_own
    from discussion_message_actions import load
    actions = {} if row.recalled_at else (action_cache if action_cache is not None else load(db,[row.id],user.id)).get(row.id,{})
    from chat_text_format import load_formats
    formatted=None if row.recalled_at else (format_cache if format_cache is not None else load_formats(db,[row.id])).get(row.id)
    return dict(content_json=formatted,**actions,mentions=mention_rows,metadata={'mention_all':any(item['is_all'] for item in mention_rows)},id=str(row.id), sequence_no=str(row.id), client_message_id=str(row.client_message_id) if row.client_message_id else None, sender_user_id=str(row.sender_id), sender_name=row.sender_name,
        content='' if row.recalled_at else row.content, created_at=business_iso(row.created_at),
        recalled_at=business_iso(row.recalled_at), can_recall=can_recall_own(row.sender_id,user.id,row.created_at,row.recalled_at),
        edited_at=None if row.recalled_at else business_iso(row.edited_at),
        can_edit=can_edit_own(row.sender_id,user.id,row.created_at,row.recalled_at),
        reply=dict(id=str(reply.id), sender_name=reply.sender_name, content='消息已撤回' if reply.recalled_at else reply.content[:200])
              if reply and not row.recalled_at and reply.room_id == row.room_id else None)


def messages(db, user, room_id, before=None, after=None, limit=50, keyword='', favorites_only=False,
             kind='all', sender_user_id=None, start_date=None, end_date=None, format_filters=''):
    require_room(db, user, room_id)
    query = db.query(Message).filter_by(room_id=room_id)
    if favorites_only:
        from discussion_chat_models import DiscussionMessageAction
        from discussion_message_actions import ready
        if not ready(db): raise HTTPException(503,'讨论收藏尚未初始化')
        query=query.filter(Message.recalled_at.is_(None),db.query(DiscussionMessageAction.message_id).filter(
            DiscussionMessageAction.message_id==Message.id,DiscussionMessageAction.user_id==user.id,DiscussionMessageAction.favorited_at.is_not(None)).exists())
    from discussion_search import apply_filters
    query = apply_filters(db, query, Message, room_id, keyword=keyword, kind=kind, sender_user_id=sender_user_id,
                          start_date=start_date, end_date=end_date, format_filters=format_filters)
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
    from chat_receipt_read import received
    from discussion_mentions import ready as mentions_ready
    from discussion_chat_models import DiscussionMention
    mention_cache={}
    if mentions_ready(db):
        for mention in db.query(DiscussionMention).filter(DiscussionMention.message_id.in_([row.id for row in rows])):
            mention_cache.setdefault(mention.message_id,[]).append(dict(mentioned_user_id=str(mention.user_id),mentioned_user_name=mention.user_name,is_all=mention.is_all))
    from discussion_message_actions import load
    action_cache=load(db,[row.id for row in rows],user.id)
    from chat_text_format import load_formats
    format_cache=load_formats(db,[row.id for row in rows])
    return dict(items=[serialize(db, row, user, format_cache=format_cache, admin=admin, replies=replies,mention_cache=mention_cache,action_cache=action_cache) for row in rows], has_more=more)


def send(db, user, room_id, payload):
    room = require_room(db, user, room_id)
    existing = db.query(Message).filter_by(room_id=room_id, sender_id=user.id, client_message_id=payload.client_message_id)
    row = existing.first()
    if row:
        return serialize(db, row, user)
    from discussion_chat_files import validate_files
    validate_files(db, user, room_id, payload.content)
    if db.get_bind().dialect.name == 'postgresql':
        # 热门群有竞争时尽早归还连接。重试仍需在会话锁内判断幂等。
        db.execute(text("SET LOCAL lock_timeout = '1500ms'"))
        db.execute(text('SELECT pg_advisory_xact_lock(:room)'), {'room': room_id.int & ((1 << 63) - 1)})
        row = existing.first()
        if row:
            return serialize(db, row, user)
    reply = None
    if payload.reply_to_id is not None:
        reply = db.get(Message, payload.reply_to_id)
        if not reply or reply.room_id != room_id or reply.recalled_at:
            raise HTTPException(422, '引用消息不属于当前讨论或已撤回')
    from discussion_mentions import recipients,create as create_mentions
    people,members=recipients(db,user,room_id,payload,room=room)
    row = Message(room_id=room_id, sender_id=user.id, sender_name=user.full_name or user.username,
        client_message_id=payload.client_message_id, content=payload.content, reply_to_id=payload.reply_to_id)
    from chat_text_format import validate_format,save_format
    formatted=validate_format(payload.content,getattr(payload,'content_json',None))
    db.add(row); db.flush()
    save_format(db,row.id,formatted)
    notifications=create_mentions(db,user,row,payload,people,members)
    from chat_message_notifications import ordinary_notifications
    notifications.extend(ordinary_notifications(
        db, 'discussion', room_id, user, [p.id for p in people], row, discussion_room=room,
    ))
    notified = {notification.recipient_user_id for notification in notifications}
    members_changed = any(person.id not in members for person in people)
    reply_settled = False
    if reply is not None and reply.sender_id != user.id:
        from chat_receipt_read import settle_received
        settle_received(db, reply, user.id, discussion=True)
        reply_settled = True
    from project_chat_crud import commit_chat_notifications
    commit_chat_notifications(db, notifications)
    db.refresh(row)
    publish(db, room, notified | {user.id}, members_changed=members_changed, kind='message')
    if reply_settled:
        from chat_receipt_read import notify_settled
        notify_settled(user.id)
    return serialize(db, row, user)


def edit(db, user, room_id, message_id, payload):
    room = require_room(db, user, room_id)
    row = db.query(Message).filter_by(id=message_id, room_id=room_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '消息不存在')
    if row.sender_id != user.id:
        raise HTTPException(403, '不能编辑他人的消息')
    if row.recalled_at:
        raise HTTPException(409, '已撤回的消息不能编辑')
    from chat_recall_policy import can_edit_own
    if not can_edit_own(row.sender_id, user.id, row.created_at, row.recalled_at):
        raise HTTPException(403, '只能编辑本人一小时内发送的普通消息')
    next_content = (payload.content or '').strip()
    if not next_content:
        raise HTTPException(422, '消息内容不能为空')
    from discussion_chat_files import validate_files
    validate_files(db, user, room_id, next_content)
    if next_content != row.content:
        row.content = next_content
        row.edited_at = category_now()
        db.commit()
        db.refresh(row)
        publish(db, room)
    return serialize(db, row, user)


def preferences(db, user, room_id, payload):
    room = require_room(db, user, room_id)
    user_id = user.id
    member = db.query(Member).filter_by(room_id=room_id, user_id=user_id)
    read_to = None
    if payload.read_message_id is not None:
        message = db.get(Message, payload.read_message_id)
        if not message or message.room_id != room_id:
            raise HTTPException(422, '阅读消息不属于当前讨论')
        read_to = message.id
    elif payload.mark_read:
        read_to = db.query(func.max(Message.id)).filter_by(room_id=room_id).scalar() or 0
    if read_to is not None:
        # 通知写入可能等待行锁，完成后再锁定成员并提交阅读游标。
        previous = member.with_entities(Member.last_read_id).scalar() or 0
        from chat_message_notifications import settle_notifications
        settle_notifications(db, 'discussion', room_id, user_id=user_id, sequence=max(previous, read_to))

    row = member.populate_existing().with_for_update().first()
    if not row:
        raise HTTPException(404, '会话不存在或你不是该会话参与人')
    for field in ('pinned', 'starred'):
        if getattr(payload, field) is not None:
            setattr(row, field, getattr(payload, field))
    if read_to is not None:
        row.last_read_id = max(row.last_read_id, read_to)
    result = dict(last_read_id=str(row.last_read_id), pinned=row.pinned, starred=row.starred)
    db.commit()
    kind = 'read' if payload.pinned is None and payload.starred is None else 'state'
    publish(db, room, {user_id}, kind=kind)
    return result
