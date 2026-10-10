"""群聊与私聊共用稳定时间线与文件校验上传。"""
import uuid
import os
from pathlib import Path
from uuid import UUID

from fastapi import Depends, File, HTTPException, Query, UploadFile, Request
from sqlalchemy.orm import Session


from database import get_db
from models import AppUser, ChatProjectMessage, ChatProjectMessageFavorite, ChatProjectAttachment
from routers.auth import get_current_user

def chat_timeline(service, project_id: UUID, before: int | None = None, after: int | None = None,
             around: UUID | None = None, limit: int = Query(30, ge=1, le=100), keyword: str = '',
             sender_user_id: UUID | None = None, favorites_only: bool = False,
             date_from: str | None = None, date_to: str | None = None,
             db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from datetime import datetime
    from chat_time import api_time
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
    return {'items': api_time(service.serialize_many(db, rows, user)), 'has_more': len(rows) >= limit}


FILE_TYPES = {'.pdf': 'application/pdf', '.txt': 'text/plain', '.csv': 'text/csv', '.zip': 'application/zip',
    '.doc': 'application/msword', '.xls': 'application/vnd.ms-excel', '.ppt': 'application/vnd.ms-powerpoint',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}


async def upload_chat_file(service, scope, project_id: UUID, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
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
        target = remote_url if is_image and scope == 'annotation' else remote_url.removesuffix('/attachments') + f'/{scope}/{project_id}/files'
        result = await upload_remote_attachment(target, content, file.filename, content_type,
            request.headers.get('authorization'), request.headers.get('x-chat-attachment-forwarded'))
        attachment = db.get(ChatProjectAttachment, result.id, populate_existing=True)
        if attachment is None or attachment.uploaded_by != user.id:
            raise HTTPException(502, '云端附件记录尚未同步，请稍后重试')
        setattr(attachment, 'direct_conversation_id' if scope == 'direct' else 'annotation_project_id', project_id)
        db.commit()
        return result
    name = uuid.uuid4().hex + suffix
    destination = get_chat_upload_dir() / name
    destination.write_bytes(content)
    attachment = ChatProjectAttachment(uploaded_by=user.id, **{('direct_conversation_id' if scope == 'direct' else 'annotation_project_id'): project_id}, original_name=Path(file.filename).name[:255],
        storage_name=name, content_type=content_type, file_size=len(content))
    db.add(attachment)
    try:
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    from chat_time import api_time
    return {'id': attachment.id, 'original_name': attachment.original_name, 'content_type': content_type,
            'file_size': len(content), 'created_at': api_time(attachment.created_at)}


