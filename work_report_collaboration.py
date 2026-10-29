"""工作报告逐项沟通和一次修订，所有时间使用 UTC+8。"""
from datetime import datetime
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, Uuid, inspect, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chat_time import now, api_time
from models import AppUser, Base
import work_report_access as access

json_type=JSONB().with_variant(JSON, 'sqlite')


class ReportFeedback(Base):
    __tablename__='work_report_feedback'
    __table_args__=(Index('ix_report_feedback_report_item_time','report_id','item_key','created_at'),)
    id: Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    report_id: Mapped[UUID]=mapped_column(Uuid,ForeignKey('daily_report.id',ondelete='CASCADE'),nullable=False)
    item_key: Mapped[str]=mapped_column(String(36),nullable=False)
    item_snapshot: Mapped[dict]=mapped_column(json_type,nullable=False)
    author_id: Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='RESTRICT'),nullable=False)
    author_name: Mapped[str]=mapped_column(String(255),nullable=False)
    content: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class ReportRevision(Base):
    __tablename__='work_report_revision'
    __table_args__=(UniqueConstraint('report_id',name='uq_work_report_one_revision'),)
    id: Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    report_id: Mapped[UUID]=mapped_column(Uuid,ForeignKey('daily_report.id',ondelete='CASCADE'),nullable=False)
    before_data: Mapped[dict]=mapped_column(json_type,nullable=False)
    after_data: Mapped[dict]=mapped_column(json_type,nullable=False)
    created_by: Mapped[UUID]=mapped_column(Uuid,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class FeedbackWrite(BaseModel):
    item_key: UUID
    content: str=Field(min_length=1,max_length=4000)

    @model_validator(mode='after')
    def clean(self):
        self.content=self.content.strip()
        if not self.content or any(token in self.content.lower() for token in ['screenshot://','data:image/','<img']):
            raise ValueError('请填写文字反馈，不支持截图')
        return self


def table_ready(db,model):
    return inspect(db.connection()).has_table(model.__tablename__)


def supervisor(user):
    return access.same_viewing_access(user)


def item_key(item):
    return str((item.display_metadata or {}).get('_feedback_key') or item.id)


def assign_item_keys(report_id,items,previous_items=()):
    def identity(item):
        metadata=item.get('display_metadata') or {}
        return f'{report_id}:{item.get("source_id")}:{metadata.get("source")}:{metadata.get("event_type")}:{item.get("task_name")}:{item.get("progress_content")}'
    previous={identity({'source_id':row.source_id,'display_metadata':row.display_metadata,'task_name':row.task_name,'progress_content':row.progress_content}):item_key(row) for row in previous_items if row.source_type=='system_event'}
    seen=set();replaced_keys={}
    for item in items:
        metadata=dict(item.get('display_metadata') or {})
        incoming_key=metadata.get('_feedback_key')
        try:key=str(UUID(str(metadata.get('_feedback_key'))))
        except (ValueError,TypeError):
            key=previous.get(identity(item)) or str(uuid5(NAMESPACE_URL,identity(item))) if item.get('source_type')=='system_event' else str(uuid4())
        if item.get('source_type')=='system_event':
            key=previous.get(identity(item)) or key
            if incoming_key and str(incoming_key)!=key:replaced_keys[str(incoming_key)]=key
        if key in seen:raise ValueError('工作项标识重复，请刷新报告后重试')
        seen.add(key);metadata['_feedback_key']=key;item['display_metadata']=metadata
    for item in items:
        metadata=item['display_metadata']
        if str(metadata.get('parent_item_key')) in replaced_keys:
            metadata['parent_item_key']=replaced_keys[str(metadata['parent_item_key'])]


def authorized_report(db,user,report_id,communication=False):
    from task_models import DailyReport
    report=db.get(DailyReport,report_id)
    if not user.is_active or user.is_deleted or not report:
        raise HTTPException(404,'报告不存在或无权查看')
    if report.user_id==user.id or communication and supervisor(user):return report
    allowed=access.sender_ids_for_rules(db,access.receiving_rules(db,user))
    if report.status!='finalized' or report.user_id not in allowed:raise HTTPException(404,'报告不存在或无权查看')
    return report


def feedback_rows(db,user,report_id):
    authorized_report(db,user,report_id,communication=True)
    if not table_ready(db,ReportFeedback):return {'ready':False,'items':[]}
    rows=db.query(ReportFeedback).filter_by(report_id=report_id).order_by(ReportFeedback.created_at,ReportFeedback.id).all()
    return {'ready':True,'items':[serialize_feedback(row) for row in rows]}


def serialize_feedback(row):
    return {key:api_time(getattr(row,key)) for key in ['id','item_key','item_snapshot','author_id','author_name','content','created_at']}


def add_feedback(db,user,report_id,payload):
    from task_models import DailyReport
    # 与修订共用报告行锁，确保快照与当前工作项一致。
    db.query(DailyReport).filter_by(id=report_id).with_for_update().first()
    report=authorized_report(db,user,report_id,communication=True)
    if not table_ready(db,ReportFeedback):raise HTTPException(503,'报告沟通表尚未初始化')
    key=str(payload.item_key)
    item=next((item for item in report.items if item_key(item)==key),None)
    previous=db.query(ReportFeedback).filter_by(report_id=report_id,item_key=key).order_by(ReportFeedback.created_at).first()
    if not item and not previous:raise HTTPException(404,'工作项不存在')
    # 作者可回复既有反馈；发起评价需拥有当前报告的查看权。
    if not previous:
        if report.user_id==user.id:raise HTTPException(403,'收到反馈后可在此回复')
        access.received_report(db,user,report_id)
    snapshot=previous.item_snapshot if previous else {'task_name':item.task_name,'progress_content':item.progress_content,'task_type':item.task_type}
    row=ReportFeedback(report_id=report_id,item_key=key,item_snapshot=snapshot,author_id=user.id,author_name=user.full_name or user.username,content=payload.content)
    db.add(row);db.commit()
    return serialize_feedback(row)


def feedback_inbox(db,user,date_from=None,date_to=None,page=1,page_size=20):
    from task_models import DailyReport
    if not table_ready(db,ReportFeedback):return {'ready':False,'total':0,'items':[]}
    allowed=access.sender_ids_for_rules(db,access.receiving_rules(db,user))
    query=db.query(DailyReport).filter(DailyReport.id.in_(db.query(ReportFeedback.report_id)))
    if not supervisor(user):query=query.filter(or_(DailyReport.user_id==user.id,(DailyReport.user_id.in_(allowed))&(DailyReport.status=='finalized')))
    if date_from:query=query.filter(DailyReport.report_date>=date_from)
    if date_to:query=query.filter(DailyReport.report_date<=date_to)
    return {'ready':True,'total':query.count(),'items':[{'report_id':r.id,'user_name':r.user.full_name or r.user.username,'report_date':r.report_date} for r in query.order_by(DailyReport.report_date.desc(),DailyReport.id).offset((page-1)*page_size).limit(page_size)]}


def revision_status(db,report_id):
    available=table_ready(db,ReportRevision)
    return available, bool(available and db.query(ReportRevision.id).filter_by(report_id=report_id).first())


def revision_history(db,user,report_id):
    authorized_report(db,user,report_id)
    if not table_ready(db,ReportRevision):return []
    return [{'before':row.before_data,'after':row.after_data,'created_at':api_time(row.created_at)} for row in db.query(ReportRevision).filter_by(report_id=report_id)]
