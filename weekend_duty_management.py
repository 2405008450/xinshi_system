"""周末值班的独立草稿、显式同步、固定周末人员与修改记录。"""
from datetime import date,datetime,timedelta
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from typing import Literal
from sqlalchemy import Date,Integer,JSON,DateTime,Uuid,Boolean,String,Index,inspect,text
from sqlalchemy.orm import Mapped,mapped_column
from models import Base,AppUser
from chat_time import now,api_time
from hr_access import require_hr
from monthly_shift import DEPARTMENTS,month_key,group_code


class WeekendDutyDraft(Base):
    __tablename__='weekend_duty_draft'
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class WeekendDutyPublication(Base):
    __tablename__='weekend_duty_publication'
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    draft_revision:Mapped[int]=mapped_column(Integer,nullable=False)
    editing_enabled:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    published_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    published_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class WeekendDutyAudit(Base):
    __tablename__='weekend_duty_audit'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    month:Mapped[date]=mapped_column(Date,nullable=False)
    action:Mapped[str]=mapped_column(String(32),nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    publication_revision:Mapped[int|None]=mapped_column(Integer,nullable=True)
    changes:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    actor_id:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    actor_name:Mapped[str]=mapped_column(String(255),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    __table_args__=(Index('ix_weekend_duty_audit_month_time','month','created_at'),)


class WeekendDutyFixedConfig(Base):
    __tablename__='weekend_duty_fixed_config'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    assignments:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class FixedAssignment(BaseModel):
    user_id:UUID
    department:str
    weekdays:list[Literal[5,6]]=Field(min_length=1,max_length=2)
    @model_validator(mode='after')
    def valid(self):
        if self.department not in {row['code'] for row in DEPARTMENTS}:raise ValueError('请选择有效的值班部门')
        if len(set(self.weekdays))!=len(self.weekdays):raise ValueError('周六、周日不能重复选择')
        return self


class FixedWrite(BaseModel):
    revision:int=Field(ge=0)
    assignments:list[FixedAssignment]=Field(default_factory=list,max_length=2000)
    @model_validator(mode='after')
    def unique_people(self):
        if len({row.user_id for row in self.assignments})!=len(self.assignments):raise ValueError('固定值班人员不能重复')
        return self


def fixed_ready(db):return inspect(db.connection()).has_table('weekend_duty_fixed_config')
def ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in ('weekend_duty_draft','weekend_duty_publication','weekend_duty_audit','weekend_duty_fixed_config'))
def require_ready(db):
    if not ready(db):raise HTTPException(503,'值班草稿、同步及固定人员表尚未初始化')
def lock_fixed(db):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(731944, 1)'))
def lock_months(db,months):
    if db.bind.dialect.name=='postgresql':
        for month in sorted(set(months)):db.execute(text('SELECT pg_advisory_xact_lock(731943, :day)'),{'day':month.toordinal()})
def fixed_row(db):return db.get(WeekendDutyFixedConfig,1) if fixed_ready(db) else None
def fixed_revision(db):
    row=fixed_row(db);return row.revision if row else 0


def effective(db,values,month):
    from weekend_duty import weekend_dates
    row=fixed_row(db)
    if not row:return [entry for entry in values if not entry.get('fixed')]
    history=(row.assignments or {}).get('versions',[])
    ids={UUID(entry['user_id']) for version in history for entry in version['assignments']}
    people={str(person.id):person for person in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    generated=[];today=now().date()
    for day in weekend_dates(month):
        version=next((item for item in reversed(history) if item['effective_from']<=day.isoformat()),None)
        for entry in version['assignments'] if version else []:
            person=people.get(entry['user_id'])
            if day.weekday() not in entry['weekdays'] or not person or (day>=today and (not person.is_active or person.is_deleted)):continue
            generated.append({'user_id':entry['user_id'],'department':entry['department'],'date':day.isoformat(),'fixed':True})
    keys={(entry['user_id'],entry['date']) for entry in generated}
    return [entry for entry in values if not entry.get('fixed') and (entry['user_id'],entry['date']) not in keys]+generated


def get_fixed(db,user):
    require_hr(db,user)
    from organization_service import directory
    people=[{**person,'default_department':next((group_code(item['name']) for item in person['departments'] if group_code(item['name'])),None)} for person in directory(db,user)['people'] if person['active']]
    row=fixed_row(db)
    return api_time({'ready':fixed_ready(db),'revision':row.revision if row else 0,'assignments':row.assignments.get('current',[]) if row else [],'people':people,'departments':DEPARTMENTS,'updated_at':row.updated_at if row else None})


def save_fixed(db,user,payload:FixedWrite):
    require_hr(db,user)
    if not fixed_ready(db):raise HTTPException(503,'固定周末值班人员表尚未初始化')
    lock_fixed(db)
    row=db.query(WeekendDutyFixedConfig).filter_by(id=1).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'固定值班配置已变化，请重新打开后重试')
    allowed={person['id'] for person in get_fixed(db,user)['people']}
    values=[entry.model_dump(mode='json') for entry in payload.assignments]
    if any(entry['user_id'] not in allowed for entry in values):raise HTTPException(422,'固定值班人员必须来自在用人员名册')
    if row is None:row=WeekendDutyFixedConfig(id=1,revision=0);db.add(row)
    history=list((row.assignments or {}).get('versions',[]))
    version={'effective_from':now().date().isoformat(),'assignments':values}
    if history and history[-1]['effective_from']==version['effective_from']:history[-1]=version
    else:history.append(version)
    row.assignments={'current':values,'versions':history};row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    db.commit();return get_fixed(db,user)


def canonical(values):return sorted([(row['user_id'],row['department'],row['date'],bool(row.get('fixed'))) for row in values])
def status(db,month,row,values):
    available=ready(db);publication=db.get(WeekendDutyPublication,month) if available else None
    return api_time({'sync_ready':available,'published':publication is not None,'publication_revision':publication.revision if publication else 0,'published_at':publication.published_at if publication else None,
        'can_edit':publication is None or publication.editing_enabled,'needs_sync':publication is None or publication.draft_revision!=(row.revision if row else 0) or canonical(publication.assignments)!=canonical(values),'fixed_revision':fixed_revision(db)})
def assert_editable(db,month):
    require_ready(db);publication=db.get(WeekendDutyPublication,month)
    if publication and not publication.editing_enabled:raise HTTPException(409,f'{month.strftime("%Y-%m")} 值班已同步，请先点击“修改”')


def audit(db,user,month,action,revision,before,after,publication_revision=None):
    require_ready(db)
    old={(entry['user_id'],entry['date']):entry for entry in before};new={(entry['user_id'],entry['date']):entry for entry in after}
    ids={UUID(key[0]) for key in old.keys()|new.keys()}
    names={str(person.id):person.full_name or person.username for person in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    def compact(entry):return {key:entry[key] for key in ('department','date','fixed') if key in entry} if entry else None
    changes=[{'user_id':key[0],'name':names.get(key[0],key[0]),'before':compact(old.get(key)),'after':compact(new.get(key))} for key in sorted(old.keys()|new.keys()) if compact(old.get(key))!=compact(new.get(key))]
    db.add(WeekendDutyAudit(month=month,action=action,revision=revision,changes=changes,publication_revision=publication_revision,actor_id=user.id,actor_name=user.full_name or user.username,created_at=now()))


def enable_edit(db,user,month,payload):
    require_hr(db,user);require_ready(db);day=month_key(month);lock_fixed(db);lock_months(db,[day])
    row=db.query(WeekendDutyPublication).filter_by(month=day).with_for_update().populate_existing().first()
    if row:
        if row.revision!=payload.publication_revision:raise HTTPException(409,'同步版本已变化，请刷新后重试')
        if not row.editing_enabled:row.editing_enabled=True;audit(db,user,day,'enable_edit',payload.revision,[],[]);db.commit()
    from weekend_duty import get_plan
    return get_plan(db,user,month)


def publish(db,user,month,payload):
    require_hr(db,user);require_ready(db);day=month_key(month);lock_fixed(db);lock_months(db,[day])
    from weekend_duty import WeekendDutyPlan,get_plan
    draft=db.query(WeekendDutyDraft).filter_by(month=day).with_for_update().populate_existing().first()
    legacy=db.query(WeekendDutyPlan).filter_by(month=day).with_for_update().populate_existing().first()
    publication=db.query(WeekendDutyPublication).filter_by(month=day).with_for_update().populate_existing().first()
    revision=draft.revision if draft else legacy.revision if legacy else 0
    if payload.revision!=revision or payload.publication_revision!=(publication.revision if publication else 0) or payload.fixed_revision!=fixed_revision(db):raise HTTPException(409,'值班草稿、同步版本或固定配置已变化，请刷新后重试')
    data=get_plan(db,user,month)
    import weekend_night_duty as night
    night_plan=db.get(night.NightDutyPlan,day) if night.ready(db) else None
    day_keys={(entry['user_id'],entry['date']) for entry in data['assignments']}
    for entry in night_plan.published if night_plan else []:
        present=(entry['user_id'],entry['date']) in day_keys
        if (entry['mode']=='standalone' and present) or (entry['mode']=='continuation' and not present):raise HTTPException(409,'白天安排与已同步夜间值班冲突，请先修改并同步对应夜间安排')
    if publication and not publication.editing_enabled and not data['needs_sync']:return data
    values=[{key:entry[key] for key in ('user_id','department','date','fixed') if key in entry} for entry in data['assignments']]
    before=publication.assignments if publication else []
    raw=[{key:entry[key] for key in ('user_id','department','date')} for entry in values]
    if draft is None:draft=WeekendDutyDraft(month=day,revision=revision,assignments=values,updated_by=user.id,updated_at=now());db.add(draft)
    if legacy is None:legacy=WeekendDutyPlan(month=day,revision=0);db.add(legacy)
    legacy.assignments=raw;legacy.revision+=1;legacy.updated_by=user.id;legacy.updated_at=now()
    if publication is None:publication=WeekendDutyPublication(month=day,revision=0);db.add(publication)
    publication.assignments=values;publication.revision+=1;publication.draft_revision=revision;publication.editing_enabled=False;publication.published_by=user.id;publication.published_at=now()
    db.query(WeekendDutyAudit).filter_by(month=day,publication_revision=None).update({'publication_revision':publication.revision},synchronize_session=False)
    audit(db,user,day,'publish',revision,before,values,publication.revision)
    db.commit()
    from notification_ws import broadcast_to_users
    broadcast_to_users([str(uid) for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()],{'type':'weekend_duty_published','month':month,'publication_revision':publication.revision})
    return get_plan(db,user,month)


def overview(db,user,month):
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    from weekend_duty import serialize
    day=month_key(month);available=ready(db);row=db.get(WeekendDutyPublication,day) if available else None
    result=serialize(db,row,day,published=True)
    return {**result,'ready':available,'published':row is not None,'publication_revision':row.revision if row else 0,'current_user_id':str(user.id)}


def history(db,user,month,public=False,offset=0,limit=50):
    if public:
        if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    else:require_hr(db,user)
    require_ready(db);query=db.query(WeekendDutyAudit).filter_by(month=month_key(month))
    if public:query=query.filter(WeekendDutyAudit.publication_revision.is_not(None))
    total=query.count();rows=query.order_by(WeekendDutyAudit.created_at.desc(),WeekendDutyAudit.id.desc()).offset(offset).limit(limit).all()
    return api_time({'total':total,'items':[{'id':row.id,'action':row.action,'revision':row.revision,'publication_revision':row.publication_revision,'changes':row.changes,'actor_name':row.actor_name,'created_at':row.created_at} for row in rows]})
