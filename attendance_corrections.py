"""补卡申请、行政确认及跨日签退的后续上班基准；所有过程留记录。"""
from datetime import date,datetime,timedelta
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,StrictBool,ConfigDict,field_validator,model_validator
from sqlalchemy import Uuid,Date,DateTime,String,Text,JSON,ForeignKey,Integer,Index,inspect,or_
from sqlalchemy.orm import Mapped,mapped_column
from models import Base,AppUser,AppNotification
from attendance_models import AttendanceClockSession as Clock
from database import get_db
from routers.auth import get_current_user
from chat_time import now,api_time
from hr_access import require_hr


class ClockCorrection(Base):
    __tablename__='attendance_clock_correction'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    day:Mapped[date]=mapped_column(Date,nullable=False)
    kind:Mapped[str]=mapped_column(String(10),nullable=False)
    record_id:Mapped[UUID|None]=mapped_column(Uuid,ForeignKey('attendance_clock_session.id'))
    segment:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    requested_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    evidence:Mapped[str]=mapped_column(Text,nullable=False,default='')
    declarations:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    status:Mapped[str]=mapped_column(String(20),nullable=False,default='pending')
    original:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    history:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    confirmed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    confirmed_by:Mapped[UUID|None]=mapped_column(Uuid,ForeignKey('app_user.id'))
    __table_args__=(Index('ix_clock_correction_user_day','user_id','day'),)


class AttendanceStartAdjustment(Base):
    __tablename__='attendance_start_adjustment'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    source_clock_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('attendance_clock_session.id'),unique=True,nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    day:Mapped[date]=mapped_column(Date,nullable=False)
    segment:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    next_start:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    history:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    __table_args__=(Index('ix_attendance_start_adjustment_user_day','user_id','day'),)


class CorrectionWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_id:UUID
    day:date
    kind:Literal['in','out']
    record_id:UUID|None=None
    segment:int=Field(default=0,ge=0)
    requested_at:datetime
    reason:str=Field(min_length=1,max_length=2000)
    evidence:str=Field(default='',max_length=16000)
    early_work_confirmed:StrictBool
    breakfast_after_eating:StrictBool
    dinner_eaten:StrictBool|None=None
    deduct_invalid_time:StrictBool|None=None
    invalid_minutes:float=Field(default=0,ge=0,le=1440,allow_inf_nan=False)
    invalid_reason:str=Field(default='',max_length=500)
    cross_day_reason:str=Field(default='',max_length=2000)
    next_start:datetime|None=None
    @model_validator(mode='after')
    def require_next_start(self):
        if self.kind=='out' and self.next_start is None:raise ValueError('补下班打卡须填写下次/第二天上班时间')
        if self.next_start is not None:
            if self.next_start.tzinfo is None:raise ValueError('后续上班时间须包含时区')
            self.next_start=api_time(self.next_start)
            if self.next_start<=self.requested_at:raise ValueError('后续上班时间须晚于补填下班时间')
        return self
    @field_validator('reason')
    @classmethod
    def reason_required(cls,value):
        if not value.strip():raise ValueError('请向行政部说明补卡原因')
        return value.strip()
    @field_validator('requested_at')
    @classmethod
    def local(cls,value):
        if value.tzinfo is None:raise ValueError('补卡时间须携带时区')
        return api_time(value)


def ready(db):return inspect(db.connection()).has_table(ClockCorrection.__tablename__)
def adjustments_ready(db):return inspect(db.connection()).has_table(AttendanceStartAdjustment.__tablename__)
def require_ready(db):
    if not ready(db):raise HTTPException(503,'补卡记录表尚未初始化')


def clock_state(row):
    return jsonable_encoder({'id':row.id,'check_in':api_time(row.check_in),'check_out':api_time(row.check_out) if row.check_out else None,'shift':row.shift_snapshot,'confirmations':getattr(row,'confirmations',{})}) if row else {}


def notify(db,person,entity_id,title,content,owner_only=False):
    from organization_service import department_condition
    recipients=[person] if owner_only else db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False),department_condition(db,['行政部','行政部门'])).all()
    if not recipients:raise HTTPException(503,'行政部没有在用人员，记录尚未提交')
    events=[];moment=now()
    for target in recipients:
        notice=AppNotification(id=uuid4(),recipient_user_id=target.id,title=title,content=content,notification_type='attendance_clock_correction',related_entity_id=entity_id,is_read=False,created_at=moment.replace(tzinfo=None));db.add(notice)
        events.append((target.id,{'type':'attendance_clock_changed'}))
        events.append((target.id,{'type':'notification','notification':jsonable_encoder({'id':notice.id,'title':title,'content':content,'notification_type':notice.notification_type,'related_entity_id':entity_id,'is_read':False,'created_at':moment})}))
    return events


def publish(events):
    from attendance_notifications import publish_leave_notifications
    publish_leave_notifications(events)


def serialize(db,row):
    person=db.get(AppUser,row.user_id)
    return api_time({**{key:getattr(row,key) for key in ('id','user_id','day','kind','record_id','segment','requested_at','reason','evidence','status','original','history','created_at','confirmed_at','confirmed_by')},'name':person.full_name or person.username})


def submit(db,user,payload):
    import attendance_clock as clock
    import attendance_service as service
    require_ready(db);clock.require_ready(db);clock.lock(db,user)
    if payload.requested_at>now():raise HTTPException(422,'补卡时间不能晚于当前时间')
    if payload.kind=='in' and payload.requested_at.date()!=payload.day:raise HTTPException(422,'上班补卡时间须属于所选考勤日期')
    if payload.segment==2 and not payload.record_id:raise HTTPException(422,'居家加班补卡请指定已有打卡记录')
    values=payload.model_dump(mode='json');old=db.query(ClockCorrection).filter_by(client_id=payload.client_id).first()
    if old:
        if old.user_id!=user.id or old.history[0].get('request')!=values:raise HTTPException(409,'申请标识已使用，请重新打开表单')
        return {'message':'补卡申请已提交','record':serialize(db,old)}
    row=db.query(Clock).filter_by(id=payload.record_id,user_id=user.id).first() if payload.record_id else db.query(Clock).filter_by(user_id=user.id,day=payload.day,segment=payload.segment).first()
    if payload.record_id and not row:
        from attendance_models import AttendanceDay
        old_clock=db.query(AttendanceDay).filter_by(id=payload.record_id,user_id=user.id).first()
        if old_clock:row=next((item for item in clock.import_legacy(db,user,old_clock.day) if item.segment==0),None)
        if not row:raise HTTPException(404,'未找到本人的打卡记录')
    if row and row.day!=payload.day:raise HTTPException(422,'记录与所选考勤日期不符')
    if payload.kind=='out' and not row:raise HTTPException(422,'请先补上班打卡，或选择已有的上班记录')
    if row and (payload.kind=='out' and payload.requested_at<service.stamp(row.check_in) or payload.kind=='in' and row.check_out and payload.requested_at>service.stamp(row.check_out)):raise HTTPException(422,'上班时间不能晚于下班时间')
    shift=row.shift_snapshot if row else service.shift_for(db,user,payload.day)
    if not shift:raise HTTPException(422,'该日期没有有效班次，无法补卡')
    if not row:
        policy=clock.clock_shift({**shift,**clock.home_office_day(db,user,payload.day)})
        previous=db.query(Clock).filter(Clock.user_id==user.id,Clock.day==payload.day,Clock.segment!=2).all()
        if clock.allows_multiple(policy):
            if payload.segment!=clock.next_multi_segment(previous):raise HTTPException(422,'请按实际组次补卡，不得跳过前一组')
        elif payload.segment>=len(clock.segments(policy)):raise HTTPException(422,'该班次没有所选打卡组')
        if payload.segment>0 and not any(item.segment==0 and item.check_out for item in previous):raise HTTPException(422,'请先完成第一组上下班打卡')
    pending=db.query(ClockCorrection.id).filter_by(user_id=user.id,day=payload.day,kind=payload.kind,segment=row.segment if row else payload.segment,status='pending').first()
    if pending:raise HTTPException(409,'本组已有待行政确认的补卡申请')
    declarations=payload.model_dump(mode='json',exclude={'client_id','day','kind','record_id','segment','requested_at','reason','evidence'})
    if payload.kind=='out':declarations['cross_day_reason']=payload.reason
    if payload.kind=='out':clock.validate_checkout(db,user,row,clock.CheckOutWrite(record_id=row.id,**declarations),payload.requested_at)
    record=ClockCorrection(id=uuid4(),client_id=payload.client_id,user_id=user.id,day=payload.day,kind=payload.kind,record_id=row.id if row else None,segment=row.segment if row else payload.segment,requested_at=payload.requested_at,reason=payload.reason,evidence=payload.evidence,declarations=declarations,original=clock_state(row) if row else {'planned_shift':jsonable_encoder(shift)},status='pending',history=[{'action':'submitted','actor_id':str(user.id),'actor_name':user.full_name or user.username,'at':now().isoformat(),'request':values}],created_at=now())
    db.add(record)
    try:
        events=notify(db,user,record.id,f'待确认补卡 · {user.full_name or user.username}',f'{payload.day} 补{"上班" if payload.kind=="in" else "下班"}打卡，申请时间：{payload.requested_at.isoformat()}。原因：{payload.reason}。请到人事管理－考勤管理－补卡与跨日记录确认。')
        db.commit()
    except Exception:db.rollback();raise
    publish(events)
    return {'message':'补卡申请已通知行政部，确认后生效','record':serialize(db,record)}


def confirm(db,user,uid):
    import attendance_clock as clock
    import attendance_service as service
    require_hr(db,user);require_ready(db)
    request=db.query(ClockCorrection).filter_by(id=uid).with_for_update().populate_existing().first()
    if not request:raise HTTPException(404,'补卡申请不存在')
    if request.status=='cancelled':raise HTTPException(409,'该申请已撤回')
    if request.status=='confirmed':return {'message':'已有行政人员确认，请勿重复确认','record':serialize(db,request)}
    person=db.get(AppUser,request.user_id);clock.lock(db,person)
    row=db.query(Clock).filter_by(id=request.record_id).with_for_update().populate_existing().first() if request.record_id else None
    if request.record_id and (not row or clock_state(row)!=request.original):raise HTTPException(409,'原打卡记录已变化，请重新核对并申请，未覆盖现有记录')
    if not row:
        if db.query(Clock.id).filter_by(user_id=person.id,day=request.day,segment=request.segment).first():raise HTTPException(409,'该组已产生打卡，请重新核对并申请')
        shift=service.shift_for(db,person,request.day)
        if not shift or jsonable_encoder(shift)!=request.original.get('planned_shift'):raise HTTPException(409,'原日期班次已变化，暂不能确认')
        completed=db.query(Clock).filter(Clock.user_id==person.id,Clock.day==request.day,Clock.check_out.isnot(None)).all()
        policy=clock.clock_shift({**shift,**clock.home_office_day(db,person,request.day),**start_override(db,person,request.day,request.segment),'dinner_already_deducted':any(clock.serialize(item).get('dinner_deduction_minutes',0)>0 for item in completed)})
        row=Clock(id=uuid4(),user_id=person.id,day=request.day,segment=request.segment,check_in=request.requested_at,shift_snapshot=clock.snapshot(policy,request.segment),confirmations={});db.add(row);db.flush()
    # 不允许补卡与本人的其他工作组重叠，避免重复累计加班。
    left=request.requested_at if request.kind=='in' else service.stamp(row.check_in)
    right=service.stamp(row.check_out) if request.kind=='in' and row.check_out else request.requested_at if request.kind=='out' else None
    for other in db.query(Clock).filter(Clock.user_id==person.id,Clock.id!=row.id,Clock.check_in<(right or now()),or_(Clock.check_out.is_(None),Clock.check_out>left)).all():
        a=service.stamp(other.check_in);b=service.stamp(other.check_out) if other.check_out else now()
        if left<(b) and (right or now())>a:raise HTTPException(409,'补卡时段与其他打卡组重叠，请核对后再申请')
    extra_events=[]
    if request.kind=='in':row.check_in=request.requested_at;row.confirmations={**row.confirmations,**{key:value for key,value in request.declarations.items() if key in ('early_work_confirmed','breakfast_after_eating')},'correction_id':str(request.id),'breakfast_notice_accepted':True}
    else:
        extra_events=clock.apply_checkout(db,person,row,clock.CheckOutWrite(record_id=row.id,**request.declarations),api_time(request.requested_at))
        row.confirmations={**row.confirmations,'confirmed_at':now().isoformat(),'correction_id':str(request.id)}
    request.record_id=row.id;request.status='confirmed';request.confirmed_at=now();request.confirmed_by=user.id
    request.history=[*request.history,{'action':'confirmed','actor_id':str(user.id),'actor_name':user.full_name or user.username,'at':now().isoformat(),'before':request.original,'after':clock_state(row)}]
    try:
        events=notify(db,person,request.id,'补卡已确认',f'{request.day} 补卡已由 {user.full_name or user.username} 确认，可在本人工作台查看全程记录。',True);db.commit()
    except Exception:db.rollback();raise
    publish([*extra_events,*events])
    return {'message':'已确认补卡，考勤已更新','record':serialize(db,request)}


def listing(db,user,company=False):
    if company:require_hr(db,user)
    require_ready(db)
    query=db.query(ClockCorrection)
    if not company:query=query.filter_by(user_id=user.id)
    rows=query.order_by(ClockCorrection.created_at.desc()).limit(500).all()
    clocks=db.query(Clock).filter_by(user_id=user.id).order_by(Clock.day.desc(),Clock.segment).limit(100).all() if not company else []
    from attendance_models import AttendanceDay
    legacy=db.query(AttendanceDay).filter_by(user_id=user.id).order_by(AttendanceDay.day.desc()).limit(100).all() if not company else []
    occupied={row.day for row in clocks}
    record_values=[clock_state(row)|{'day':row.day,'segment':row.segment} for row in clocks]+[clock_state(row)|{'day':row.day,'segment':0} for row in legacy if row.day not in occupied]
    adjustments=db.query(AttendanceStartAdjustment,AppUser.full_name,AppUser.username,Clock.check_in,Clock.check_out).join(AppUser,AppUser.id==AttendanceStartAdjustment.user_id).join(Clock,Clock.id==AttendanceStartAdjustment.source_clock_id).order_by(AttendanceStartAdjustment.created_at.desc()) if adjustments_ready(db) else None
    if adjustments is not None and not company:adjustments=adjustments.filter(AttendanceStartAdjustment.user_id==user.id)
    return api_time({'items':[serialize(db,row) for row in rows],'clock_records':record_values,'adjustments':[{'id':row.id,'user_id':row.user_id,'name':name or username,'check_in':check_in,'check_out':check_out,'day':row.day,'next_start':row.next_start,'reason':row.reason,'history':row.history,'created_at':row.created_at} for row,name,username,check_in,check_out in adjustments.limit(500).all()] if adjustments is not None else []})


def next_scheduled_start(db,user,row,moment):
    import attendance_service as service
    import attendance_clock as clock
    shift=clock.clock_shift(row.shift_snapshot)
    if shift.get('flexible'):return None,0
    if (shift.get('code')=='customer_remote' or shift.get('night_duty')=='continuation') and getattr(row,'segment',0)==0 and not shift.get('clock_pairs_unrestricted'):
        periods=service.intervals(row.day,{'periods':clock.segments(shift)[1]})
        if periods:return periods[0][0],1
    for offset in range(1,min((moment.date()-row.day).days+1,32)+1):
        day=row.day+timedelta(days=offset)
        try:following=service.shift_for(db,user,day)
        except HTTPException:continue
        periods=service.intervals(day,following)
        if periods:return periods[0][0],0
    return None,0


def apply_late_checkout(db,user,row,payload,moment):
    import attendance_service as service
    threshold,segment=next_scheduled_start(db,user,row,moment)
    if (not threshold or moment<threshold) and payload.next_start is None:return
    if not payload.cross_day_reason.strip() or payload.next_start is None:raise HTTPException(422,'已超过下次预定上班时间，请说明签退原因并填写第二天/第二次上班时间')
    if payload.next_start.date()>row.day:segment=0
    if payload.next_start<=moment:raise HTTPException(422,'后续上班时间须晚于本次下班打卡时间，避免时间重叠')
    if not adjustments_ready(db):raise HTTPException(503,'后续上班时间调整表尚未初始化')
    adjustment=db.query(AttendanceStartAdjustment).filter_by(source_clock_id=row.id).first()
    if adjustment is None:adjustment=AttendanceStartAdjustment(id=uuid4(),source_clock_id=row.id,user_id=user.id,history=[],created_at=now());db.add(adjustment)
    # 重新确认同一来源时，先撤销仅由该来源带入的旧基准，避免两个日期重复免迟到。
    old_rows=db.query(Clock).filter(Clock.user_id==user.id,Clock.shift_snapshot['start_adjustment_id'].as_string()==str(adjustment.id)).all()
    for previous in old_rows:
        baseline={}
        for entry in adjustment.history or []:
            found=next((change.get('before',{}).get('shift',{}) for change in entry.get('updated_records',[]) if change.get('record_id')==str(previous.id)),None)
            if found is not None:baseline=found;break
        snapshot=dict(previous.shift_snapshot)
        for key in ('late_start_at','start_adjustment_id'):
            if key in baseline:snapshot[key]=baseline[key]
            else:snapshot.pop(key,None)
        previous.shift_snapshot=snapshot
    audit={'at':now().isoformat(),'source_check_in':api_time(row.check_in).isoformat(),'source_check_out':moment.isoformat(),'next_start':payload.next_start.isoformat(),'reason':payload.cross_day_reason.strip(),'updated_records':[]}
    if adjustment.next_start:audit['previous_next_start']=api_time(adjustment.next_start).isoformat()
    adjustment.day=payload.next_start.date();adjustment.segment=segment;adjustment.next_start=payload.next_start;adjustment.reason=payload.cross_day_reason.strip()
    for following in db.query(Clock).filter_by(user_id=user.id,day=adjustment.day,segment=segment).all():
        audit['updated_records'].append({'record_id':str(following.id),'before':clock_state(following)})
        following.shift_snapshot={**following.shift_snapshot,'late_start_at':payload.next_start.isoformat(),'start_adjustment_id':str(adjustment.id)}
        audit['updated_records'][-1]['after']=clock_state(following)
    adjustment.history=[*(adjustment.history or []),audit]
    events=notify(db,user,adjustment.id,f'跨日/跨组签退记录 · {user.full_name or user.username}',f'原考勤日 {row.day}，本次签退 {moment.isoformat()}；后续上班基准 {payload.next_start.isoformat()}（仍保留15分钟宽限）。原因：{payload.cross_day_reason}。行政部可在考勤管理查看全程记录。')
    return events


def start_override(db,user,day,segment):
    if not adjustments_ready(db):return {}
    row=db.query(AttendanceStartAdjustment).filter_by(user_id=user.id,day=day,segment=segment).order_by(AttendanceStartAdjustment.next_start.desc()).first()
    return {'late_start_at':api_time(row.next_start).isoformat(),'start_adjustment_id':str(row.id)} if row else {}


def cancel(db,user,uid):
    require_ready(db)
    row=db.query(ClockCorrection).filter_by(id=uid,user_id=user.id).with_for_update().first()
    if not row:raise HTTPException(404,'申请不存在')
    if row.status!='pending':raise HTTPException(409,'只有待确认申请可撤回')
    row.status='cancelled';row.history=[*row.history,{'action':'cancelled','actor_id':str(user.id),'actor_name':user.full_name or user.username,'at':now().isoformat()}];db.commit()
    return {'message':'已撤回，可重新申请'}


router=APIRouter(prefix='/attendance/clock-corrections',tags=['attendance'])
@router.get('')
def get_records(company:bool=False,db=Depends(get_db),user=Depends(get_current_user)):return listing(db,user,company)
@router.post('')
def request_correction(payload:CorrectionWrite,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    from attendance_service import desktop_request
    if not desktop_request(request):raise HTTPException(403,'补卡请使用电脑端')
    return submit(db,user,payload)
@router.post('/{uid}/confirm')
def confirm_correction(uid:UUID,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    from attendance_service import desktop_request
    if not desktop_request(request):raise HTTPException(403,'确认补卡请使用电脑端')
    return confirm(db,user,uid)

@router.post('/{uid}/cancel')
def cancel_correction(uid:UUID,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
    from attendance_service import desktop_request
    if not desktop_request(request):raise HTTPException(403,'撤回补卡请使用电脑端')
    return cancel(db,user,uid)
