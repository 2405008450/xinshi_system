"""报告逐项沟通的接收记录和定向通知，不扩展整份报告权限。"""
from uuid import UUID,uuid4
from sqlalchemy import Boolean,DateTime,ForeignKey,Index,UniqueConstraint,Uuid,inspect
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from fastapi import HTTPException
from models import Base,AppUser,AppNotification
from chat_time import now


class ReportFeedbackRecipient(Base):
    __tablename__='work_report_feedback_recipient'
    __table_args__=(UniqueConstraint('feedback_id','user_id',name='uq_report_feedback_recipient'),Index('ix_report_feedback_recipient_user','user_id','feedback_id'))
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    feedback_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('work_report_feedback.id',ondelete='CASCADE'),nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='CASCADE'),nullable=False)
    grants_access:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


def ready(db):return inspect(db.connection()).has_table(ReportFeedbackRecipient.__tablename__)


def received_query(db,user,report_id=None,item_key=None):
    from work_report_collaboration import ReportFeedback
    query=db.query(ReportFeedback).join(ReportFeedbackRecipient,ReportFeedbackRecipient.feedback_id==ReportFeedback.id).filter(ReportFeedbackRecipient.user_id==user.id,ReportFeedbackRecipient.grants_access.is_(True))
    if report_id is not None:query=query.filter(ReportFeedback.report_id==report_id)
    if item_key is not None:query=query.filter(ReportFeedback.item_key==str(item_key))
    return query


def has_received(db,user,report_id=None,item_key=None):
    return bool(user.is_active and not user.is_deleted and ready(db) and received_query(db,user,report_id,item_key).first())


def directory(db,user,report_id):
    from work_report_collaboration import authorized_report
    from organization_service import directory as organization_directory
    authorized_report(db,user,report_id,communication=True)
    catalog=organization_directory(db,user)
    return {'ready':ready(db),'people':[p for p in catalog['people'] if p['active']],'departments':catalog['items']}


def resolve(db,user,report,payload):
    from work_report_access import active_people,sender_ids_for_rules
    from work_report_collaboration import ReportFeedback
    from department_models import Department
    from types import SimpleNamespace
    if payload.recipient_mode!='default' and not ready(db):raise HTTPException(503,'报告沟通接收记录表尚未初始化')
    ids={report.user_id}
    if payload.recipient_mode=='all':ids.update(uid for uid, in active_people(db).with_entities(AppUser.id))
    elif payload.recipient_mode=='people':
        if not payload.recipient_ids:raise HTTPException(422,'请选择接收人员')
        selected=set(payload.recipient_ids)
        if active_people(db).filter(AppUser.id.in_(selected)).count()!=len(selected):raise HTTPException(422,'接收人员不存在、已停用或已删除，请重新选择')
        ids.update(selected)
    elif payload.recipient_mode=='departments':
        if not payload.department_ids:raise HTTPException(422,'请选择接收部门')
        selected=set(payload.department_ids)
        if db.query(Department).filter(Department.id.in_(selected)).count()!=len(selected):raise HTTPException(422,'接收部门不存在，请重新选择')
        ids.update(sender_ids_for_rules(db,[SimpleNamespace(senders_all=False,sender_ids=[],all_departments=False,department_ids=[str(uid) for uid in selected])]))
    else:
        ids.update(uid for uid, in db.query(ReportFeedback.author_id).filter_by(report_id=report.id,item_key=str(payload.item_key)))
        if ready(db):ids.update(uid for uid, in db.query(ReportFeedbackRecipient.user_id).join(ReportFeedback,ReportFeedback.id==ReportFeedbackRecipient.feedback_id).filter(ReportFeedback.report_id==report.id,ReportFeedback.item_key==str(payload.item_key)))
    people=active_people(db).filter(AppUser.id.in_(ids)).order_by(AppUser.full_name,AppUser.username).all()
    if payload.recipient_mode=='default':
        from work_report_collaboration import full_feedback_access
        people=[person for person in people if full_feedback_access(db,person,report) or has_received(db,person,report.id,payload.item_key)]
    return people


def queue(db,user,report,row,people):
    events=[];moment=now();available=ready(db)
    for person in people:
        if available:db.add(ReportFeedbackRecipient(id=uuid4(),feedback_id=row.id,user_id=person.id,grants_access=row.item_snapshot.get('feedback_recipient_mode')!='default',created_at=moment))
        if person.id==user.id:continue
        title=f'工作报告沟通 · {row.author_name}'[:255]
        content=f'{report.user.full_name or report.user.username} · {report.report_date} · {row.item_snapshot.get("task_name") or "工作项"}\n{row.content}'
        notification=AppNotification(id=uuid4(),recipient_user_id=person.id,title=title,content=content,notification_type='work_report_feedback',related_entity_id=report.id,is_read=False,created_at=moment.replace(tzinfo=None))
        db.add(notification)
        events.append((person.id,{'type':'notification','notification':{'id':str(notification.id),'title':title,'content':content,'notification_type':'work_report_feedback','related_entity_id':str(report.id),'is_read':False,'created_at':moment.isoformat()}}))
    return events
