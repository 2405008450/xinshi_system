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
