"""标注业务三种通知的共享默认接收人。"""
from uuid import UUID,uuid5,NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import inspect
from pydantic import BaseModel,Field
from models import AppUser
from department_service import can_manage
from organization_service import department_condition
from resource_request_dispatch_models import ResourceRequestDispatchDefault as Config
from resource_development_models import DevelopmentAudit
from business_time import business_now
from chat_time import now
KINDS={'circle':'发圈设置','post':'发帖设置','development':'需求设置'}
class DefaultWrite(BaseModel):
    user_ids:list[UUID]|None=Field(default=None,max_length=500)
    revision:int=Field(ge=0)

def ready(db):return inspect(db.connection()).has_table(Config.__tablename__)

def eligible(db,kind):
    if kind not in KINDS:raise HTTPException(422,'不支持的通知类型')
    query=db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False))
    if kind!='post':query=query.filter(department_condition(db,['标注项目部']))
    return query.order_by(AppUser.full_name,AppUser.id).all()

def initial(db,kind):
    people=eligible(db,kind)
    if kind=='circle':return [p.id for p in people if p.full_name in {'黄杰','王露'}]
    if kind=='development':return [p.id for p in people if p.username in {'jinglin','williamzhao'}]
    hr={uid for uid, in db.query(AppUser.id).filter(department_condition(db,['HR部']))}
    return [p.id for p in people if p.id in hr and p.username.casefold() not in {'zixia','williamzhao','lulu'}]

def catalog(db,user,kind):
    available=ready(db)
    people=eligible(db,kind);allowed={p.id for p in people}
    row=db.get(Config,kind) if available else None
    ids=initial(db,kind) if not row or row.user_ids is None else [UUID(i) for i in row.user_ids]
    return dict(kind=kind,label=KINDS[kind],user_ids=[str(i) for i in ids if i in allowed],users=[dict(id=str(p.id),name=p.full_name or p.username,department=p.department or '') for p in people],revision=row.revision if row else 0,can_manage=can_manage(db,user) and available,ready=available,rule_based=not row or row.user_ids is None)

def save(db,user,kind,payload):
    if not can_manage(db,user):raise HTTPException(403,'仅 ethan、jimmy 和超级管理员可修改默认接收人')
    if not ready(db):raise HTTPException(503,'默认接收人配置表尚未初始化')
    if kind not in KINDS:raise HTTPException(422,'不支持的通知类型')
    from resource_development_service import lock_writes
    lock_writes(db)
    row=db.query(Config).filter_by(kind=kind).with_for_update().first()
    if (row.revision if row else 0)!=payload.revision:raise HTTPException(409,'默认名单已被修改，请刷新后重试')
    ids=set(payload.user_ids) if payload.user_ids is not None else None
    if ids is not None and not ids<={p.id for p in eligible(db,kind)}:raise HTTPException(422,'部分人员已停用或不在候选范围内，请重新选择')
    before=catalog(db,user,kind)
    if not row:row=Config(kind=kind,revision=0);db.add(row)
    row.user_ids=sorted([str(i) for i in ids]) if ids is not None else None
    row.revision+=1;row.updated_by=user.id;row.updated_at=now();db.flush()
    after=catalog(db,user,kind)
    db.add(DevelopmentAudit(entity_id=uuid5(NAMESPACE_URL,'annotation-dispatch-default:'+kind),entity_type='dispatch_defaults',actor_id=user.id,action='update',before=before,after=after,created_at=business_now()))
    db.commit()
    return after
