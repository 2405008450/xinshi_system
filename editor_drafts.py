"""按账号隔离的未提交编辑草稿；不修改业务记录，不自动提交表单。"""
import json
import re
from typing import Any
from uuid import UUID
from sqlalchemy import JSON, DateTime,ForeignKey,Integer,String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped,mapped_column
from pydantic import BaseModel,Field,model_validator
from models import Base,AppUser
from chat_time import now,api_time

SECRET=re.compile(r'password|passwd|passphrase|secret|token|credential|private.?key|api.?key|access.?key|authorization',re.I)


def clean_payload(value):
    if isinstance(value,dict):return {key:clean_payload(item) for key,item in value.items() if key not in ('__proto__','constructor','prototype') and not SECRET.search(key)}
    if isinstance(value,list):return [clean_payload(item) for item in value]
    return value


class EditorDraft(Base):
    __tablename__='editor_draft'
    user_id: Mapped[UUID]=mapped_column(ForeignKey('app_user.id',ondelete='CASCADE'),primary_key=True)
    namespace: Mapped[str]=mapped_column(String(80),primary_key=True)
    draft_key: Mapped[str]=mapped_column(String(220),primary_key=True)
    payload: Mapped[Any]=mapped_column(JSONB().with_variant(JSON(), 'sqlite'),nullable=True)
    revision: Mapped[int]=mapped_column(Integer,nullable=False)
    updated_at: Mapped[Any]=mapped_column(DateTime(timezone=True),nullable=False)


class DraftWrite(BaseModel):
    namespace:str=Field(min_length=1,max_length=80)
    key:str=Field(min_length=1,max_length=220)
    revision:int=Field(ge=0,strict=True)
    payload:Any=None

    @model_validator(mode='after')
    def bounded_payload(self):
        self.payload=clean_payload(self.payload)
        try:encoded=json.dumps(self.payload,ensure_ascii=False,allow_nan=False)
        except (ValueError,TypeError):raise ValueError('草稿须为有效的JSON内容')
        if len(encoded.encode('utf-8'))>256*1024:raise ValueError('单份草稿不能超过256KB')
        if self.namespace=='work-report' and any(value in encoded.lower() for value in ['screenshot://','data:image/','<img']):raise ValueError('工作报告禁止截图')
        return self


class DraftBatch(BaseModel):
    drafts:list[DraftWrite]=Field(min_length=1,max_length=20)


def serialize(row,namespace,key):
    return dict(namespace=namespace,key=key,payload=row.payload if row else None,revision=row.revision if row else 0,updated_at=api_time(row.updated_at) if row else None)


def read(db,user,namespace,key):
    row=db.get(EditorDraft,(user.id,namespace,key))
    return serialize(row,namespace,key)


def save_batch(db,user,entries):
    db.query(AppUser.id).filter_by(id=user.id).with_for_update().first()
    results=[]
    for entry in entries:
        row=db.query(EditorDraft).filter_by(user_id=user.id,namespace=entry.namespace,draft_key=entry.key).with_for_update().first()
        revision=row.revision if row else 0
        # 响应丢失后重试同一内容可直接确认，不能因此制造假版本冲突。
        if row and row.payload==entry.payload:
            results.append(dict(namespace=entry.namespace,key=entry.key,revision=row.revision,updated_at=api_time(row.updated_at)));continue
        if revision!=entry.revision:
            results.append(dict(namespace=entry.namespace,key=entry.key,conflict=True,revision=revision));continue
        if not row:
            row=EditorDraft(user_id=user.id,namespace=entry.namespace,draft_key=entry.key)
            db.add(row)
        row.payload=entry.payload;row.revision=revision+1;row.updated_at=now()
        results.append(dict(namespace=entry.namespace,key=entry.key,revision=row.revision,updated_at=api_time(row.updated_at)))
        db.flush()
    db.commit()
    return results


def clear_report_draft(db,report):
    key=str(report.report_date)
    row=db.get(EditorDraft,(report.user_id,'work-report',key))
    if not row:
        row=EditorDraft(user_id=report.user_id,namespace='work-report',draft_key=key,revision=0)
        db.add(row)
    row.payload=None;row.revision+=1;row.updated_at=now()


def report_draft_revision(db,report):
    if not db:return 0
    row=db.get(EditorDraft,(report.user_id,'work-report',str(report.report_date)))
    return row.revision if row else 0
