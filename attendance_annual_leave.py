"""按自然年、来源和班次折算的年假抵扣；人事调整与不可覆盖的审计记录。"""
from datetime import date,datetime,timedelta
from decimal import Decimal,ROUND_DOWN
from uuid import UUID,uuid4
from typing import Literal
from types import SimpleNamespace
from fastapi import HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import String,Integer,Text,DateTime,JSON,Uuid,ForeignKey,Index,inspect
from sqlalchemy.orm import Mapped,mapped_column
from models import Base,AppUser,EmployeeLeave
from attendance_models import AttendanceLeave,AttendanceDay,AttendanceClockSession
from employee_employment import EmployeeEmployment,annual_days,ready as employment_ready
from attendance_policy import clock_sources,lateness_events
from chat_time import now,api_time


class LeaveSettlement(Base):
    __tablename__='attendance_leave_settlement'
    source_key:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False,index=True)
    mode:Mapped[str]=mapped_column(String(20),nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    updated_by:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class LeaveSettlementAudit(Base):
    __tablename__='attendance_leave_settlement_audit'
    __table_args__=(Index('ix_leave_settlement_audit_source_time','source_key','created_at'),)
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    source_key:Mapped[str]=mapped_column(String(64),ForeignKey('attendance_leave_settlement.source_key'),nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False,index=True)
    actor_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    actor_name:Mapped[str]=mapped_column(String(255),nullable=False)
    before_mode:Mapped[str]=mapped_column(String(20),nullable=False)
    after_mode:Mapped[str]=mapped_column(String(20),nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    before_snapshot:Mapped[dict]=mapped_column(JSON,nullable=False)
    after_snapshot:Mapped[dict]=mapped_column(JSON,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class SettlementWrite(BaseModel):
    client_id:UUID
    source_kind:Literal['application','lateness']
    source_id:UUID
    mode:Literal['auto','wage']
    revision:int=Field(ge=0)
    reason:str=Field(min_length=1,max_length=1000)
    @field_validator('reason')
    @classmethod
    def clean(cls,value):
        if not value.strip():raise ValueError('请填写调整原因')
        return value.strip()


def ready(db):return all(inspect(db.connection()).has_table(name) for name in (LeaveSettlement.__tablename__,LeaveSettlementAudit.__tablename__))


def nominal_minutes(day,shift):
    from attendance_service import intervals,merged
    shift=shift or {}
    return round(sum((b-a).total_seconds()/60 for a,b in merged(intervals(day,{**shift,'periods':shift.get('full_periods',shift.get('periods',[]))}))),2)


def sources(db,ids,year,extra=None):
    """跨年申请逐日归属，不把整张申请时长重复扣在两个年度。"""
    import attendance_service as attendance
    left=date(year,1,1);right=date(year,12,31)
    clocks,leaves=clock_sources(db,ids,left,right)
    snapshots={row.id:row.days for row in db.query(AttendanceLeave).filter(AttendanceLeave.id.in_([item.id for item in leaves])).all()} if leaves else {}
    result=[]
    for leave in leaves:
        days=snapshots.get(leave.id)
        if days is None:
            target=db.get(AppUser,leave.employee_id)
            days=attendance.preview_leave(db,target,SimpleNamespace(start_at=max(attendance.stamp(leave.start_date),attendance.midnight(left)),end_at=min(attendance.stamp(leave.end_date),attendance.midnight(right+timedelta(days=1)))))['days']
        for item in days:
            if left.isoformat()<=item['day']<=right.isoformat() and item['minutes']>0:
                result.append({'entry_id':f'leave:{leave.id}:{item["day"]}','source_key':f'application:{leave.id}','source_kind':'application','source_id':str(leave.id),'user_id':str(leave.employee_id),'day':item['day'],'minutes':item['minutes'],'day_minutes':nominal_minutes(date.fromisoformat(item['day']),item.get('shift')),'reason':leave.reason,'start_at':attendance.stamp(leave.start_date),'end_at':attendance.stamp(leave.end_date)})
    clock_map={str(row.id):row for row in clocks}
    for item in lateness_events(clocks,leaves):
        row=clock_map[item['clock_id']]
        result.append({**item,'entry_id':item['id'],'source_key':f'lateness:{row.id}','source_kind':'lateness','source_id':str(row.id),'day_minutes':nominal_minutes(row.day,row.shift_snapshot)})
    return [*result,*([item for item in extra if item['day'][:4]==str(year)] if extra else [])]


def allocate(entries,hire,year,modes=None,on_date=None):
    """按发生日期FIFO抵扣；已发生与未来预留分别展示，不借用尚未生效额度。"""
    asof=on_date or now().date();spent=Decimal(0);used=Decimal(0);reserved=Decimal(0);result=[]
    for item in sorted(entries,key=lambda item:(item['day'],str(item.get('start_at','')),item['entry_id'])):
        day=date.fromisoformat(item['day']);mode=(modes or {}).get(item['source_key'],{});mode_name=mode.get('mode','auto')
        minutes=Decimal(str(item['minutes']));unit=Decimal(str(item['day_minutes']));quota=annual_days(hire,min(day,asof))
        annual=Decimal(0)
        if mode_name=='auto' and quota is not None and unit>0:
            annual=min(minutes,max(Decimal(0),Decimal(quota)-spent)*unit).quantize(Decimal('.01'),rounding=ROUND_DOWN)
        annual_days_used=annual/unit if unit>0 else Decimal(0);spent+=annual_days_used
        if day<=asof:used+=annual_days_used
        else:reserved+=annual_days_used
        wage=minutes if mode_name=='wage' else Decimal(0)
        outstanding=minutes-annual-wage
        result.append({**item,'mode':mode_name,'revision':mode.get('revision',0),'annual_minutes':float(annual),'annual_days':round(float(annual_days_used),6),'wage_minutes':float(wage),'makeup_required_minutes':float(outstanding),'future':day>asof,'quota_pending':quota is None or unit<=0})
    quota=annual_days(hire,min(date(year,12,31),asof))
    return {'year':year,'hire_date':hire,'annual_leave_days':quota,'used_days':round(float(used),6),'reserved_days':round(float(reserved),6),'remaining_days':round(float(max(Decimal(0),Decimal(quota or 0)-spent)),6) if quota is not None else None,'annual_minutes':round(sum(row['annual_minutes'] for row in result),2),'wage_minutes':round(sum(row['wage_minutes'] for row in result),2),'makeup_required_minutes':round(sum(row['makeup_required_minutes'] for row in result),2),'entries':result}


def ledger(db,users,year,extra=None,with_history=True):
    ids=[person.id for person in users];all_entries=sources(db,ids,year,extra) if ids else []
    hires={row.user_id:row.hire_date for row in db.query(EmployeeEmployment).filter(EmployeeEmployment.user_id.in_(ids)).all()} if ids and employment_ready(db) else {}
    available=ready(db)
    modes={row.source_key:{'mode':row.mode,'revision':row.revision} for row in db.query(LeaveSettlement).filter(LeaveSettlement.user_id.in_(ids)).all()} if ids and available else {}
    history={}
    if ids and available and with_history:
        audits=db.query(LeaveSettlementAudit).filter(LeaveSettlementAudit.user_id.in_(ids)).order_by(LeaveSettlementAudit.created_at.desc(),LeaveSettlementAudit.revision.desc()).all()
        for row in audits:
            if str(year) not in row.before_snapshot and str(year) not in row.after_snapshot:continue
            def scoped(snapshot):
                return {year:{**{key:value for key,value in value.items() if key!='entries'},'entries':[item for item in value.get('entries',[]) if item['source_key']==row.source_key]} for year,value in snapshot.items()}
            history.setdefault(row.source_key,[]).append({'id':str(row.id),'user_id':str(row.user_id),'source_key':row.source_key,'actor_name':row.actor_name,'before_mode':row.before_mode,'after_mode':row.after_mode,'reason':row.reason,'revision':row.revision,'created_at':row.created_at,'before_snapshot':scoped(row.before_snapshot),'after_snapshot':scoped(row.after_snapshot)})
    output=[]
    for user in users:
        values=allocate([row for row in all_entries if row['user_id']==str(user.id)],hires.get(user.id),year,modes)
        for item in values['entries']:item['history']=history.get(item['source_key'],[])
        output.append({**values,'user_id':str(user.id),'name':user.full_name or user.username,'username':user.username,'ready':available,'history':[item for items in history.values() for item in items if item['user_id']==str(user.id)]})
    return api_time(output)


def overview(db,user,year,admin=False):
    from hr_access import require_hr
    import attendance_service as attendance
    if admin:require_hr(db,user)
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    attendance.require_ready(db)
    users=db.query(AppUser).filter(AppUser.is_deleted.is_(False)).order_by(AppUser.full_name,AppUser.username).all() if admin else [user]
    return {'year':year,'people':ledger(db,users,year)}


def adjustment(db,actor,payload):
    from hr_access import require_hr
    from attendance_clock import lock
    from fastapi.encoders import jsonable_encoder
    require_hr(db,actor)
    if not ready(db):raise HTTPException(503,'年假抵扣调整表尚未初始化')
    source_key=f'{payload.source_kind}:{payload.source_id}'
    if payload.source_kind=='application':source=db.get(EmployeeLeave,payload.source_id)
    else:source=db.get(AttendanceClockSession,payload.source_id) or db.get(AttendanceDay,payload.source_id)
    if not source:raise HTTPException(404,'请假或迟到来源不存在')
    target_id=source.employee_id if payload.source_kind=='application' else source.user_id
    target=db.get(AppUser,target_id)
    if not target or target.is_deleted:raise HTTPException(404,'人员不存在')
    lock(db,target)
    old=db.query(LeaveSettlementAudit).filter_by(client_id=payload.client_id).first()
    if old:
        if old.source_key!=source_key or old.after_mode!=payload.mode or old.reason!=payload.reason or old.actor_id!=actor.id:raise HTTPException(409,'调整请求标识已使用，请重新提交')
        return {'message':'调整已保存，请勿重复提交','revision':old.revision}
    row=db.query(LeaveSettlement).filter_by(source_key=source_key).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'抵扣方式已被其他人修改，请刷新后重试')
    years=range(source.start_date.year,source.end_date.year+1) if payload.source_kind=='application' else [source.day.year]
    before={str(year):ledger(db,[target],year,with_history=False)[0] for year in years}
    if not any(item['source_key']==source_key for value in before.values() for item in value['entries']) and payload.mode!='auto':raise HTTPException(422,'该来源当前没有可调整的有效请假时长')
    previous=row.mode if row else 'auto'
    if previous==payload.mode:return {'message':'抵扣方式未变化','revision':row.revision if row else 0}
    if not row:row=LeaveSettlement(source_key=source_key,user_id=target.id,revision=0);db.add(row)
    row.mode=payload.mode;row.revision+=1;row.updated_by=actor.id;row.updated_at=now();db.flush()
    after={str(year):ledger(db,[target],year,with_history=False)[0] for year in years}
    # 快照包含整年受影响的重新分配结果，调整历史永不覆盖。
    audit=LeaveSettlementAudit(client_id=payload.client_id,source_key=source_key,user_id=target.id,actor_id=actor.id,actor_name=actor.full_name or actor.username,before_mode=previous,after_mode=payload.mode,revision=row.revision,reason=payload.reason,before_snapshot=jsonable_encoder(before),after_snapshot=jsonable_encoder(after),created_at=now())
    db.add(audit);db.commit()
    try:
        from notification_ws import dispatch_personal_message
        dispatch_personal_message(target.id,{'type':'annual_leave_changed'})
    except Exception:pass
    return {'message':'抵扣方式已保存，调整记录可查看','revision':row.revision}


def preview(db,user,days):
    extra=[{'entry_id':f'preview:{row["day"]}','source_key':'preview','source_kind':'application','source_id':'preview','user_id':str(user.id),'day':row['day'],'minutes':row['minutes'],'day_minutes':nominal_minutes(date.fromisoformat(row['day']),row.get('shift')),'reason':'本次请假预览','start_at':f'{row["day"]}T23:59:59+08:00','end_at':f'{row["day"]}T23:59:59+08:00'} for row in days if row['minutes']>0]
    values=[value for year in sorted({int(row['day'][:4]) for row in extra}) for value in ledger(db,[user],year,extra,with_history=False)[0]['entries'] if value['source_key']=='preview']
    return {'annual_minutes':round(sum(row['annual_minutes'] for row in values),2),'makeup_required_minutes':round(sum(row['makeup_required_minutes'] for row in values),2),'days':values,'note':'请假优先抵扣已生效年假，余额不足部分待补班；人事可改为扣工资并留调整记录。预览不占用额度，以保存后的实际记录为准。'}
