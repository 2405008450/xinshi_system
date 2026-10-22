"""业务通知与聊天提醒的统一查询边界，不改动已有通知记录。"""
from typing import Literal

NotificationChannel = Literal['all', 'business', 'chat']
CHAT_NOTIFICATION_TYPES = (
    'project_chat', 'project_chat_mention', 'annotation_project_chat_mention',
    'annotation_project_chat_invite', 'direct_chat', 'direct_chat_mention', 'direct_chat_invite',
)


def filter_notification_channel(query, model, channel: NotificationChannel = 'all'):
    if channel == 'chat':
        return query.filter(model.notification_type.in_(CHAT_NOTIFICATION_TYPES))
    if channel == 'business':
        return query.filter(model.notification_type.notin_(CHAT_NOTIFICATION_TYPES))
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
    return query.filter(or_(
        model.notification_type.notin_(CHAT_NOTIFICATION_TYPES),
        and_(model.notification_type.in_(('annotation_project_chat_mention', 'annotation_project_chat_invite')), target.in_(visible_ids(db, 'annotation', user))),
        and_(model.notification_type.in_(('project_chat', 'project_chat_mention')), translation),
        and_(model.notification_type.in_(('direct_chat', 'direct_chat_mention', 'direct_chat_invite')), direct),
    ))
