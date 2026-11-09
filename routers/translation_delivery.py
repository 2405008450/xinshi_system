from uuid import UUID
from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field
from database import get_db
from routers.auth import get_current_user,require_any_permission
import translation_chat_delivery as service

router=APIRouter(prefix='/translation-delivery',tags=['translation_delivery'])


class SettingsWrite(BaseModel):
    revision:int=Field(ge=0)
    weekday_user_id:UUID|None=None
    leave_backup_user_id:UUID|None=None
    sunday_user_ids:list[UUID]=Field(default_factory=list,max_length=100)
    extra_audience:list[str]=Field(default_factory=list,max_length=1000)
    participant_audience:list[str]=Field(default_factory=lambda:['all'],max_length=1000)


class ChatSend(BaseModel):
    request_key:UUID
    extra_audience:list[str]=Field(default_factory=list,max_length=1000)
    mail_id:UUID|None=None


@router.get('/settings')
def settings(db=Depends(get_db),user=Depends(get_current_user)):
    return service.catalog(db,user)


@router.put('/settings')
def save(payload:SettingsWrite,db=Depends(get_db),user=Depends(get_current_user)):
    return service.save_settings(db,user,payload)


@router.get('/{project_id}/counts',dependencies=[Depends(require_any_permission('projects:read','projects:write'))])
def counts(project_id:UUID,db=Depends(get_db)):
    return service.counts(db,project_id)


@router.post('/{project_id}/chat',dependencies=[Depends(require_any_permission('projects:write'))])
def send(project_id:UUID,payload:ChatSend,db=Depends(get_db),user=Depends(get_current_user)):
    try:return service.send(db,user,project_id,payload.request_key,payload.extra_audience,payload.mail_id)
    except Exception:
        db.rollback();raise
