"""独立周末夜间居家值班；草稿与发布分离，不产生普通居家申请。"""
from datetime import date,datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import Date,DateTime,Integer,JSON,Uuid,Boolean,inspect
from sqlalchemy.orm import Mapped,mapped_column
from models import Base,AppUser
from chat_time import now,api_time
from monthly_shift import month_key,directory
from hr_access import require_hr
import weekend_duty_management as duty


class NightDutyPlan(Base):
    __tablename__='weekend_night_duty_plan'
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    published:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    published_revision:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    editing:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    history:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class Assignment(BaseModel):
    user_id:UUID
    date:date
    mode:Literal['standalone','continuation']


class Write(BaseModel):
    revision:int=Field(ge=0)
    assignments:list[Assignment]=Field(default_factory=list,max_length=2000)
    @model_validator(mode='after')
    def unique(self):
        if len({(row.user_id,row.date) for row in self.assignments})!=len(self.assignments):raise ValueError('同一人员同一天只能安排一种夜间值班')
        return self


class Version(BaseModel):
    revision:int=Field(ge=0)


def ready(db):return inspect(db.connection()).has_table(NightDutyPlan.__tablename__)


def assignment(db,uid,day):
    row=db.get(NightDutyPlan,day.replace(day=1)) if ready(db) else None
    return next((entry for entry in row.published if entry['user_id']==str(uid) and entry['date']==day.isoformat()),None) if row else None


def decorate(shift,entry):
    if not entry:return shift
    continuation=entry['mode']=='continuation'
    # 接续白天沿用原到岗时间，统一18:00结束；晚间重新打卡。
    periods=[]
    if continuation:
        for period in (shift or {}).get('periods',['09:00–12:00','13:30–18:00']):
            left,right=period.replace('—','–').replace('-','–').split('–')
            if left<'18:00':periods.append(f'{left}–{min(right,"18:00")}')
        if not periods:periods=['09:00–12:00','13:30–18:00']
    return {'code':'weekend_night','label':'周末夜间值班（接续）' if continuation else '周末夜间值班（单独）','periods':periods+['19:00–23:00'],
            'department':'customer','fixed':False,'weekend_duty':True,'night_duty':entry['mode'],
            'home_office_day':not continuation,'night_day_periods':len(periods)}


def serialize(db,row,month,public=False):
    from weekend_duty import weekend_dates
    entries=(row.published if public else row.assignments) if row else []
    ids={UUID(entry['user_id']) for entry in entries}
    visible_history=[entry for entry in (row.history if row else []) if not public or entry.get('publication_revision') is not None]
    ids.update(UUID(value['user_id']) for event in visible_history for value in event['before']+event['after'])
    names={str(person.id):person.full_name or person.username for person in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    return api_time({'ready':ready(db),'month':month.strftime('%Y-%m'),'dates':[day.isoformat() for day in weekend_dates(month)],
        'assignments':[{**entry,'name':names.get(entry['user_id'],'已删除人员')} for entry in entries],
        'revision':row.revision if row else 0,'published_revision':row.published_revision if row else 0,
        'can_edit':row.editing if row else True,'needs_sync':not row or row.revision!=row.published_revision,
        'names':names,'history':visible_history})


def get_plan(db,user,month,public=False):
    if public:
        if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    else:require_hr(db,user)
    day=month_key(month)
    return serialize(db,db.get(NightDutyPlan,day) if ready(db) else None,day,public)


def validate(db,user,day,entries,publishing=False):
    allowed={person['id'] for person in directory(db,user)['people'] if any(dep['id']=='customer' for dep in person['departments'])}
    daytime=db.get(duty.WeekendDutyPublication,day) if duty.ready(db) else None
    daytime_ids={(entry['user_id'],entry['date']) for entry in (daytime.assignments if daytime else [])}
    for entry in entries:
        target=date.fromisoformat(entry['date'])
        if target.replace(day=1)!=day or target.weekday()<5:raise HTTPException(422,'夜间值班仅支持所选月份的周六、周日')
        if entry['user_id'] not in allowed:raise HTTPException(422,'请从在用客户/销售人员中安排夜间值班')
        key=(entry['user_id'],entry['date'])
        if publishing and entry['mode']=='continuation' and key not in daytime_ids:raise HTTPException(422,'接续人员须先在同一天的白天值班安排中同步')
        if entry['mode']=='standalone' and key in daytime_ids:raise HTTPException(422,'同一天已有白天值班，请选择接续值班')


def mutate(db,user,month,payload,action='save'):
    require_hr(db,user)
    if not ready(db):raise HTTPException(503,'周末夜间值班表尚未初始化')
    day=month_key(month);duty.lock_months(db,[day])
    row=db.query(NightDutyPlan).filter_by(month=day).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'夜间安排已变化，请刷新后重试')
    if not row:row=NightDutyPlan(month=day,assignments=[],published=[],revision=0,published_revision=0,editing=True,history=[]);db.add(row)
    before=list(row.assignments)
    if action=='save':
        if not row.editing:raise HTTPException(409,'已同步，请先点击修改')
        values=[entry.model_dump(mode='json') for entry in payload.assignments];validate(db,user,day,values)
        if values==before:return serialize(db,row,day)
        row.assignments=values;row.revision+=1
    elif action=='sync':
        validate(db,user,day,row.assignments,True)
        row.published=list(row.assignments);row.published_revision=row.revision;row.editing=False
    else:row.editing=True
    moment=now();row.updated_by=user.id;row.updated_at=moment
    history=list(row.history)
    if action=='sync':history=[{**entry,'publication_revision':row.revision} if entry.get('publication_revision') is None else entry for entry in history]
    row.history=history+[{'action':action,'actor':user.full_name or user.username,'at':moment.isoformat(),'before':before,'after':list(row.assignments),'publication_revision':row.revision if action=='sync' else None}]
    db.commit()
    if action=='sync':
        from notification_ws import broadcast_to_users
        broadcast_to_users([str(uid) for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()],{'type':'weekend_duty_published','month':month})
    return serialize(db,row,day)


from database import get_db
from routers.auth import get_current_user
router=APIRouter(prefix='/weekend-night-duty',tags=['周末夜间值班'])
@router.get('')
def read(month:str,public:bool=False,db=Depends(get_db),user=Depends(get_current_user)):return get_plan(db,user,month,public)
@router.put('')
def save(month:str,payload:Write,db=Depends(get_db),user=Depends(get_current_user)):return mutate(db,user,month,payload)
@router.post('/sync')
def sync(month:str,payload:Version,db=Depends(get_db),user=Depends(get_current_user)):return mutate(db,user,month,payload,'sync')
@router.post('/edit')
def edit(month:str,payload:Version,db=Depends(get_db),user=Depends(get_current_user)):return mutate(db,user,month,payload,'edit')
