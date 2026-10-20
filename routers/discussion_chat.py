from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from database import get_db
from routers.chat_topics import actor
import discussion_chat_service as service

router = APIRouter(prefix='/chat/discussions', tags=['discussion_chat'])


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=10000)
    client_message_id: UUID
    reply_to_id: int | None = Field(default=None, ge=1)


class PreferenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pinned: bool | None = None
    starred: bool | None = None
    mark_read: bool = False
    read_message_id: int | None = Field(default=None, ge=1)


@router.get('/{room_id}/messages')
def messages(room_id: UUID, before: int | None = Query(None, ge=1), after: int | None = Query(None, ge=1),
             limit: int = Query(50, ge=1, le=100), keyword: str = Query('', max_length=200), db=Depends(get_db), user=Depends(actor)):
    if before is not None and after is not None:
        raise HTTPException(422, '不能同时指定向前和向后翻页')
    return service.messages(db, user, room_id, before, after, limit, keyword)


@router.post('/{room_id}/messages', status_code=201)
def send(room_id: UUID, payload: MessageCreate, db=Depends(get_db), user=Depends(actor)):
    return service.send(db, user, room_id, payload)


@router.put('/{room_id}/preferences')
def preferences(room_id: UUID, payload: PreferenceWrite, db=Depends(get_db), user=Depends(actor)):
    return service.preferences(db, user, room_id, payload)


@router.put('/{room_id}/messages/{message_id}/recall')
def recall(room_id: UUID, message_id: int, db=Depends(get_db), user=Depends(actor)):
    service.require_room(db, user, room_id)
    row = db.query(service.Message).filter_by(id=message_id, room_id=room_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '消息不存在')
    if row.recalled_at:
        return service.serialize(db, row, user)
    if not service.serialize(db, row, user)['can_recall']:
        raise HTTPException(403, '仅本人可在24小时内撤回，或由超级管理员处理')
    row.recalled_at = service.category_now()
    db.commit(); service.publish(db)
    return service.serialize(db, row, user)
