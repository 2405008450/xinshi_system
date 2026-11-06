"""财务内部说明沿用旧收费备注；客户说明单独保存，作为对外对账单备注。"""
from uuid import UUID
from sqlalchemy import Column,Uuid,ForeignKey,Text,Integer,DateTime,CheckConstraint,inspect
from fastapi import HTTPException
from models import Base
from annotation_progress_time import business_now

class TranslationFinanceNote(Base):
    __tablename__='translation_finance_note'
    __table_args__=(CheckConstraint('(sub_order_id IS NULL AND order_id=project_id) OR order_id=sub_order_id',name='ck_translation_finance_note_owner'),)
    order_id=Column(Uuid,primary_key=True)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False,index=True)
    sub_order_id=Column(Uuid,ForeignKey('translation_sub_order.id',ondelete='CASCADE'),unique=True)
    internal_note=Column(Text)
    customer_note=Column(Text,nullable=False,default='')
    revision=Column(Integer,nullable=False,default=0)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)

def ready(db):
    if db.info.get('translation_finance_notes_ready'):return True
    value=inspect(db.connection()).has_table(TranslationFinanceNote.__tablename__)
    if value:db.info['translation_finance_notes_ready']=True
    return value

def rows(db,project_id):
    if not db or not ready(db):return {}
    cache=db.info.setdefault('translation_finance_notes_cache',{})
    key=str(project_id)
    if key not in cache:cache[key]={str(row.order_id):row for row in db.query(TranslationFinanceNote).filter_by(project_id=project_id).all()}
    return cache[key]

def values(db,project,owner,charge):
    row=rows(db,project.id).get(str(owner.id))
    return dict(explanation=(charge.remarks or '') if charge else (row.internal_note or '' if row else ''),customer_explanation=row.customer_note or '' if row else '')

def apply(db,user,project,owner,*,internal=None,customer=None):
    if internal is None and customer is None:return
    if not ready(db):raise HTTPException(503,'客户说明存储尚未初始化')
    row=db.get(TranslationFinanceNote,owner.id)
    if row is None:row=TranslationFinanceNote(order_id=owner.id,project_id=project.id,sub_order_id=None if owner is project else owner.id,revision=0,customer_note='');db.add(row)
    if internal is not None:
        row.internal_note=internal
        for charge in owner.customer_charge_items:charge.remarks=internal
    if customer is not None:row.customer_note=customer
    row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    owner.updated_at=project.updated_at=business_now().replace(tzinfo=None)
    db.info.setdefault('translation_finance_notes_cache',{}).pop(str(project.id),None)
