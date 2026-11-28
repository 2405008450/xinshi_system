"""口译三个进度轨道共用既有状态历史；进度与会话发送在同一事务保存。"""
from datetime import datetime
from typing import Literal
from uuid import UUID,uuid5,NAMESPACE_URL
from pydantic import BaseModel,Field,field_validator
from fastapi import HTTPException
from annotation_progress_time import business_now,business_datetime,project_progress_datetime
from interpretation_models import InterpretationProject,InterpretationProjectStatusHistory
from interpretation_partial_cancellation import CancellationDetails

LABELS={'project':'项目进度','customer':'客户进度','interpreter':'译员情况'}
PREFIXES={'customer':'【客户进度】\n','interpreter':'【译员情况】\n'}

class ProgressWrite(BaseModel):
    track:Literal['project','customer','interpreter']='project'
    project_status:str|None=None
    change_note:str=Field(min_length=1,max_length=9500)
    effective_on:datetime
    expected_updated_at:datetime|None=None
    cancellation_details:CancellationDetails|None=None
    request_key:UUID
    send_to_chat:bool=True
    user_ids:list[UUID]|None=Field(default=None,max_length=20)
    @field_validator('change_note')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('请填写具体进度')
        return value.strip()

def project(db,project_id):
    value=db.get(InterpretationProject,project_id)
    if not value:raise HTTPException(404,'口译项目不存在')
    return value

def audience(db,item,actor):
    from interpretation_lifecycle import recipients
    from workflow_models import ProjectWorkbenchResponsibility as Role
    from models import AppUser
    manager,defaults=recipients(db,item)
    ids={manager}
    assigned={row.assignee_id for row in db.query(Role).filter(Role.interpretation_project_id==item.id,Role.role_code=='project_manager') if row.assignee_id}
    ids.update(assigned)
    for value in defaults:
        if len(assigned)>=2:break
        assigned.add(value);ids.add(value)
    return db.query(AppUser).filter(AppUser.id.in_(ids-{None,actor.id}),AppUser.is_active.is_(True)).all()

def context(db,project_id,actor):
    item=project(db,project_id)
    from project_statistics import INTERPRETATION_STATUSES
    allowed={'initial_follow_up','client_interpreter_connected','deal_pending_execution','in_progress','cancelled','partially_cancelled','ended','settled',item.project_status}
    allowed.update(value for value, in db.query(InterpretationProjectStatusHistory.to_status).filter_by(project_id=project_id))
    return dict(users=[dict(id=str(row.id),name=row.full_name or row.username) for row in audience(db,item,actor)],statuses=[dict(value=value,label=label) for value,label in INTERPRETATION_STATUSES.items() if value in allowed and value])

def track_of(note):
    return next((key for key,prefix in PREFIXES.items() if (note or '').startswith(prefix)),'project')

def history(db,project_id,track):
    from models import AppUser
    project(db,project_id)
    rows=db.query(InterpretationProjectStatusHistory).filter_by(project_id=project_id).order_by(InterpretationProjectStatusHistory.effective_on.desc()).all()
    names={row.id:row.full_name or row.username for row in db.query(AppUser).filter(AppUser.id.in_({row.changed_by for row in rows if row.changed_by}))}
    return [dict(id=str(row.id),toStatus=row.to_status,effectiveOn=business_datetime(row.effective_on or row.changed_at or business_now()).isoformat(),changedAt=business_datetime(row.changed_at or row.effective_on or business_now()).isoformat(),changeNote=(row.change_note or '').removeprefix(PREFIXES.get(track,'\0')),changedByName=names.get(row.changed_by,'系统')) for row in rows if track_of(row.change_note)==track]

def save(db,project_id,payload,actor):
    item=db.query(InterpretationProject).filter_by(id=project_id).with_for_update().populate_existing().one_or_none()
    if not item:raise HTTPException(404,'口译项目不存在')
    identifier=uuid5(NAMESPACE_URL,f'interpretation-progress:{project_id}:{payload.request_key}')
    note=PREFIXES.get(payload.track,'')+payload.change_note
    previous=db.get(InterpretationProjectStatusHistory,identifier)
    if previous:
        expected=note
        if payload.cancellation_details:
            from interpretation_partial_cancellation import prepare_cancellation
            expected=prepare_cancellation(db,item,previous.to_status,payload.cancellation_details,note)
        if previous.changed_by!=actor.id or previous.change_note!=expected:raise HTTPException(409,'提交标识已用于其他进度，请重新打开窗口')
        return dict(saved=True)
    if payload.expected_updated_at is not None:
        from concurrency import assert_fresh
        assert_fresh(item,payload.expected_updated_at)
    previous_status=item.project_status
    if payload.track=='project':
        from interpretation_service import update_interpretation_project_status
        from interpretation_schemas import InterpretationProjectStatusUpdate
        status=InterpretationProjectStatusUpdate(project_status=payload.project_status or item.project_status).project_status
        update_interpretation_project_status(db,project_id,status,payload.effective_on,note,actor.id,False,cancellation_details=payload.cancellation_details,commit=False,status_event_id=identifier)
    else:
        event=InterpretationProjectStatusHistory(id=identifier,project_id=project_id,from_status=item.project_status,to_status=item.project_status,effective_on=project_progress_datetime(payload.effective_on),changed_at=project_progress_datetime(business_now()),change_note=note,changed_by=actor.id)
        db.add(event);item.updated_at=project_progress_datetime(business_now())
    db.flush()
    if payload.send_to_chat:
        from project_delivery import send,ProjectChatDispatch
        permitted={row.id for row in audience(db,item,actor)}
        targets=set(payload.user_ids) if payload.user_ids is not None else permitted
        if targets-permitted:raise HTTPException(422,'只能选择该项目的客户经理及项目经理')
        body=payload.change_note
        if payload.track=='project' and previous_status!=item.project_status:
            from project_statistics import INTERPRETATION_STATUSES
            body='项目状态：'+INTERPRETATION_STATUSES.get(item.project_status,item.project_status)+'\n变更原因：'+payload.change_note
        send(db,actor,'interpretation',project_id,payload.request_key,progress_notice=(item.order_no+' · '+LABELS[payload.track],body),mention_override=targets)
    else:db.commit()
    return dict(saved=True)
