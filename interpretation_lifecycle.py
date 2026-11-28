"""口译合同、译员方向及单价扩展；只使用独立附加表，不改动既有业务表。"""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4,uuid5,NAMESPACE_URL
from sqlalchemy import Column,Uuid,ForeignKey,JSON,Boolean,DateTime,inspect
from models import Base
from annotation_progress_time import business_now,business_datetime,project_progress_datetime

class InterpretationLifecycle(Base):
    __tablename__='interpretation_project_lifecycle'
    project_id=Column(Uuid,ForeignKey('interpretation_project.id',ondelete='CASCADE'),primary_key=True)
    assignment_data=Column(JSON,nullable=False,default=dict)
    date_automation_enabled=Column(Boolean,nullable=False,default=False,index=True)
    activated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)
    notice_keys=Column(JSON,nullable=False,default=list)
    pending_status_ids=Column(JSON,nullable=False,default=list)

CONTRACT_STATUSES={'client_contract_signed','interpreter_contract_signed','both_contracts_signed'}
PREPARATION={'initial_follow_up','candidates_provided','candidates_added','candidates_adjusted','client_selected','client_changed','client_cancelled','client_added','client_reduced','client_mixed','deal_pending_execution',*CONTRACT_STATUSES,'client_interpreter_connected'}

def ready(db):
    key='_interpretation_lifecycle_ready'
    if key not in db.info:db.info[key]=inspect(db.connection()).has_table(InterpretationLifecycle.__tablename__)
    return db.info[key]

def attach(db,projects):
    values={row.project_id:row for row in db.query(InterpretationLifecycle).filter(InterpretationLifecycle.project_id.in_([p.id for p in projects]))} if projects and ready(db) else {}
    from resource_models import ResourcePerson
    from sqlalchemy.orm import selectinload
    ids={row.translator.resource_person_id for project in projects if len(project.language_directions)>1 for row in project.interpreter_assignments if row.translator and row.translator.resource_person_id}
    people={person.id:person for person in db.query(ResourcePerson).options(selectinload(ResourcePerson.language_skills)).filter(ResourcePerson.id.in_(ids))} if ids else {}
    for project in projects:
        extra=values.get(project.id);data=extra.assignment_data if extra else {}
        for assignment in project.interpreter_assignments:
            item=data.get(str(assignment.translator_id),{})
            assignment.cancellation_issues=item.get('cancellation_issues',[]);assignment.contract_path=item.get('contract_path','');assignment.language_ids=item.get('language_ids') or auto_direction(db,assignment.translator,project.language_directions,people);assignment.rates=item.get('rates',[])

def bounds(project):
    starts=[business_datetime(row.scheduled_start) for row in project.time_ranges if row.scheduled_start]
    ends=[business_datetime(row.actual_end or row.scheduled_end) for row in project.time_ranges if row.actual_end or row.scheduled_end]
    return (min(starts) if starts else None,max(ends) if ends else None)

def auto_direction(db,translator,directions,people=None):
    if not directions:return []
    if len(directions)==1:return [str(value) for value in directions[0].language_ids]
    from resource_models import ResourcePerson
    person=(people.get(translator.resource_person_id) if people is not None else db.get(ResourcePerson,translator.resource_person_id)) if translator.resource_person_id else None
    if not person:return []
    native={str(row.language_id) for row in person.language_skills if row.role=='native'}
    foreign=[row for row in person.language_skills if row.role=='foreign']
    first=min((row.priority for row in foreign),default=None)
    languages=native|{str(row.language_id) for row in foreign if row.priority==first}
    matches=[row for row in directions if set(map(str,row.language_ids))<=languages]
    return list(map(str,matches[0].language_ids)) if len(matches)==1 else []

def save_assignments(db,project,payload_items,id_map):
    from fastapi import HTTPException
    if not ready(db):
        if any(getattr(row,'contract_path',None) or getattr(row,'rates',None) or getattr(row,'language_ids',None) for row in payload_items):raise HTTPException(503,'口译合同与译员附加信息表尚未初始化')
        return
    record=db.get(InterpretationLifecycle,project.id)
    if record is None:
        record=InterpretationLifecycle(project_id=project.id,assignment_data={},date_automation_enabled=False,activated_at=business_now(),notice_keys=[],pending_status_ids=[]);db.add(record)
    from models import Translator
    data={key:{'cancellation_issues':deepcopy(value['cancellation_issues'])} for key,value in (record.assignment_data or {}).items() if value.get('cancellation_issues')}
    for item in payload_items:
        key=str(id_map[item.translator_id]);before=(record.assignment_data or {}).get(key,{})
        fields=item.model_fields_set;details=deepcopy(before)
        if 'contract_path' in fields:details['contract_path']=(item.contract_path or '').strip()
        if 'rates' in fields and item.rates is not None:details['rates']=[rate.model_dump(mode='json') for rate in item.rates]
        directions=[[str(value) for value in row.language_ids] for row in project.language_directions]
        chosen=[str(value) for value in item.language_ids] if item.language_ids is not None else details.get('language_ids',[])
        if not chosen:chosen=auto_direction(db,db.get(Translator,id_map[item.translator_id]),project.language_directions)
        if chosen and chosen not in directions:raise HTTPException(422,'译员口译方向必须从当前项目方向中选择')
        details['language_ids']=chosen
        allowed={row.display for row in project.language_directions if list(map(str,row.language_ids))==chosen}
        if any(rate.get('direction') not in allowed for rate in details.get('rates',[])):raise HTTPException(422,'译员组合单价必须使用已选择的口译方向')
        data[key]=details
    record.assignment_data=data
    _,end=bounds(project)
    record.date_automation_enabled=bool(record.date_automation_enabled or end and end>=business_now())

def contract_signature(project):
    rows=list(project.interpreter_assignments)
    selected=[row for row in rows if getattr(row,'client_selected',False)]
    relevant=selected or rows
    return (bool((project.contract_path or '').strip()),bool(relevant) and all(bool((getattr(row,'contract_path','') or '').strip()) for row in relevant))

def apply_contract_status(project,before,force=False):
    after=contract_signature(project)
    if (before==after and not force) or project.project_status not in PREPARATION:return None
    if all(after):status='both_contracts_signed'
    elif after[0]:status='client_contract_signed'
    elif after[1]:status='interpreter_contract_signed'
    else:status='client_selected' if any(getattr(row,'client_selected',False) for row in project.interpreter_assignments) else 'candidates_provided' if project.interpreter_assignments else 'initial_follow_up'
    project.project_status=status
    return {'both_contracts_signed':'客户合同及全部相关译员合同路径已填写','client_contract_signed':'客户合同路径已填写','interpreter_contract_signed':'全部相关译员合同路径已填写'}.get(status,'合同路径已清除，请重新核对签署情况')

def recipients(db,project):
    from project_client_manager import attach as managers
    from models import AppUser
    managers(db,'interpretation',[project]);people=db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    manager=getattr(project,'client_manager_id',None)
    if not manager:
        name=project.current_client_manager
        manager=next((p.id for p in people if name and name in {p.full_name,p.username}),None)
    from interpretation_settings import mention_ids
    return manager,[person.id for person in people if str(person.id) in mention_ids(db,people)]

def notify(db,project,user_ids,key,content):
    from models import AppNotification
    from automatic_project_notice import mark_automatic
    result=[]
    for uid in set(user_ids)-{None}:
        identifier=uuid5(NAMESPACE_URL,f'interpretation-lifecycle:{project.id}:{key}:{uid}')
        if db.get(AppNotification,identifier):continue
        note=AppNotification(id=identifier,recipient_user_id=uid,title=f'{project.order_no} · 口译项目提醒',content=mark_automatic(content),notification_type='interpretation_lifecycle',related_project_type='interpretation',related_entity_id=project.id,is_read=False,created_at=project_progress_datetime(business_now()))
        db.add(note);result.append(note)
    return result

def notify_contracts(db,project,previous_selected,current_selected,token):
    if previous_selected==current_selected:return []
    manager,pms=recipients(db,project)
    if not current_selected:
        return notify(db,project,[manager],str(token)+':cancel-customer','客户已取消全部选定人选，请核对客户合同的修改/解除，并更新客户合同路径。')+notify(db,project,pms,str(token)+':cancel-interpreters','客户已取消人选，请核对译员合同的修改/解除，并更新相关译员合同路径。')
    changed=bool(previous_selected)
    verb='签署/修改' if changed else '签署'
    notes=notify(db,project,[manager],str(token)+':customer',f'客户已调整人选，请{verb}客户合同，并填写客户合同路径。' if changed else '客户已选定人选，请签署客户合同，并填写客户合同路径。')
    notes+=notify(db,project,pms,str(token)+':interpreters',f'请{verb}译员合同，并在各译员下填写译员合同路径。')
    return notes

def worker_once():
    from sqlalchemy.orm import Session
    from database import engine
    from interpretation_models import InterpretationProject,InterpretationProjectStatusHistory
    from models import AppUser
    from project_chat_crud import _push_notifications
    with Session(engine) as db:
        if not ready(db):return
        if engine.dialect.name=='postgresql':
            from sqlalchemy import text
            if not db.execute(text('SELECT pg_try_advisory_xact_lock(261128071)')).scalar():return
        records=db.query(InterpretationLifecycle).filter_by(date_automation_enabled=True).all()
        notices=[];events=[];now=business_now()
        for record in records:
            project=db.get(InterpretationProject,record.project_id)
            if not project or project.project_status in {'cancelled','partially_cancelled','settled'}:continue
            start,end=bounds(project)
            if not start or not end:continue
            attach(db,[project]);from interpretation_client_selection import attach as selection
            selection(db,[project]);manager,pms=recipients(db,project)
            eligible=project.project_status in {'deal_pending_execution',*CONTRACT_STATUSES,'client_interpreter_connected','in_progress'} or any(getattr(row,'client_selected',False) for row in project.interpreter_assignments)
            target='ended' if eligible and now>=end else 'in_progress' if eligible and now>=start else None
            if target and project.project_status!=target and project.project_status!='ended':
                event=InterpretationProjectStatusHistory(id=uuid4(),project_id=project.id,from_status=project.project_status,to_status=target,effective_on=project_progress_datetime(end if target=='ended' else start),changed_at=project_progress_datetime(now),change_note='项目结束时间已到，自动调整为已结束' if target=='ended' else '项目开始时间已到，自动调整为进行中')
                project.project_status=target;project.updated_at=project_progress_datetime(now);db.add(event);events.append((project.id,event.id,project.created_by or manager));record.pending_status_ids=[*(record.pending_status_ids or []),str(event.id)]
                notices+=notify(db,project,[manager,*pms],str(event.id),event.change_note+'；请保持跟进、收集客户反馈并核对结款。')
            if now.hour<9:continue
            slot='evening' if now.hour>=18 else 'afternoon' if now.hour>=14 else 'morning'
            from work_report_calendar import is_workday
            from fastapi import HTTPException
            before=start.date()-timedelta(days=1)
            try:
                while not is_workday(before):before-=timedelta(days=1)
            except HTTPException:before=None
            after=end.date();remaining=2
            try:
                while remaining:
                    after+=timedelta(days=1)
                    if is_workday(after):remaining-=1
            except HTTPException:after=None
            if before is None or after is None:
                notices+=notify(db,project,[manager],f'calendar:{start.year}:{end.year}',f'部分项目跟进提醒需要配置{start.year}年至{end.year}年的节假日调休日历，请先人工跟进；已知日期提醒及按具体时间自动切换状态不受影响。')
            message=None
            if now.date()==before:message='项目将开始，请向客户及译员再次确认时间、地点、项目资料和联系方式。'
            elif start.date()<=now.date()<=end.date():message='项目已标记结束，请收集客户反馈并核对结款。' if project.project_status=='ended' else '项目已到执行日期，请核对进行中状态并保持跟进。'
            elif now.date()==after:message='请核对项目已结束，收集客户反馈并跟进结款。'
            if message:
                key=f'{now.date()}:{slot}:{start.isoformat()}:{end.isoformat()}'
                if key not in (record.notice_keys or []):
                    from interpretation_client_selection import InterpretationClientSelectedInterpreter,ready as selection_ready
                    selected_at=db.query(InterpretationClientSelectedInterpreter.selected_at).filter_by(project_id=project.id).order_by(InterpretationClientSelectedInterpreter.selected_at).first() if selection_ready(db) else None
                    if selected_at and start-business_datetime(selected_at[0])>timedelta(days=7):message+=' 客户确定人选距项目开始超过一周，请特别提醒客户和译员本项目信息。'
                    notices+=notify(db,project,[manager],key,message);record.notice_keys=[*(record.notice_keys or [])[-100:],key]
        db.commit()
        if notices:_push_notifications(notices)
        from project_delivery import send
        import logging
        for record in records:
            project=db.get(InterpretationProject,record.project_id)
            if not project:continue
            manager,_=recipients(db,project)
            actor=db.get(AppUser,project.created_by or manager) if project.created_by or manager else None
            if not actor:continue
            for event_id in list(record.pending_status_ids or []):
                try:
                    from uuid import UUID
                    send(db,actor,'interpretation',project.id,uuid5(NAMESPACE_URL,f'interpretation-lifecycle-status:{event_id}'),status_change_id=UUID(event_id))
                    record.pending_status_ids=[value for value in record.pending_status_ids if value!=event_id];db.commit()
                except Exception:
                    db.rollback();logging.getLogger(__name__).exception('口译自动状态会话发送失败，下一轮重试')
