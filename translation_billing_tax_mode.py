"""订单计费税口径；保留含税、不含税原值，只选择实际计费口径。"""
from decimal import Decimal
from sqlalchemy import Column,Uuid,String,DateTime,ForeignKey,CheckConstraint,inspect
from models import Base
from annotation_progress_time import business_now
from fastapi import HTTPException


class TranslationBillingTaxMode(Base):
    __tablename__='translation_billing_tax_mode'
    __table_args__=(CheckConstraint("mode IN ('excl_tax','incl_tax')",name='ck_translation_billing_tax_mode'),)
    order_id=Column(Uuid,primary_key=True)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False,index=True)
    mode=Column(String(16),nullable=False)
    updated_by=Column(Uuid,nullable=False)
    updated_at=Column(DateTime(timezone=True),nullable=False)


def ready(db):
    return db is not None and inspect(db.connection()).has_table(TranslationBillingTaxMode.__tablename__)


def modes(db,project_id):
    if not ready(db):return {}
    cache=db.info.setdefault('translation_billing_tax_modes',{})
    key=str(project_id)
    if key not in cache:cache[key]={str(row.order_id):row.mode for row in db.query(TranslationBillingTaxMode).filter_by(project_id=project_id).all()}
    return cache[key]


def save(db,user,project,owner,mode):
    if not ready(db):raise HTTPException(503,'计费口径存储尚未初始化')
    row=db.get(TranslationBillingTaxMode,owner.id)
    if mode is None:
        if row is not None:db.delete(row)
    else:
        if row is None:row=TranslationBillingTaxMode(order_id=owner.id,project_id=project.id);db.add(row)
        row.mode=mode;row.updated_by=user.id;row.updated_at=business_now()
    owner.updated_at=project.updated_at=business_now().replace(tzinfo=None)
    db.info.setdefault('translation_billing_tax_modes',{}).pop(str(project.id),None)


def available(node):
    result=[]
    for mode,override in [('excl_tax','adjusted_total'),('incl_tax','adjusted_total_incl_tax')]:
        if node.get(override) is not None or node.get('totals_'+mode) or any((price.get('tax_prices') or {}).get('unit_price_'+mode) is not None for price in node.get('prices',[])):
            result.append(mode)
    return result


def effective(node,requested=None,fallback='excl_tax'):
    options=available(node)
    if len(options)==1:return options[0]
    return requested if requested in options else fallback if fallback in options else options[0] if options else None


def attach(node,stored,fallback='excl_tax'):
    for child in node.get('children',[]):attach(child,stored,fallback)
    node['billing_tax_mode']=stored.get(node['id'])
    mode=effective(node,node['billing_tax_mode'],fallback)
    if node.get('children'):
        amounts={};chosen=set()
        for child in node['children']:
            chosen.add(child.get('effective_billing_tax_mode'))
            for currency,amount in child.get('billing_totals',{}).items():amounts[currency]=amounts.get(currency,Decimal(0))+Decimal(amount)
        mode=next(iter(chosen)) if len(chosen)==1 else 'mixed'
        node['billing_totals']={currency:str(amount) for currency,amount in amounts.items()}
    else:node['billing_totals']=node.get('totals_'+mode,{}) if mode else {}
    node['effective_billing_tax_mode']=mode
