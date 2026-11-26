"""口译项目共享设置：默认会话@人员。"""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import Column,Integer,JSON,DateTime,ForeignKey,Uuid,inspect,text,CheckConstraint
from sqlalchemy.orm import Session
from models import Base
from database import get_db
from annotation_progress_time import business_now
from routers.auth import require_any_permission,require_permission,get_current_user

DEFAULT_MENTION_USERNAMES={'zixia','kuangjiao'}
class InterpretationProjectSettings(Base):
    __tablename__='interpretation_project_settings'
    __table_args__=(CheckConstraint('id = 1',name='ck_interpretation_project_settings_singleton'),)
    id=Column(Integer,primary_key=True)
    mention_user_ids=Column(JSON,nullable=False)
    revision=Column(Integer,nullable=False,default=1)
    updated_by=Column(Uuid,ForeignKey('app_user.id'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)

class SettingsWrite(BaseModel):
    mention_user_ids:list[UUID]=Field(max_length=500)
    revision:int=Field(ge=0)


def ready(db):
    if not hasattr(db,'connection'):return False
    key='_interpretation_settings_ready'
    if key not in db.info:db.info[key]=inspect(db.connection()).has_table(InterpretationProjectSettings.__tablename__)
    return db.info[key]


def mention_ids(db,members):
    allowed={str(person.id) for person in members}
    row=db.get(InterpretationProjectSettings,1) if ready(db) else None
    if row is not None:return set(row.mention_user_ids)&allowed
    return {str(person.id) for person in members if person.username.casefold() in DEFAULT_MENTION_USERNAMES}


def catalog(db):
    from translation_chat_delivery import people
    members=people(db)
    row=db.get(InterpretationProjectSettings,1) if ready(db) else None
    return dict(ready=ready(db),revision=row.revision if row else 0,mention_user_ids=sorted(mention_ids(db,members)),
        default_mention_user_ids=[str(p.id) for p in members if p.username.casefold() in DEFAULT_MENTION_USERNAMES],
        users=[dict(id=str(p.id),name=p.full_name or p.username,username=p.username) for p in members])


def save(db,actor,payload):
    if not ready(db):raise HTTPException(503,'口译设置表尚未初始化')
    from translation_chat_delivery import people
    allowed={person.id for person in people(db)}
    selected=set(payload.mention_user_ids)
    if not selected<=allowed:raise HTTPException(422,'部分人员已停用或不具备会话参与权限，请重新选择')
    if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(261126071)'))
    row=db.query(InterpretationProjectSettings).filter_by(id=1).with_for_update().first()
    if (row.revision if row else 0)!=payload.revision:raise HTTPException(409,'口译设置已被其他人更新，请重新打开后保存')
    if row is None:row=InterpretationProjectSettings(id=1,revision=0,mention_user_ids=[]);db.add(row)
    row.mention_user_ids=sorted(str(value) for value in selected)
    row.revision+=1;row.updated_by=actor.id;row.updated_at=business_now()
    db.commit()
    return catalog(db)

router=APIRouter(prefix='/projects/interpretation-settings',tags=['interpretation-settings'])
@router.get('',dependencies=[Depends(require_any_permission('projects:read','projects:write'))])
def read_settings(db:Session=Depends(get_db)):return catalog(db)
@router.put('',dependencies=[Depends(require_permission('projects:write'))])
def write_settings(payload:SettingsWrite,db:Session=Depends(get_db),actor=Depends(get_current_user)):
    return save(db,actor,payload)
