from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser
from routers.auth import get_current_user
import chat_message_interactions as service

router = APIRouter(prefix='/conversations/{kind}/{conversation_id}')


class MessageBatch(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=100)


@router.post('/message-stats')
def message_stats(kind: str, conversation_id: UUID, payload: MessageBatch, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.stats(db, kind, conversation_id, user, payload.message_ids)


@router.post('/message-views')
def message_views(kind: str, conversation_id: UUID, payload: MessageBatch, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.mark_views(db, kind, conversation_id, user, payload.message_ids)


@router.get('/messages/{message_id}/references')
def message_references(kind: str, conversation_id: UUID, message_id: str, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=50), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.references(db, kind, conversation_id, user, message_id, offset, limit)
