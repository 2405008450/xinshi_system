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
from monthly_shift import PlanWrite,group_code,SHIFTS,DEPARTMENTS


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


def effective(db,values,start,weekly=False):
    today=now().date()
    current=today-timedelta(days=today.weekday()) if weekly else today.replace(day=1)
    row=db.get(FixedShiftConfig,1) if ready(db) else None
    if not row:return values
    key='week_start' if weekly else 'month_start'
    versions=row.assignments.get('versions',[])
    snapshot=next((version for version in reversed(versions) if version[key]<=start.isoformat()),None)
    if not snapshot:return values
    fixed=entries(db,snapshot['assignments'],only_active=start>=current);ids={entry['user_id'] for entry in fixed}
    return [entry for entry in values if entry['user_id'] not in ids]+fixed


def get_config(db,user):
    require_hr(db,user)
    from organization_service import directory
    people=[{**person,'default_department':next((group_code(item['name']) for item in person['departments'] if group_code(item['name'])),None)} for person in directory(db,user)['people'] if person['active']]
    row=db.get(FixedShiftConfig,1) if ready(db) else None
    return api_time({'ready':ready(db),'revision':row.revision if row else 0,'assignments':row.assignments.get('current',[]) if row else [],
                     'departments':DEPARTMENTS,'shifts':SHIFTS,'people':people,'updated_at':row.updated_at if row else None})


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
