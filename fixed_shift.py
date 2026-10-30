"""固定班次配置；仅行政部管理，按 UTC+8 应用于当前及未来周期。"""
from datetime import datetime,timedelta
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import Integer,JSON,DateTime,Uuid,inspect
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser
from chat_time import now,api_time
from hr_access import require_hr
from monthly_shift import Assignment,PlanWrite,group_code,SHIFTS,DEPARTMENTS
from pydantic import Field,model_validator


FIXED_ONLY_SHIFTS=[
    {'code':'fixed_early_early','label':'早早班（固定）','periods':['08:30–12:00','13:30–16:00'],'description':'08:30上班，16:00下班，午休12:00–13:30；每天可多组上下班打卡，不限定上午、下午；上一组签退后才能开始下一组。','multiple_clock_sessions':True},
    {'code':'management','label':'管理/管培生班次','periods':['08:50–12:00','13:30–20:00'],'description':'08:50上班，20:00下班；午休12:00–13:30。'},
    {'code':'flexible','label':'灵活班次','periods':[],'description':'不设预定上下班时间；每天可多组打卡，须先下班打卡再开始下一组。不判迟到，不将全部打卡时长自动认定为加班。','flexible':True},
]
HOME_ROTATION={'code':'home_rotation','label':'居家班次（轮班）','periods':[],'description':'按每周安排的早晚班时间轮班，同时标记为居家办公；保留在排班界面。'}
FIXED_ONLY_CODES={item['code'] for item in FIXED_ONLY_SHIFTS}
FIXED_SHIFTS=SHIFTS+FIXED_ONLY_SHIFTS+[HOME_ROTATION]

class FixedAssignment(Assignment):
    @model_validator(mode='after')
    def valid_cell(self):
        if self.department not in {row['code'] for row in DEPARTMENTS} or self.shift not in {row['code'] for row in FIXED_SHIFTS}:raise ValueError('请选择有效部门和固定班次')
        if self.shift=='customer_remote' and self.department!='customer':raise ValueError('客户部居家晚班仅适用于客户部')
        return self

class FixedWrite(PlanWrite):
    assignments:list[FixedAssignment]=Field(default_factory=list,max_length=2000)


class FixedShiftConfig(Base):
    __tablename__='fixed_shift_config'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    assignments:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


def ready(db):return inspect(db.connection()).has_table('fixed_shift_config')


def entries(db,values,only_active=True):
    ids=[UUID(entry['user_id']) for entry in values]
    people={str(user.id):user for user in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    return [{**entry,'name':people[entry['user_id']].full_name or people[entry['user_id']].username,
             'active':people[entry['user_id']].is_active and not people[entry['user_id']].is_deleted,'fixed':True}
            for entry in values if entry['user_id'] in people and (not only_active or people[entry['user_id']].is_active and not people[entry['user_id']].is_deleted)]


def effective(db,values,start,weekly=False,for_schedule=True):
    today=now().date()
    current=today-timedelta(days=today.weekday()) if weekly else today.replace(day=1)
    row=db.get(FixedShiftConfig,1) if ready(db) else None
    if not row:return values
    key='week_start' if weekly else 'month_start'
    versions=row.assignments.get('versions',[])
    snapshot=next((version for version in reversed(versions) if version[key]<=start.isoformat()),None)
    if not snapshot:return values
    fixed=entries(db,snapshot['assignments'],only_active=start>=current)
    if not for_schedule:return fixed
    by_id={entry['user_id']:entry for entry in fixed}
    result=[]
    for entry in values:
        setting=by_id.get(entry['user_id'])
        if setting and setting['shift']=='home_rotation':result.append({**entry,'fixed':False,'home_office_day':True,'home_rotation':True})
        elif not setting:result.append(entry)
    return result+[entry for entry in fixed if entry['shift'] not in FIXED_ONLY_CODES|{'home_rotation'}]


def get_config(db,user):
    require_hr(db,user)
    from organization_service import directory
    people=[{**person,'default_department':next((group_code(item['name']) for item in person['departments'] if group_code(item['name'])),None)} for person in directory(db,user)['people'] if person['active']]
    row=db.get(FixedShiftConfig,1) if ready(db) else None
    return api_time({'ready':ready(db),'revision':row.revision if row else 0,'assignments':row.assignments.get('current',[]) if row else [],
                     'departments':DEPARTMENTS,'shifts':FIXED_SHIFTS,'people':people,'updated_at':row.updated_at if row else None})


def save_config(db,user,payload:PlanWrite):
    require_hr(db,user)
    if not ready(db):raise HTTPException(503,'固定班次配置表尚未初始化')
    row=db.query(FixedShiftConfig).filter_by(id=1).with_for_update().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'固定班次已被调整，请重新打开后重试')
    from organization_service import directory
    allowed={person['id'] for person in directory(db,user)['people'] if person['active']}
    values=[entry.model_dump(mode='json') for entry in payload.assignments]
    if any(entry['user_id'] not in allowed for entry in values):raise HTTPException(422,'固定班次人员必须来自在用人员名册')
    if not row:row=FixedShiftConfig(id=1,revision=0);db.add(row)
    today=now().date()
    history=list((row.assignments or {}).get('versions',[]))
    snapshot={'week_start':(today-timedelta(days=today.weekday())).isoformat(),'month_start':today.replace(day=1).isoformat(),'assignments':values}
    # 同一周、月内可合并最后快照；跨周或跨月保留，以免自动带入的历史班次消失。
    if history and all(history[-1][key]==snapshot[key] for key in ('week_start','month_start')):history[-1]=snapshot
    else:history.append(snapshot)
    row.assignments={'current':values,'versions':history};row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'固定班次已被其他人创建，请重新打开后重试')
    return get_config(db,user)
