"""标注群聊增量接口；由 project_chat 路由注册，不改变笔译接口。"""
import uuid
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import annotation_chat_service as service
from chat_history_search import ChatHistoryError, search_chat_history
from database import get_db
from models import AnnotationChatMember, AppUser, ChatProjectMessage, ChatProjectMessageFavorite, ChatProjectAttachment
from annotation_models import AnnotationProject
from annotation_chat_conversation import AnnotationChatConversation, created_ids, ready as conversation_registry_ready
from routers.auth import get_current_user

router = APIRouter(prefix='/annotation')

from annotation_progress_chat import MentionSelection


@router.get('/progress-mention-defaults')
def progress_mention_defaults(scope: str = Query('progress',pattern='^(progress|creation)$'), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from annotation_progress_chat import options
    return options(db, user, scope)


@router.put('/progress-mention-defaults')
def save_progress_mention_defaults(payload: MentionSelection, scope: str = Query('progress',pattern='^(progress|creation)$'), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from annotation_progress_chat import save_defaults
    return save_defaults(db, user, payload, scope)


class FollowRequest(BaseModel):
    following: bool


class RestoreFavoritesRequest(BaseModel):
    project_ids: list[UUID] = Field(min_length=1, max_length=10)


@router.get('/unfollowed-projects')
def unfollowed_projects(offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if not service.can_view(db, user):
        raise HTTPException(403, '没有项目沟通权限')
    query = db.query(AnnotationProject).join(AnnotationChatMember, AnnotationChatMember.project_id == AnnotationProject.id).filter(
        AnnotationChatMember.user_id == user.id, AnnotationChatMember.following.is_(False), AnnotationChatMember.explicit_unfollow.is_(True))
    total = query.count()
    rows = query.order_by(AnnotationProject.order_no.desc(), AnnotationProject.id).offset(offset).limit(limit).all()
    return {'total': total, 'items': [dict(project_id=row.id, project_name=row.project_name, order_no=row.order_no) for row in rows]}


@router.post('/restore-favorites')
def restore_favorites(payload: RestoreFavoritesRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if not service.can_view(db, user):
        raise HTTPException(403, '没有项目沟通权限')
    restored, failed = [], []
    for project_id in dict.fromkeys(payload.project_ids):
        try:
            service.require_project(db, project_id, user, lock=True)
            member = db.get(AnnotationChatMember, (project_id, user.id))
            if not member.following and not member.explicit_unfollow:
                raise HTTPException(409, '该项目不在取消关注列表中')
            member.following = True
            member.explicit_unfollow = False
            # 恢复收藏不等于阅读，保留原有未读游标。
            db.commit()
        except HTTPException as error:
            db.rollback()
            failed.append(dict(project_id=project_id, reason=error.detail))
            continue
        except SQLAlchemyError:
            db.rollback()
            failed.append(dict(project_id=project_id, reason='保存失败，请重试'))
            continue
        restored.append(project_id)
        service.publish(db, project_id, 'members')
        service.notify_state(user.id, project_id)
    return {'restored': restored, 'failed': failed}


class InviteRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=100)


class ReadRequest(BaseModel):
    message_id: UUID


class RefreshRequest(BaseModel):
    message_ids: list[UUID] = Field(default_factory=list, max_length=200)


class DefaultParticipantsWrite(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list, max_length=1000)


@router.get('/default-participants')
def default_participants(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    import chat_default_participant_service as defaults
    if not service.can_view(db, user):
        raise HTTPException(403, '没有项目沟通权限')
    return defaults.catalog(db, user)


@router.put('/default-participants')
def save_default_participants(payload: DefaultParticipantsWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    import chat_default_participant_service as defaults
    return defaults.save(db, user, payload.user_ids)


class ConversationStatusRequest(BaseModel):
    project_ids: list[UUID] = Field(min_length=1, max_length=100)


@router.get('/conversation-capabilities')
def conversation_capabilities(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return {'can_create': service.can_view(db, user), 'can_join_existing': service.annotation_department_member(db, user)}


@router.post('/conversation-status')
def conversation_status(payload: ConversationStatusRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if not service.can_view(db, user):
        raise HTTPException(403, '没有项目沟通权限')
    ids = set(payload.project_ids)
    projects = db.query(AnnotationProject.id).filter(AnnotationProject.id.in_(ids)).all()
    created = created_ids(db,ids)
    joined = created & {pid for pid, in db.query(AnnotationChatMember.project_id).filter(AnnotationChatMember.project_id.in_(ids), AnnotationChatMember.user_id == user.id)}
    can_join = service.annotation_department_member(db, user)
    return {'items': [dict(project_id=pid, created=pid in created, joined=pid in joined,
        can_join=pid in joined or can_join or pid not in created) for pid, in projects]}


@router.post('/{project_id}/start')
def start(project_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    project = service.require_project_record(db, project_id, user, lock=True)
    if project_id in created_ids(db,[project_id]) and db.query(AnnotationChatMember).filter_by(project_id=project_id).first():
        from chat_access_service import is_member
        if not is_member(db, 'annotation', project_id, user):
            if not service.annotation_department_member(db, user):
                service.require_project(db, project_id, user)
            service.add_member(db, project_id, user.id, baseline=0)
            db.commit()
            service.publish(db, project_id, 'members')
        return {'project_id': project.id, 'created': True, 'joined': True}
    if db.query(ChatProjectMessage.id).filter_by(annotation_project_id=project_id).first():
        raise HTTPException(404, '历史会话尚未配置参与人，请联系管理员')
    import chat_default_participant_service as defaults
    ids = set(defaults.default_user_ids(db)) | {user.id}
    eligible = {row.id for row in service.eligible_users(db, ids)}
    for uid in ids & eligible:
        service.add_member(db, project_id, uid)
    if conversation_registry_ready(db) and not db.get(AnnotationChatConversation,project_id):
        db.add(AnnotationChatConversation(project_id=project_id,created_by=user.id))
    db.commit()
    service.publish(db, project_id, 'members')
    return {'project_id': project.id, 'created': True, 'joined': True}


@router.get('/unread')
def unread(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if not service.can_view(db, user):
        raise HTTPException(403, '没有查看项目的权限')
    count = func.count(ChatProjectMessage.id)
    rows = db.query(AnnotationProject.id, AnnotationProject.project_name, AnnotationProject.order_no, count).join(
        AnnotationChatMember, AnnotationChatMember.project_id == AnnotationProject.id).outerjoin(
        ChatProjectMessage, (ChatProjectMessage.annotation_project_id == AnnotationProject.id)
        & (ChatProjectMessage.sequence_no > AnnotationChatMember.last_read_sequence)
        & ChatProjectMessage.recalled_at.is_(None)
        & (ChatProjectMessage.sender_user_id != user.id)).filter(
        AnnotationChatMember.user_id == user.id, AnnotationChatMember.following.is_(True)).group_by(
        AnnotationProject.id).order_by(AnnotationProject.order_no.desc(), AnnotationProject.id).all()
    followed = [{'project_id': r[0], 'project_name': r[1], 'order_no': r[2], 'unread': r[3]} for r in rows]
    return {'items': [item for item in followed if item['unread']], 'followed_items': followed,
            'total': sum(r[3] for r in rows)}


@router.get('/{project_id}/group')
def group(project_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    project = service.require_project(db, project_id, user, lock=True)
    service.ensure_default_members(db, project_id)
    db.commit()
    users = service.eligible_users(db)
    members = {m.user_id for m in db.query(AnnotationChatMember).filter_by(project_id=project_id).all()}
    me = db.get(AnnotationChatMember, (project_id, user.id))
    return {'project_name': project.project_name, 'order_no': project.order_no,
            'following': bool(me and me.following),
            'last_read_sequence': me.last_read_sequence if me else 0,
            'members': [{'id': u.id, 'name': u.full_name or u.username} for u in users if u.id in members],
            'eligible_users': [{'id': u.id, 'name': u.full_name or u.username} for u in users if u.id in members],
            'invitable_users': [{'id': u.id, 'name': u.full_name or u.username} for u in users if u.id not in members]}


@router.put('/{project_id}/following')
def follow(project_id: UUID, payload: FollowRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user, lock=True)
    member = service.add_member(db, project_id, user.id)
    member.following = payload.following
    member.explicit_unfollow = not payload.following
    if payload.following:
        member.last_read_sequence = service.latest_sequence(db, project_id)
    db.commit()
    service.publish(db, project_id, 'members')
    service.notify_state(user.id, project_id)
    return {'following': member.following}


@router.post('/{project_id}/invitations')
def invite(project_id: UUID, payload: InviteRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from crud import create_notifications_for_users
    from project_chat_crud import _push_notifications
    project = service.require_project(db, project_id, user, lock=True)
    targets = [db.get(AppUser, uid) for uid in set(payload.user_ids)]
    if any(not service.can_view(db, target) for target in targets):
        raise HTTPException(400, '邀请对象必须为具备项目查看权限的有效用户')
    invited = []
    for target in targets:
        existing = db.get(AnnotationChatMember, (project_id, target.id))
        if existing and (existing.following or existing.explicit_unfollow):
            continue
        member = service.add_member(db, project_id, target.id)
        member.following = True
        invited.append(target.id)
    notifications = create_notifications_for_users(db, recipient_user_ids=invited,
        title='项目群聊邀请', content=f'{user.full_name or user.username}邀请你参与项目 {project.order_no} / {project.project_name or "-"} 的沟通',
        notification_type='annotation_project_chat_invite', related_project_type='annotation', related_entity_id=project_id, commit=False) if invited else []
    db.commit()
    _push_notifications(notifications)
    service.publish(db, project_id, 'members')
    return {'invited_count': len(invited)}


@router.put('/{project_id}/read')
def read(project_id: UUID, payload: ReadRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user, lock=True)
    message = service.message_query(db, project_id).filter(ChatProjectMessage.id == payload.message_id).first()
    if not message:
        raise HTTPException(404, '消息不存在')
    member = service.add_member(db, project_id, user.id, following=False, baseline=0)
    member.last_read_sequence = max(member.last_read_sequence, message.sequence_no)
    db.commit()
    service.notify_state(user.id, project_id)
    return {'last_read_sequence': member.last_read_sequence}


@router.get('/{project_id}/history')
def history(project_id: UUID, kind: str = Query('all', pattern='^(all|image|link|file)$'),
            topic_id: UUID | None = None,
            keyword: str = '', sender_user_id: UUID | None = None, favorites_only: bool = False,
            date_from: str | None = None, date_to: str | None = None, cursor: str | None = None,
            limit: int = Query(30, ge=1, le=50),
            db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from datetime import datetime
    service.require_project(db, project_id, user)
    try:
        parsed_from = datetime.fromisoformat(date_from) if date_from else None
        parsed_to = datetime.fromisoformat(date_to) if date_to else None
        return search_chat_history(
            db, project_type='annotation', project_id=project_id, user_id=user.id, kind=kind,
            keyword=keyword, sender_user_id=sender_user_id, date_from=parsed_from, date_to=parsed_to,
            favorites_only=favorites_only, cursor=cursor, limit=limit,
            topic_id=topic_id,
        )
    except ValueError as exc:
        status_code = 400 if isinstance(exc, ChatHistoryError) or '日期' in str(exc) else 400
        raise HTTPException(status_code, str(exc) or '检索参数无效') from exc


@router.get('/{project_id}/timeline')
def timeline(project_id: UUID, before: int | None = None, after: int | None = None,
             around: UUID | None = None, limit: int = Query(30, ge=1, le=100), keyword: str = '',
             sender_user_id: UUID | None = None, favorites_only: bool = False,
             date_from: str | None = None, date_to: str | None = None,
             db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from chat_common_handlers import chat_timeline
    return chat_timeline(service, project_id, before, after, around, limit, keyword, sender_user_id, favorites_only, date_from, date_to, db, user)


@router.post('/{project_id}/refresh')
def refresh(project_id: UUID, payload: RefreshRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user)
    rows = service.message_query(db, project_id).filter(ChatProjectMessage.id.in_(payload.message_ids)).all()
    return {'items': service.serialize_many(db, rows, user)}


@router.get('/{project_id}/sent/{client_message_id}')
def sent(project_id: UUID, client_message_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user, lock=True)
    row = service.message_query(db, project_id).filter(ChatProjectMessage.sender_user_id == user.id,
        ChatProjectMessage.client_message_id == client_message_id).first()
    return {'message': service.serialize_many(db, [row], user)[0] if row else None}


@router.post('/{project_id}/messages/{message_id}/recall')
def recall(project_id: UUID, message_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = service.recall_message(db, project_id, message_id, user)
    return service.serialize_many(db, [row], user)[0]


FILE_TYPES = {'.pdf': 'application/pdf', '.txt': 'text/plain', '.csv': 'text/csv', '.zip': 'application/zip',
    '.doc': 'application/msword', '.xls': 'application/vnd.ms-excel', '.ppt': 'application/vnd.ms-powerpoint',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}


@router.post('/{project_id}/files', status_code=201)
async def upload(project_id: UUID, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from chat_common_handlers import upload_chat_file
    return await upload_chat_file(service, 'annotation', project_id, request, file, db, user)


@router.get('/{project_id}/files/{attachment_id}')
async def download(project_id: UUID, attachment_id: UUID, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from fastapi.responses import FileResponse
    from routers.project_chat import get_chat_upload_dir
    from models import ChatProjectMessageAttachment
    service.require_project(db, project_id, user)
    attachment = service.authorize_attachment(db, attachment_id, user)
    from chat_screenshot_storage import read_attachment
    stored=read_attachment(db,attachment)
    if stored is not None:return stored
    if attachment.storage_name.startswith('material:'):
        from annotation_task_images import download_chat_image
        return await download_chat_image(db,project_id,attachment.storage_name,request)
    if attachment.annotation_project_id and attachment.annotation_project_id != project_id:
        raise HTTPException(404, '附件不属于当前项目')
    links = db.query(ChatProjectMessage).join(ChatProjectMessageAttachment,
        ChatProjectMessageAttachment.message_id == ChatProjectMessage.id).filter(ChatProjectMessageAttachment.attachment_id == attachment_id).all()
    if links and not any(row.annotation_project_id == project_id and not row.recalled_at for row in links):
        raise HTTPException(404, '附件不属于当前项目')
    from chat_attachment_storage import remote_attachment_url, read_remote_attachment
    remote_url = remote_attachment_url()
    if remote_url:
        return await read_remote_attachment(remote_url, attachment_id, request.headers.get('authorization'),
            request.headers.get('x-chat-attachment-forwarded'), allow_files=True)
    path = get_chat_upload_dir() / attachment.storage_name
    if not path.is_file():
        raise HTTPException(404, '文件不存在')
    return FileResponse(path, filename=attachment.original_name, media_type=attachment.content_type,
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
