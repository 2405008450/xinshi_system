"""行政部门管理的月度周末值班安排；同人可在不同周末日期重复安排。"""
import calendar
from datetime import date,datetime
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import Date,Integer,JSON,DateTime,Uuid,inspect
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser
from chat_time import now,api_time
from hr_access import require_hr
from monthly_shift import DEPARTMENTS,month_key,directory


class WeekendDutyPlan(Base):
    __tablename__='weekend_duty_plan'
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class DutyAssignment(BaseModel):
    user_id:UUID
    department:str
    date:date

    @model_validator(mode='after')
    def valid(self):
        if self.department not in {row['code'] for row in DEPARTMENTS}:raise ValueError('请选择参与值班的部门')
        if self.date.weekday()<5:raise ValueError('值班安排仅支持周六、周日')
        return self


class DutyWrite(BaseModel):
    revision:int=Field(ge=0)
    assignments:list[DutyAssignment]=Field(default_factory=list,max_length=5000)

    @model_validator(mode='after')
    def unique_daily_assignment(self):
        if len({(row.user_id,row.date) for row in self.assignments})!=len(self.assignments):raise ValueError('同一人员同一天只能安排一次值班')
        return self


def ready(db):return inspect(db.connection()).has_table(WeekendDutyPlan.__tablename__)


def weekend_dates(month):
    return [day for number in range(1,calendar.monthrange(month.year,month.month)[1]+1) if (day:=date(month.year,month.month,number)).weekday()>=5]


def serialize(db,row,month):
    entries=row.assignments if row else []
    ids={UUID(entry['user_id']) for entry in entries}
    people={str(person.id):person for person in db.query(AppUser).filter(AppUser.id.in_(ids))} if ids else {}
    actor=db.get(AppUser,row.updated_by) if row else None
    return api_time({'ready':ready(db),'month':month.strftime('%Y-%m'),'revision':row.revision if row else 0,
        'dates':[day.isoformat() for day in weekend_dates(month)],'departments':DEPARTMENTS,
        'assignments':[{**entry,'name':(people[entry['user_id']].full_name or people[entry['user_id']].username) if entry['user_id'] in people else '已删除人员','active':bool(entry['user_id'] in people and people[entry['user_id']].is_active and not people[entry['user_id']].is_deleted)} for entry in entries],
        'updated_at':row.updated_at if row else None,'updated_by_name':(actor.full_name or actor.username) if actor else None})


def get_plan(db,user,month):
    require_hr(db,user);day=month_key(month)
    return serialize(db,db.get(WeekendDutyPlan,day) if ready(db) else None,day)


def save_plan(db,user,month,payload):
    require_hr(db,user);day=month_key(month)
    if not ready(db):raise HTTPException(503,'周末值班安排表尚未初始化')
    if any(entry.date.replace(day=1)!=day for entry in payload.assignments):raise HTTPException(422,'值班日期必须属于当前选择的月份')
    row=db.query(WeekendDutyPlan).filter_by(month=day).with_for_update().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'本月值班安排已被修改，请刷新后重试')
    previous={(entry['user_id'],entry['date']):entry for entry in row.assignments} if row else {}
    allowed={person['id'] for person in directory(db,user)['people']}
    values=[entry.model_dump(mode='json') for entry in payload.assignments]
    for entry in values:
        if entry['user_id'] not in allowed and entry!=previous.get((entry['user_id'],entry['date'])):raise HTTPException(422,'所选人员不在参与值班的在用部门名册中')
    if not row:row=WeekendDutyPlan(month=day,revision=0);db.add(row)
    row.assignments=values;row.revision+=1;row.updated_at=now();row.updated_by=user.id
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'本月值班安排已被其他人创建，请刷新后重试')
    return serialize(db,row,day)
