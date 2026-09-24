"""标注开放群：权限、关注、稳定分页与消息生命周期。"""
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from annotation_models import AnnotationProject
from crud import create_notifications_for_users, get_user_roles_with_role_names
from models import (AppUser, AppNotification, AnnotationChatMember, ChatProjectMessage,
                    ChatProjectAttachment, ChatProjectMessageAttachment, ChatProjectMessageFavorite,
                    ChatProjectMessageAcknowledgement, Role, RolePermission, UserRole)
from notification_ws import broadcast_to_users, notification_manager
from permission_service import user_has_permission
from permission_registry import SUPER_ROLE_NAMES


def can_view(db, user):
    return bool(user and user.is_active and user_has_permission(db, user.id, 'projects:read'))


def require_project(db, project_id, user, *, lock=False):
    if not can_view(db, user):
        raise HTTPException(403, '没有查看项目的权限')
    query = db.query(AnnotationProject).filter(AnnotationProject.id == project_id)
    project = (query.with_for_update() if lock else query).first()
    if project is None:
        raise HTTPException(404, '标注项目不存在')
    return project


def latest_sequence(db, project_id):
    return db.query(func.max(ChatProjectMessage.sequence_no)).filter(
        ChatProjectMessage.annotation_project_id == project_id).scalar() or 0


def add_member(db, project_id, user_id, *, following=True, baseline=None):
    existing = db.get(AnnotationChatMember, (project_id, user_id))
    if existing is not None:
        return existing
    db.execute(insert(AnnotationChatMember).values(
        project_id=project_id, user_id=user_id, following=following,
        last_read_sequence=latest_sequence(db, project_id) if baseline is None else baseline,
    ).on_conflict_do_nothing())
    return db.get(AnnotationChatMember, (project_id, user_id), populate_existing=True)


def ensure_default_members(db, project_id):
    from project_chat_crud import _chat_participant_user_ids
    for user_id in _chat_participant_user_ids(db, annotation_project_id=project_id):
        member = add_member(db, project_id, user_id)
        if not member.explicit_unfollow:
            member.following = True
    db.flush()


def eligible_users(db, ids=None):
    query = db.query(AppUser).join(UserRole, UserRole.user_id == AppUser.id).join(
        Role, Role.id == UserRole.role_id).outerjoin(RolePermission, RolePermission.role_id == Role.id).filter(
        AppUser.is_active.is_(True), or_(Role.role_name.in_(SUPER_ROLE_NAMES),
        RolePermission.permission_code.in_(['projects:read', '*'])))
    if ids is not None:
        query = query.filter(AppUser.id.in_(ids))
    return query.distinct().order_by(AppUser.username).all()


def publish(db, project_id, kind='changed', message_id=None):
    """仅推送失效事件；消息内容经当前权限校验后按需拉取。"""
    ids = {row.user_id for row in db.query(AnnotationChatMember).filter_by(
        project_id=project_id, following=True).all()}
    ids.update(notification_manager.annotation_viewers(str(project_id)))
    valid = [user.id for user in eligible_users(db, ids)] if ids else []
    broadcast_to_users(valid, {'type': 'annotation_chat_changed', 'projectId': str(project_id),
                              'kind': kind, 'messageId': str(message_id) if message_id else None})


def notify_state(user_id, project_id):
    broadcast_to_users([user_id], {'type': 'annotation_chat_changed', 'projectId': str(project_id), 'kind': 'state'})


def is_admin(db, user):
    return not SUPER_ROLE_NAMES.isdisjoint(get_user_roles_with_role_names(db, user.id))


def chat_now():
    """数据库无时区时间统一为香港时间，不能使用云主机的 UTC 本地时钟。"""
    return datetime.now(ZoneInfo('Asia/Hong_Kong')).replace(tzinfo=None)


def can_recall(message, user_id, admin=False, now=None):
    return bool(message.message_type == 'user' and not message.recalled_at and (
        admin or (message.sender_user_id == user_id and message.created_at and
                  (now or chat_now()) <= message.created_at + timedelta(hours=24))))


def message_query(db, project_id):
    return db.query(ChatProjectMessage).options(
        selectinload(ChatProjectMessage.mentions),
        selectinload(ChatProjectMessage.acknowledgements),
        selectinload(ChatProjectMessage.attachment_links).selectinload(ChatProjectMessageAttachment.attachment),
    ).filter(ChatProjectMessage.annotation_project_id == project_id)


def serialize_many(db, rows, user):
    from routers.project_chat import _serialize_message
    from project_chat_crud import get_chat_message_favorite_times
    favorites = get_chat_message_favorite_times(db, [row.id for row in rows], user.id)
    reply_ids = {row.reply_to_message_id for row in rows if row.reply_to_message_id}
    replies = {row.id: row for row in db.query(ChatProjectMessage).filter(ChatProjectMessage.id.in_(reply_ids)).all()} if reply_ids else {}
    admin = is_admin(db, user)
    result = []
    for row in rows:
        data = _serialize_message(row, 'annotation', favorites.get(row.id), user.id).model_dump()
        data.update(sequence_no=row.sequence_no, client_message_id=row.client_message_id,
                    recalled_at=row.recalled_at, recall_label=row.recall_label,
                    can_recall=can_recall(row, user.id, admin), reply=None)
        reply = replies.get(row.reply_to_message_id)
        if reply and reply.annotation_project_id == row.annotation_project_id:
            data['reply'] = {'id': reply.id, 'sender_name': reply.sender_name,
                             'content': reply.recall_label if reply.recalled_at else (reply.content[:200] or '[附件]'),
                             'recalled': bool(reply.recalled_at)}
        if row.recalled_at:
            data.update(content='', content_json=None, attachments=[], mentions=[], reply=None,
                        acknowledgements=[], acknowledgement_count=0, is_acknowledged=False,
                        is_favorited=False, favorited_at=None, mentioned_user_id=None, mentioned_user_name=None)
        result.append(data)
    return result


def send_message(db, project_id, user, payload):
    from project_chat_crud import _create_chat_mentions, _push_notifications
    project = require_project(db, project_id, user, lock=True)
    # 同一项目写入串行化，保证阅读序号和幂等重试不会越过尚未提交的消息。
    if payload.client_message_id:
        existing = message_query(db, project_id).filter(
            ChatProjectMessage.sender_user_id == user.id,
            ChatProjectMessage.client_message_id == payload.client_message_id).first()
        if existing:
            return existing
    if payload.reply_to_message_id:
        reply = message_query(db, project_id).filter(ChatProjectMessage.id == payload.reply_to_message_id).first()
        if not reply or reply.recalled_at:
            raise HTTPException(400, '引用消息不存在、已撤回或属于其他项目')
    attachment_ids = list(dict.fromkeys(payload.attachment_ids))
    attachments = db.query(ChatProjectAttachment).filter(ChatProjectAttachment.id.in_(attachment_ids)).with_for_update().all() if attachment_ids else []
    if len(attachments) != len(attachment_ids) or any(a.uploaded_by != user.id or (a.annotation_project_id and a.annotation_project_id != project_id) for a in attachments):
        raise HTTPException(400, '附件不存在或不属于当前用户')
    if attachment_ids and db.query(ChatProjectMessageAttachment).filter(
            ChatProjectMessageAttachment.attachment_id.in_(attachment_ids)).first():
        raise HTTPException(400, '附件已经发送，请重新上传')
    from workflow_models import WorkflowHandoverAttachment
    if attachment_ids and db.query(WorkflowHandoverAttachment).filter(
            WorkflowHandoverAttachment.attachment_id.in_(attachment_ids)).first():
        raise HTTPException(400, '交接附件不能直接绑定到标注群，请重新上传')
    mention_ids = set(payload.mentioned_user_ids or [])
    if payload.mentioned_user_id:
        mention_ids.add(payload.mentioned_user_id)
    for user_id in mention_ids:
        if not can_view(db, db.get(AppUser, user_id)):
            raise HTTPException(400, '提及的用户无项目查看权限或已停用')
    ensure_default_members(db, project_id)
    member = add_member(db, project_id, user.id)
    if not member.explicit_unfollow:
        member.following = True
    message = ChatProjectMessage(annotation_project_id=project_id, sender_user_id=user.id,
        sender_name=user.full_name or user.username, content=payload.content.strip(), message_type='user',
        client_message_id=payload.client_message_id, reply_to_message_id=payload.reply_to_message_id,
        event_data={})
    db.add(message)
    db.flush()
    db.add_all(ChatProjectMessageAttachment(message_id=message.id, attachment_id=a.id) for a in attachments)
    mentioned = _create_chat_mentions(db, message, user, mentioned_user_ids=list(mention_ids))
    notifications = []
    if mentioned:
        # 通知不缓存正文，撤回后不会在桌面通知或旧缓存泄露消息内容。
        notifications = create_notifications_for_users(db, recipient_user_ids=[u.id for u in mentioned],
            title='标注项目沟通提醒', content=f'{message.sender_name} 在项目 {project.order_no} / {project.project_name or "-"} 中 @了你，点击查看消息',
            notification_type='annotation_project_chat_mention', related_project_type='annotation',
            related_entity_id=project_id, commit=False)
    db.commit()
    _push_notifications(notifications)
    publish(db, project_id, 'message', message.id)
    notify_state(user.id, project_id)
    return message_query(db, project_id).filter(ChatProjectMessage.id == message.id).one()


def recall_message(db, project_id, message_id, user):
    require_project(db, project_id, user, lock=True)
    message = message_query(db, project_id).filter(ChatProjectMessage.id == message_id).with_for_update().populate_existing().first()
    if not message:
        raise HTTPException(404, '消息不存在')
    admin = is_admin(db, user)
    if message.recalled_at:
        if message.sender_user_id != user.id and not admin:
            raise HTTPException(403, '不能撤回他人的消息')
        return message
    if not can_recall(message, user.id, admin):
        raise HTTPException(403, '只能撤回本人24小时内发送的消息')
    message.recalled_at = chat_now()
    message.recalled_by = user.id
    message.recall_label = (f'{message.sender_name}撤回了一条消息' if message.sender_user_id == user.id
                            else f'管理员{user.full_name or user.username}移除了一条消息')
    message.content = ''
    message.content_json = None
    message.updated_at = chat_now()
    db.query(ChatProjectMessageFavorite).filter_by(message_id=message.id).delete(synchronize_session=False)
    db.query(ChatProjectMessageAcknowledgement).filter_by(message_id=message.id).delete(synchronize_session=False)
    # 兼容历史版本含正文的通知；新的通知本身不写正文。
    db.query(AppNotification).filter_by(related_project_type='annotation', related_entity_id=project_id,
        notification_type='annotation_project_chat_mention').update(
            {'content': '项目沟通消息已更新，点击查看当前消息'}, synchronize_session=False)
    db.commit()
    publish(db, project_id, 'recall', message.id)
    return message


def authorize_attachment(db, attachment_id, user):
    attachment = db.get(ChatProjectAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, '附件不存在')
    links = db.query(ChatProjectMessage).join(ChatProjectMessageAttachment,
        ChatProjectMessageAttachment.message_id == ChatProjectMessage.id).filter(
        ChatProjectMessageAttachment.attachment_id == attachment_id).all()
    if not links:
        # 共用附件表也保存工作流交接图片，保留原项目查看权限下的读取能力。
        from workflow_models import WorkflowHandoverAttachment
        if db.query(WorkflowHandoverAttachment).filter_by(attachment_id=attachment_id).first() and can_view(db, user):
            return attachment
        if attachment.uploaded_by != user.id:
            raise HTTPException(403, '没有访问附件的权限')
        if attachment.annotation_project_id:
            require_project(db, attachment.annotation_project_id, user)
    elif not any(not row.recalled_at and can_view(db, user) for row in links):
        raise HTTPException(404, '附件已撤回或不可访问')
    return attachment
