"""项目安排的共同说明，按项目保存，供所有被安排人员查看。"""
from datetime import datetime
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import ForeignKey,Integer,Text,DateTime,Uuid,inspect
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from chat_time import now,api_time

class ArrangementInstruction(Base):
    __tablename__='translation_arrangement_instruction'
    project_id:Mapped[UUID]=mapped_column(ForeignKey('translation_project.id',ondelete='CASCADE'),primary_key=True)
    content:Mapped[str]=mapped_column(Text,nullable=False,default='')
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    updated_by:Mapped[UUID]=mapped_column(Uuid,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)

class InstructionWrite(BaseModel):
    content:str=Field(default='',max_length=10000)
    revision:int=Field(ge=0)

def ready(db):return inspect(db.connection()).has_table(ArrangementInstruction.__tablename__)
def read(db,project_id):
    row=db.get(ArrangementInstruction,project_id) if ready(db) else None
    return api_time({'common_instruction':row.content if row else '', 'instruction_revision':row.revision if row else 0})

def write_locked(db,user,project_id,content,revision):
    """调用方先锁项目安排计划；提交与审计由同一事务负责。"""
    if not ready(db):raise HTTPException(503,'项目共同说明表尚未初始化')
    row=db.query(ArrangementInstruction).filter_by(project_id=project_id).with_for_update().first()
    if revision!=(row.revision if row else 0):raise HTTPException(409,'共同说明已被修改，请刷新安排后重试')
    content=content.strip()
    if content==(row.content if row else ''):return False
    if not row:row=ArrangementInstruction(project_id=project_id,revision=0);db.add(row)
    row.content=content;row.revision+=1;row.updated_by=user.id;row.updated_at=now();db.flush()
    return True

def save(db,user,project_id,payload):
    import project_arrangement_history as history
    plan=history.lock_plan(db,project_id,user)
    before=history.snapshot(db,project_id,plan)
    if write_locked(db,user,project_id,payload.content,payload.revision):history.append_history(db,plan,user,'instruction',before)
    db.commit()
    return history.detail(db,project_id)
