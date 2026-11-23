"""财务内部说明沿用旧收费备注；客户说明单独保存，作为对外对账单备注。"""
from uuid import UUID
import hashlib,json
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

def load_rows(db, project_ids):
    if not project_ids or not ready(db):
        return
    cache=db.info.setdefault('translation_finance_notes_cache',{})
    missing = {project_id for project_id in project_ids if str(project_id) not in cache}
    if not missing:
        return
    cache.update({str(project_id): {} for project_id in missing})
    for row in db.query(TranslationFinanceNote).filter(TranslationFinanceNote.project_id.in_(missing)):
        cache[str(row.project_id)][str(row.order_id)] = row


def rows(db,project_id):
    if db is None:
        return {}
    load_rows(db, [project_id])
    return db.info.get('translation_finance_notes_cache', {}).get(str(project_id), {})

def values(db,project,owner,charge):
    row=rows(db,project.id).get(str(owner.id))
    return dict(explanation=(charge.remarks or '') if charge else (row.internal_note or '' if row else ''),customer_explanation=row.customer_note or '' if row else '')

def sync_targets(project,owner):
    prefix=getattr(owner,'sub_order_no',None)
    return [owner,*sorted([child for child in project.sub_orders if child.id!=owner.id and (owner is project or prefix and child.sub_order_no.startswith(prefix+'.'))],key=lambda child:child.sub_order_no)]


def apply(db,user,project,owner,*,internal=None,customer=None):
    if internal is None and customer is None:return
    if not ready(db):raise HTTPException(503,'客户说明存储尚未初始化')
    targets=sync_targets(project,owner)
    overwritten=[]
    for target in targets[1:]:
        row=db.get(TranslationFinanceNote,target.id)
        existing_internal=(row.internal_note or '') if row else ''
        if not existing_internal.strip():existing_internal='\n'.join(dict.fromkeys(charge.remarks for charge in target.customer_charge_items if charge.remarks and charge.remarks.strip()))
        for field,previous,value in [('内部说明',existing_internal,internal),('客户说明',(row.customer_note or '') if row else '',customer)]:
            if value is not None and previous.strip() and previous!=value:
                overwritten.append(dict(order_id=str(target.id),order_no=target.sub_order_no,field=field,before=previous,after=value))
    if overwritten:
        plan=hashlib.sha256(json.dumps(overwritten,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        if plan not in db.info.get('finance_note_sync_plans',[]):
            raise HTTPException(409,dict(code='finance_note_sync_confirmation_required',message='同步会覆盖子订单已有说明，请确认后继续',plan=plan,overwrites=overwritten))
    moment=business_now()
    for target in targets:
        row=db.get(TranslationFinanceNote,target.id)
        if row is None:row=TranslationFinanceNote(order_id=target.id,project_id=project.id,sub_order_id=None if target is project else target.id,revision=0,customer_note='');db.add(row)
        if internal is not None:
            row.internal_note=internal
            for charge in target.customer_charge_items:charge.remarks=internal
        if customer is not None:row.customer_note=customer
        row.revision+=1;row.updated_by=user.id;row.updated_at=moment
        target.updated_at=moment.replace(tzinfo=None)
    project.updated_at=moment.replace(tzinfo=None)
    db.info.setdefault('translation_finance_notes_cache',{}).pop(str(project.id),None)
