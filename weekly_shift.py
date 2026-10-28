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
import weekly_shift_publication as publication


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
    return {**data,'ready':ready(db),'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),**publication.status(db,start,row,data['assignments'])}


def get_plan(db,user,week):
    require_hr(db,user);start=week_key(week)
    draft=db.get(publication.WeeklyShiftDraft,start) if publication.ready(db) else None
    return serialize(db,draft or (db.get(WeeklyShiftPlan,start) if ready(db) else None),start)


def overview(db,user,week):
    return publication.published_plan(db,user,week)


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
    publication.require_ready(db)
    legacy={row.week_start:row for row in db.query(WeeklyShiftPlan).filter(WeeklyShiftPlan.week_start.in_([source,target])).order_by(WeeklyShiftPlan.week_start).with_for_update().populate_existing().all()}
    drafts={row.week_start:row for row in db.query(publication.WeeklyShiftDraft).filter(publication.WeeklyShiftDraft.week_start.in_([source,target])).order_by(publication.WeeklyShiftDraft.week_start).with_for_update().populate_existing().all()}
    rows={**legacy,**drafts}
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
        publication.assert_editable(db,start)
    for start,values in changes:
        previous=rows.get(start)
        before=list(previous.assignments) if previous else []
        row=drafts.get(start)
        if row is None:row=publication.WeeklyShiftDraft(week_start=start,revision=previous.revision if previous else 0);db.add(row)
        row.assignments=values;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
        publication.audit(db,user,start,payload.operation,row.revision,before,values)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'两周排班已发生变化，请重新预览并确认')
    return {'source':get_plan(db,user,source.isoformat()),'target':get_plan(db,user,target.isoformat())}


def save_plan(db,user,week,payload:WeeklyPlanWrite):
    require_hr(db,user);start=week_key(week)
    if not ready(db):raise HTTPException(503,'每周班次安排表尚未初始化')
    lock_weeks(db,[start])
    publication.assert_editable(db,start)
    row=db.query(publication.WeeklyShiftDraft).filter_by(week_start=start).with_for_update().populate_existing().first()
    legacy=db.get(WeeklyShiftPlan,start) if row is None else None
    current=row or legacy
    if payload.revision!=(current.revision if current else 0):raise HTTPException(409,'本周排班已被调整，请刷新后重试')
    previous={entry['user_id']:entry for entry in current.assignments} if current else {}
    allowed={person['id'] for person in directory(db,user)['people']}
    from fixed_shift import effective
    allowed.update(entry['user_id'] for entry in effective(db,[],start,weekly=True))
    values=[{key:entry[key] for key in ('user_id','department','shift')} for entry in effective(db,[entry.model_dump(mode='json') for entry in payload.assignments],start,weekly=True)]
    for entry in values:
        if entry['user_id'] not in allowed and entry!=previous.get(entry['user_id']):raise HTTPException(422,'所选人员不在参与排班的在用部门名册中')
    if current and publication.canonical(current.assignments)==publication.canonical(values):return serialize(db,current,start)
    before=list(current.assignments) if current else []
    if not row:row=publication.WeeklyShiftDraft(week_start=start,revision=current.revision if current else 0);db.add(row)
    row.assignments=values;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    publication.audit(db,user,start,'draft_save',row.revision,before,values)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'本周排班已被其他人创建，请刷新后重试')
    return serialize(db,row,start)


def my_plan(db,user,week):
    return publication.published_plan(db,user,week,mine=True)
