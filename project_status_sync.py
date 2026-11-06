"""项目状态轻量同步：仅在事务提交后推送，不创建消息通知或业务表。"""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import event,inspect
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import require_permission

router=APIRouter(prefix='/project-status-sync',tags=['项目状态同步'])
KEY='project_status_sync_changes'

def models():
    from models import TranslationProject,TranslationSubOrder
    from interpretation_models import InterpretationProject
    from annotation_models import AnnotationProject
    from recruitment_models import RecruitmentProject
    return {'translation':(TranslationProject,'project_status'),'translation_suborder':(TranslationSubOrder,'status'),'interpretation':(InterpretationProject,'project_status'),'annotation':(AnnotationProject,'project_status'),'recruitment':(RecruitmentProject,'project_status')}

class WatchItem(BaseModel):
    model_config=ConfigDict(extra='forbid')
    projectType:str
    id:UUID

class SnapshotRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    items:list[WatchItem]=Field(max_length=2000)

def snapshot(db,items):
    catalog=models();result=[]
    for kind in {item.projectType for item in items}:
        if kind not in catalog:raise HTTPException(422,'项目类型无效')
        model,field=catalog[kind];ids={item.id for item in items if item.projectType==kind}
        result.extend({'projectType':kind,'id':str(id),'status':value or ''} for id,value in db.query(model.id,getattr(model,field)).filter(model.id.in_(ids)).all())
    return result

@router.post('/snapshot',dependencies=[Depends(require_permission('projects:read'))])
def read_snapshot(data:SnapshotRequest,db:Session=Depends(get_db)):
    return {'items':snapshot(db,data.items)}

def capture(session,flush_context,instances):
    catalog=models()
    for row in session.dirty:
        for kind,(model,field) in catalog.items():
            if isinstance(row,model) and inspect(row).attrs[field].history.has_changes():
                session.info.setdefault(KEY,{})[(kind,str(row.id))]={'projectType':kind,'id':str(row.id),'status':getattr(row,field) or ''}
                break

def committed(session):
    if session.in_nested_transaction():return
    items=list(session.info.pop(KEY,{}).values())
    if items:
        from notification_ws import dispatch_project_status
        dispatch_project_status(items)

def rolled_back(session):session.info.pop(KEY,None)

event.listen(Session,'before_flush',capture)
event.listen(Session,'after_commit',committed)
event.listen(Session,'after_rollback',rolled_back)
