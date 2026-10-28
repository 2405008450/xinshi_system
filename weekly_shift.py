"""每周班次安排，周一至周日；与历史月度安排独立存储。"""
from datetime import date,datetime,timedelta
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from typing import Literal
from sqlalchemy import Date,Integer,JSON,DateTime,Uuid,inspect,text
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser
from chat_time import now,api_time
from hr_access import require_hr
from monthly_shift import PlanWrite,SHIFTS,DEPARTMENTS,directory,serialize as serialize_month


class WeeklyShiftPlan(Base):
    __tablename__='weekly_shift_plan'
    week_start:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class WeeklyPlanWrite(PlanWrite):
    @model_validator(mode='after')
    def unique_people(self):
        if len({row.user_id for row in self.assignments})!=len(self.assignments):raise ValueError('同一人员每周只能安排一个班次')
        return self


def ready(db):return inspect(db.connection()).has_table(WeeklyShiftPlan.__tablename__)


def week_key(value):
    try:
        if len(value)!=10:raise ValueError()
        day=date.fromisoformat(value)
        start=day-timedelta(days=day.weekday())
        start+timedelta(days=6)
        return start
    except (ValueError,TypeError,OverflowError):raise HTTPException(422,'请选择有效的排班周日期（YYYY-MM-DD）')


def serialize(db,row,start):
    data=serialize_month(db,row,start,weekly=True)
    data.pop('month',None)
    return {**data,'ready':ready(db),'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat()}


def get_plan(db,user,week):
    require_hr(db,user);start=week_key(week)
    return serialize(db,db.get(WeeklyShiftPlan,start) if ready(db) else None,start)


def overview(db,user,week):
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    start=week_key(week)
    data=serialize(db,db.get(WeeklyShiftPlan,start) if ready(db) else None,start)
    # 工作台公开班次与人员姓名，不公开他人的请假明细。
    for entry in data['assignments']:
        entry.pop('leaves',None)
        entry.pop('leave_minutes',None)
    return data


def lock_weeks(db,starts):
    # 同时保护尚未创建的周；所有周写入使用相同锁，按日期排序避免互换死锁。
    if db.bind.dialect.name=='postgresql':
        for start in sorted(set(starts)):
            db.execute(text('SELECT pg_advisory_xact_lock(731942, :day)'),{'day':start.toordinal()})


class WeekTransfer(BaseModel):
    source_week:str
    target_week:str
    operation:Literal['copy','move','swap']
    source_revision:int=Field(ge=0)
    target_revision:int=Field(ge=0)


def transfer_plan(db,user,payload:WeekTransfer):
    require_hr(db,user)
    source,target=week_key(payload.source_week),week_key(payload.target_week)
    if source==target:raise HTTPException(422,'请选择不同的两周')
    if not ready(db):raise HTTPException(503,'每周班次安排表尚未初始化')
    lock_weeks(db,[source,target])
    rows={row.week_start:row for row in db.query(WeeklyShiftPlan).filter(WeeklyShiftPlan.week_start.in_([source,target])).order_by(WeeklyShiftPlan.week_start).with_for_update().populate_existing().all()}
    for start,revision in [(source,payload.source_revision),(target,payload.target_revision)]:
        if revision!=(rows[start].revision if start in rows else 0):raise HTTPException(409,'两周排班已发生变化，请重新预览并确认')
    from fixed_shift import effective
    def movable(start):
        fixed_ids={entry['user_id'] for entry in effective(db,[],start,weekly=True)}
        return [{key:entry[key] for key in ('user_id','department','shift')} for entry in (rows[start].assignments if start in rows else []) if entry['user_id'] not in fixed_ids]
    source_values,target_values=movable(source),movable(target)
    if not source_values and (payload.operation!='swap' or not target_values):raise HTTPException(422,'没有可复制、转移或互换的非固定班次安排')
    changes=[(target,source_values)]
    if payload.operation!='copy':changes.append((source,target_values if payload.operation=='swap' else []))
    for start,values in changes:
        row=rows.get(start)
        if row is None:row=WeeklyShiftPlan(week_start=start,revision=0);db.add(row)
        row.assignments=values;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'两周排班已发生变化，请重新预览并确认')
    return {'source':get_plan(db,user,source.isoformat()),'target':get_plan(db,user,target.isoformat())}


def save_plan(db,user,week,payload:WeeklyPlanWrite):
    require_hr(db,user);start=week_key(week)
    if not ready(db):raise HTTPException(503,'每周班次安排表尚未初始化')
    lock_weeks(db,[start])
    row=db.query(WeeklyShiftPlan).filter_by(week_start=start).with_for_update().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'本周排班已被调整，请刷新后重试')
    previous={entry['user_id']:entry for entry in row.assignments} if row else {}
    allowed={person['id'] for person in directory(db,user)['people']}
    from fixed_shift import effective
    allowed.update(entry['user_id'] for entry in effective(db,[],start,weekly=True))
    values=[{key:entry[key] for key in ('user_id','department','shift')} for entry in effective(db,[entry.model_dump(mode='json') for entry in payload.assignments],start,weekly=True)]
    for entry in values:
        if entry['user_id'] not in allowed and entry!=previous.get(entry['user_id']):raise HTTPException(422,'所选人员不在参与排班的在用部门名册中')
    if not row:row=WeeklyShiftPlan(week_start=start,revision=0);db.add(row)
    row.assignments=values;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'本周排班已被其他人创建，请刷新后重试')
    return serialize(db,row,start)


def my_plan(db,user,week):
    start=week_key(week)
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    row=db.get(WeeklyShiftPlan,start) if ready(db) else None
    from fixed_shift import effective
    entry=next((value for value in effective(db,row.assignments if row else [],start,weekly=True) if value['user_id']==str(user.id)),None)
    return api_time({'ready':ready(db),'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),
        'assignment':{**entry,'name':user.full_name or user.username} if entry else None,'shifts':SHIFTS,'departments':DEPARTMENTS,'updated_at':row.updated_at if row and entry else None})
