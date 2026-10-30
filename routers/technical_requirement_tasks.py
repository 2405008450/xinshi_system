from uuid import UUID
from fastapi import APIRouter, Depends
from database import get_db
from routers.auth import get_current_user
import technical_requirement_tasks as service
router = APIRouter(prefix='/technical-development/requirements', tags=['technical_requirement_tasks'])


@router.get('/{room_id}')
def context(room_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return service.context(db, user, room_id)


@router.post('/{room_id}')
def save(room_id: UUID, payload: service.SourceWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.save(db, user, room_id, payload)
