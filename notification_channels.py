"""业务通知与聊天提醒的统一查询边界，不改动已有通知记录。"""
from typing import Literal

NotificationChannel = Literal['all', 'business', 'chat', 'system']
CONVERSATION_NOTIFICATION_TYPES = ('resource_request_dispatch', 'chat_summary')
CHAT_NOTIFICATION_TYPES = (
    'discussion_chat', 'discussion_chat_mention', 'project_chat', 'project_chat_mention', 'annotation_project_chat', 'annotation_project_chat_mention',
    'annotation_project_chat_invite', 'direct_chat', 'direct_chat_mention', 'direct_chat_invite',
)


def chat_notification_predicate(model):
    from sqlalchemy import func, or_
    kind = func.lower(func.trim(func.coalesce(model.notification_type, '')))
    return or_(kind == 'chat', kind.startswith('chat_', autoescape=True),
               kind.endswith('_chat', autoescape=True), kind.contains('_chat_', autoescape=True)) & kind.notin_(CONVERSATION_NOTIFICATION_TYPES)


def filter_notification_channel(query, model, channel: NotificationChannel = 'all'):
    from sqlalchemy import func
    chat = chat_notification_predicate(model)
    if channel == 'chat':
        return query.filter(chat)
    if channel == 'business':
        return query.filter(~chat)
    if channel == 'system':
        return query.filter(~chat, func.lower(func.trim(func.coalesce(model.notification_type, ''))).notin_(CONVERSATION_NOTIFICATION_TYPES))
    return query


def filter_notification_visibility(query, model, db, user_id):
    from types import SimpleNamespace
    from sqlalchemy import and_, false, func, or_
    from chat_access_service import visible_ids
    from chat_schema import phase_one_ready
    from models import ChatDirectConversation
    user = SimpleNamespace(id=user_id)
    target = func.coalesce(model.related_entity_id, model.related_project_id)
    direct = false()
    translation = false()
    if phase_one_ready(db):
        direct = target.in_(db.query(ChatDirectConversation.id).filter(or_(
            ChatDirectConversation.user_low_id == user_id, ChatDirectConversation.user_high_id == user_id)))
        translation = target.in_(visible_ids(db, 'translation', user))
    chat = chat_notification_predicate(model)
    kind = func.lower(func.trim(func.coalesce(model.notification_type, '')))
    return query.filter(or_(
        ~chat,
        and_(chat, or_(model.related_project_type == 'discussion', kind.startswith('discussion_chat', autoescape=True)), target.in_(visible_ids(db,'discussion',user))),
        and_(chat, or_(model.related_project_type == 'annotation', kind.startswith('annotation_project_chat', autoescape=True)), target.in_(visible_ids(db, 'annotation', user))),
        and_(chat, or_(model.related_project_type == 'translation', kind.startswith('project_chat', autoescape=True)), translation),
        and_(chat, or_(model.related_project_type == 'direct', kind.startswith('direct_chat', autoescape=True)), direct),
    ))
