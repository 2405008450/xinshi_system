"""居家资格、日申请额度与行政通知；不把待审批记录当作获批。"""
import calendar
from datetime import date,datetime,timedelta
from uuid import UUID,uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import inspect,text
from models import AppUser,AppNotification
from department_models import Department,DepartmentMember
from employee_employment import EmployeeEmployment
from home_office_models import HomeOfficeQualification as Qualification,HomeOfficeApplication as Application,HomeOfficeAnnualUsage as AnnualUsage,HomeOfficeApplicationDuration as Duration
from chat_time import now,api_time
from work_report_calendar import is_workday


class QualificationWrite(BaseModel):
    client_id:UUID
    reason:str=Field(min_length=1,max_length=1000)
    @field_validator('reason')
    @classmethod
    def clean(cls,value):
        if not value.strip():raise ValueError('请填写申请理由')
        return value.strip()


class ApplicationWrite(BaseModel):
    client_id:UUID
    requested_date:date
    minutes:Literal[120,240,480]=480
    reason:str=Field(default='',max_length=1000)
    @field_validator('reason')
    @classmethod
    def clean(cls,value):return value.strip()


class UsageWrite(BaseModel):
    user_id:UUID
    year:int=Field(ge=2000,le=9999)
    used_days:int=Field(ge=0,le=366)
    revision:int=Field(ge=0)
    note:str=Field(default='',max_length=500)


def add_months(day,months):
    year,month=divmod(day.year*12+day.month-1+months,12);month+=1
    if year>9999:return date.max
    return date(year,month,min(day.day,calendar.monthrange(year,month)[1]))


def ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in ('employee_employment','home_office_qualification','home_office_application','home_office_annual_usage'))


def require_ready(db):
    if not ready(db):raise HTTPException(503,'居家办公申请数据表尚未初始化')


def active(user):
    if not user or not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')


def lock(db,user):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(731946,:uid)'),{'uid':user.id.int%2147483647})
    db.query(AppUser).filter_by(id=user.id).with_for_update().one()


def manager(db):
    rows=db.query(AppUser).join(DepartmentMember,DepartmentMember.user_id==AppUser.id).filter(AppUser.full_name=='赵震锋',AppUser.is_active.is_(True),AppUser.is_deleted.is_(False),DepartmentMember.position=='总经理').all()
    unique={row.id:row for row in rows}
    return next(iter(unique.values())) if len(unique)==1 else None


def eligibility(db,user,on_date=None):
    day=on_date or now().date();row=db.get(EmployeeEmployment,user.id)
    hire=row.hire_date if row else None
    pending=db.query(Qualification).filter_by(user_id=user.id,status='pending').first()
    approved=db.query(Qualification).filter_by(user_id=user.id,status='approved').first()
    apply_on=add_months(hire,3) if hire else None;automatic_on=add_months(hire,6) if hire else None
    automatic=bool(hire and day>=automatic_on);qualified=automatic or bool(approved)
    return api_time({'hire_date':hire,'qualification_apply_on':apply_on,'automatic_on':automatic_on,'qualified':qualified,'automatic':automatic,
        'can_apply_qualification':bool(hire and day>=apply_on and not qualified and not pending),'qualification_pending':pending is not None,
        'qualification_hint':'请先由人员管理填写入职时间' if not hire else '入职已满6个月，自动获得资格' if automatic else '已获批居家办公资格' if approved else '资格申请待审批；审批功能待开发' if pending else '已满3个月，可以提出资格申请（理由必填）' if day>=apply_on else '入职满3个月后可以提出资格申请'})


def annual_limit(hire,year):
    if hire is None:return 0
    start=add_months(hire,3);count=0
    for month in range(1,13):
        left=max(start,date(year,month,1));right=date(year,month,calendar.monthrange(year,month)[1])
        if (right-left).days+1>=20:count+=1
    return min(12,count)


def durations(db,rows):
    ids=[row.id for row in rows]
    return {row.application_id:row.minutes for row in db.query(Duration).filter(Duration.application_id.in_(ids)).all()} if ids and inspect(db.connection()).has_table(Duration.__tablename__) else {}


def application_values(db,rows):
    lengths=durations(db,rows)
    return [{'id':str(row.id),'requested_date':row.requested_date,'reason':row.reason,'status':row.status,'created_at':row.created_at,'minutes':lengths.get(row.id,480),'hours':lengths.get(row.id,480)/60,'user_id':str(row.user_id)} for row in rows]


def quota(db,user,day):
    hire_row=db.get(EmployeeEmployment,user.id);hire=hire_row.hire_date if hire_row else None
    rows=db.query(Application).filter(Application.user_id==user.id,Application.status.in_(['pending','approved'])).all()
    values=application_values(db,rows)
    month=[row for row in values if row['requested_date'].year==day.year and row['requested_date'].month==day.month]
    month_minutes=sum(row['minutes'] for row in month);partial=sum(row['minutes'] for row in month if row['minutes']<480)
    two_count=sum(row['minutes']==120 for row in month);full_count=sum(row['minutes']==480 for row in month)
    year_minutes=sum(row['minutes'] for row in values if row['requested_date'].year==day.year);limit=annual_limit(hire,day.year)
    manual=db.get(AnnualUsage,(user.id,day.year));manual_days=manual.used_days if manual else 0
    manual_ready=manual is not None or day.year>now().year
    annual_minutes=year_minutes+manual_days*480
    quarter=(day.month-1)//3;half=(day.month-1)//6
    quarter_minutes=sum(row['minutes'] for row in values if row['requested_date'].year==day.year and (row['requested_date'].month-1)//3==quarter)
    half_minutes=sum(row['minutes'] for row in values if row['requested_date'].year==day.year and (row['requested_date'].month-1)//6==half)
    messages=[]
    if not manual_ready:messages.append('请先联系行政部补录今年已居家天数（含0天）')
    if month_minutes>=960:messages.append('本月16小时已满')
    if quarter_minutes>=4*480:messages.append('本季度4天已满')
    if half_minutes>=8*480:messages.append('本半年8天已满')
    if annual_minutes>=limit*480:messages.append(f'{day.year}年度额度{limit}天已满')
    options=[]
    for minutes in (120,240,480):
        if month_minutes+minutes>960 or quarter_minutes+minutes>4*480 or half_minutes+minutes>8*480 or annual_minutes+minutes>limit*480:continue
        if minutes==480 and full_count>=1:continue
        if minutes<480 and partial+minutes>480:continue
        if minutes==120 and two_count>=2:continue
        options.append(minutes)
    if not options and not messages:messages.append('本月剩余时长不满足申请组合或周期剩余额度不足')
    reason='；'.join(messages)+'，不能再申请' if messages else None
    return {'month_limit':2,'month_used':month_minutes/480,'month_hours':month_minutes/60,'month_hour_limit':16,'partial_hours':partial/60,'two_hour_count':two_count,'full_day_count':full_count,'allowed_minutes':options if manual_ready else [],'quarter_limit':4,'quarter_used':quarter_minutes/480,'half_limit':8,'half_used':half_minutes/480,'annual_limit':limit,'annual_used':annual_minutes/480,'manual_used_days':manual_days if manual_ready else None,'manual_usage_ready':manual_ready,'system_used_days':year_minutes/480,'annual_remaining':max(0,(limit*480-annual_minutes)/480),'limit_message':reason,'quota_available':reason is None}


def records(db,user):
    return api_time({'qualification_requests':[{'id':str(row.id),'reason':row.reason,'status':row.status,'created_at':row.created_at} for row in db.query(Qualification).filter_by(user_id=user.id).order_by(Qualification.created_at.desc()).all()],
        'applications':application_values(db,db.query(Application).filter_by(user_id=user.id).order_by(Application.requested_date.desc()).all())})


def overview(db,user,requested_date=None):
    active(user)
    if not ready(db):return {'ready':False,'qualification_hint':'居家办公申请尚未初始化','applications':[],'qualification_requests':[]}
    day=requested_date or now().date();state=eligibility(db,user)
    approver=manager(db)
    return {**state,**quota(db,user,day),**records(db,user),'ready':True,'quota_date':day.isoformat(),'approver_name':'总经理 赵震锋','approver_ready':approver is not None,'approval_note':'审批：待开发'}


def notify(db,user,row,kind):
    from organization_service import department_condition
    recipients=db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False),department_condition(db,['行政部','行政部门'])).all()
    approver=manager(db)
    if kind=='qualification' and approver and all(target.id!=approver.id for target in recipients):recipients.append(approver)
    if not recipients:raise HTTPException(503,'行政部尚无在用人员，申请未提交，请联系管理员')
    title=f'居家办公{"资格" if kind=="qualification" else ""}申请 · {user.full_name or user.username}'
    content=f'{user.full_name or user.username} 提交居家办公{"资格" if kind=="qualification" else ""}申请。'+(f'申请日期：{row.requested_date.isoformat()}，时长 {getattr(row,"request_minutes",480)/60:g} 小时。' if kind!='qualification' else '批准人：总经理 赵震锋。')+f'理由：{row.reason}。审批：待开发。'
    moment=now();events=[]
    for target in recipients:
        notice=AppNotification(id=uuid4(),recipient_user_id=target.id,title=title,content=content,notification_type='home_office_application',related_entity_id=row.id,is_read=False,created_at=moment.replace(tzinfo=None))
        db.add(notice);events.append((target.id,{'type':'notification','notification':{'id':str(notice.id),'recipient_user_id':str(target.id),'title':title,'content':content,'notification_type':'home_office_application','related_entity_id':str(row.id),'is_read':False,'created_at':moment.isoformat()}}))
    return events


def publish(events):
    from attendance_notifications import publish_leave_notifications
    publish_leave_notifications(events)


def apply_qualification(db,user,payload):
    active(user);require_ready(db);lock(db,user)
    existing=db.query(Qualification).filter_by(client_id=payload.client_id).first()
    if existing:
        if existing.user_id!=user.id:raise HTTPException(409,'申请标识已使用')
        return {'message':'资格申请已提交，请勿重复提交',**overview(db,user)}
    state=eligibility(db,user)
    if not state['can_apply_qualification']:raise HTTPException(409,state['qualification_hint'])
    approver=manager(db)
    if not approver:raise HTTPException(503,'组织架构尚未配置总经理赵震锋，资格申请未提交')
    row=Qualification(id=uuid4(),client_id=payload.client_id,user_id=user.id,reason=payload.reason,status='pending',approver_id=approver.id,created_at=now());db.add(row)
    try:events=notify(db,user,row,'qualification');db.commit()
    except Exception:db.rollback();raise
    publish(events)
    return {'message':'资格申请已通知行政部及总经理赵震锋；审批待开发',**overview(db,user)}


def apply(db,user,payload):
    active(user);require_ready(db);lock(db,user)
    existing=db.query(Application).filter_by(client_id=payload.client_id).first()
    if existing:
        if existing.user_id!=user.id or existing.requested_date!=payload.requested_date or existing.reason!=payload.reason or durations(db,[existing]).get(existing.id,480)!=payload.minutes:raise HTTPException(409,'申请标识已使用')
        return {'message':'申请已提交，请勿重复提交',**overview(db,user,payload.requested_date)}
    state=eligibility(db,user)
    if not state['qualified']:raise HTTPException(409,'尚未获得居家办公资格；未满6个月须先获资格批准')
    day=payload.requested_date
    if day<now().date():raise HTTPException(422,'不能申请已经过去的日期')
    if not is_workday(day):raise HTTPException(422,'请选择工作日，每次可申请2、4或8小时')
    if db.query(Application.id).filter_by(user_id=user.id,requested_date=day).first():raise HTTPException(409,'该日期已提交申请，不能重复申请')
    limits=quota(db,user,day)
    if not limits['quota_available']:raise HTTPException(409,limits['limit_message'])
    if payload.minutes not in limits['allowed_minutes']:raise HTTPException(409,'本月可拆分8小时限2+2+4或4+4，2小时最多2次，另外8小时须整段申请；当前组合或周期剩余额度不足')
    if not inspect(db.connection()).has_table(Duration.__tablename__):raise HTTPException(503,'居家申请时长表尚未初始化')
    if payload.minutes<480:
        from attendance_models import AttendanceClockSession
        if inspect(db.connection()).has_table(AttendanceClockSession.__tablename__) and db.query(AttendanceClockSession).filter(AttendanceClockSession.user_id==user.id,AttendanceClockSession.day==day,AttendanceClockSession.segment!=2).count()>2:raise HTTPException(409,'当天已有超过两组的打卡记录，不能按2/4小时居家申请')
    row=Application(id=uuid4(),client_id=payload.client_id,user_id=user.id,requested_date=day,reason=payload.reason,status='pending',created_at=now());db.add(row)
    db.flush();db.add(Duration(application_id=row.id,minutes=payload.minutes));row.request_minutes=payload.minutes
    try:events=notify(db,user,row,'application');db.commit()
    except Exception:db.rollback();raise
    publish(events)
    return {'message':'居家办公申请已通知行政部；审批待开发',**overview(db,user,day)}


def company(db,user):
    from hr_access import require_hr
    from organization_service import directory
    require_hr(db,user);require_ready(db)
    people={person['id']:person for person in directory(db,user)['people']}
    from attendance_models import AttendanceClockSession
    overtime=db.query(AttendanceClockSession).filter(AttendanceClockSession.segment==2).order_by(AttendanceClockSession.check_in.desc()).limit(500).all()
    overtime_records=[{'id':row.id,'name':people.get(str(row.user_id),{}).get('name','已删除人员'),'day':row.day,'check_in':row.check_in,'check_out':row.check_out,'invalid_minutes':row.confirmations.get('invalid_minutes',0),'invalid_reason':row.confirmations.get('invalid_reason','')} for row in overtime]
    applications=application_values(db,db.query(Application).order_by(Application.created_at.desc()).limit(500).all())
    for item in applications:item['name']=people.get(item['user_id'],{}).get('name','已删除人员')
    return api_time({'company_overtime':overtime_records,'year':now().year,'usage_people':usage_people(db,people),'applications':applications,
        'qualification_requests':[{'id':row.id,'name':people.get(str(row.user_id),{}).get('name','已删除人员'),'reason':row.reason,'status':row.status,'created_at':row.created_at} for row in db.query(Qualification).order_by(Qualification.created_at.desc()).limit(500).all()],'approval_note':'审批：待开发'})


def usage_people(db,people):
    year=now().year;ids=[UUID(uid) for uid in people]
    usage={str(row.user_id):row for row in db.query(AnnualUsage).filter(AnnualUsage.user_id.in_(ids),AnnualUsage.year==year).all()} if ids else {}
    hires={str(row.user_id):row.hire_date for row in db.query(EmployeeEmployment).filter(EmployeeEmployment.user_id.in_(ids)).all()} if ids else {}
    system={}
    requests=db.query(Application).filter(Application.user_id.in_(ids),Application.requested_date>=date(year,1,1),Application.requested_date<date(year+1,1,1),Application.status.in_(['pending','approved'])).all() if ids else []
    for item in application_values(db,requests):system[item['user_id']]=system.get(item['user_id'],0)+item['minutes']/480
    return [{'user_id':uid,'name':person['name'],'year':year,'hire_date':hires.get(uid),'manual_used_days':usage[uid].used_days if uid in usage else None,'revision':usage[uid].revision if uid in usage else 0,'system_used_days':system.get(uid,0),'annual_limit':annual_limit(hires.get(uid),year),'annual_used':(usage[uid].used_days if uid in usage else 0)+system.get(uid,0),'history':usage[uid].history if uid in usage else []} for uid,person in people.items()]


def save_usage(db,user,payload):
    from hr_access import require_hr
    from notification_ws import dispatch_personal_message
    require_hr(db,user);require_ready(db)
    if payload.year!=now().year:raise HTTPException(422,'这里只补录今年的已居家天数')
    target=db.query(AppUser).filter_by(id=payload.user_id,is_deleted=False).first()
    if not target:raise HTTPException(404,'人员不存在')
    lock(db,target);row=db.query(AnnualUsage).filter_by(user_id=target.id,year=payload.year).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'已居家天数已被其他人修改，请刷新后重试')
    if row and row.used_days==payload.used_days:return {'message':'已居家天数未变化'}
    before=row.used_days if row else None;history=list(row.history) if row else []
    moment=now();history.append({'before':before,'after':payload.used_days,'note':payload.note.strip(),'actor_name':user.full_name or user.username,'actor_id':str(user.id),'at':moment.isoformat()})
    if not row:row=AnnualUsage(user_id=target.id,year=payload.year,revision=0);db.add(row)
    row.used_days=payload.used_days;row.revision+=1;row.history=history;row.updated_by=user.id;row.updated_at=moment;db.commit()
    # 广播仅刷新本人工作台；失败不回滚已入库数据。
    try:dispatch_personal_message(target.id,{'type':'home_office_usage_changed','year':payload.year})
    except Exception:pass
    return {'message':'今年已居家天数已保存并更新本人工作台'}
