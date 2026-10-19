from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from database import get_db
from routers.chat_topics import actor
from chat_session_category_models import ChatSessionCategory, category_now
import chat_session_category_service as service

router = APIRouter(prefix='/chat', tags=['chat_session_categories'])


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)


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
    row = ChatSessionCategory(name=service.validate_name(db, payload.name), updated_by=user.id)
    db.add(row)
    service.commit(db)
    return service.serialize(row)


@router.put('/session-categories/{category_id}')
def update(category_id: UUID, payload: CategoryUpdate, db=Depends(get_db), user=Depends(actor)):
    from fastapi import HTTPException
    service.require_manager(db, user)
    row = service.require_category(db, category_id)
    if row.revision != payload.revision:
        raise HTTPException(409, '分类已被其他人修改，请重新加载后重试')
    if payload.name is not None:
        row.name = service.validate_name(db, payload.name, row.id)
    if payload.active is not None:
        row.active = payload.active
    row.revision += 1
    row.updated_by, row.updated_at = user.id, category_now()
    service.commit(db)
    return service.serialize(row)


@router.put('/sessions/{kind}/{conversation_id}/categories/{category_id}')
def add(kind: str, conversation_id: UUID, category_id: UUID, db=Depends(get_db), user=Depends(actor)):
    return service.set_membership(db, user, kind, conversation_id, category_id, True)


@router.delete('/sessions/{kind}/{conversation_id}/categories/{category_id}')
def remove(kind: str, conversation_id: UUID, category_id: UUID, db=Depends(get_db), user=Depends(actor)):
    return service.set_membership(db, user, kind, conversation_id, category_id, False)


@router.get('/sessions/{kind}/{conversation_id}/categories')
def memberships(kind: str, conversation_id: UUID, db=Depends(get_db), user=Depends(actor)):
    return {'category_ids': service.memberships(db, user, kind, conversation_id)}
