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
    if db is None:
        return False
    key = 'translation_billing_tax_mode_ready'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(TranslationBillingTaxMode.__tablename__)
    return db.info[key]


def load_modes(db, project_ids):
    if not project_ids or not ready(db):
        return
    cache = db.info.setdefault('translation_billing_tax_modes', {})
    missing = {project_id for project_id in project_ids if str(project_id) not in cache}
    if not missing:
        return
    cache.update({str(project_id): {} for project_id in missing})
    for project_id, order_id, mode in db.query(
        TranslationBillingTaxMode.project_id, TranslationBillingTaxMode.order_id, TranslationBillingTaxMode.mode,
    ).filter(TranslationBillingTaxMode.project_id.in_(missing)):
        cache[str(project_id)][str(order_id)] = mode


def modes(db,project_id):
    if db is None:
        return {}
    load_modes(db, [project_id])
    return db.info.get('translation_billing_tax_modes', {}).get(str(project_id), {})


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
    db.info.pop('translation_monthly_tax_modes',None)


def available(node):
    result=[]
    for mode,override in [('excl_tax','adjusted_total'),('incl_tax','adjusted_total_incl_tax')]:
        if node.get(override) is not None or node.get('totals_'+mode) or any(
            (price.get('tax_prices') or {}).get(prefix+mode) is not None
            for price in node.get('prices',[]) for prefix in ('unit_price_', 'total_')
        ):
            result.append(mode)
    return result


def effective(node,requested=None,fallback='excl_tax'):
    options=available(node)
    if len(options)==1:return options[0]
    return requested if requested in options else fallback if fallback in options else options[0] if options else None


def order_mode(node, stored, fallback):
    if stored.get(node['id']):
        return stored[node['id']]
    if node.get('price_aggregate'):
        modes = {order_mode(child, stored, None) for child in node['children']} - {None}
        return next(iter(modes)) if len(modes) == 1 else fallback
    return effective(node, fallback=fallback)


def attach(node,stored,fallback='excl_tax',unified=None):
    for child in node.get('children',[]):
        attach(child,stored,fallback,unified)
    node['billing_tax_mode']=stored.get(node['id'])
    mode=unified or effective(node,node['billing_tax_mode'],fallback)
    if node.get('price_aggregate'):
        amounts={};chosen=set()
        for child in node['children']:
            chosen.add(child.get('effective_billing_tax_mode'))
            for currency,amount in child.get('billing_totals',{}).items():amounts[currency]=amounts.get(currency,Decimal(0))+Decimal(amount)
        mode=unified or (next(iter(chosen)) if len(chosen)==1 else 'mixed')
        override = node.get('effective_total_adjustment') or {}
        if mode not in ('excl_tax', 'incl_tax') and override:
            mode = effective(node, fallback=fallback)
        if mode in override:
            amounts[override['currency']] = override[mode]
        node['billing_totals']={currency:str(amount) for currency,amount in amounts.items()}
        if unified:
            node['billing_tax_pending'] = any(
                child.get('billing_tax_pending') and (mode not in override or
                    bool(set(child.get('totals_'+mode, {})) - {override['currency']}))
                for child in node['children']
            )
    else:
        node['billing_totals']=node.get('totals_'+mode,{}) if mode else {}
        if unified and not node.get('fixed_pricing_from'):
            override = (node.get('effective_total_adjustment') or {}).get(
                unified, node.get('adjusted_total' if unified == 'excl_tax' else 'adjusted_total_incl_tax')
            )
            missing_price = any(
                (price.get('tax_prices') or {}).get('unit_price_'+unified) is None
                and (price.get('tax_prices') or {}).get('total_'+unified) is None
                for price in node.get('prices', [])
            )
            node['billing_tax_pending'] = override is None and (not node['billing_totals'] or missing_price)
    if unified:
        node['unified_billing_tax_mode']=unified
        node['incomplete'] |= node.get('billing_tax_pending', False)
    direct_adjustment = node.get('total_adjustment') or {}
    legacy_amount = node.get('adjusted_total_incl_tax' if mode=='incl_tax' else 'adjusted_total')
    manual = direct_adjustment.get(mode) if node.get('price_aggregate') or node.get('pricing_mode')=='fixed' else legacy_amount
    if manual is not None and node['billing_totals']:
        currency = direct_adjustment.get('currency') or node['currency']
        priced_currencies = {price.get('currency') for price in node.get('prices', [])}
        if priced_currencies <= {currency}:
            node['incomplete'] = False
    node['effective_billing_tax_mode']=mode
