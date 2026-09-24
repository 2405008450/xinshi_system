"""标注群聊增量接口；由 project_chat 路由注册，不改变笔译接口。"""
import uuid
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

import annotation_chat_service as service
from database import get_db
from models import AnnotationChatMember, AppUser, ChatProjectMessage, ChatProjectMessageFavorite, ChatProjectAttachment
from annotation_models import AnnotationProject
from routers.auth import get_current_user

router = APIRouter(prefix='/annotation')


class FollowRequest(BaseModel):
    following: bool


class InviteRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=100)


class ReadRequest(BaseModel):
    message_id: UUID


class RefreshRequest(BaseModel):
    message_ids: list[UUID] = Field(default_factory=list, max_length=200)


@router.get('/unread')
def unread(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    if not service.can_view(db, user):
        raise HTTPException(403, '没有查看项目的权限')
    from sqlalchemy import or_
    from workflow_models import ProjectWorkbenchResponsibility
    assigned = db.query(ProjectWorkbenchResponsibility.annotation_project_id).filter(
        ProjectWorkbenchResponsibility.assignee_id == user.id,
        ProjectWorkbenchResponsibility.annotation_project_id.is_not(None))
    responsible = db.query(AnnotationProject.id).filter(or_(AnnotationProject.created_by == user.id,
        AnnotationProject.client_manager_id == user.id, AnnotationProject.id.in_(assigned))).all()
    for (project_id,) in responsible:
        member = service.add_member(db, project_id, user.id)
        db.query(AnnotationChatMember).filter_by(project_id=project_id, user_id=user.id,
            explicit_unfollow=False).update({'following': True}, synchronize_session=False)
    db.commit()
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
    members = {m.user_id for m in db.query(AnnotationChatMember).filter_by(project_id=project_id, following=True).all()}
    me = db.get(AnnotationChatMember, (project_id, user.id))
    return {'project_name': project.project_name, 'order_no': project.order_no,
            'following': bool(me and me.following),
            'members': [{'id': u.id, 'name': u.full_name or u.username} for u in users if u.id in members],
            'eligible_users': [{'id': u.id, 'name': u.full_name or u.username} for u in users]}


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


@router.get('/{project_id}/timeline')
def timeline(project_id: UUID, before: int | None = None, after: int | None = None,
             around: UUID | None = None, limit: int = Query(30, ge=1, le=100), keyword: str = '',
             sender_user_id: UUID | None = None, favorites_only: bool = False,
             date_from: str | None = None, date_to: str | None = None,
             db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from datetime import datetime
    service.require_project(db, project_id, user)
    query = service.message_query(db, project_id)
    if keyword.strip():
        query = query.filter(ChatProjectMessage.recalled_at.is_(None), ChatProjectMessage.content.ilike('%' + keyword.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%', escape='\\'))
    if sender_user_id:
        query = query.filter(ChatProjectMessage.sender_user_id == sender_user_id)
    if favorites_only:
        query = query.join(ChatProjectMessageFavorite).filter(ChatProjectMessageFavorite.user_id == user.id, ChatProjectMessage.recalled_at.is_(None))
    try:
        if date_from:
            query = query.filter(ChatProjectMessage.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(ChatProjectMessage.created_at <= datetime.fromisoformat(date_to))
    except ValueError as exc:
        raise HTTPException(400, '日期格式无效') from exc
    if around:
        anchor = service.message_query(db, project_id).filter(ChatProjectMessage.id == around).first()
        if not anchor:
            raise HTTPException(404, '引用消息不存在')
        older = query.filter(ChatProjectMessage.sequence_no <= anchor.sequence_no).order_by(ChatProjectMessage.sequence_no.desc()).limit(limit).all()
        newer = query.filter(ChatProjectMessage.sequence_no > anchor.sequence_no).order_by(ChatProjectMessage.sequence_no).limit(limit).all()
        rows = list(reversed(older)) + newer
    else:
        if before is not None:
            query = query.filter(ChatProjectMessage.sequence_no < before)
        if after is not None:
            query = query.filter(ChatProjectMessage.sequence_no > after)
        rows = query.order_by(ChatProjectMessage.sequence_no.asc() if after is not None else ChatProjectMessage.sequence_no.desc()).limit(limit).all()
        if after is None:
            rows.reverse()
    return {'items': service.serialize_many(db, rows, user), 'has_more': len(rows) >= limit}


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
    from routers.project_chat import get_chat_upload_dir, IMAGE_SIGNATURES, IMAGE_EXTENSIONS
    service.require_project(db, project_id, user)
    if os.getenv('CHAT_UPLOADS_PAUSED', 'false').strip().lower() == 'true':
        raise HTTPException(503, '附件上传维护中，请稍后重试')
    suffix = Path(file.filename or '').suffix.lower()
    image_types = {v: k for k, v in IMAGE_EXTENSIONS.items()} | {'.jpeg': 'image/jpeg'}
    content_type = image_types.get(suffix) or FILE_TYPES.get(suffix)
    if not content_type:
        raise HTTPException(415, '支持图片、PDF、Office、TXT、CSV、ZIP文件')
    is_image = content_type in IMAGE_SIGNATURES
    max_bytes = (10 if is_image else 20) * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise HTTPException(413, '文件不能为空，图片最多10MB，其他文件最多20MB')
    if is_image and not IMAGE_SIGNATURES[content_type](content):
        raise HTTPException(415, '图片格式与内容不匹配')
    if suffix == '.pdf' and not content.startswith(b'%PDF-'):
        raise HTTPException(415, 'PDF格式无效')
    if suffix in {'.zip', '.docx', '.xlsx', '.pptx'} and not content.startswith(b'PK'):
        raise HTTPException(415, '文件格式无效')
    if suffix in {'.doc', '.xls', '.ppt'} and not content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        raise HTTPException(415, 'Office文件格式无效')
    if suffix in {'.txt', '.csv'} and (b'\x00' in content[:4096] or content.startswith(b'MZ')):
        raise HTTPException(415, '文本文件格式无效')
    from chat_attachment_storage import remote_attachment_url, upload_remote_attachment
    remote_url = remote_attachment_url()
    if remote_url:
        # 图片兼容旧云端接口；其他文件通过本次新增的云端文件接口保存。
        target = remote_url if is_image else remote_url.removesuffix('/attachments') + f'/annotation/{project_id}/files'
        result = await upload_remote_attachment(target, content, file.filename, content_type,
            request.headers.get('authorization'), request.headers.get('x-chat-attachment-forwarded'))
        attachment = db.get(ChatProjectAttachment, result.id, populate_existing=True)
        if attachment is None or attachment.uploaded_by != user.id:
            raise HTTPException(502, '云端附件记录尚未同步，请稍后重试')
        attachment.annotation_project_id = project_id
        db.commit()
        return result
    name = uuid.uuid4().hex + suffix
    destination = get_chat_upload_dir() / name
    destination.write_bytes(content)
    attachment = ChatProjectAttachment(uploaded_by=user.id, annotation_project_id=project_id, original_name=Path(file.filename).name[:255],
        storage_name=name, content_type=content_type, file_size=len(content))
    db.add(attachment)
    try:
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return {'id': attachment.id, 'original_name': attachment.original_name, 'content_type': content_type,
            'file_size': len(content), 'created_at': attachment.created_at}


@router.get('/{project_id}/files/{attachment_id}')
async def download(project_id: UUID, attachment_id: UUID, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from fastapi.responses import FileResponse
    from routers.project_chat import get_chat_upload_dir
    from models import ChatProjectMessageAttachment
    service.require_project(db, project_id, user)
    attachment = service.authorize_attachment(db, attachment_id, user)
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
