"""单条收到确认视为已读，不推进会话游标或清除其他消息。"""
from sqlalchemy import or_, false, select


def received(db, message, user_id, discussion=False):
    from models import AppNotification
    if discussion:
        from discussion_message_actions import ready
        from discussion_chat_models import DiscussionMessageAction as Action, DiscussionMention as Mention
        ack = select(Action.message_id).where(Action.message_id == message.id, Action.user_id == user_id, Action.acknowledged_at.is_not(None)).exists() if ready(db) else false()
        from discussion_mentions import ready as mentions_ready
        read = select(Mention.message_id).join(AppNotification, AppNotification.id == Mention.notification_id).where(Mention.message_id == message.id, Mention.user_id == user_id, AppNotification.recipient_user_id == user_id, AppNotification.is_read.is_(True)).exists() if mentions_ready(db) else false()
    else:
        from models import ChatProjectMessageAcknowledgement as Ack, ChatMentionNotificationTarget as Target
        from chat_schema import phase_one_ready
        ack = select(Ack.message_id).where(Ack.message_id == message.id, Ack.user_id == user_id).exists()
        read = select(Target.message_id).join(AppNotification, AppNotification.id == Target.notification_id).where(Target.message_id == message.id, AppNotification.recipient_user_id == user_id, AppNotification.is_read.is_(True)).exists() if phase_one_ready(db) else false()
    return or_(ack, read)


def settle_received(db, message, user_id, discussion=False):
    from models import AppNotification
    from chat_time import now
    if discussion:
        from discussion_mentions import ready
        from discussion_chat_models import DiscussionMention
        if not ready(db): return
        ids = db.query(DiscussionMention.notification_id).filter(DiscussionMention.message_id == message.id, DiscussionMention.user_id == user_id)
    else:
        from chat_schema import phase_one_ready
        from models import ChatMentionNotificationTarget
        if not phase_one_ready(db): return
        ids = db.query(ChatMentionNotificationTarget.notification_id).filter(ChatMentionNotificationTarget.message_id == message.id)
    for row in db.query(AppNotification).filter(AppNotification.id.in_(ids), AppNotification.recipient_user_id == user_id, AppNotification.is_read.is_not(True)):
        row.is_read = True
        row.read_at = now().replace(tzinfo=None)
