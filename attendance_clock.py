"""手动分段打卡及可追溯加班抵扣；旧记录只读兼容，不重算历史确认。"""
from datetime import timedelta
from uuid import UUID
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,Field,StrictBool,model_validator
from sqlalchemy import inspect,text
from attendance_models import AttendanceClockSession as Clock,AttendanceDay
from models import AppUser
from chat_time import now,api_time


class CheckInWrite(BaseModel):
    segment:int=Field(default=0,ge=0,le=1)
    breakfast_notice_accepted:StrictBool
    work_mode:Literal['scheduled','company_home_overtime']='scheduled'


class CheckOutWrite(BaseModel):
    record_id:UUID
    early_work_confirmed:StrictBool|None=None
    breakfast_after_eating:StrictBool
    dinner_eaten:StrictBool|None=None
    deduct_invalid_time:StrictBool|None=None
    invalid_minutes:float=Field(default=0,ge=0,le=1440,allow_inf_nan=False)
    invalid_reason:str=Field(default='',max_length=500)
    @model_validator(mode='after')
    def valid(self):
        if self.deduct_invalid_time is True and (self.invalid_minutes<=0 or not self.invalid_reason.strip()):raise ValueError('请填写需扣除的无效时间（分钟）及原因')
        if self.deduct_invalid_time is not True and (self.invalid_minutes or self.invalid_reason.strip()):raise ValueError('未选择扣除无效时间，不能填写扣除时长或原因')
        return self


def ready(db):return inspect(db.connection()).has_table(Clock.__tablename__)
def require_ready(db):
    if not ready(db):raise HTTPException(503,'分段打卡表尚未初始化')
def lock(db,user):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(731945,:uid)'),{'uid':user.id.int%2147483647})
    db.query(AppUser).filter_by(id=user.id).with_for_update().one()


def segments(shift):
    periods=(shift or {}).get('periods',[])
    return [periods[:2],periods[2:]] if (shift or {}).get('code')=='customer_remote' else [periods]


def snapshot(shift,index):
    return {**shift,'full_periods':shift['periods'],'periods':segments(shift)[index],'clock_policy':'manual-v1','segment':index}


def import_legacy(db,user,day):
    """仅在本人主动打卡事务中延续当日旧记录，不批量迁移。"""
    rows=db.query(Clock).filter_by(user_id=user.id,day=day).all()
    if rows:return rows
    old=db.query(AttendanceDay).filter_by(user_id=user.id,day=day).first()
    if old:
        row=Clock(user_id=user.id,day=day,segment=0,check_in=old.check_in,check_out=old.check_out,
                  shift_snapshot=old.shift_snapshot if old.check_out else snapshot(old.shift_snapshot,0),confirmations={'legacy_id':str(old.id),'legacy_completed':bool(old.check_out)})
        db.add(row);db.flush();return [row]
    return []


def serialize(row,leaves=()):
    import attendance_service as service
    if row.confirmations.get('legacy_completed'):return {**service.serialize_day(row,leaves),'segment':row.segment,'confirmations':row.confirmations}
    result=service.metrics(row,leaves)
    result.update(early_minutes=0,early_overtime_minutes=0,raw_overtime_minutes=0,breakfast_deduction_minutes=0,dinner_deduction_minutes=0,invalid_deduction_minutes=0,violation_count=0,overtime_net_minutes=0,deduction_details=[])
    periods=service.intervals(row.day,row.shift_snapshot)
    left=service.stamp(row.check_in);right=service.stamp(row.check_out) if row.check_out else None
    exclusions=service.merged([(service.stamp(item.start_date),service.stamp(item.end_date)) for item in leaves]+[(service.midnight(row.day)+timedelta(hours=12),service.midnight(row.day)+timedelta(hours=13,minutes=30))]+[(periods[i][1],periods[i+1][0]) for i in range(len(periods)-1)])
    def minutes(a,b):return round(max(0,(b-a).total_seconds()-sum(service.overlap(a,b,c,d) for c,d in exclusions))/60,2) if b>a else 0
    early=minutes(left,min(right or periods[0][0],periods[0][0])) if periods else 0
    result['early_minutes']=early
    if right:
        early_count=early if row.confirmations.get('early_work_confirmed') else 0
        late=minutes(max(left,periods[-1][1]),right) if periods else 0
        breakfast=0 if row.confirmations.get('breakfast_after_eating') else 15
        remote=row.shift_snapshot.get('code')=='customer_remote'
        dinner=20 if not remote and (row.shift_snapshot.get('fixed') or (row.shift_snapshot.get('code') in ('late','late_late') and row.confirmations.get('dinner_eaten'))) else 0
        invalid=row.confirmations.get('invalid_minutes',0) if remote or row.shift_snapshot.get('home_office_day') else 0
        raw=minutes(left,right) if row.shift_snapshot.get('overtime_only') else round(early_count+late,2);net=round(raw-breakfast-dinner-invalid,2)
        details=[{'reason':'提前到达并实际工作' if early_count else '提前到达未工作，不计加班','minutes':early_count,'kind':'credit'},
                 {'reason':'班次结束后工作','minutes':late,'kind':'credit'}]
        if row.shift_snapshot.get('overtime_only'):details=[{'reason':'公司要求居家加班的实际工作时间','minutes':raw,'kind':'credit'}]
        if breakfast:details.append({'reason':'早餐前打卡，早餐抵扣并记违纪一次','minutes':breakfast,'kind':'deduction'})
        if dinner:details.append({'reason':'固定班次晚餐' if row.shift_snapshot.get('fixed') else '已进食晚餐','minutes':dinner,'kind':'deduction'})
        if invalid:details.append({'reason':row.confirmations.get('invalid_reason','无效工作时间'),'minutes':invalid,'kind':'deduction'})
        result.update(early_overtime_minutes=early_count,raw_overtime_minutes=raw,breakfast_deduction_minutes=breakfast,dinner_deduction_minutes=dinner,invalid_deduction_minutes=invalid,violation_count=int(breakfast>0),overtime_minutes=net,overtime_net_minutes=net,deduction_details=details)
    return api_time({'id':str(row.id),'user_id':str(row.user_id),'day':row.day.isoformat(),'segment':row.segment,'check_in':row.check_in,'check_out':row.check_out,'shift':row.shift_snapshot,'confirmations':row.confirmations,**result})


def check_in(db,user,request,payload):
    import attendance_service as service
    service.require_ready(db);require_ready(db)
    if not service.desktop_request(request):raise HTTPException(403,'上班打卡请使用电脑端')
    if not payload.breakfast_notice_accepted:raise HTTPException(422,'请阅读早餐提示后点击打卡')
    lock(db,user);moment=now();day=moment.date();rows=import_legacy(db,user,day)
    if payload.work_mode=='company_home_overtime':return check_in_home_overtime(db,user,rows,moment)
    regular=[row for row in rows if row.segment!=2]
    shift=regular[0].shift_snapshot if regular else service.shift_for(db,user,day)
    if shift and 'full_periods' in shift:shift={**shift,'periods':shift['full_periods']}
    if not shift:raise HTTPException(409,'今日无有效班次，不能打卡')
    if payload.segment>=len(segments(shift)):raise HTTPException(422,'该班次没有第二段打卡')
    existing=next((row for row in regular if row.segment==payload.segment),None)
    if existing:
        db.commit();return {'message':'已保留本段首次上班打卡','record':serialize(existing,service.day_leaves(db,user.id,day))}
    if any(not row.check_out for row in rows):raise HTTPException(409,'请先完成上一段下班打卡')
    if payload.segment==1 and not any(row.segment==0 and row.check_out for row in regular):raise HTTPException(409,'请先完成第一段上下班打卡')
    if payload.segment==1 and any(row.confirmations.get('legacy_completed') for row in regular):raise HTTPException(409,'今日旧版打卡已完成，不再追加分段')
    if payload.segment==1:
        previous=next(row for row in rows if row.segment==0)
        if moment<service.intervals(day,snapshot(shift,0))[-1][1]:raise HTTPException(409,'第一段预定结束后才能开始第二段打卡')
    pending=db.query(Clock).filter(Clock.user_id==user.id,Clock.day<day,Clock.check_out.is_(None)).first()
    pending=pending or db.query(AttendanceDay).filter(AttendanceDay.user_id==user.id,AttendanceDay.day==day-timedelta(days=1),AttendanceDay.check_out.is_(None)).first()
    if pending:raise HTTPException(409,'仍有此前未签退记录，请先完成下班打卡')
    shift={**shift,**home_office_day(db,user,day)}
    row=Clock(user_id=user.id,day=day,segment=payload.segment,check_in=moment,shift_snapshot=snapshot(shift,payload.segment),confirmations={'breakfast_notice_accepted':True})
    db.add(row);db.commit()
    return {'message':'上班打卡成功','record':serialize(row,service.day_leaves(db,user.id,day))}


def check_out(db,user,request,payload):
    import attendance_service as service
    service.require_ready(db);require_ready(db)
    if not service.desktop_request(request):raise HTTPException(403,'下班打卡请使用电脑端')
    lock(db,user);moment=now()
    row=db.query(Clock).filter_by(id=payload.record_id,user_id=user.id).with_for_update().first()
    if not row:
        old=db.query(AttendanceDay).filter_by(id=payload.record_id,user_id=user.id).first()
        if not old:raise HTTPException(404,'未找到本人的上班打卡记录')
        row=import_legacy(db,user,old.day)[0]
    if row.check_out:return {'message':'已保留本段首次下班打卡','record':serialize(row,service.day_leaves(db,user.id,row.day))}
    if moment<service.stamp(row.check_in):raise HTTPException(409,'当前时间早于上班记录')
    remote=row.shift_snapshot.get('code')=='customer_remote'
    if not row.shift_snapshot.get('overtime_only') and payload.early_work_confirmed is None:raise HTTPException(422,'请选择提前到达时间是否已在工作')
    at_home=remote or bool(row.shift_snapshot.get('home_office_day')) or bool(home_office_day(db,user,row.day).get('home_office_day'))
    if at_home and not remote:row.shift_snapshot={**row.shift_snapshot,'home_office_day':True}
    if at_home and payload.deduct_invalid_time is None:raise HTTPException(422,'请选择是否扣除无效时间')
    if not at_home and payload.deduct_invalid_time is not None:raise HTTPException(422,'本班次无需填写居家无效时间')
    if not remote and row.shift_snapshot.get('code') in ('late','late_late') and payload.dinner_eaten is None:raise HTTPException(422,'请选择有无进食晚餐')
    if remote and payload.dinner_eaten is not None:raise HTTPException(422,'居家晚班无需晚餐确认')
    if payload.invalid_minutes>(moment-service.stamp(row.check_in)).total_seconds()/60:raise HTTPException(422,'扣除时间不能超过本段已打卡时长')
    row.confirmations={**row.confirmations,**payload.model_dump(mode='json',exclude={'record_id'}),'confirmed_at':api_time(moment).isoformat()}
    row.check_out=moment
    legacy_id=row.confirmations.get('legacy_id')
    if legacy_id:
        old=db.get(AttendanceDay,UUID(legacy_id))
        if old and not old.check_out:old.check_out=moment
    db.commit()
    return {'message':'打卡成功','record':serialize(row,service.day_leaves(db,user.id,row.day))}


def today_status(db,user):
    import attendance_service as service
    service.require_ready(db);day=now().date();available=ready(db)
    rows=db.query(Clock).filter_by(user_id=user.id,day=day).order_by(Clock.segment).all() if available else []
    old=db.query(AttendanceDay).filter_by(user_id=user.id,day=day).first() if not rows else None
    regular=[row for row in rows if row.segment!=2]
    shift=regular[0].shift_snapshot if regular else old.shift_snapshot if old else service.shift_for(db,user,day)
    if shift and 'full_periods' in shift:shift={**shift,'periods':shift['full_periods']}
    home=home_office_day(db,user,day)
    if shift:shift={**shift,**home}
    entries=[serialize(row,service.day_leaves(db,user.id,day)) for row in rows] if rows else [service.serialize_day(old,service.day_leaves(db,user.id,day))] if old else []
    if home.get('home_office_day'):
        entries=[{**entry,'shift':{**entry['shift'],**home}} if not entry['shift'].get('overtime_only') else entry for entry in entries]
    pending=db.query(Clock).filter(Clock.user_id==user.id,Clock.day<day,Clock.check_out.is_(None)).order_by(Clock.day.desc()).first() if available else None
    legacy_pending=db.query(AttendanceDay).filter(AttendanceDay.user_id==user.id,AttendanceDay.day==day-timedelta(days=1),AttendanceDay.check_out.is_(None)).first() if not pending and not entries else None
    pending_value=serialize(pending,service.day_leaves(db,user.id,pending.day)) if pending else service.serialize_day(legacy_pending,service.day_leaves(db,user.id,legacy_pending.day)) if legacy_pending else None
    open_record=next((row for row in entries if not row['check_out']),None)
    regular_entries=[entry for entry in entries if entry.get('segment',0)!=2]
    return api_time({'day':day.isoformat(),'shift':shift,'record':open_record or (entries[-1] if entries else None),'sessions':entries,'segment_count':len(segments(shift)) if shift else 0,'can_check_in':bool(available and shift and not open_record and not pending_value and not (old and old.check_out) and not any(row.confirmations.get('legacy_completed') for row in regular) and len(regular_entries)<len(segments(shift))),'next_segment':min(len(regular_entries),1),'can_home_overtime_check_in':bool(available and not open_record and not pending_value and not any(row.segment==2 for row in rows)),'home_overtime_record':next((entry for entry in entries if entry.get('segment')==2),None),'pending_previous':pending_value,'clock_ready':available,
        'leaves':[{'start_at':leave.start_date,'end_at':leave.end_date,'reason':leave.reason,'minutes':round(sum(service.overlap(service.stamp(leave.start_date),service.stamp(leave.end_date),a,b) for a,b in service.intervals(day,shift))/60,2)} for leave in service.day_leaves(db,user.id,day)]})


def monthly_balances(db,ids,start,end):
    """按人员、自然月抵扣，不能用甲员工的负额扣乙员工加班。"""
    if not ids:return []
    import attendance_service as service
    from models import EmployeeLeave
    left=start.replace(day=1);right=(end.replace(day=28)+timedelta(days=4)).replace(day=1)
    sessions=db.query(Clock).filter(Clock.user_id.in_(ids),Clock.day>=left,Clock.day<right).all() if ready(db) else []
    occupied={(row.user_id,row.day) for row in sessions}
    legacy=db.query(AttendanceDay).filter(AttendanceDay.user_id.in_(ids),AttendanceDay.day>=left,AttendanceDay.day<right).all()
    leaves=db.query(EmployeeLeave).filter(EmployeeLeave.employee_id.in_(ids),EmployeeLeave.start_date<service.midnight(right).replace(tzinfo=None),EmployeeLeave.end_date>service.midnight(left).replace(tzinfo=None)).all()
    values={}
    for row in [*sessions,*[row for row in legacy if (row.user_id,row.day) not in occupied]]:
        if not row.check_out:continue
        key=(str(row.user_id),row.day.strftime('%Y-%m'))
        value=values.setdefault(key,{'user_id':key[0],'month':key[1],'raw_minutes':0,'deduction_minutes':0,'net_minutes':0})
        own_leaves=[leave for leave in leaves if leave.employee_id==row.user_id]
        result=serialize(row,own_leaves) if isinstance(row,Clock) else service.serialize_day(row,own_leaves)
        deductions=sum(result.get(field,0) for field in ('breakfast_deduction_minutes','dinner_deduction_minutes','invalid_deduction_minutes'))
        value['raw_minutes']+=result.get('raw_overtime_minutes',result['overtime_minutes']);value['deduction_minutes']+=deductions;value['net_minutes']+=result['overtime_minutes']
    from work_report_lunch import reports as lunch_reports,credited as lunch_credited
    clock_rows=[*sessions,*[row for row in legacy if (row.user_id,row.day) not in occupied]]
    for (uid,day),report in lunch_reports(db,ids,left,right-timedelta(days=1)).items():
        _reported,credited=lunch_credited(report,day,[row for row in clock_rows if row.user_id==uid and row.day==day])
        key=(str(uid),day.strftime('%Y-%m'))
        if credited and key in values:values[key]['raw_minutes']+=credited;values[key]['net_minutes']+=credited
    return [{**value,'raw_minutes':round(value['raw_minutes'],2),'deduction_minutes':round(value['deduction_minutes'],2),'net_minutes':round(value['net_minutes'],2),'overtime_minutes':round(max(0,value['net_minutes']),2),'remaining_deduction_minutes':round(max(0,-value['net_minutes']),2)} for value in values.values()]


def home_office_day(db,user,day):
    from home_office_models import HomeOfficeApplication
    if not inspect(db.connection()).has_table(HomeOfficeApplication.__tablename__):return {}
    row=db.query(HomeOfficeApplication).filter(HomeOfficeApplication.user_id==user.id,HomeOfficeApplication.requested_date==day,HomeOfficeApplication.status.in_(['pending','approved'])).first()
    return {'home_office_day':True,'home_office_approval_status':row.status} if row else {}


def check_in_home_overtime(db,user,rows,moment):
    import attendance_service as service
    existing=next((row for row in rows if row.segment==2),None)
    if existing:
        db.commit();return {'message':'已保留本日居家加班首次上班打卡','record':serialize(existing,service.day_leaves(db,user.id,existing.day))}
    if any(not row.check_out for row in rows):raise HTTPException(409,'请先完成当前班次的下班打卡，不能重复累计工作时间')
    pending=db.query(Clock).filter(Clock.user_id==user.id,Clock.day<moment.date(),Clock.check_out.is_(None)).first()
    pending=pending or db.query(AttendanceDay).filter(AttendanceDay.user_id==user.id,AttendanceDay.day==moment.date()-timedelta(days=1),AttendanceDay.check_out.is_(None)).first()
    if pending:raise HTTPException(409,'请先完成此前未签退的记录')
    shift={'code':'company_home_overtime','label':'公司要求居家加班','periods':[],'full_periods':[],'overtime_only':True,'home_office_day':True,'clock_policy':'manual-v1','segment':2,'fixed':False}
    row=Clock(user_id=user.id,day=moment.date(),segment=2,check_in=moment,shift_snapshot=shift,confirmations={'breakfast_notice_accepted':True,'work_mode':'company_home_overtime'})
    db.add(row);db.commit()
    return {'message':'公司要求居家加班上班打卡成功，不占居家申请额度','record':serialize(row,service.day_leaves(db,user.id,row.day))}
