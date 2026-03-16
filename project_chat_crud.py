import datetime as dt
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from crud import create_notifications_for_users, get_users_by_role_names
from models import AppUser, ChatProjectEnabled, ChatProjectMention, ChatProjectMessage, TranslationProject
from notification_ws import dispatch_personal_message
from workflow_crud import STAGE_BY_KEY


CHAT_MANAGER_ROLES = {'admin', '超级管理员', '项目经理'}


def _serialize_notification(notification) -> dict:
    return {
        'id': str(notification.id),
        'title': notification.title,
        'content': notification.content,
        'notification_type': notification.notification_type,
        'is_read': notification.is_read,
        'related_project_id': str(notification.related_project_id) if notification.related_project_id else None,
        'created_at': notification.created_at.isoformat() if notification.created_at else None,
    }



def _push_notifications(notifications: list) -> None:
    for notification in notifications:
        dispatch_personal_message(
            notification.recipient_user_id,
            {
                'type': 'notification',
                'notification': _serialize_notification(notification),
            },
        )



def get_project_chat_settings(db: Session, project_id: UUID) -> Optional[ChatProjectEnabled]:
    return db.query(ChatProjectEnabled).filter(ChatProjectEnabled.project_id == project_id).first()



def set_project_chat_settings(
    db: Session,
    project_id: UUID,
    enabled: bool,
    operator_id: Optional[UUID] = None,
) -> ChatProjectEnabled:
    now = dt.datetime.utcnow()
    settings = get_project_chat_settings(db, project_id)
    if settings is None:
        settings = ChatProjectEnabled(
            project_id=project_id,
            enabled=enabled,
            enabled_by=operator_id,
            enabled_at=now if enabled else None,
            updated_at=now,
        )
        db.add(settings)
    else:
        settings.enabled = enabled
        settings.enabled_by = operator_id
        settings.updated_at = now
        if enabled:
            settings.enabled_at = now
    db.commit()
    db.refresh(settings)
    return settings



def list_project_chat_messages(
    db: Session,
    project_id: UUID,
    skip: int = 0,
    limit: int = 20,
    keyword: Optional[str] = None,
    sender_user_id: Optional[UUID] = None,
    date_from: Optional[dt.datetime] = None,
    date_to: Optional[dt.datetime] = None,
) -> tuple[list[ChatProjectMessage], int]:
    query = (
        db.query(ChatProjectMessage)
        .options(selectinload(ChatProjectMessage.mentions))
        .filter(ChatProjectMessage.project_id == project_id)
    )

    if keyword:
        query = query.filter(ChatProjectMessage.content.ilike(f'%{keyword.strip()}%'))
    if sender_user_id:
        query = query.filter(ChatProjectMessage.sender_user_id == sender_user_id)
    if date_from:
        query = query.filter(ChatProjectMessage.created_at >= date_from)
    if date_to:
        query = query.filter(ChatProjectMessage.created_at <= date_to)

    total = query.count()
    items = (
        query.order_by(ChatProjectMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total



def _collect_stage_role_users(db: Session, stage_key: Optional[str]) -> list[UUID]:
    if not stage_key:
        return []
    stage_info = STAGE_BY_KEY.get(stage_key) or {}
    role_names: list[str] = []
    assign_roles = stage_info.get('assignRoles') or []
    for role_name in assign_roles:
        if role_name and role_name not in role_names:
            role_names.append(role_name)
    stage_role = stage_info.get('role')
    if stage_role and stage_role != '-':
        for raw_name in str(stage_role).replace('／', '/').split('/'):
            role_name = raw_name.strip()
            if role_name and role_name not in role_names:
                role_names.append(role_name)
    return [user.id for user in get_users_by_role_names(db, role_names)]



def get_default_chat_recipient_ids(db: Session, project: TranslationProject) -> list[UUID]:
    recipients: set[UUID] = set()

    if project.created_by:
        recipients.add(project.created_by)
    if project.pm_confirmed_by:
        recipients.add(project.pm_confirmed_by)

    workflow = project.workflow_instance
    if workflow:
        if workflow.current_assignee_id:
            recipients.add(workflow.current_assignee_id)
        if workflow.group_assign_role:
            recipients.update(user.id for user in get_users_by_role_names(db, [workflow.group_assign_role]))
        else:
            recipients.update(_collect_stage_role_users(db, workflow.current_stage_key))

    return list(recipients)



def create_project_chat_message(
    db: Session,
    project_id: UUID,
    sender: AppUser,
    content: str,
    mentioned_user_id: Optional[UUID] = None,
) -> ChatProjectMessage:
    settings = get_project_chat_settings(db, project_id)
    if settings is None or not settings.enabled:
        raise ValueError('Project chat is disabled')

    project = (
        db.query(TranslationProject)
        .options(selectinload(TranslationProject.workflow_instance))
        .filter(TranslationProject.id == project_id)
        .first()
    )
    if project is None:
        raise ValueError('Project not found')

    message = ChatProjectMessage(
        project_id=project_id,
        sender_user_id=sender.id,
        sender_name=(sender.full_name or sender.username),
        content=(content or '').strip(),
    )
    db.add(message)
    db.flush()

    mention_user = None
    if mentioned_user_id and mentioned_user_id != sender.id:
        mention_user = (
            db.query(AppUser)
            .filter(AppUser.id == mentioned_user_id, AppUser.is_active == True)
            .first()
        )
        if mention_user is None:
            raise ValueError('Mentioned user not found')
        db.add(ChatProjectMention(
            message_id=message.id,
            mentioned_user_id=mention_user.id,
            mentioned_user_name=(mention_user.full_name or mention_user.username),
        ))

    db.commit()

    created = (
        db.query(ChatProjectMessage)
        .options(selectinload(ChatProjectMessage.mentions))
        .filter(ChatProjectMessage.id == message.id)
        .first()
    )
    if created is None:
        raise ValueError('Failed to load created message')

    preview = created.content.replace('\r', ' ').replace('\n', ' ').strip()
    if len(preview) > 60:
        preview = preview[:57] + '...'

    default_recipients = set(get_default_chat_recipient_ids(db, project))
    default_recipients.discard(sender.id)

    mention_recipients: set[UUID] = set()
    if mention_user is not None:
        mention_recipients.add(mention_user.id)
        default_recipients.discard(mention_user.id)

    notifications = []
    if mention_recipients:
        notifications.extend(create_notifications_for_users(
            db,
            recipient_user_ids=list(mention_recipients),
            title='项目沟通提醒',
            content=f'{created.sender_name} 在项目 {project.order_no} / {project.project_name} 中 @了你：{preview}',
            notification_type='project_chat_mention',
            related_project_id=project.id,
            commit=True,
        ))
    if default_recipients:
        notifications.extend(create_notifications_for_users(
            db,
            recipient_user_ids=list(default_recipients),
            title='项目沟通新消息',
            content=f'{created.sender_name} 在项目 {project.order_no} / {project.project_name} 中发送了新消息：{preview}',
            notification_type='project_chat',
            related_project_id=project.id,
            commit=True,
        ))
    if notifications:
        _push_notifications(notifications)

    return created
