"""服务端考勤时钟、班次快照、午休扣除与请假交集统计。"""
import logging,re,math
from datetime import date,datetime,time,timedelta
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from models import AppUser,EmployeeLeave
from attendance_models import AttendanceDay,AttendanceLeave
from chat_time import now,api_time,BUSINESS_TIMEZONE
from hr_access import require_hr
import monthly_shift as monthly
import weekly_shift as weekly
import fixed_shift
from work_report_calendar import is_workday,period_bounds

logger=logging.getLogger(__name__)

def stamp(value):return api_time(value)
def midnight(day):return datetime.combine(day,time.min,tzinfo=BUSINESS_TIMEZONE)
def ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in ('attendance_day','attendance_leave'))
def require_ready(db):
    if not ready(db):raise HTTPException(503,'考勤数据表尚未初始化，暂不能记录或查询')

def desktop_request(request):
    ua=request.headers.get('user-agent','')
    platform=request.headers.get('sec-ch-ua-platform','').strip('"').lower()
    return bool(ua and not re.search(r'Android|iPhone|iPad|iPod|Mobile',ua,re.I) and request.headers.get('sec-ch-ua-mobile')!='?1'
                and request.headers.get('x-client-type')!='mobile' and (platform in ('windows','macos','linux','chrome os') or re.search(r'Windows NT|Macintosh|X11|CrOS',ua)))

def shift_for(db,user,day):
    return shifts_for(db,[user],day).get(str(user.id))


def shifts_for(db,users,day):
    """与单人考勤共用班次优先级，批量查询不随候选人数增加。"""
    # 自然工作日及显式安排周末值班的日期适用班次；不将报告 07:00 换日规则套到考勤。
    import weekend_duty
    duty_ids=set()
    if weekend_duty.management.ready(db):
        plan=db.get(weekend_duty.management.WeekendDutyPublication,day.replace(day=1))
        duty_ids={row['user_id'] for row in (plan.assignments if plan else []) if row['date']==day.isoformat()}
    workday=is_workday(day)
    if not duty_ids and not workday:return {}
    start=day-timedelta(days=day.weekday())
    from weekly_shift_publication import WeeklyShiftPublication,ready as publication_ready
    row=db.get(WeeklyShiftPublication,start) if publication_ready(db) else None
    values=row.assignments if row else []
    weekly_entries={value['user_id']:value for value in values}
    start=day.replace(day=1)
    row=db.get(monthly.MonthlyShiftPlan,start) if monthly.ready(db) else None
    values=fixed_shift.effective(db,row.assignments if row else [],start)
    monthly_entries={value['user_id']:value for value in values}
    shifts={row['code']:row for row in monthly.SHIFTS}
    result={}
    for user in users:
        uid=str(user.id)
        if not workday and uid not in duty_ids:continue
        entry=weekly_entries.get(uid) or monthly_entries.get(uid)
        shift=shifts.get(entry['shift']) if entry else None
        if shift:result[uid]={**shift,'department':entry['department'],'weekend_duty':uid in duty_ids,'fixed':bool(entry.get('fixed'))}
    return result

def intervals(day,shift):
    result=[]
    for value in (shift or {}).get('periods',[]):
        start,end=re.split('[–—-]',value)
        left=datetime.combine(day,time.fromisoformat(start),tzinfo=BUSINESS_TIMEZONE)
        right=datetime.combine(day,time.fromisoformat(end),tzinfo=BUSINESS_TIMEZONE)
        if right<=left:right+=timedelta(days=1)
        result.append((left,right))
    return result

def overlap(left,right,start,end):return max(0,(min(right,end)-max(left,start)).total_seconds())
def merged(windows):
    values=[]
    for left,right in sorted(windows):
        if values and left<=values[-1][1]:values[-1]=(values[-1][0],max(right,values[-1][1]))
        else:values.append((left,right))
    return values

def metrics(row,leaves=()):
    day=row.day;periods=intervals(day,row.shift_snapshot)
    if not periods:return {'late_count':0,'late_minutes':0,'overtime_minutes':0,'lunch_deducted_minutes':0}
    check_in=stamp(row.check_in);check_out=stamp(row.check_out) if row.check_out else None
    windows=merged([(stamp(leave.start_date),stamp(leave.end_date)) for leave in leaves])
    expected=[]
    for left,right in periods:
        pieces=[(left,right)]
        for start,end in windows:
            pieces=[item for a,b in pieces for item in ((a,min(b,start)),(max(a,end),b)) if item[1]>item[0]]
        expected.extend(pieces)
    expected_start=expected[0][0] if expected else None
    # 迟到只统计班次内、扣除请假和休息后的应出勤时间，并减去 10 分钟宽限。
    missed=sum(overlap(a,b,a,min(b,check_in)) for a,b in expected)
    late=max(0,missed-600) if expected_start and check_in>expected_start else 0
    result={'late_count':int(late>0),'late_minutes':round(late/60,2),'overtime_minutes':0,'lunch_deducted_minutes':0}
    if not check_out:return result
    breaks=[(midnight(day)+timedelta(hours=12),midnight(day)+timedelta(hours=13,minutes=30))]
    # 居家班等分段班次的其他休息区间也不计出勤，避免将空档算作加班。
    breaks+= [(periods[index][1],periods[index+1][0]) for index in range(len(periods)-1)]
    exclusions=merged(breaks+windows)
    actual=max(0,(check_out-check_in).total_seconds()-sum(overlap(check_in,check_out,a,b) for a,b in exclusions))
    required=sum((b-a).total_seconds() for a,b in expected)
    result.update(overtime_minutes=round(max(0,actual-required)/60,2),lunch_deducted_minutes=round(overlap(check_in,check_out,*breaks[0])/60,2))
    return result

def serialize_day(row,leaves=()):
    return api_time({'id':str(row.id),'user_id':str(row.user_id),'day':row.day.isoformat(),'check_in':row.check_in,'check_out':row.check_out,'shift':row.shift_snapshot,**metrics(row,leaves)})

def auto_check_in(db,user,request):
    # 登录和旧客户端 arrival 只返回提示，不再代替本人完成上班打卡。
    return {'status':'manual_required' if desktop_request(request) else 'mobile','message':'请在工作台阅读早餐提示后点击上班打卡'}


def check_out(db,user,request,payload):
    from attendance_clock import check_out as clock_out
    return clock_out(db,user,request,payload)


def day_leaves(db,user_id,day):
    left=midnight(day).replace(tzinfo=None);right=left+timedelta(days=1)
    return db.query(EmployeeLeave).filter(EmployeeLeave.employee_id==user_id,EmployeeLeave.start_date<right,EmployeeLeave.end_date>left).all()

class LeaveWindow(BaseModel):
    start_at:datetime
    end_at:datetime
    @model_validator(mode='after')
    def valid(self):
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:raise ValueError('请假时间须包含 +08:00 时区')
        self.start_at=stamp(self.start_at);self.end_at=stamp(self.end_at)
        if self.end_at<=self.start_at or self.end_at-self.start_at>timedelta(days=31):raise ValueError('请假结束时间须晚于开始，单次最多 31 天')
        return self
class LeaveWrite(LeaveWindow):
    client_id:UUID
    reason:str=Field(min_length=1,max_length=500)

def preview_leave(db,user,payload):
    left=payload.start_at;right=payload.end_at;days=[]
    day=left.date()
    while midnight(day)<right:
        shift=shift_for(db,user,day)
        periods=intervals(day,shift)
        minutes=round(sum(overlap(left,right,a,b) for a,b in periods)/60,2)
        days.append({'day':day.isoformat(),'shift':shift,'minutes':minutes})
        day+=timedelta(days=1)
    return {'days':days,'minutes':round(sum(row['minutes'] for row in days),2),'note':'请假时长仅计算班次内时段，已扣除午休及其他班间休息；休息日不计时长。'}

def create_leave(db,user,payload):
    require_ready(db)
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(784312901)'))
    # 同一人员的重试和并发请求串行，避免重复请假、重复群发通知。
    db.query(AppUser).filter_by(id=user.id).with_for_update().one()
    existing=db.query(AttendanceLeave).filter_by(client_id=payload.client_id).first()
    if existing:
        if existing.user_id!=user.id:raise HTTPException(409,'请求标识已使用，请重新提交')
        return {'id':str(existing.id),'minutes':sum(row['minutes'] for row in existing.days),'message':'请假记录已保存，全员通知已生成'}
    if not payload.reason.strip():raise HTTPException(422,'请填写请假原因')
    if db.query(EmployeeLeave.id).filter(EmployeeLeave.employee_id==user.id,EmployeeLeave.start_date<payload.end_at.replace(tzinfo=None),EmployeeLeave.end_date>payload.start_at.replace(tzinfo=None)).first():raise HTTPException(409,'所选时段与已有请假重叠')
    preview=preview_leave(db,user,payload)
    if preview['minutes']<=0:raise HTTPException(422,'所选时段没有有效班次，请调整时段或联系行政部安排班次')
    uid=uuid4();moment=now()
    row=AttendanceLeave(id=uid,client_id=payload.client_id,user_id=user.id,start_at=payload.start_at,end_at=payload.end_at,reason=payload.reason.strip(),days=preview['days'],created_at=moment)
    db.add(row)
    db.add(EmployeeLeave(id=uid,employee_id=user.id,employee_name=user.full_name or user.username,start_date=payload.start_at.replace(tzinfo=None),end_date=payload.end_at.replace(tzinfo=None),reason=payload.reason.strip(),leave_type='请假',created_by=user.id,updated_by=user.id,created_at=moment.replace(tzinfo=None),updated_at=moment.replace(tzinfo=None)))
    from attendance_notifications import queue_leave_notifications,publish_leave_notifications
    events=queue_leave_notifications(db,user,row,preview['minutes'])
    db.commit()
    publish_leave_notifications(events)
    return {'id':str(uid),'minutes':preview['minutes'],'message':'请假记录已保存，全员通知已生成'}


def attendance_report(db,user,anchor,period,*,admin=False,keyword='',department='',page=1,limit=50):
    require_ready(db)
    if admin:require_hr(db,user)
    if period not in ('week','month'):raise HTTPException(422,'请选择周或月统计')
    start,end=period_bounds(anchor,period);end_exclusive=end+timedelta(days=1)
    from organization_service import directory
    # 名册及主部门、跨部门使用同一过滤范围；本人接口绝不接受其他人员选择。
    catalog=directory(db,user)
    candidates=catalog['people'] if admin else [person for person in catalog['people'] if person['id']==str(user.id)]
    terms=keyword.casefold().split()
    people={person['id']:person for person in candidates if all(term in f"{person['name']} {person['username']}".casefold() for term in terms)
            and (not department or any(str(item['id'])==department for item in person['departments']))}
    ids=[UUID(uid) for uid in people]
    punches=db.query(AttendanceDay).filter(AttendanceDay.user_id.in_(ids),AttendanceDay.day>=start,AttendanceDay.day<=end).all() if ids else []
    leaves=db.query(EmployeeLeave).filter(EmployeeLeave.employee_id.in_(ids),EmployeeLeave.start_date<midnight(end_exclusive).replace(tzinfo=None),EmployeeLeave.end_date>midnight(start).replace(tzinfo=None)).all() if ids else []
    snapshots={row.id:row for row in db.query(AttendanceLeave).filter(AttendanceLeave.id.in_([leave.id for leave in leaves])).all()} if leaves else {}
    daily={};leave_items=[]
    def item(uid,day):
        key=(str(uid),day)
        if key not in daily:
            person=people[str(uid)]
            daily[key]={'user_id':str(uid),'name':person['name'],'username':person['username'],'department':'、'.join(row['name'] for row in person['departments']),'day':day.isoformat(),'check_in':None,'check_out':None,'shift':None,'late_count':0,'late_minutes':0,'overtime_minutes':0,'lunch_deducted_minutes':0,'leave_minutes':0,'leaves':[]}
        return daily[key]
    for leave in leaves:
        if leave.id in snapshots:days=snapshots[leave.id].days
        else:
            employee=db.get(AppUser,leave.employee_id)
            left=max(stamp(leave.start_date),midnight(start));right=min(stamp(leave.end_date),midnight(end_exclusive))
            days=preview_leave(db,employee,LeaveWindow(start_at=left,end_at=right))['days']
        selected=[row for row in days if start.isoformat()<=row['day']<=end.isoformat() and row['minutes']>0]
        total=round(sum(row['minutes'] for row in selected),2)
        leave_items.append({'id':str(leave.id),'user_id':str(leave.employee_id),'name':people[str(leave.employee_id)]['name'],'start_at':stamp(leave.start_date),'end_at':stamp(leave.end_date),'reason':leave.reason,'minutes':total,'days':selected})
        for value in selected:
            current=item(leave.employee_id,date.fromisoformat(value['day']))
            current['leave_minutes']+=value['minutes'];current['shift']=value['shift']
            current['leaves'].append({'id':str(leave.id),'start_at':stamp(leave.start_date),'end_at':stamp(leave.end_date),'reason':leave.reason,'minutes':value['minutes']})
    from attendance_clock import Clock,ready as clock_ready,serialize as serialize_clock
    sessions=db.query(Clock).filter(Clock.user_id.in_(ids),Clock.day>=start,Clock.day<=end).order_by(Clock.day,Clock.segment).all() if ids and clock_ready(db) else []
    session_keys={(row.user_id,row.day) for row in sessions}
    for row in punches:
        if (row.user_id,row.day) in session_keys:continue
        current=item(row.user_id,row.day)
        current.update(serialize_day(row,[leave for leave in leaves if leave.employee_id==row.user_id]))
    for row in sessions:
        current=item(row.user_id,row.day)
        value=serialize_clock(row,[leave for leave in leaves if leave.employee_id==row.user_id])
        entries=current.setdefault('sessions',[]);entries.append(value);entries.sort(key=lambda entry:entry['check_in'])
        current['check_in']=entries[0]['check_in'];current['check_out']=max(entry['check_out'] for entry in entries) if all(entry['check_out'] for entry in entries) else None
        regular=next((entry for entry in entries if not entry['shift'].get('overtime_only')),entries[0])
        current['shift']={**regular['shift'],'periods':regular['shift'].get('full_periods',regular['shift']['periods'])}
        keys=('late_count','late_minutes','overtime_minutes','lunch_deducted_minutes','raw_overtime_minutes','breakfast_deduction_minutes','dinner_deduction_minutes','invalid_deduction_minutes','violation_count')
        for key in keys:current[key]=round(sum(entry.get(key,0) for entry in entries),2)
        current['deduction_details']=[detail for entry in entries for detail in entry.get('deduction_details',[])]
    from attendance_models import AttendanceDelayStart
    if ids and inspect(db.connection()).has_table(AttendanceDelayStart.__tablename__):
        delays=db.query(AttendanceDelayStart).filter(AttendanceDelayStart.user_id.in_(ids),AttendanceDelayStart.requested_start>=midnight(start),AttendanceDelayStart.requested_start<midnight(end_exclusive)).all()
        for delay in delays:
            current=item(delay.user_id,stamp(delay.requested_start).date())
            current.setdefault('delay_start_requests',[]).append({'requested_start':stamp(delay.requested_start),'reason':delay.reason,'created_at':stamp(delay.created_at)})
    from work_report_lunch import reports as lunch_reports,credited as lunch_credited
    lunch_values=lunch_reports(db,ids,start,end)
    clock_rows=[*sessions,*[row for row in punches if (row.user_id,row.day) not in session_keys]]
    for (uid,day),value in lunch_values.items():
        current=item(uid,day)
        reported,credited=lunch_credited(value,day,[row for row in clock_rows if row.user_id==uid and row.day==day])
        original_lunch=current.get('lunch_deducted_minutes',0)
        current['raw_overtime_minutes']=current.get('raw_overtime_minutes',current['overtime_minutes'])+credited
        current['overtime_minutes']+=credited
        current.update(lunch_reported_minutes=reported,lunch_overtime_minutes=credited,lunch_original_deducted_minutes=original_lunch,lunch_deducted_minutes=max(0,original_lunch-credited),lunch_projects=value['projects'])
    totals={key:0 for key in ('late_count','late_minutes','overtime_minutes','leave_minutes','raw_overtime_minutes','breakfast_deduction_minutes','dinner_deduction_minutes','invalid_deduction_minutes','violation_count','lunch_overtime_minutes')}
    summaries={uid:{'user_id':uid,'name':person['name'],'department':'、'.join(row['name'] for row in person['departments']),**totals} for uid,person in people.items()}
    for row in daily.values():
        for key in totals:
            totals[key]+=row.get(key,0);summaries[row['user_id']][key]+=row.get(key,0)
    period_months={}
    for row in daily.values():
        key=(row['user_id'],row['day'][:7]);period_months[key]=period_months.get(key,0)+row['overtime_minutes']
    for uid,summary in summaries.items():
        summary['overtime_net_minutes']=round(summary['overtime_minutes'],2);summary['overtime_minutes']=round(sum(max(0,value) for (person_id,_),value in period_months.items() if person_id==uid),2)
    totals['overtime_net_minutes']=round(totals['overtime_minutes'],2)
    totals['overtime_minutes']=round(sum(summary['overtime_minutes'] for summary in summaries.values()),2)
    from attendance_clock import monthly_balances
    from employee_employment import allowances
    annual_allowances=allowances(db,ids,anchor.year)
    for uid,summary in summaries.items():summary.update(annual_allowances.get(uid,{}))
    balances=[{**value,'name':people[value['user_id']]['name']} for value in monthly_balances(db,ids,start,end)]
    rows=sorted(daily.values(),key=lambda row:(row['day'],row['name']),reverse=True)
    return api_time({'start':start,'end':end,'period':period,'annual_leave':annual_allowances.get(str(user.id)) if not admin else None,'monthly_balances':balances,'totals':{key:round(value,2) for key,value in totals.items()},'people':list(summaries.values()),'records':rows[(page-1)*limit:page*limit],'total':len(rows),'leaves':leave_items,'departments':catalog['items'] if admin else [],'note':'迟到从宽限 10 分钟后累计；手动打卡后按确认的真实工作时间计算加班；扣除午休、班间休息、请假及早餐、晚餐、无效时间。每日负净额继续抵扣当月累计加班，最终累计不低于零。'})

def today_status(db,user):
    from attendance_clock import today_status as clock_status
    return clock_status(db,user)


def leave_badges(db,assignments,start,weekly_period=False):
    if not assignments or not ready(db):return assignments
    end=start+timedelta(days=6) if weekly_period else (start.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)
    rows=db.query(AttendanceLeave).filter(AttendanceLeave.user_id.in_([UUID(row['user_id']) for row in assignments]),AttendanceLeave.start_at<midnight(end+timedelta(days=1)),AttendanceLeave.end_at>midnight(start)).all()
    output=[]
    for assignment in assignments:
        leaves=[]
        for row in rows:
            if str(row.user_id)!=assignment['user_id']:continue
            minutes=sum(day['minutes'] for day in row.days if start.isoformat()<=day['day']<=end.isoformat())
            if minutes:leaves.append({'id':str(row.id),'start_at':stamp(row.start_at),'end_at':stamp(row.end_at),'minutes':minutes})
        output.append({**assignment,'leave_minutes':round(sum(row['minutes'] for row in leaves),2),'leaves':leaves})
    return output
