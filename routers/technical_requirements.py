from uuid import UUID
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,Field,ConfigDict
from database import get_db
from routers.auth import get_current_user
import technical_requirements as service

router=APIRouter(prefix='/chat/technical',tags=['technical_requirements'])


class OpenRoom(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_ids:list[UUID]=Field(default_factory=list,max_length=2000)


class DocumentWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    content:str=Field(max_length=100000)
    revision:int=Field(ge=1)


class AppendWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message_id:int=Field(ge=1)
    request_id:UUID


@router.post('/projects/{project_id}/room')
def open_room(project_id:UUID,payload:OpenRoom,db=Depends(get_db),user=Depends(get_current_user)):
    return service.open_room(db,user,project_id,payload.user_ids)


@router.get('/rooms')
def listing(keyword:str=Query('',max_length=200),offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user)):
    if not service.ready(db):return dict(items=[],total=0)
    from technical_requirement_models import TechnicalRoom
    from annotation_models import AnnotationProject
    from discussion_chat_models import DiscussionMember
    from sqlalchemy import func
    from search_matching import keyword_contains
    query=db.query(TechnicalRoom).join(AnnotationProject,AnnotationProject.id==TechnicalRoom.project_id).join(DiscussionMember,DiscussionMember.room_id==TechnicalRoom.room_id).filter(DiscussionMember.user_id==user.id)
    if keyword.strip():query=query.filter(keyword_contains(func.coalesce(AnnotationProject.order_no,'')+' '+func.coalesce(AnnotationProject.project_name,'')+' '+TechnicalRoom.requirements,keyword))
    total=query.count()
    return dict(items=[service.serialize(db,row) for row in query.order_by(TechnicalRoom.updated_at.desc(),TechnicalRoom.project_id).offset(offset).limit(limit)],total=total)


@router.get('/rooms/{room_id}')
def detail(room_id:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    if not service.ready(db):return dict(enabled=False)
    from technical_requirement_models import TechnicalRoom
    if not db.query(TechnicalRoom).filter_by(room_id=room_id).first():return dict(enabled=False)
    return dict(service.serialize(db,service.get_room(db,user,room_id)),enabled=True)


@router.put('/rooms/{room_id}')
def save(room_id:UUID,payload:DocumentWrite,db=Depends(get_db),user=Depends(get_current_user)):
    return service.save(db,user,room_id,payload.content,payload.revision)


@router.post('/rooms/{room_id}/append')
def append(room_id:UUID,payload:AppendWrite,db=Depends(get_db),user=Depends(get_current_user)):
    return service.append(db,user,room_id,payload.message_id,payload.request_id)
