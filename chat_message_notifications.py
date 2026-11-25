"""普通聊天通知与消息生命周期同步；复用现有通知表，不保存消息正文。"""
from sqlalchemy import func, or_

from chat_time import now, BUSINESS_TIMEZONE
from models import AppNotification, AppUser, ChatProjectMessage, ChatMentionNotificationTarget


def ordinary_notifications(db, kind, conversation_id, sender, mentioned_ids, message, *, discussion_room=None):
    from crud import create_notifications_for_users
    from chat_access_service import member_ids
    if kind == 'direct':
        from models import ChatDirectConversation
        conversation = db.get(ChatDirectConversation, conversation_id)
        members = {conversation.user_low_id, conversation.user_high_id}
    else:
        members = member_ids(db, kind, conversation_id)
    ids = members - {sender.id} - set(mentioned_ids)
    if kind == 'discussion':
        from discussion_mentions import eligible_users
        recipients = [user.id for user in eligible_users(db, discussion_room, ids)] if ids else []
    elif kind in {'annotation', 'translation'}:
        from annotation_chat_service import project_chat_eligible_ids
        recipients = project_chat_eligible_ids(db, ids, allow_annotation_department=kind == 'annotation')
    else:
        recipients = [uid for uid, in db.query(AppUser.id).filter(
            AppUser.id.in_(ids), AppUser.is_active.is_(True),
        )] if ids else []
    labels = {'direct': '私聊', 'translation': '项目群聊', 'annotation': '标注群聊', 'discussion': '讨论群聊'}
    types = {'direct': 'direct_chat', 'translation': 'project_chat', 'annotation': 'annotation_project_chat', 'discussion': 'discussion_chat'}
    # 讨论使用独立整数消息 ID，同事务的业务时间用于同步阅读和撤回。
    stamp = message.created_at if kind == 'discussion' else now()
    if stamp.tzinfo:
        stamp = stamp.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None)
    return create_notifications_for_users(db, sorted(recipients), title=f'{labels[kind]}新消息',
        content=f'{sender.full_name or sender.username} 发来了新消息，点击查看', notification_type=types[kind],
        related_project_type=kind, related_entity_id=conversation_id,
        related_project_id=conversation_id if kind == 'translation' else None,
        commit=False, created_at=stamp, batch=kind in {'annotation', 'translation'})


def settle_notifications(db, kind, conversation_id, *, user_id=None, sequence=None, message=None):
    """阅读只处理游标以内的通知；撤回仅处理对应消息，绝不清空整场会话。"""
    query = db.query(AppNotification).filter(AppNotification.related_project_type == kind,
        func.coalesce(AppNotification.related_entity_id, AppNotification.related_project_id) == conversation_id,
        AppNotification.is_read.is_(False))
    if user_id is not None:
        query = query.filter(AppNotification.recipient_user_id == user_id)
    if kind == 'discussion':
        from discussion_chat_models import DiscussionMessage, DiscussionMention
        targets = db.query(DiscussionMention.notification_id).join(DiscussionMessage).filter(DiscussionMessage.room_id == conversation_id)
        targets = targets.filter(DiscussionMessage.id == message.id) if message is not None else targets.filter(DiscussionMessage.id <= sequence)
        stamp = message.created_at if message is not None else db.query(DiscussionMessage.created_at).filter_by(room_id=conversation_id, id=sequence).scalar()
        if stamp is None:
            return
        if stamp.tzinfo:
            stamp = stamp.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None)
        ordinary = (AppNotification.notification_type == 'discussion_chat') & (AppNotification.created_at == stamp if message is not None else AppNotification.created_at <= stamp)
        query = query.filter(or_(AppNotification.id.in_(targets), ordinary))
    else:
        from chat_schema import phase_one_ready
        if not phase_one_ready(db):
            return
        column = {'direct': ChatProjectMessage.direct_conversation_id, 'annotation': ChatProjectMessage.annotation_project_id,
                  'translation': ChatProjectMessage.project_id}[kind]
        targets = db.query(ChatMentionNotificationTarget.notification_id).join(ChatProjectMessage).filter(column == conversation_id)
        targets = targets.filter(ChatProjectMessage.id == message.id) if message is not None else targets.filter(ChatProjectMessage.sequence_no <= sequence)
        query = query.filter(AppNotification.id.in_(targets))
    for row in query.all():
        row.is_read = True
        row.read_at = now().replace(tzinfo=None)

