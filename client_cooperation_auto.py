"""已确认笔译项目自动产生客户合作关系；读历史数据时不批量回写。"""
from uuid import uuid4
from sqlalchemy import Column, DateTime, ForeignKey, Uuid, case, event, exists, func, inspect, or_, select
from sqlalchemy.orm import Session, aliased
from models import Base, Client, SubClient, TranslationProject, TranslationSubOrder
from annotation_progress_time import business_now, business_datetime

# 后续正常生产节点意味着确认已完成；取消、暂停不能凭当前值反推确认。
CONFIRMED_STATUSES=('confirmed','已确认','in_progress','organized','arranged','translator_assigned','sent_to_translator','translator_returned','special_checked','typeset','special_checked_typeset','reviewed','sent_to_client','completed','client_feedback','feedback_sent_to_client')


class ClientProjectConfirmation(Base):
    __tablename__='client_project_confirmation'
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),primary_key=True)
    received_at=Column(DateTime(timezone=True))
    confirmed_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


def expressions(model=Client):
    root=aliased(TranslationProject);sub=aliased(SubClient)
    confirmed=or_(root.project_status.in_(CONFIRMED_STATUSES),exists(select(ClientProjectConfirmation.project_id).where(ClientProjectConfirmation.project_id==root.id)),exists(select(TranslationSubOrder.id).where(TranslationSubOrder.parent_project_id==root.id,TranslationSubOrder.status.in_(CONFIRMED_STATUSES))))
    owner=root.sub_client_id==model.id if model is SubClient else or_(root.client_id==model.id,root.sub_client_id.in_(select(sub.id).where(sub.parent_client_id==model.id)))
    eligible=exists(select(root.id).where(owner,confirmed)).correlate(model)
    first=select(func.min(root.customer_reception_time)).where(owner,confirmed).correlate(model).scalar_subquery()
    return case((eligible,'active'),else_=func.coalesce(model.client_status,'pending')),case((eligible,first),else_=model.cooperation_start_date)


def attach_clients(db,clients=(),sub_clients=()):
    for model,rows in ((Client,list(clients)),(SubClient,[*sub_clients,*[sub for client in clients for sub in client.sub_clients]])):
        if not rows:continue
        status,start=expressions(model)
        values={key:(state,date) for key,state,date in db.query(model.id,status,start).filter(model.id.in_([row.id for row in rows])).all()}
        for row in rows:
            row._auto_client_status,row._auto_cooperation_start_date=values[row.id]


def capture(session,flush_context,instances):
    changed=list(session.new)+list(session.dirty)
    roots={}
    for row in changed:
        if isinstance(row,TranslationProject):roots[id(row)]=row
        elif isinstance(row,TranslationSubOrder):
            status=inspect(row).attrs.status.history
            if row.status in CONFIRMED_STATUSES or any(value in CONFIRMED_STATUSES for value in status.deleted):
                root=session.get(TranslationProject,row.parent_project_id)
                if root:roots[id(root)]=root
    if not roots:return
    with session.no_autoflush:
        for root in roots.values():
            if not root.id:root.id=uuid4()
            evidence=session.get(ClientProjectConfirmation,root.id)
            history=inspect(root).attrs.project_status.history
            child_confirmed=any(isinstance(row,TranslationSubOrder) and row.parent_project_id==root.id and (row.status in CONFIRMED_STATUSES or any(value in CONFIRMED_STATUSES for value in inspect(row).attrs.status.history.deleted)) for row in changed)
            if not evidence and (root.project_status in CONFIRMED_STATUSES or any(value in CONFIRMED_STATUSES for value in history.deleted) or child_confirmed):
                evidence=ClientProjectConfirmation(project_id=root.id,confirmed_at=business_now());session.add(evidence)
            if not evidence:continue
            evidence.received_at=business_datetime(root.customer_reception_time) if root.customer_reception_time else None
            sub=session.get(SubClient,root.sub_client_id) if root.sub_client_id else None
            client_id=root.client_id or (sub.parent_client_id if sub else None)
            client=session.get(Client,client_id) if client_id else None
            for owner in (client,sub):
                if not owner:continue
                before=(owner.client_status,owner.cooperation_start_date)
                owner.client_status='active'
                if root.customer_reception_time:
                    received=business_datetime(root.customer_reception_time).replace(tzinfo=None)
                    if owner.cooperation_start_date is None or received<business_datetime(owner.cooperation_start_date).replace(tzinfo=None):owner.cooperation_start_date=received
                if before!=(owner.client_status,owner.cooperation_start_date):owner.updated_at=business_now().replace(tzinfo=None)


event.listen(Session,'before_flush',capture)
