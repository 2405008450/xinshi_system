"""客户每月对账单制作进度，独立于任务及账单金额。"""
from uuid import UUID,uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import Column,Uuid,String,Integer,DateTime,ForeignKey,CheckConstraint,inspect,func
from models import Base,Client
from annotation_progress_time import business_now

class StatementProgress(Base):
    __tablename__='customer_statement_progress'
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
    billing_month=Column(String(7),primary_key=True)
    progress=Column(String(20),nullable=False,default='not_started')
    revision=Column(Integer,nullable=False,default=0)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)
    __table_args__=(CheckConstraint("progress IN ('not_started','partial','completed')",name='ck_statement_progress_value'),)

class StatementProgressEvent(Base):
    __tablename__='customer_statement_progress_event'
    id=Column(Uuid,primary_key=True,default=uuid4)
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),nullable=False,index=True)
    billing_month=Column(String(7),nullable=False,index=True)
    before=Column(String(20),nullable=False)
    after=Column(String(20),nullable=False)
    actor_id=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    actor_name=Column(String(255),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)

Progress=Literal['not_started','partial','completed']
class ProgressWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    billing_month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    progress:Progress
    revision:int=Field(ge=0)
    manager_ids:list[UUID]=Field(default_factory=list,max_length=2000)
    only_mine:bool=False
    client_manager:str|None=None

def ready(db):return inspect(db.connection()).has_table(StatementProgress.__tablename__)

def write(db,user,client_id,data):
    from statement_customer_groups import snapshot,pending_clients
    from finance_manager_scope import manager_fields
    if not ready(db):raise HTTPException(503,'对账单进度存储尚未初始化')
    try:
        if not db.query(Client).filter_by(id=client_id).with_for_update().first():raise HTTPException(404,'客户不存在')
        scope=manager_fields(db,user,data.manager_ids,data.only_mine,data.client_manager)
        projects,_=snapshot(db,client_id,data.billing_month,scope)
        if not projects and client_id not in pending_clients(db,data.billing_month,scope):raise HTTPException(422,'该客户不在当前月份和客户经理的项目范围内')
        row=db.get(StatementProgress,(client_id,data.billing_month))
        if (row.revision if row else 0)!=data.revision:raise HTTPException(409,'进度已被其他人调整，请刷新客户后重试')
        previous=row.progress if row else 'not_started'
        if row is None:row=StatementProgress(client_id=client_id,billing_month=data.billing_month,revision=0);db.add(row)
        if previous!=data.progress:
            db.add(StatementProgressEvent(client_id=client_id,billing_month=data.billing_month,before=previous,after=data.progress,actor_id=user.id,actor_name=user.full_name or user.username or '用户'))
            row.revision+=1
        row.progress=data.progress;row.updated_by=user.id;row.updated_at=business_now();db.commit()
        return dict(progress=row.progress,progress_revision=row.revision)
    except Exception:
        db.rollback();raise
