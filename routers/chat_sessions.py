"""统一会话目录、用户搜索和用户级偏好。"""
from search_matching import keyword_ilike, keyword_or
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import func, or_, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from models import (AppUser, AnnotationChatMember, ChatDirectConversation, ChatDirectMember,
    ChatProjectMemberPref, ChatProjectMessage, ChatProjectMention, TranslationProject, ChatProjectEnabled)
from annotation_models import AnnotationProject
from annotation_schemas import ANNOTATION_PROJECT_STATUSES
from chat_time import api_time, now
from permission_service import user_has_permission
from notification_ws import broadcast_to_users
import annotation_chat_service as annotation
import direct_chat_service as direct
from chat_schema import phase_one_ready, require_phase_one
from chat_mention_history import list_mentions, mention_count, annotation_mention_counts, decorate_mention_sessions, mention_session_statistics
import chat_session_category_service as session_categories

router = APIRouter(prefix='/chat', tags=['chat_sessions'])
from routers.chat_message_interactions import router as interactions_router
router.include_router(interactions_router)


class PresenceRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=200)


class PresenceHeartbeat(BaseModel):
    client_id: UUID
    sequence: int = Field(ge=1, le=2147483647)
    active: bool = True


@router.post('/presence/heartbeat')
def desktop_heartbeat(payload: PresenceHeartbeat, request: Request,
                      db=Depends(get_db), user=Depends(get_current_user)):
    from attendance_service import desktop_request
    from chat_presence_registry import record
    if not user.is_active or user.is_deleted:
        raise HTTPException(403, '账号已停用')
    if not desktop_request(request):
        return dict(recorded=False)
    return dict(recorded=record(db, user.id, payload.client_id, payload.sequence, payload.active))


@router.post('/presence')
def desktop_presence(payload: PresenceRequest, db=Depends(get_db), user=Depends(get_current_user)):
    if not user.is_active:
        raise HTTPException(403, '账号已停用')
    people = db.query(AppUser).filter(AppUser.id.in_(set(payload.user_ids)), AppUser.is_active.is_(True), AppUser.is_deleted.is_(False)).all()
    ids = [person.id for person in people]
    from notification_ws import notification_manager
    local_statuses = notification_manager.desktop_presence(ids)
    from chat_presence_registry import desktop_presence as shared_presence
    statuses = shared_presence(db, ids)
    for uid in ids:
        if local_statuses[str(uid)]:
            statuses[str(uid)] = True
    from chat_work_presence import work_presence
    schedules = work_presence(db, people)
    return api_time(dict(checked_at=now(), items=[dict(
        user_id=str(uid), desktop_online=statuses[str(uid)], **schedules[str(uid)]) for uid in ids]))


@router.get('/messages/search')
def global_message_search(keyword: str = Query('', max_length=200), offset: int = Query(0, ge=0),
                          limit: int = Query(30, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user)):
    from chat_global_search import search_messages
    return search_messages(db, user, keyword, offset=offset, limit=limit)

DIRECTORY_LIMIT = 1000
RECENT_LIMIT = 8


class ConversationInviteWrite(BaseModel):
    user_ids: list[UUID]


def _require_participant_scope(db, user, kind, conversation_id):
    from chat_access_service import require_member
    require_member(db, kind, conversation_id, user)
    if kind == 'discussion':
        import discussion_chat_service
        discussion_chat_service.require_room(db, user, conversation_id)
    elif not annotation.can_view(db, user):
        raise HTTPException(403, '没有项目沟通权限')


@router.get('/conversations/{kind}/{conversation_id}/participants')
def conversation_participants(kind: Literal['annotation', 'translation', 'discussion'], conversation_id: UUID,
                              db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    _require_participant_scope(db, user, kind, conversation_id)
    from chat_access_service import member_ids
    ids = member_ids(db, kind, conversation_id)
    users = db.query(AppUser).order_by(AppUser.full_name, AppUser.username).all()
    import discussion_chat_service
    room = discussion_chat_service.require_room(db, user, conversation_id) if kind == 'discussion' else None
    eligible = [row for row in users if row.is_active and (discussion_chat_service.can_view_room(db, row, room) if kind == 'discussion' else annotation.can_view(db, row))]
    item = lambda row: dict(id=row.id, name=row.full_name or row.username)
    return dict(members=[item(row) for row in users if row.id in ids], eligible_users=[item(row) for row in eligible if row.id not in ids])


@router.post('/conversations/{kind}/{conversation_id}/invitations')
def conversation_invite(kind: Literal['translation', 'discussion'], conversation_id: UUID, payload: ConversationInviteWrite,
                        db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    _require_participant_scope(db, user, kind, conversation_id)
    if not payload.user_ids or len(payload.user_ids) > 1000:
        raise HTTPException(422, '每次请选择1至1000位人员')
    targets = db.query(AppUser).filter(AppUser.id.in_(set(payload.user_ids)), AppUser.is_active.is_(True)).all()
    import discussion_chat_service
    room = discussion_chat_service.require_room(db, user, conversation_id) if kind == 'discussion' else None
    if len(targets) != len(set(payload.user_ids)) or any(not (discussion_chat_service.can_view_room(db, target, room) if kind == 'discussion' else annotation.can_view(db, target)) for target in targets):
        raise HTTPException(422, '邀请对象已停用或没有相应模块权限')
    from chat_access_service import MEMBERS
    model, column = MEMBERS[kind]
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert_member = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    for target in targets:
        db.execute(insert_member(model).values(**{column.key: conversation_id, 'user_id': target.id,
            'pinned': False, 'starred': False, 'last_read_id' if kind == 'discussion' else 'last_read_sequence': 0}).on_conflict_do_nothing())
    db.commit()
    broadcast_to_users([user.id, *[target.id for target in targets]], {'type': 'chat_sessions_changed'})
    return conversation_participants(kind, conversation_id, db, user)


@router.post('/conversations/{kind}/{conversation_id}/participants/remove')
def conversation_remove_participants(kind: Literal['annotation', 'translation', 'discussion'], conversation_id: UUID,
                                    payload: ConversationInviteWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if not payload.user_ids or len(payload.user_ids) > 1000:
        raise HTTPException(422, '请选择需要移出的参与人')
    if user.id in payload.user_ids:
        raise HTTPException(400, '不能通过删除参与人移出自己')
    if kind == 'annotation':
        annotation.require_project(db, conversation_id, user, lock=True)
    else:
        _require_participant_scope(db, user, kind, conversation_id)
        if kind == 'translation':
            db.query(TranslationProject).filter_by(id=conversation_id).with_for_update().first()
    from chat_access_service import MEMBERS, member_ids, require_member
    require_member(db, kind, conversation_id, user)
    before = member_ids(db, kind, conversation_id)
    targets = set(payload.user_ids)
    if not targets.issubset(before):
        raise HTTPException(400, '部分人员已经不在会话中，请刷新后重试')
    model, column = MEMBERS[kind]
    db.query(model).filter(column == conversation_id, model.user_id.in_(targets)).delete(synchronize_session=False)
    db.commit()
    broadcast_to_users(list(before), {'type': 'chat_sessions_changed'})
    broadcast_to_users(list(targets), {'type': 'chat_conversation_removed', 'projectType': kind, 'projectId': str(conversation_id)})
    if kind == 'annotation':
        annotation.publish(db, conversation_id, 'members')
        for uid in targets:
            annotation.notify_state(uid, conversation_id)
    return {'removed_count': len(targets)}


@router.post('/conversations/{kind}/{conversation_id}/participants/leave')
def conversation_leave(kind: Literal['annotation', 'translation', 'discussion'], conversation_id: UUID,
                       db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if kind == 'annotation':
        annotation.require_project(db, conversation_id, user, lock=True)
    else:
        _require_participant_scope(db, user, kind, conversation_id)
        if kind == 'translation':
            db.query(TranslationProject).filter_by(id=conversation_id).with_for_update().first()
    from chat_access_service import MEMBERS, member_ids
    before = member_ids(db, kind, conversation_id)
    model, column = MEMBERS[kind]
    db.query(model).filter(column == conversation_id, model.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    broadcast_to_users(list(before), {'type': 'chat_sessions_changed'})
    broadcast_to_users([user.id], {'type': 'chat_conversation_removed', 'projectType': kind, 'projectId': str(conversation_id)})
    if kind == 'annotation':
        annotation.publish(db, conversation_id, 'members')
    return {'left': True}


def _department(value):
    text = (value or '').strip()
    return text or None


def _user_item(row, conversation_id=None):
    item = {'id': row.id, 'name': row.full_name or row.username, 'username': row.username, 'department': _department(row.department)}
    if conversation_id:
        item['conversation_id'] = conversation_id
    return item


def _peer_id(row, user_id):
    return row.user_high_id if row.user_low_id == user_id else row.user_low_id


def _direct_conversations(db, user):
    if not phase_one_ready(db):
        return []
    return db.query(ChatDirectConversation).filter(or_(
        ChatDirectConversation.user_low_id == user.id, ChatDirectConversation.user_high_id == user.id)).all()


def _recent_contacts(db, user, conversations):
    ordered = sorted((row for row in conversations if row.last_message_at), key=lambda row: (row.last_message_at, row.id), reverse=True)
    peer_ids = [_peer_id(row, user.id) for row in ordered]
    active = {uid for (uid,) in db.query(AppUser.id).filter(AppUser.id.in_(peer_ids), AppUser.is_active.is_(True))} if peer_ids else set()
    result = []
    for row in ordered:
        peer = _peer_id(row, user.id)
        if peer not in active:
            continue
        result.append({'user_id': peer, 'conversation_id': row.id, 'last_message_at': api_time(row.last_message_at)})
        if len(result) >= RECENT_LIMIT:
            break
    return result


@router.get('/users')
def users(keyword: str = '', limit: int = Query(50, ge=1, le=100), scope: str = Query('search'), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    conversations = _direct_conversations(db, user)
    recent = _recent_contacts(db, user, conversations)
    if scope == 'recent':
        return {'recent': recent}
    query = db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.id != user.id)
    if keyword.strip():
        text = '%' + keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(AppUser.full_name, _search_part, escape='\\'),
            keyword_ilike(AppUser.username, _search_part, escape='\\'),
            keyword_ilike(AppUser.department, _search_part, escape='\\'),
        ), text))
    if scope == 'directory':
        department_key = func.nullif(func.btrim(AppUser.department), '')
        query = query.order_by(department_key.asc().nullslast(), AppUser.full_name.asc().nullslast(), AppUser.username.asc(), AppUser.id.asc())
        cap = DIRECTORY_LIMIT
    else:
        query = query.order_by(AppUser.full_name.asc().nullslast(), AppUser.username.asc(), AppUser.id.asc())
        cap = limit
    conversation_ids = {_peer_id(row, user.id): row.id for row in conversations}
    items = [_user_item(row, conversation_ids.get(row.id)) for row in query.limit(cap)]
    return {
        'items': items,
        'recent': recent,
        'self': _user_item(user),
        'truncated': scope == 'directory' and len(items) >= DIRECTORY_LIMIT,
    }


def summaries(db, column, ids, baselines, user_id):
    if not ids:
        return {}
    latest = db.query(column.label('scope_id'), func.max(ChatProjectMessage.sequence_no).label('seq')).filter(column.in_(ids), ChatProjectMessage.message_type == 'user').group_by(column).subquery()
    last = db.query(ChatProjectMessage).join(latest, and_(column == latest.c.scope_id, ChatProjectMessage.sequence_no == latest.c.seq)).all()
    last_mentions = {mid for (mid,) in db.query(ChatProjectMention.message_id).filter(
        ChatProjectMention.message_id.in_([row.id for row in last]),
        ChatProjectMention.mentioned_user_id == user_id)} if last else set()
    # 单次扫描各会话未读序号；不拉取历史正文。
    unread_rows = db.query(column, ChatProjectMessage.sequence_no, ChatProjectMessage.id,
        ChatProjectMention.mentioned_user_id).outerjoin(ChatProjectMention,
        and_(ChatProjectMention.message_id == ChatProjectMessage.id, ChatProjectMention.mentioned_user_id == user_id)).filter(
        column.in_(ids), ChatProjectMessage.message_type == 'user', ChatProjectMessage.recalled_at.is_(None), ChatProjectMessage.sender_user_id != user_id,
        or_(*[and_(column == uid, ChatProjectMessage.sequence_no > baseline) for uid, baseline in baselines.items()])).order_by(ChatProjectMessage.sequence_no).all()
    result = {uid: {'unread': 0, 'mention_unread': 0, 'mention_message_ids': [], 'last_message': None} for uid in ids}
    for uid, seq, mid, mentioned in unread_rows:
        result[uid]['unread'] += 1
        if mentioned:
            result[uid]['mention_unread'] += 1
            result[uid]['mention_message_ids'].append(mid)
    for row in last:
        result[getattr(row, column.key)]['last_message'] = {'id': row.id,
            'preview': row.recall_label if row.recalled_at else ' '.join(row.content.split())[:140] or '[附件]',
            'sender_name': row.sender_name, 'created_at': api_time(row.created_at),
            'mentions_me': not row.recalled_at and row.id in last_mentions}
    return result


def decorate_member_counts(db, rows):
    from chat_access_service import MEMBERS
    for kind, (model, column) in MEMBERS.items():
        ids = {UUID(str(row['project_id'])) for row in rows if row['kind'] == kind}
        if not ids:
            continue
        counts = {str(pid): count for pid, count in db.query(column, func.count(model.user_id)).join(AppUser, AppUser.id == model.user_id).filter(
            column.in_(ids), AppUser.is_active.is_(True)).group_by(column).all()}
        for row in rows:
            if row['kind'] == kind:
                row['member_count'] = counts.get(str(row['project_id']), 0)


@router.get('/sessions')
def sessions(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    ready = phase_one_ready(db)
    mention_stats = mention_session_statistics(db, user)
    history_total = sum(count for count, _stamp in mention_stats.values())
    annotation_counts = [dict(project_id=UUID(pid), count=count) for (kind, pid), (count, _stamp) in mention_stats.items() if kind == 'annotation']
    rows = []
    if annotation.can_view(db, user):
        # 直接沿用关注与退订条件，不重复执行结果未使用的未读查询。
        mentioned_projects = db.query(ChatProjectMessage.annotation_project_id).join(ChatProjectMention,
            ChatProjectMention.message_id == ChatProjectMessage.id).outerjoin(AnnotationChatMember,
            and_(AnnotationChatMember.project_id == ChatProjectMessage.annotation_project_id, AnnotationChatMember.user_id == user.id)).filter(
            ChatProjectMention.mentioned_user_id == user.id, ChatProjectMessage.recalled_at.is_(None),
            ChatProjectMessage.sequence_no > func.coalesce(AnnotationChatMember.last_read_sequence, 0))
        # 未迁移时仅查询已有列，消息预览与提及统计仍复用完整逻辑。
        conditions = [AnnotationChatMember.following.is_(True), AnnotationProject.id.in_(mentioned_projects)]
        if ready:
            conditions.extend([AnnotationChatMember.pinned.is_(True), AnnotationChatMember.starred.is_(True)])
        projects = db.query(AnnotationProject, AnnotationChatMember).outerjoin(AnnotationChatMember,
            and_(AnnotationChatMember.project_id == AnnotationProject.id, AnnotationChatMember.user_id == user.id)).filter(AnnotationChatMember.user_id == user.id, or_(*conditions)).all()
        stats = summaries(db, ChatProjectMessage.annotation_project_id, [p.id for p, m in projects], {p.id: m.last_read_sequence if m else 0 for p, m in projects}, user.id)
        for p, m in projects:
            rows.append(dict(key=f'annotation:{p.id}', kind='annotation', project_id=p.id, title=p.project_name or '未命名项目',
                subtitle=p.order_no, project_status=p.project_status, following=bool(m and m.following), pinned=bool(ready and m and m.pinned), starred=bool(ready and m and m.starred), is_creator=user.id in (p.created_by, p.client_manager_id), **stats[p.id]))
    if not ready:
        import discussion_chat_service
        rows.extend(discussion_chat_service.catalog(db, user))
        decorate_member_counts(db, rows)
        session_categories.decorate_sessions(db, rows)
        decorate_mention_sessions(db, user, rows, mention_stats)
        return {'phase_one_enabled': False, 'items': rows, 'total': sum(r['unread'] for r in rows), 'mention_history_total': history_total,
            'session_categories': session_categories.catalog(db, user),
            'annotation_mention_counts': annotation_counts,
            'mention_total': sum(r['mention_unread'] for r in rows)}
    if annotation.can_view(db, user):
        prefs = {m.project_id: m for m in db.query(ChatProjectMemberPref).filter_by(user_id=user.id)}
        from chat_access_service import visible_ids
        projects = db.query(TranslationProject).filter(TranslationProject.id.in_(visible_ids(db, 'translation', user))).outerjoin(ChatProjectEnabled,
            ChatProjectEnabled.project_id == TranslationProject.id).filter(or_(ChatProjectEnabled.enabled.is_(True),
            TranslationProject.id.in_(prefs), TranslationProject.created_by == user.id,
            TranslationProject.id.in_(db.query(ChatProjectMessage.project_id).filter(ChatProjectMessage.project_id.is_not(None), ChatProjectMessage.message_type == 'user')))).all()
        stats = summaries(db, ChatProjectMessage.project_id, [p.id for p in projects], {p.id: prefs[p.id].last_read_sequence if p.id in prefs else 0 for p in projects}, user.id)
        for p in projects:
            m = prefs.get(p.id)
            rows.append(dict(key=f'translation:{p.id}', kind='translation', project_id=p.id, title=p.project_name or '未命名项目',
                subtitle=p.order_no, pinned=bool(m and m.pinned), starred=bool(m and m.starred),
                is_creator=user.id in (p.created_by, p.project_manager_id), **stats[p.id]))
    conversations = db.query(ChatDirectConversation, ChatDirectMember).join(ChatDirectMember,
        ChatDirectMember.conversation_id == ChatDirectConversation.id).filter(ChatDirectMember.user_id == user.id,
        ChatDirectMember.hidden_at.is_(None), or_(ChatDirectConversation.user_low_id == user.id, ChatDirectConversation.user_high_id == user.id)).all()
    target_ids = [p.user_high_id if p.user_low_id == user.id else p.user_low_id for p, m in conversations]
    targets = {u.id: u for u in db.query(AppUser).filter(AppUser.id.in_(target_ids))} if target_ids else {}
    stats = summaries(db, ChatProjectMessage.direct_conversation_id, [p.id for p, m in conversations], {p.id: m.last_read_sequence for p, m in conversations}, user.id)
    for p, m in conversations:
        target = targets[p.user_high_id if p.user_low_id == user.id else p.user_low_id]
        rows.append(dict(key=f'direct:{p.id}', kind='direct', project_id=p.id, title=target.full_name or target.username,
            subtitle=((target.department or '').strip() + ('' if target.is_active else '（账号已停用）')), department=_department(target.department), pinned=m.pinned, starred=m.starred, is_creator=False, **stats[p.id]))
    import discussion_chat_service
    rows.extend(discussion_chat_service.catalog(db, user))
    decorate_member_counts(db, rows)
    session_categories.decorate_sessions(db, rows)
    decorate_mention_sessions(db, user, rows, mention_stats)
    return {'phase_one_enabled': True, 'items': rows, 'session_categories': session_categories.catalog(db, user), 'total': sum(r['unread'] for r in rows), 'mention_history_total': history_total, 'mention_total': sum(r['mention_unread'] for r in rows), 'annotation_mention_counts': annotation_counts}


@router.get('/mentions')
def mentions(keyword: str = Query('', max_length=200), before: str | None = Query(None,max_length=400),
             limit: int = Query(50, ge=1, le=100), project_type: Literal['annotation', 'translation', 'discussion', 'direct'] | None = None,
             project_status: str | None = None, project_id: UUID | None = None,
             sort: Literal['time_desc', 'time_asc', 'customer_asc', 'customer_desc'] = 'time_desc',
             db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if project_id is not None and project_type is None:
        raise HTTPException(422, '指定项目时必须同时指定项目类型')
    if project_status is not None and project_status not in ANNOTATION_PROJECT_STATUSES:
        raise HTTPException(422, '无效的标注项目状态')
    if project_status and project_type == 'translation':
        raise HTTPException(422, '标注项目状态不能用于笔译项目')
    return list_mentions(db, user, keyword=keyword, before=before, limit=limit,
                         project_type=project_type, project_status=project_status, project_id=project_id, sort=sort)


class PreferenceRequest(BaseModel):
    pinned: bool | None = None
    starred: bool | None = None
    mark_read: bool = False
    read_message_id: UUID | None = None


@router.put('/sessions/{kind}/{project_id}/preferences')
def preferences(kind: str, project_id: UUID, payload: PreferenceRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    ready = phase_one_ready(db)
    if not ready and (kind != 'annotation' or payload.pinned is not None or payload.starred is not None):
        require_phase_one(db)
    if kind == 'direct':
        direct.require_project(db, project_id, user, lock=True)
        member = db.get(ChatDirectMember, (project_id, user.id))
        column = ChatProjectMessage.direct_conversation_id
    elif kind == 'annotation':
        annotation.require_project(db, project_id, user, lock=True)
        member = annotation.add_member(db, project_id, user.id)
        column = ChatProjectMessage.annotation_project_id
    elif kind == 'translation':
        from chat_access_service import require_member
        require_member(db, 'translation', project_id, user)
        if not user_has_permission(db, user.id, 'projects:read'):
            raise HTTPException(403, '没有项目查看权限')
        if not db.query(TranslationProject).filter_by(id=project_id).with_for_update().first():
            raise HTTPException(404, '项目不存在')
        db.execute(insert(ChatProjectMemberPref).values(project_id=project_id, user_id=user.id).on_conflict_do_nothing())
        member = db.get(ChatProjectMemberPref, (project_id, user.id), populate_existing=True)
        column = ChatProjectMessage.project_id
    else:
        raise HTTPException(400, '不支持的会话类型')
    for field in ('pinned', 'starred'):
        value = getattr(payload, field)
        if value is not None:
            setattr(member, field, value)
    if payload.mark_read:
        member.last_read_sequence = max(member.last_read_sequence, db.query(func.max(ChatProjectMessage.sequence_no)).filter(column == project_id).scalar() or 0)
    elif payload.read_message_id:
        message = db.query(ChatProjectMessage).filter(column == project_id, ChatProjectMessage.id == payload.read_message_id).first()
        if not message:
            raise HTTPException(404, '消息不属于当前会话')
        member.last_read_sequence = max(member.last_read_sequence, message.sequence_no)
    db.commit()
    broadcast_to_users([user.id], {'type': 'chat_sessions_changed'})
    return {'pinned': bool(ready and member.pinned), 'starred': bool(ready and member.starred), 'last_read_sequence': member.last_read_sequence}


@router.get('/mentions/{notification_id}/target')
def mention_target(notification_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from models import AppNotification
    notification = db.query(AppNotification).filter_by(id=notification_id, recipient_user_id=user.id).first()
    if not notification:
        raise HTTPException(404, '通知不存在')
    from chat_access_service import require_member
    kind = notification.related_project_type
    if kind in {'annotation', 'translation'}:
        require_member(db, kind, notification.related_entity_id or notification.related_project_id, user)
    if kind == 'discussion':
        import discussion_chat_service
        from discussion_mentions import ready as discussion_mentions_ready
        from discussion_chat_models import DiscussionMention, DiscussionMessage
        discussion_chat_service.require_room(db,user,notification.related_entity_id)
        target=db.query(DiscussionMention).join(DiscussionMessage,DiscussionMessage.id==DiscussionMention.message_id).filter(DiscussionMention.notification_id==notification.id,DiscussionMention.user_id==user.id,DiscussionMessage.room_id==notification.related_entity_id,DiscussionMessage.recalled_at.is_(None)).first() if discussion_mentions_ready(db) else None
        return {'message_id':str(target.message_id) if target else None}
    if phase_one_ready(db):
        from models import ChatMentionNotificationTarget
        target = db.get(ChatMentionNotificationTarget, notification_id)
        if target:
            return {'message_id': target.message_id}
    column = ChatProjectMessage.annotation_project_id if notification.related_project_type == 'annotation' else ChatProjectMessage.project_id
    query = db.query(ChatProjectMessage).join(ChatProjectMention).filter(column == (notification.related_entity_id or notification.related_project_id),
        ChatProjectMention.mentioned_user_id == user.id)
    # 通知和消息在同一事务创建，按通知时间定位对应消息，兼容历史通知。
    row = query.filter(ChatProjectMessage.created_at <= notification.created_at).order_by(ChatProjectMessage.sequence_no.desc()).first()
    return {'message_id': row.id if row else None}
