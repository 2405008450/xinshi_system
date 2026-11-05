"""客户对账单内容与跨客户操作的专门授权。管理员角色不替代赵震锋授权。"""
from uuid import uuid4,UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import Column,Uuid,String,Boolean,Integer,JSON,ForeignKey,DateTime,inspect
from models import Base,Client,AppUser
from database import get_db
from routers.auth import get_current_user
from annotation_progress_time import business_now,business_datetime

class StatementGrant(Base):
    __tablename__='customer_statement_grant'
    user_id=Column(Uuid,ForeignKey('app_user.id',ondelete='CASCADE'),primary_key=True)
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
    edit_content=Column(Boolean,nullable=False,default=False)
    cross_client=Column(Boolean,nullable=False,default=False)
    revision=Column(Integer,nullable=False,default=0)
    granted_by=Column(Uuid,ForeignKey('app_user.id'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)

class StatementGrantEvent(Base):
    __tablename__='customer_statement_grant_event'
    id=Column(Uuid,primary_key=True,default=uuid4)
    user_id=Column(Uuid,ForeignKey('app_user.id'),nullable=False,index=True)
    client_id=Column(Uuid,ForeignKey('client.id'),nullable=False,index=True)
    actor_id=Column(Uuid,ForeignKey('app_user.id'),nullable=False)
    actor_name=Column(String(255),nullable=False)
    before=Column(JSON,nullable=False)
    after=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)

class StatementTaskOwner(Base):
    __tablename__='customer_statement_task_owner'
    task_id=Column(String(200),primary_key=True)
    client_id=Column(Uuid,ForeignKey('client.id'),nullable=False,index=True)

def manager(user):return bool(user and user.is_active and not user.is_deleted and (user.username or '').casefold()=='williamzhao')
def ready(db):
    if db.info.get('statement_access_ready'):return True
    result=all(inspect(db.connection()).has_table(model.__tablename__) for model in (StatementGrant,StatementGrantEvent,StatementTaskOwner))
    if result:db.info['statement_access_ready']=True
    return result
def flags(db,user,client_id):
    if manager(user):return dict(edit_content=True,cross_client=True)
    row=db.get(StatementGrant,(user.id,UUID(str(client_id)))) if ready(db) else None
    return dict(edit_content=bool(row and row.edit_content),cross_client=bool(row and row.cross_client))
def allowed_ids(db,user,clients,kind):
    ids=set(map(str,clients))
    if manager(user):return ids
    if not ready(db):return set()
    return {str(row[0]) for row in db.query(StatementGrant.client_id).filter(StatementGrant.user_id==user.id,StatementGrant.client_id.in_([UUID(uid) for uid in ids]),getattr(StatementGrant,kind).is_(True)).all()}
def require(db,user,clients,kind):
    ids=set(map(str,clients));missing=ids-allowed_ids(db,user,ids,kind)
    if missing:
        names=[client.client_short_name or client.client_name for client in db.query(Client).filter(Client.id.in_([UUID(uid) for uid in missing])).all()]
        raise HTTPException(403,'未获得'+('、'.join(names) or '相关客户')+'的对账单'+('内容修改' if kind=='edit_content' else '跨客户操作')+'授权')
def content_clients(client_id,payload):
    return {str(client_id)}|{task.get('origin_client_id',str(client_id)) for task in payload.get('tasks',{}).values()}
def capabilities(db,user,client_id,payload):
    ids=content_clients(client_id,payload)
    return dict(edit_content=allowed_ids(db,user,ids,'edit_content')==ids,cross_client=flags(db,user,client_id)['cross_client'])

router=APIRouter(prefix='/statement-access',tags=['对账单授权'])
@router.get('/context')
def access_context(db=Depends(get_db),user=Depends(get_current_user)):
    rows=db.query(StatementGrant).filter_by(user_id=user.id).all() if ready(db) else []
    return dict(can_manage=manager(user),grants=[dict(client_id=str(row.client_id),edit_content=row.edit_content,cross_client=row.cross_client) for row in rows])

def require_manager(user):
    if not manager(user):raise HTTPException(403,'只有赵震锋可以管理对账单授权')

@router.get('/configuration')
def configuration(db=Depends(get_db),user=Depends(get_current_user)):
    require_manager(user)
    rows=db.query(StatementGrant).all() if ready(db) else []
    return dict(ready=ready(db),users=[dict(id=str(p.id),name=p.full_name or p.username,username=p.username) for p in db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).order_by(AppUser.full_name,AppUser.id)],clients=[dict(id=str(p.id),name=p.client_short_name or p.client_name,code=p.client_code) for p in db.query(Client).order_by(Client.client_short_name,Client.id)],grants=[dict(user_id=str(row.user_id),client_id=str(row.client_id),edit_content=row.edit_content,cross_client=row.cross_client,revision=row.revision) for row in rows])

class GrantWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:UUID
    client_id:UUID
    revision:int
    edit_content:bool
    cross_client:bool

class GrantExpected(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:UUID
    client_id:UUID
    revision:int

class BatchGrantWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_ids:list[UUID]=Field(min_length=1,max_length=5000)
    client_ids:list[UUID]=Field(min_length=1,max_length=5000)
    expected:list[GrantExpected]=Field(min_length=1,max_length=5000)
    edit_content:bool|None=None
    cross_client:bool|None=None

@router.put('/grants/batch')
def batch_grant(data:BatchGrantWrite,db=Depends(get_db),user=Depends(get_current_user)):
    require_manager(user)
    if not ready(db):raise HTTPException(503,'对账单授权存储尚未初始化')
    users=set(data.user_ids);clients=set(data.client_ids)
    if not users or not clients or len(users)!=len(data.user_ids) or len(clients)!=len(data.client_ids) or len(users)*len(clients)>5000:raise HTTPException(422,'请选择不重复的人员和客户，一次最多5000组授权')
    if data.edit_content is None and data.cross_client is None:raise HTTPException(422,'请至少明确选择一项需要统一设置的权限')
    expected={(item.user_id,item.client_id):item.revision for item in data.expected}
    keys={(uid,cid) for uid in users for cid in clients}
    if len(expected)!=len(data.expected) or set(expected)!=keys:raise HTTPException(422,'授权版本范围不完整或重复，请刷新后重试')
    try:
        locked=db.query(Client).filter(Client.id.in_(clients)).order_by(Client.id).with_for_update().all()
        people=db.query(AppUser).filter(AppUser.id.in_(users),AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()
        if len(locked)!=len(clients) or len(people)!=len(users):raise HTTPException(422,'所选客户不存在或人员已停用，请刷新后重试')
        rows={(row.user_id,row.client_id):row for row in db.query(StatementGrant).filter(StatementGrant.user_id.in_(users),StatementGrant.client_id.in_(clients)).with_for_update().populate_existing().all()}
        for key in keys:
            if expected[key]!=(rows[key].revision if key in rows else 0):raise HTTPException(409,'部分授权已被更新，本次全部未保存，请刷新后重试')
        changed=0
        for uid,cid in sorted(keys,key=lambda key:(str(key[1]),str(key[0]))):
            row=rows.get((uid,cid))
            before=dict(edit_content=bool(row and row.edit_content),cross_client=bool(row and row.cross_client))
            after={field:before[field] if getattr(data,field) is None else getattr(data,field) for field in before}
            if row is None:row=StatementGrant(user_id=uid,client_id=cid,revision=0);db.add(row)
            row.edit_content=after['edit_content'];row.cross_client=after['cross_client'];row.revision+=1;row.granted_by=user.id;row.updated_at=business_now()
            db.add(StatementGrantEvent(user_id=uid,client_id=cid,actor_id=user.id,actor_name=user.full_name or user.username,before=before,after=after,created_at=business_now()))
            changed+=before!=after
        db.commit();return dict(affected_count=len(keys),changed_count=changed)
    except Exception:
        db.rollback();raise

@router.put('/grant')
def grant(data:GrantWrite,db=Depends(get_db),user=Depends(get_current_user)):
    require_manager(user)
    if not ready(db):raise HTTPException(503,'对账单授权存储尚未初始化')
    db.query(Client).filter_by(id=data.client_id).with_for_update().first()
    if not db.get(Client,data.client_id) or not db.get(AppUser,data.user_id):raise HTTPException(404,'客户或人员不存在')
    row=db.get(StatementGrant,(data.user_id,data.client_id))
    if data.revision!=(row.revision if row else 0):raise HTTPException(409,'授权已更新，请刷新后重试')
    before=dict(edit_content=bool(row and row.edit_content),cross_client=bool(row and row.cross_client))
    if row is None:row=StatementGrant(user_id=data.user_id,client_id=data.client_id,revision=0);db.add(row)
    row.edit_content=data.edit_content;row.cross_client=data.cross_client;row.revision+=1;row.granted_by=user.id;row.updated_at=business_now()
    db.add(StatementGrantEvent(user_id=data.user_id,client_id=data.client_id,actor_id=user.id,actor_name=user.full_name or user.username,before=before,after=dict(edit_content=data.edit_content,cross_client=data.cross_client),created_at=business_now()))
    db.commit();return dict(revision=row.revision)

@router.get('/history')
def grant_history(skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user)):
    require_manager(user)
    if not ready(db):return dict(items=[],total=0)
    query=db.query(StatementGrantEvent)
    return dict(total=query.count(),items=[dict(id=str(row.id),user_id=str(row.user_id),client_id=str(row.client_id),actor_name=row.actor_name,before=row.before,after=row.after,created_at=business_datetime(row.created_at).isoformat()) for row in query.order_by(StatementGrantEvent.created_at.desc(),StatementGrantEvent.id).offset(skip).limit(limit)])
