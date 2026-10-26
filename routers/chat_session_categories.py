from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from database import get_db
from routers.chat_topics import actor
from chat_session_category_models import ChatSessionCategory, category_now
import chat_session_category_service as service

router = APIRouter(prefix='/chat', tags=['chat_session_categories'])


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    parent_key: UUID | None = None
    conversation: bool = False
    directory: bool = False


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None


@router.get('/session-categories')
def catalog(db=Depends(get_db), user=Depends(actor)):
    return service.catalog(db, user)


@router.post('/session-categories', status_code=201)
def create(payload: CategoryCreate, db=Depends(get_db), user=Depends(actor)):
    service.require_manager(db, user)
    if payload.directory and payload.conversation:
        from fastapi import HTTPException
        raise HTTPException(422, '二级菜单和会话不能同时创建')
    parent_key = service.validate_parent(db, payload.parent_key, conversation=payload.conversation)
    from discussion_chat_service import ANNOTATION_ROOT
    is_conversation = bool(not payload.directory and (payload.conversation or parent_key and str(parent_key) != ANNOTATION_ROOT))
    row = ChatSessionCategory(name=service.validate_name(db, payload.name, parent_key=parent_key), updated_by=user.id)
    db.add(row)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(409, '已有同名目录，请重新检查名称') from error
    if parent_key:
        db.add(service.Folder(category_id=row.id, parent_key=parent_key))
    if is_conversation:
        from discussion_chat_service import schema_ready
        if not schema_ready(db):
            from fastapi import HTTPException
            raise HTTPException(503, '会话参与人配置尚未就绪')
        from discussion_chat_models import DiscussionMember
        db.add(DiscussionMember(room_id=row.id, user_id=user.id, last_read_id=0, pinned=False, starred=False))
    service.commit(db)
    return dict(service.serialize(row), parent_key=parent_key,
                is_conversation=is_conversation)


@router.put('/session-categories/{category_id}')
def update(category_id: UUID, payload: CategoryUpdate, db=Depends(get_db), user=Depends(actor)):
    from fastapi import HTTPException
    service.require_manager(db, user)
    row = service.require_category(db, category_id)
    service.protect_resource_discussion(db, category_id, payload.active)
    if str(row.id) in service.BUILTIN_INDEX:
        from fastapi import HTTPException
        raise HTTPException(422, '内置目录不可修改')
    if row.revision != payload.revision:
        raise HTTPException(409, '分类已被其他人修改，请重新加载后重试')
    if payload.name is not None:
        location = db.get(service.Folder, row.id) if service.folder_schema_ready(db) else None
        row.name = service.validate_name(db, payload.name, row.id, location.parent_key if location else None)
    if payload.active is not None:
        row.active = payload.active
    row.revision += 1
    row.updated_by, row.updated_at = user.id, category_now()
    service.commit(db)
    location = db.get(service.Folder, row.id) if service.folder_schema_ready(db) else None
    return dict(service.serialize(row), parent_key=location.parent_key if location else None)


@router.put('/sessions/{kind}/{conversation_id}/categories/{category_id}')
def add(kind: str, conversation_id: UUID, category_id: UUID, db=Depends(get_db), user=Depends(actor)):
    return service.set_membership(db, user, kind, conversation_id, category_id, True)


@router.delete('/sessions/{kind}/{conversation_id}/categories/{category_id}')
def remove(kind: str, conversation_id: UUID, category_id: UUID, db=Depends(get_db), user=Depends(actor)):
    return service.set_membership(db, user, kind, conversation_id, category_id, False)


@router.get('/sessions/{kind}/{conversation_id}/categories')
def memberships(kind: str, conversation_id: UUID, db=Depends(get_db), user=Depends(actor)):
    return {'category_ids': service.memberships(db, user, kind, conversation_id)}
