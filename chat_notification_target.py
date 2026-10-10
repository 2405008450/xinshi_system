"""新提醒保存精确消息目标，历史提醒保留兼容定位。"""
from chat_schema import phase_one_ready
from models import ChatMentionNotificationTarget


def link_notifications(db, notifications, message_id):
    if notifications and phase_one_ready(db):
        db.flush()
        db.add_all(ChatMentionNotificationTarget(notification_id=n.id, message_id=message_id) for n in notifications)
