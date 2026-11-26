"""单条收到确认或引用回复视为已读，不推进会话游标或清除其他消息。"""
from sqlalchemy import inspect, or_, false, select
from sqlalchemy.orm import aliased


def received(db, message, user_id, discussion=False):
    from models import AppNotification
    if discussion:
        from discussion_message_actions import ready
        from discussion_chat_models import DiscussionMessage as Message, DiscussionMessageAction as Action, DiscussionMention as Mention
        ack = select(Action.message_id).where(Action.message_id == message.id, Action.user_id == user_id, Action.acknowledged_at.is_not(None)).exists() if ready(db) else false()
        from discussion_mentions import ready as mentions_ready
        read = select(Mention.message_id).join(AppNotification, AppNotification.id == Mention.notification_id).where(Mention.message_id == message.id, Mention.user_id == user_id, AppNotification.recipient_user_id == user_id, AppNotification.is_read.is_(True)).exists() if mentions_ready(db) else false()
        Reply = aliased(Message)
        replied = select(Reply.id).where(Reply.reply_to_id == message.id, Reply.sender_id == user_id, Reply.recalled_at.is_(None)).exists()
    else:
        from models import ChatProjectMessage, ChatProjectMessageAcknowledgement as Ack, ChatMentionNotificationTarget as Target
        from chat_schema import phase_one_ready
        ack = select(Ack.message_id).where(Ack.message_id == message.id, Ack.user_id == user_id).exists()
        read = select(Target.message_id).join(AppNotification, AppNotification.id == Target.notification_id).where(Target.message_id == message.id, AppNotification.recipient_user_id == user_id, AppNotification.is_read.is_(True)).exists() if phase_one_ready(db) else false()
        Reply = aliased(ChatProjectMessage)
        replied = select(Reply.id).where(Reply.reply_to_message_id == message.id, Reply.sender_user_id == user_id, Reply.recalled_at.is_(None)).exists()
    return or_(ack, read, replied)


def settle_received(db, message, user_id, discussion=False):
    from models import AppNotification
    from chat_time import BUSINESS_TIMEZONE
    from chat_message_notifications import mark_notifications_read
    if not inspect(db.connection()).has_table(AppNotification.__tablename__):
        return False
    if discussion:
        from discussion_mentions import ready
        from discussion_chat_models import DiscussionMention
        filters = []
        if ready(db):
            ids = db.query(DiscussionMention.notification_id).filter(DiscussionMention.message_id == message.id, DiscussionMention.user_id == user_id)
            filters.append(AppNotification.id.in_(ids))
        stamp = getattr(message, 'created_at', None)
        if stamp is not None:
            if stamp.tzinfo:
                stamp = stamp.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None)
            filters.append(
                (AppNotification.related_project_type == 'discussion')
                & (AppNotification.related_entity_id == message.room_id)
                & (AppNotification.notification_type == 'discussion_chat')
                & (AppNotification.created_at == stamp)
            )
        if not filters:
            return False
        query = db.query(AppNotification).filter(
            or_(*filters),
            AppNotification.recipient_user_id == user_id,
            AppNotification.is_read.is_not(True),
        )
    else:
        from chat_schema import phase_one_ready
        from models import ChatMentionNotificationTarget
        if not phase_one_ready(db):
            return False
        ids = db.query(ChatMentionNotificationTarget.notification_id).filter(ChatMentionNotificationTarget.message_id == message.id)
        query = db.query(AppNotification).filter(
            AppNotification.id.in_(ids),
            AppNotification.recipient_user_id == user_id,
            AppNotification.is_read.is_not(True),
        )
    return mark_notifications_read(query) > 0


def notify_settled(user_id):
    from notification_ws import broadcast_to_users
    broadcast_to_users([user_id], {'type': 'chat_sessions_changed'})
    broadcast_to_users([user_id], {'type': 'chat_mention_changed'})
