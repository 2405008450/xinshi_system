from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from crud import get_translation_project, get_user_roles_with_role_names
from database import get_db
from models import AppUser
from project_chat_crud import create_project_chat_message, get_project_chat_settings, list_project_chat_messages, set_project_chat_settings
from routers.auth import get_current_user
from schemas import (
    ProjectChatMessageCreate,
    ProjectChatMessageQueryResponse,
    ProjectChatMessageResponse,
    ProjectChatSettingsResponse,
    ProjectChatSettingsUpdateRequest,
)

router = APIRouter(prefix='/project-chat', tags=['project_chat'], dependencies=[Depends(get_current_user)])


MANAGE_ROLES = {'admin', '超级管理员', '项目经理'}



def _serialize_settings(project_id: UUID, settings, can_manage: bool) -> ProjectChatSettingsResponse:
    return ProjectChatSettingsResponse(
        project_id=project_id,
        enabled=bool(settings.enabled) if settings else False,
        enabled_by=settings.enabled_by if settings else None,
        enabled_at=settings.enabled_at if settings else None,
        updated_at=settings.updated_at if settings else None,
        can_manage=can_manage,
    )



def _serialize_message(message) -> ProjectChatMessageResponse:
    mention = message.mentions[0] if getattr(message, 'mentions', None) else None
    return ProjectChatMessageResponse(
        id=message.id,
        project_id=message.project_id,
        sender_user_id=message.sender_user_id,
        sender_name=message.sender_name,
        content=message.content,
        created_at=message.created_at,
        updated_at=message.updated_at,
        mentioned_user_id=mention.mentioned_user_id if mention else None,
        mentioned_user_name=mention.mentioned_user_name if mention else None,
    )



def _require_project(db: Session, project_id: UUID):
    project = get_translation_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Project not found')
    return project



def _can_manage_chat(db: Session, user_id: UUID) -> bool:
    roles = set(get_user_roles_with_role_names(db, user_id))
    return not MANAGE_ROLES.isdisjoint(roles)


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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You do not have permission to manage project chat')
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
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _require_project(db, project_id)
    settings = get_project_chat_settings(db, project_id)
    can_manage = _can_manage_chat(db, current_user.id)
    if settings is None or not settings.enabled:
        return ProjectChatMessageQueryResponse(items=[], total=0, enabled=False, can_manage=can_manage)
    items, total = list_project_chat_messages(
        db,
        project_id=project_id,
        skip=skip,
        limit=limit,
        keyword=keyword,
        sender_user_id=sender_user_id,
        date_from=date_from,
        date_to=date_to,
    )
    return ProjectChatMessageQueryResponse(
        items=[_serialize_message(item) for item in items],
        total=total,
        enabled=True,
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
            mentioned_user_id=payload.mentioned_user_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_message(message)
