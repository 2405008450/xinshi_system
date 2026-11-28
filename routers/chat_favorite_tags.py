from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from database import get_db
from routers.auth import get_current_user
import chat_favorite_tags as service

router=APIRouter(prefix='/chat/favorite-tags',tags=['chat'])
Kind=Literal['annotation','translation','direct','discussion']

class TagCreate(BaseModel):
    name:str=Field(min_length=1,max_length=60)

class TagSelection(BaseModel):
    tag_ids:list[UUID]=Field(max_length=20)

def actor(user=Depends(get_current_user)):
    if not user.is_active or getattr(user,'is_deleted',False):raise HTTPException(403,'账号已停用')
    return user

@router.get('')
def catalog(db=Depends(get_db),user=Depends(actor)):return dict(items=service.catalog(db))

@router.post('')
def create(payload:TagCreate,db=Depends(get_db),user=Depends(actor)):return service.create(db,user,payload.name)

@router.get('/{kind}/{conversation_id}/{message_id}')
def read(kind:Kind,conversation_id:UUID,message_id:str,db=Depends(get_db),user=Depends(actor)):
    return service.message_tags(db,user,kind,conversation_id,message_id)

@router.put('/{kind}/{conversation_id}/{message_id}')
def write(kind:Kind,conversation_id:UUID,message_id:str,payload:TagSelection,db=Depends(get_db),user=Depends(actor)):
    return service.message_tags(db,user,kind,conversation_id,message_id,payload.tag_ids)
