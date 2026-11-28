"""项目操作中的创建／进入会话；已有会话不会重复发送项目通知。"""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db
from routers.auth import get_current_user, require_any_permission
from business_mail_service import PROJECT_MODELS
from chat_session_category_models import ChatSessionCategory
from discussion_chat_models import DiscussionMember
from permission_service import user_has_permission

router=APIRouter(prefix='/chat/project-entry',tags=['项目会话'])
Module=Literal['translation','interpretation','recruitment']

class CreateRequest(BaseModel):
    request_key: UUID

def project_and_room(db,module,pid):
    project=db.get(PROJECT_MODELS[module],pid)
    if not project: raise HTTPException(404,'项目不存在')
    if module=='translation':
        from translation_chat_delivery import TranslationProjectConversation
        query=db.query(ChatSessionCategory).join(TranslationProjectConversation,TranslationProjectConversation.room_id==ChatSessionCategory.id).filter(TranslationProjectConversation.project_id==pid).order_by(TranslationProjectConversation.day)
    else:
        from project_delivery import ProjectChatDispatch
        query=db.query(ChatSessionCategory).join(ProjectChatDispatch,ProjectChatDispatch.room_id==ChatSessionCategory.id).filter(ProjectChatDispatch.module==module,ProjectChatDispatch.project_id==pid).order_by(ProjectChatDispatch.created_at)
    room=query.filter(ChatSessionCategory.active.is_(True)).first()
    return project,room

def native_enabled(db,module,project):
    if module!='translation':return False
    from models import ChatProjectEnabled
    return db.query(ChatProjectEnabled.id).filter_by(project_id=project.id,enabled=True).first() is not None

def result(db,user,project,room,module=None):
    if not room and native_enabled(db,module,project):
        from models import ChatProjectMemberPref
        joined=bool(db.get(ChatProjectMemberPref,(project.id,user.id)))
        target=dict(key=f'translation:{project.id}',projectId=str(project.id),projectType='translation',title=project.project_name,subtitle=project.order_no) if joined else None
        return dict(created=True,joined=joined,canCreate=user_has_permission(db,user.id,'projects:write'),target=target)

    joined=bool(room and db.get(DiscussionMember,(room.id,user.id)))
    target=dict(key=f'discussion:{room.id}',projectId=str(room.id),projectType='discussion',title=room.name,subtitle=project.order_no) if joined else None
    return dict(created=bool(room),joined=joined,canCreate=user_has_permission(db,user.id,'projects:write'),target=target)

@router.get('/{module}/{project_id}',dependencies=[Depends(require_any_permission('projects:read','projects:write'))])
def status(module:Module,project_id:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    project,room=project_and_room(db,module,project_id)
    return result(db,user,project,room,module)

@router.post('/{module}/{project_id}',dependencies=[Depends(require_any_permission('projects:write'))])
def create(module:Module,project_id:UUID,payload:CreateRequest,db=Depends(get_db),user=Depends(get_current_user)):
    try:
        # 锁定同一项目，二次检查避免并发点击重复发出项目概览。
        db.query(PROJECT_MODELS[module]).filter(PROJECT_MODELS[module].id==project_id).with_for_update().first()
        project,room=project_and_room(db,module,project_id)
        if not room and native_enabled(db,module,project):
            from models import ChatProjectMemberPref
            if not db.get(ChatProjectMemberPref,(project.id,user.id)):
                db.add(ChatProjectMemberPref(project_id=project.id,user_id=user.id,last_read_sequence=0,pinned=False,starred=False))
            db.commit()
            return result(db,user,project,room,module)
        if not room:
            if module=='translation':
                from translation_chat_delivery import send
                sent=send(db,user,project_id,payload.request_key)
            else:
                from project_delivery import send
                sent=send(db,user,module,project_id,payload.request_key)
            room=db.get(ChatSessionCategory,UUID(sent['room_id']))
        if not db.get(DiscussionMember,(room.id,user.id)):
            db.add(DiscussionMember(room_id=room.id,user_id=user.id,last_read_id=0,pinned=False,starred=False))
        db.commit()
        return result(db,user,project,room,module)
    except Exception:
        db.rollback();raise
