import os
import uuid
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from crud import get_translation_project, get_user_roles_with_role_names
from database import get_db
from annotation_models import AnnotationProject
from models import AppUser, ChatProjectAttachment, ChatProjectMessage
from project_chat_crud import (
    create_annotation_project_chat_message,
    create_project_chat_message,
    favorite_chat_message,
    get_chat_message_favorite_times,
    get_project_chat_settings,
    list_annotation_project_chat_messages,
    list_project_chat_messages,
    set_project_chat_settings,
    unfavorite_chat_message,
)
from routers.auth import get_current_user, require_module_access
from schemas import (
    AnnotationProjectChatMessageCreate,
    ProjectChatMessageCreate,
    ProjectChatFavoriteResponse,
    ProjectChatMessageQueryResponse,
    ProjectChatMentionResponse,
    ProjectChatMessageResponse,
    ProjectChatAttachmentResponse,
    ProjectChatSettingsResponse,
    ProjectChatSettingsUpdateRequest,
)

router = APIRouter(prefix='/project-chat', tags=['project_chat'], dependencies=[Depends(require_module_access("projects:read", "workflow:operate"))])


MANAGE_ROLES = {'admin', '超级管理员', '项目经理'}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_SIGNATURES = {
    'image/jpeg': lambda value: value.startswith(b'\xff\xd8\xff'),
    'image/png': lambda value: value.startswith(b'\x89PNG\r\n\x1a\n'),
    'image/gif': lambda value: value.startswith((b'GIF87a', b'GIF89a')),
    'image/webp': lambda value: len(value) >= 12 and value[:4] == b'RIFF' and value[8:12] == b'WEBP',
}
IMAGE_EXTENSIONS = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
}


def get_chat_upload_dir() -> Path:
    path = Path(os.getenv('CHAT_UPLOAD_DIR', 'data/chat_uploads')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path



def _serialize_settings(project_id: UUID, settings, can_manage: bool) -> ProjectChatSettingsResponse:
    return ProjectChatSettingsResponse(
        project_id=project_id,
        enabled=bool(settings.enabled) if settings else False,
        enabled_by=settings.enabled_by if settings else None,
        enabled_at=settings.enabled_at if settings else None,
        updated_at=settings.updated_at if settings else None,
        can_manage=can_manage,
    )



def _serialize_message(
    message,
    project_type: str = 'translation',
    favorited_at: datetime | None = None,
) -> ProjectChatMessageResponse:
    mention_rows = sorted(
        getattr(message, 'mentions', None) or [],
        key=lambda item: (item.created_at is None, item.created_at or datetime.min, str(item.id)),
    )
    mentions = [
        ProjectChatMentionResponse(
            mentioned_user_id=mention.mentioned_user_id,
            mentioned_user_name=mention.mentioned_user_name,
        )
        for mention in mention_rows
    ]
    mention = mention_rows[0] if mention_rows else None
    attachment_links = [] if project_type == 'annotation' else (getattr(message, 'attachment_links', None) or [])
    attachments = [
        ProjectChatAttachmentResponse(
            id=link.attachment.id,
            original_name=link.attachment.original_name,
            content_type=link.attachment.content_type,
            file_size=link.attachment.file_size,
            created_at=link.attachment.created_at,
        )
        for link in attachment_links
        if link.attachment
    ]
    return ProjectChatMessageResponse(
        id=message.id,
        project_id=message.annotation_project_id if project_type == 'annotation' else message.project_id,
        project_type=project_type,
        sender_user_id=message.sender_user_id,
        sender_name=message.sender_name,
        content=message.content,
        content_json=message.content_json,
        message_type=message.message_type,
        metadata=message.event_data or {},
        created_at=message.created_at,
        updated_at=message.updated_at,
        mentioned_user_id=mention.mentioned_user_id if mention else None,
        mentioned_user_name=mention.mentioned_user_name if mention else None,
        mentions=mentions,
        is_favorited=favorited_at is not None,
        favorited_at=favorited_at,
        attachments=attachments,
    )



def _require_project(db: Session, project_id: UUID):
    project = get_translation_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='项目不存在')
    return project


def _require_annotation_project(db: Session, project_id: UUID):
    project = db.get(AnnotationProject, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='标注项目不存在')
    return project



def _can_manage_chat(db: Session, user_id: UUID) -> bool:
    roles = set(get_user_roles_with_role_names(db, user_id))
    return not MANAGE_ROLES.isdisjoint(roles)


def _require_visible_message(db: Session, message_id: UUID) -> ChatProjectMessage:
    """按消息列表的可见性规则校验，避免通过消息 ID 越权收藏。"""
    message = db.get(ChatProjectMessage, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='消息不存在')

    if message.annotation_project_id is not None:
        _require_annotation_project(db, message.annotation_project_id)
        return message

    if message.project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='消息不存在')
    _require_project(db, message.project_id)
    settings = get_project_chat_settings(db, message.project_id)
    if message.message_type == 'user' and not bool(settings and settings.enabled):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='消息不存在')
    return message


@router.get('/annotation/{project_id}/messages', response_model=ProjectChatMessageQueryResponse)
def list_annotation_messages_endpoint(
    project_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    sender_user_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_annotation_project(db, project_id)
    items, total = list_annotation_project_chat_messages(
        db,
        annotation_project_id=project_id,
        skip=skip,
        limit=limit,
        keyword=keyword,
        sender_user_id=sender_user_id,
        date_from=date_from,
        date_to=date_to,
        current_user_id=current_user.id,
        favorites_only=favorites_only,
    )
    favorite_times = get_chat_message_favorite_times(db, [item.id for item in items], current_user.id)
    return ProjectChatMessageQueryResponse(
        items=[_serialize_message(item, 'annotation', favorite_times.get(item.id)) for item in items],
        total=total,
        enabled=True,
        can_manage=False,
    )


@router.post('/annotation/{project_id}/messages', response_model=ProjectChatMessageResponse, status_code=status.HTTP_201_CREATED)
def create_annotation_message_endpoint(
    project_id: UUID,
    payload: AnnotationProjectChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_annotation_project(db, project_id)
    try:
        message = create_annotation_project_chat_message(
            db,
            annotation_project_id=project_id,
            sender=current_user,
            content=payload.content,
            mentioned_user_id=payload.mentioned_user_id,
            mentioned_user_ids=payload.mentioned_user_ids,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_message(message, 'annotation')


@router.put('/messages/{message_id}/favorite', response_model=ProjectChatFavoriteResponse)
def favorite_message_endpoint(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_visible_message(db, message_id)
    favorite = favorite_chat_message(db, message_id, current_user.id)
    return ProjectChatFavoriteResponse(
        message_id=message_id,
        is_favorited=True,
        favorited_at=favorite.created_at,
    )


@router.delete('/messages/{message_id}/favorite', response_model=ProjectChatFavoriteResponse)
def unfavorite_message_endpoint(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_visible_message(db, message_id)
    unfavorite_chat_message(db, message_id, current_user.id)
    return ProjectChatFavoriteResponse(message_id=message_id, is_favorited=False)


@router.post('/attachments', response_model=ProjectChatAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    content_type = (file.content_type or '').lower()
    validator = IMAGE_SIGNATURES.get(content_type)
    if validator is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail='仅支持 JPEG、PNG、GIF、WebP 图片')

    content = await file.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='图片内容为空')
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='单张图片不能超过 10MB')
    if not validator(content):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='图片格式与文件内容不匹配')

    storage_name = f'{uuid.uuid4().hex}{IMAGE_EXTENSIONS[content_type]}'
    destination = get_chat_upload_dir() / storage_name
    destination.write_bytes(content)
    attachment = ChatProjectAttachment(
        uploaded_by=current_user.id,
        original_name=(file.filename or 'image')[:255],
        storage_name=storage_name,
        content_type=content_type,
        file_size=len(content),
    )
    db.add(attachment)
    try:
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return ProjectChatAttachmentResponse(
        id=attachment.id,
        original_name=attachment.original_name,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        created_at=attachment.created_at,
    )


@router.get('/attachments/{attachment_id}')
def read_attachment_endpoint(
    attachment_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    attachment = db.query(ChatProjectAttachment).filter(ChatProjectAttachment.id == attachment_id).first()
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='图片不存在')
    path = get_chat_upload_dir() / attachment.storage_name
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='图片文件不存在')
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.original_name)


@router.get('/{project_id}/settings', response_model=ProjectChatSettingsResponse)
def get_settings_endpoint(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_project(db, project_id)
    settings = get_project_chat_settings(db, project_id)
    return _serialize_settings(project_id, settings, _can_manage_chat(db, current_user.id))


@router.post('/{project_id}/settings', response_model=ProjectChatSettingsResponse)
def update_settings_endpoint(
    project_id: UUID,
    payload: ProjectChatSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_project(db, project_id)
    if not _can_manage_chat(db, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='没有权限管理项目沟通')
    settings = set_project_chat_settings(db, project_id, payload.enabled, current_user.id)
    return _serialize_settings(project_id, settings, True)


@router.get('/{project_id}/messages', response_model=ProjectChatMessageQueryResponse)
def list_messages_endpoint(
    project_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    sender_user_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_project(db, project_id)
    settings = get_project_chat_settings(db, project_id)
    can_manage = _can_manage_chat(db, current_user.id)
    chat_enabled = bool(settings and settings.enabled)
    items, total = list_project_chat_messages(
        db,
        project_id=project_id,
        skip=skip,
        limit=limit,
        keyword=keyword,
        sender_user_id=sender_user_id,
        date_from=date_from,
        date_to=date_to,
        include_user_messages=chat_enabled,
        current_user_id=current_user.id,
        favorites_only=favorites_only,
    )
    favorite_times = get_chat_message_favorite_times(db, [item.id for item in items], current_user.id)
    return ProjectChatMessageQueryResponse(
        items=[_serialize_message(item, favorited_at=favorite_times.get(item.id)) for item in items],
        total=total,
        enabled=chat_enabled,
        can_manage=can_manage,
    )


@router.post('/{project_id}/messages', response_model=ProjectChatMessageResponse, status_code=status.HTTP_201_CREATED)
def create_message_endpoint(
    project_id: UUID,
    payload: ProjectChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_project(db, project_id)
    try:
        message = create_project_chat_message(
            db,
            project_id=project_id,
            sender=current_user,
            content=payload.content,
            content_json=payload.content_json,
            mentioned_user_id=payload.mentioned_user_id,
            mentioned_user_ids=payload.mentioned_user_ids,
            attachment_ids=payload.attachment_ids,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_message(message)
