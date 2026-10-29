"""实际完成的周末值班→补班优先→剩余额度待审批调休。"""
from datetime import date,timedelta
from uuid import UUID,uuid4
import math
from sqlalchemy import inspect
from fastapi import HTTPException
from models import AppUser
from attendance_models import AttendanceCompTimeRequest as CompRequest,AttendanceLeave
from employee_employment import EmployeeEmployment,ready as employment_ready
from attendance_policy import clock_sources,lateness_events,month_end,monthly
from attendance_service import LeaveWrite,preview_leave,midnight,stamp,intervals,overlap,merged
from chat_time import now,api_time


def ready(db):return inspect(db.connection()).has_table(CompRequest.__tablename__)


def month_keys(start,end):
    day=start.replace(day=1);result=[]
    while day<=end:
        result.append(day.strftime('%Y-%m'));day=month_end(day)+timedelta(days=1)
    return result


def allocation(duties,obligations,requests,hire,cutoff):
    """纯计算：分钟FIFO分配，所有来源保留；待审批申请也预留。"""
    exempt=hire.strftime('%Y-%m') if hire and (month_end(hire)-hire).days+1<=15 else None
    months=[value for value in month_keys(hire,cutoff) if value!=exempt] if hire and hire<=cutoff else []
    counts={};extra=[];details=[]
    for duty in sorted(duties,key=lambda item:(item['day'],item['id'])):
        month=duty['day'][:7];counts[month]=counts.get(month,0)+1
        eligible=month==exempt or counts[month]>1
        value={**duty,'extra':eligible,'available_minutes':duty['minutes'] if eligible else 0,'uses':[]}
        details.append(value)
        if eligible:extra.append(value)
    # 无值班月份也须补足累计每月1天基数，避免只计算有值班的月份。
    missing_base=max(0,len(months)-sum(bool(counts.get(month)) for month in months))
    for item in extra[:missing_base]:
        item['uses'].append({'duty_id':item['id'],'day':item['day'],'minutes':item['available_minutes'],'kind':'baseline','source_id':'累计未完成月份的每月1天基数'})
        item['available_minutes']=0
    def take(minutes,kind,source_id):
        output=[]
        for item in extra:
            amount=min(minutes,item['available_minutes'])
            if amount>0:
                item['available_minutes']=round(item['available_minutes']-amount,2);minutes=round(minutes-amount,2)
                link={'duty_id':item['id'],'day':item['day'],'minutes':amount,'kind':kind,'source_id':source_id}
                output.append(link);item['uses'].append(link)
            if minutes<=0:break
        return output,max(0,minutes)
    leave_details=[]
    for item in sorted(obligations,key=lambda item:(item['day'],item['id'])):
        links,remaining=take(item['minutes'],'makeup',item['id'])
        leave_details.append({**item,'makeup_links':links,'makeup_minutes':round(item['minutes']-remaining,2),'remaining_minutes':remaining})
    request_details=[]
    for item in sorted(requests,key=lambda item:(item['created_at'],item['id'])):
        links,remaining=take(item['minutes'],'comp_time',item['id'])
        request_details.append({**item,'reserved_links':links,'uncovered_minutes':remaining})
    # 完整自然月为统计单位，当前月为暂计；首月免值班时也不计入平均分母。
    average=round(len(duties)/len(months),4) if months else 0
    eligible=bool(hire and months and len(duties)>len(months))
    available=round(sum(item['available_minutes'] for item in extra),2) if eligible else 0
    return {'hire_date':hire,'exempt_month':exempt,'counted_months':len(months),'duty_days':len(duties),'average_days':average,'eligible':eligible,'available_minutes':available,'extra_minutes':round(sum(item['minutes'] for item in extra),2),'makeup_remaining_minutes':round(sum(item['remaining_minutes'] for item in leave_details),2),'reserved_minutes':sum(item['minutes'] for item in requests),'duties':details,'obligations':leave_details,'requests':request_details}


def request_value(row):return api_time({'id':str(row.id),'user_id':str(row.user_id),'start_at':row.start_at,'end_at':row.end_at,'minutes':row.minutes,'reason':row.reason,'status':row.status,'created_at':row.created_at,'allocation_snapshot':row.allocation_snapshot})


def balances(db,users,cutoff):
    ids=[user.id for user in users]
    hires={row.user_id:row.hire_date for row in db.query(EmployeeEmployment).filter(EmployeeEmployment.user_id.in_(ids)).all()} if ids and employment_ready(db) else {}
    left=min([value for value in hires.values() if value and value<=cutoff] or [date(cutoff.year,1,1)])
    clocks,leaves=clock_sources(db,ids,left,cutoff)
    # 已提交的未来请假同样先占用补班，不能先调休再使同一时长重复补班。
    from models import EmployeeLeave
    if ids:
        leaves=db.query(EmployeeLeave).filter(EmployeeLeave.employee_id.in_(ids),EmployeeLeave.end_date>midnight(left).replace(tzinfo=None)).all()
    late=lateness_events(clocks,leaves)
    snapshots={row.id:row for row in db.query(AttendanceLeave).filter(AttendanceLeave.user_id.in_(ids)).all()} if ids else {}
    requests=db.query(CompRequest).filter(CompRequest.user_id.in_(ids),CompRequest.status.in_(['pending','approved'])).all() if ids and ready(db) else []
    output=[]
    for user in users:
        hire=hires.get(user.id);begin=hire or left
        own=[row for row in clocks if row.user_id==user.id and begin<=row.day<=cutoff]
        duty_days={}
        for row in own:
            shift=row.shift_snapshot
            if row.day.weekday()<5 or not shift.get('weekend_duty') or shift.get('overtime_only'):continue
            from work_report_calendar import CALENDARS
            calendar=CALENDARS.get(row.day.year)
            value=row.day.strftime('%m-%d')
            # 法定节假日另走待开发规则；调休补工作日不是额外周末值班。
            if not calendar or value in calendar['workdays'] or any(a<=value<=b for a,b in calendar['holidays']):continue
            duty_days.setdefault(row.day,[]).append(row)
        duties=[]
        for day,rows in duty_days.items():
            if any(not row.check_out for row in rows):continue
            if any(row.shift_snapshot.get('code')=='customer_remote' and hasattr(row,'segment') and not getattr(row,'confirmations',{}).get('legacy_completed') for row in rows) and len(rows)<2:continue
            windows=[]
            for row in rows:
                windows.extend((max(stamp(row.check_in),a),min(stamp(row.check_out),b)) for a,b in intervals(day,row.shift_snapshot) if min(stamp(row.check_out),b)>max(stamp(row.check_in),a))
            exclusions=merged([(stamp(item.start_date),stamp(item.end_date)) for item in leaves if item.employee_id==user.id]+[(midnight(day)+timedelta(hours=12),midnight(day)+timedelta(hours=13,minutes=30))])
            minutes=sum(max(0,(b-a).total_seconds()-sum(overlap(a,b,c,d) for c,d in exclusions))/60 for a,b in merged(windows))
            minutes=max(0,minutes-sum((getattr(row,'confirmations',{}) or {}).get('invalid_minutes',0) for row in rows))
            if minutes>0:duties.append({'id':f'duty:{user.id}:{day}','day':day.isoformat(),'minutes':round(minutes,2),'clock_ids':[str(row.id) for row in rows],'home':any(row.shift_snapshot.get('home_office_day') or row.shift_snapshot.get('code')=='customer_remote' for row in rows)})
        obligations=[{**item,'day':item['day']} for item in late if item['user_id']==str(user.id) and item['day']>=begin.isoformat()]
        for leave in leaves:
            if leave.employee_id!=user.id:continue
            from types import SimpleNamespace
            days=snapshots[leave.id].days if leave.id in snapshots else preview_leave(db,user,SimpleNamespace(start_at=max(stamp(leave.start_date),midnight(begin)),end_at=stamp(leave.end_date)))['days']
            for item in days:
                if begin.isoformat()<=item['day'] and item['minutes']>0:obligations.append({'id':f'leave:{leave.id}:{item["day"]}','leave_id':str(leave.id),'day':item['day'],'source':'application','reason':leave.reason,'minutes':item['minutes'],'future':item['day']>cutoff.isoformat()})
        values=allocation(duties,obligations,[{key:value for key,value in request_value(row).items() if key!='allocation_snapshot'} for row in requests if row.user_id==user.id],hire,cutoff)
        output.append({**values,'user_id':str(user.id),'name':user.full_name or user.username,'cutoff':cutoff,'ready':ready(db)})
    return api_time(output)


def overview(db,user,year,admin=False):
    from hr_access import require_hr
    if admin:require_hr(db,user)
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    users=db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).order_by(AppUser.full_name,AppUser.username).all() if admin else [user]
    cutoff=now().date();end=min(date(year,12,31),cutoff)
    policies=monthly(db,[item.id for item in users],date(year,1,1),end) if year<=cutoff.year else []
    names={str(item.id):item.full_name or item.username for item in users}
    for item in policies:item['name']=names[item['user_id']]
    return api_time({'year':year,'balances':balances(db,users,cutoff),'monthly_policy':policies,'approval_note':'调休、请假等批准流程统一待开发；提交申请仅预留额度，不视为已获批准。'})


def submit(db,user,payload):
    from attendance_clock import lock
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    if not ready(db):raise HTTPException(503,'调休申请表尚未初始化')
    lock(db,user)
    existing=db.query(CompRequest).filter_by(client_id=payload.client_id).first()
    if existing:
        if existing.user_id!=user.id:raise HTTPException(409,'申请标识已使用')
        return {'record':request_value(existing),'message':'该申请已撤回，请新建申请' if existing.status=='cancelled' else '申请已保存，审批待开发'}
    if not payload.reason.strip():raise HTTPException(422,'请填写调休事由')
    if payload.start_at<now():raise HTTPException(422,'请选择未来的调休时段')
    from models import EmployeeLeave
    if db.query(EmployeeLeave.id).filter(EmployeeLeave.employee_id==user.id,EmployeeLeave.start_date<payload.end_at.replace(tzinfo=None),EmployeeLeave.end_date>payload.start_at.replace(tzinfo=None)).first():raise HTTPException(409,'调休时段与已有请假重叠')
    if db.query(CompRequest).filter(CompRequest.user_id==user.id,CompRequest.status.in_(['pending','approved']),CompRequest.start_at<payload.end_at,CompRequest.end_at>payload.start_at).first():raise HTTPException(409,'与已有调休申请重叠')
    value=balances(db,[user],now().date())[0]
    if not value['eligible']:raise HTTPException(422,'累计实际周末值班平均须超过每月1天；请先补全入职时间及实际值班记录')
    preview=preview_leave(db,user,payload);minutes=math.ceil(preview['minutes'])
    if minutes<=0:raise HTTPException(422,'所选时段没有应出勤班次')
    if minutes>value['available_minutes']:raise HTTPException(422,'补班及已申请调休占用后，剩余多值班时长不足')
    from fastapi.encoders import jsonable_encoder
    snapshot=jsonable_encoder(api_time({'balance':value,'days':preview['days'],'policy':'makeup-first-v1'}))
    row=CompRequest(id=uuid4(),client_id=payload.client_id,user_id=user.id,start_at=payload.start_at,end_at=payload.end_at,minutes=minutes,reason=payload.reason.strip(),status='pending',allocation_snapshot=snapshot,created_at=now())
    db.add(row);db.commit()
    return {'record':request_value(row),'message':'调休申请已保存并预留额度；审批待开发，尚未批准'}


def cancel(db,user,request_id):
    from attendance_clock import lock
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    if not ready(db):raise HTTPException(503,'调休申请表尚未初始化')
    lock(db,user)
    row=db.query(CompRequest).filter_by(id=request_id,user_id=user.id).with_for_update().first()
    if not row:raise HTTPException(404,'未找到本人的调休申请')
    if row.status not in ('pending','cancelled'):raise HTTPException(409,'只能撤回待审批申请')
    if row.status!='cancelled':row.allocation_snapshot={**row.allocation_snapshot,'cancelled_at':api_time(now()).isoformat(),'cancelled_by':str(user.id)}
    row.status='cancelled';db.commit()
    return {'id':str(row.id),'status':row.status,'message':'申请已撤回，预留额度已释放'}
