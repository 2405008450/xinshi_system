"""笔译客户财务修改记录：价格、调价及下级继承变化同事务保存。"""
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import Column,ForeignKey,String,Uuid,DateTime,JSON,Index,inspect
from models import Base
from annotation_progress_time import business_now,business_datetime


class TranslationFinanceEvent(Base):
    __tablename__='translation_customer_finance_event'
    id=Column(Uuid,primary_key=True,default=uuid4)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_id=Column(Uuid,nullable=False)
    actor_name=Column(String(255),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False)


class TranslationFinanceEventItem(Base):
    __tablename__='translation_customer_finance_event_item'
    __table_args__=(Index('ix_translation_finance_event_item_order','order_id'),)
    event_id=Column(Uuid,ForeignKey('translation_customer_finance_event.id',ondelete='CASCADE'),primary_key=True)
    order_id=Column(Uuid,primary_key=True)
    order_no=Column(String(100),nullable=False)
    project_name=Column(String(255),nullable=False)
    before_snapshot=Column(JSON,nullable=False)
    after_snapshot=Column(JSON,nullable=False)


def ready(db):
    inspector=inspect(db.connection())
    return inspector.has_table(TranslationFinanceEvent.__tablename__) and inspector.has_table(TranslationFinanceEventItem.__tablename__)


def require_ready(db):
    if not ready(db):raise HTTPException(503,'客户财务修改记录尚未初始化，请联系管理员')


def capture(project):
    from translation_customer_finance import tree
    result={}
    def visit(row):
        fields=('order_no','project_name','prices','recorded_prices','price_aggregate','recorded_adjusted_total','recorded_adjusted_total_incl_tax','adjusted_total','explanation','customer_explanation','billing_month','recorded_billing_month','totals','adjusted_totals','calculated_totals_excl_tax','calculated_totals_incl_tax')
        result[row['id']]={field:row.get(field) for field in fields}
        result[row['id']].update({field:row.get(field) for field in ('billing_tax_mode','effective_billing_tax_mode','billing_totals')})
        if row['id']==str(project.id):
            result[row['id']].update({field:row.get(field) for field in ('quotation_required','statement_required','quotation_draft','document_notes','invoice_data')})
        if result[row['id']]['adjusted_total'] is not None:
            from decimal import Decimal
            result[row['id']]['adjusted_total']=format(Decimal(result[row['id']]['adjusted_total']),'.2f')
        for child in row['children']:visit(child)
    visit(tree(project)['item'])
    return result


def append(db,user,project,before):
    require_ready(db);db.flush();after=capture(project)
    changed=[key for key in set(before)|set(after) if before.get(key)!=after.get(key)]
    if not changed:return
    event=TranslationFinanceEvent(id=uuid4(),project_id=project.id,actor_id=user.id,actor_name=user.full_name or user.username,created_at=business_now())
    db.add(event);db.flush()
    from uuid import UUID
    for key in changed:
        row=after.get(key) or before[key]
        db.add(TranslationFinanceEventItem(event_id=event.id,order_id=UUID(key),order_no=row['order_no'],project_name=row['project_name'] or '-',before_snapshot=before.get(key,{}),after_snapshot=after.get(key,{})))


def history(db,project_id,order_id=None,page=1):
    if not ready(db):return {'ready':False,'items':[],'total':0}
    q=db.query(TranslationFinanceEventItem,TranslationFinanceEvent).join(TranslationFinanceEvent,TranslationFinanceEvent.id==TranslationFinanceEventItem.event_id).filter(TranslationFinanceEvent.project_id==project_id)
    if order_id and order_id!=project_id:q=q.filter(TranslationFinanceEventItem.order_id==order_id)
    total=q.count()
    rows=q.order_by(TranslationFinanceEvent.created_at.desc(),TranslationFinanceEvent.id.desc(),TranslationFinanceEventItem.order_no).offset((page-1)*10).limit(10).all()
    return {'ready':True,'total':total,'items':[{'id':str(event.id)+':'+str(item.order_id),'actor_name':event.actor_name,'created_at':business_datetime(event.created_at).isoformat(),
        'order_no':item.order_no,'project_name':item.project_name,'before':item.before_snapshot,'after':item.after_snapshot} for item,event in rows]}
