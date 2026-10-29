"""排班草稿发布与审计。公开接口只读取已同步快照，不合并实时固定班次。"""
from datetime import date,datetime
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import Date,Integer,JSON,DateTime,Uuid,Boolean,String,Index,inspect
from sqlalchemy.orm import Mapped,mapped_column
from models import Base,AppUser
from chat_time import now,api_time
from hr_access import require_hr
from monthly_shift import SHIFTS,DEPARTMENTS


class WeeklyShiftDraft(Base):
    __tablename__='weekly_shift_draft'
    week_start:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class WeeklyShiftPublication(Base):
    __tablename__='weekly_shift_publication'
    week_start:Mapped[date]=mapped_column(Date,primary_key=True)
    assignments:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    draft_revision:Mapped[int]=mapped_column(Integer,nullable=False)
    editing_enabled:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    published_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    published_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class WeeklyShiftAudit(Base):
    __tablename__='weekly_shift_audit'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    week_start:Mapped[date]=mapped_column(Date,nullable=False)
    action:Mapped[str]=mapped_column(String(32),nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    publication_revision:Mapped[int|None]=mapped_column(Integer,nullable=True)
    changes:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    actor_id:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    actor_name:Mapped[str]=mapped_column(String(255),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    __table_args__=(Index('ix_weekly_shift_audit_week_time','week_start','created_at'),)


class SyncWrite(BaseModel):
    revision:int=Field(ge=0)
    publication_revision:int=Field(ge=0)
    fixed_revision:int=Field(ge=0)


def ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in ('weekly_shift_draft','weekly_shift_publication','weekly_shift_audit'))


def require_ready(db):
    if not ready(db):raise HTTPException(503,'班次同步与修改记录表尚未初始化')


def canonical(values):
    return sorted([(str(row['user_id']),row['department'],row['shift'],bool(row.get('fixed'))) for row in values])


def fixed_revision(db):
    from fixed_shift import FixedShiftConfig,ready as fixed_ready
    row=db.get(FixedShiftConfig,1) if fixed_ready(db) else None
    return row.revision if row else 0


def status(db,start,row,values):
    available=ready(db)
    publication=db.get(WeeklyShiftPublication,start) if available else None
    revision=row.revision if row else 0
    return api_time({'sync_ready':available,'publication_revision':publication.revision if publication else 0,
        'published_at':publication.published_at if publication else None,'published':publication is not None,
        'needs_sync':publication is None or publication.draft_revision!=revision or canonical(publication.assignments)!=canonical(values),
        'can_edit':publication is None or publication.editing_enabled,'fixed_revision':fixed_revision(db)})


def assert_editable(db,start):
    require_ready(db)
    row=db.get(WeeklyShiftPublication,start)
    if row and not row.editing_enabled:raise HTTPException(409,f'{start.isoformat()} 所在周已同步，请先点击“修改”')


def changes(db,before,after):
    old={str(row['user_id']):row for row in before};new={str(row['user_id']):row for row in after}
    ids=[UUID(key) for key in old.keys()|new.keys()]
    people={str(p.id):p.full_name or p.username for p in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    fields=('department','shift','fixed')
    def compact(row):return {key:row[key] for key in fields if key in row} if row else None
    return [{'user_id':key,'name':people.get(key,key),'before':compact(old.get(key)),'after':compact(new.get(key))}
        for key in sorted(old.keys()|new.keys()) if compact(old.get(key))!=compact(new.get(key))]


def audit(db,user,start,action,revision,before,after,publication_revision=None):
    require_ready(db)
    db.add(WeeklyShiftAudit(week_start=start,action=action,revision=revision,changes=changes(db,before,after),
        publication_revision=publication_revision,actor_id=user.id,actor_name=user.full_name or user.username,created_at=now()))


def enable_edit(db,user,week,payload:SyncWrite):
    require_hr(db,user);require_ready(db)
    from weekly_shift import week_key,lock_weeks,get_plan
    start=week_key(week);lock_weeks(db,[start])
    publication=db.query(WeeklyShiftPublication).filter_by(week_start=start).with_for_update().populate_existing().first()
    if publication:
        if publication.revision!=payload.publication_revision:raise HTTPException(409,'同步版本已变化，请刷新后重试')
        if not publication.editing_enabled:
            publication.editing_enabled=True
            audit(db,user,start,'enable_edit',payload.revision,[],[])
            db.commit()
    return get_plan(db,user,start.isoformat())


def publish(db,user,week,payload:SyncWrite):
    require_hr(db,user);require_ready(db)
    from weekly_shift import WeeklyShiftPlan,week_key,lock_weeks,get_plan
    start=week_key(week);lock_weeks(db,[start])
    draft=db.query(WeeklyShiftDraft).filter_by(week_start=start).with_for_update().populate_existing().first()
    legacy=db.query(WeeklyShiftPlan).filter_by(week_start=start).with_for_update().populate_existing().first()
    publication=db.query(WeeklyShiftPublication).filter_by(week_start=start).with_for_update().populate_existing().first()
    revision=draft.revision if draft else legacy.revision if legacy else 0
    if payload.revision!=revision or payload.publication_revision!=(publication.revision if publication else 0) or payload.fixed_revision!=fixed_revision(db):raise HTTPException(409,'草稿、固定班次或同步版本已变化，请刷新后重新确认')
    data=get_plan(db,user,start.isoformat())
    values=[{key:row[key] for key in ('user_id','department','shift','fixed') if key in row} for row in data['assignments']]
    if publication and not publication.editing_enabled and not data['needs_sync']:return data
    before=publication.assignments if publication else []
    if draft is None:
        draft=WeeklyShiftDraft(week_start=start,revision=revision,assignments=[{key:entry[key] for key in ('user_id','department','shift')} for entry in values],updated_by=user.id,updated_at=now());db.add(draft)
    # 兼容仍读取旧表的已部署客户端：只有用户点击同步才写旧公开表。
    if legacy is None:legacy=WeeklyShiftPlan(week_start=start,revision=0);db.add(legacy)
    legacy.assignments=[{key:entry[key] for key in ('user_id','department','shift')} for entry in values]
    legacy.revision+=1;legacy.updated_by=user.id;legacy.updated_at=now()
    if publication is None:publication=WeeklyShiftPublication(week_start=start,revision=0);db.add(publication)
    publication.assignments=values;publication.revision+=1;publication.draft_revision=revision
    publication.editing_enabled=False;publication.published_by=user.id;publication.published_at=now()
    # 尚未发布的草稿记录在本次同步后才可被工作台读取。
    db.query(WeeklyShiftAudit).filter_by(week_start=start,publication_revision=None).update({'publication_revision':publication.revision},synchronize_session=False)
    audit(db,user,start,'publish',revision,before,values,publication.revision)
    db.commit()
    from notification_ws import broadcast_to_users
    recipients=[str(uid) for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()]
    broadcast_to_users(recipients,{'type':'weekly_shift_published','week_start':start.isoformat(),'publication_revision':publication.revision})
    return get_plan(db,user,start.isoformat())


def published_plan(db,user,week,mine=False):
    if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    from weekly_shift import week_key
    from datetime import timedelta
    start=week_key(week);available=ready(db)
    row=db.get(WeeklyShiftPublication,start) if available else None
    values=[dict(entry) for entry in row.assignments] if row else []
    if mine:values=[entry for entry in values if entry['user_id']==str(user.id)]
    ids=[UUID(entry['user_id']) for entry in values]
    people={str(person.id):person for person in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    values=[{**entry,'name':people[entry['user_id']].full_name or people[entry['user_id']].username,
        'active':people[entry['user_id']].is_active and not people[entry['user_id']].is_deleted} for entry in values if entry['user_id'] in people]
    if mine and values:
        from attendance_service import leave_badges
        values=leave_badges(db,values,start,weekly_period=True)
    result={'ready':available,'published':row is not None,'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),
        'publication_revision':row.revision if row else 0,'updated_at':row.published_at if row else None,'published_at':row.published_at if row else None,'shifts':SHIFTS,'departments':DEPARTMENTS}
    return api_time({**result,**({'assignment':values[0] if values else None} if mine else {'assignments':values})})


def history(db,user,week,public=False,offset=0,limit=50):
    if public:
        if not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
    else:require_hr(db,user)
    require_ready(db)
    from weekly_shift import week_key
    query=db.query(WeeklyShiftAudit).filter_by(week_start=week_key(week))
    if public:query=query.filter(WeeklyShiftAudit.publication_revision.is_not(None))
    total=query.count()
    rows=query.order_by(WeeklyShiftAudit.created_at.desc(),WeeklyShiftAudit.id.desc()).offset(offset).limit(limit).all()
    return api_time({'total':total,'items':[{'id':row.id,'action':row.action,'revision':row.revision,'publication_revision':row.publication_revision,'actor_name':row.actor_name,'created_at':row.created_at,'changes':row.changes} for row in rows]})
