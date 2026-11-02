"""预览并确认同客户、同账单月份、同语种方向的各级订单单价同步。"""
import hashlib,json
from decimal import Decimal
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from database import get_db
from models import TranslationProject,TranslationSubOrder,TranslationSubOrderChargeItem
from routers.auth import require_permission,get_current_user
from annotation_progress_time import business_now
import translation_customer_finance as finance
import customer_translation_rates as rates
import translation_quantity_basis as basis
import translation_finance_audit as audit


class SyncScope(BaseModel):
    order_id:UUID
    version:str
    billing_month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    token:str|None=None


def plan(db,project_id,payload,lock=False):
    source=finance.crud.get_translation_project(db,project_id)
    if not source or not source.client_id:raise HTTPException(422,'请先保存项目及关联客户')
    roots=db.query(TranslationProject).filter_by(client_id=source.client_id).filter(TranslationProject.annotation_migrated_at.is_(None)).order_by(TranslationProject.id)
    if lock:roots=roots.with_for_update().populate_existing()
    roots=roots.all()
    if lock:db.query(TranslationSubOrder).filter(TranslationSubOrder.parent_project_id.in_([root.id for root in roots])).order_by(TranslationSubOrder.id).with_for_update().populate_existing().all()
    rates.invalidate_metadata(db);basis.invalidate(db)
    projects=[finance.crud.get_translation_project(db,root.id) for root in roots]
    source=next((root for root in projects if root.id==project_id),None)
    if source is None:raise HTTPException(409,'来源订单的客户已变化，请重新预览')
    if finance.version(source)!=payload.version:raise HTTPException(409,'来源订单已变化，请重新打开后预览')
    source_owner=next((owner for owner in finance.hierarchy(source)[0] if owner.id==payload.order_id),None)
    if source_owner is None:raise HTTPException(422,'来源订单不属于当前项目')
    source_month_ids={str(row.id) for row in source_owner.customer_charge_items if row.billing_month==payload.billing_month}
    source_prices=[row for row in rates.order_rates(db,source_owner,source_owner.language_pair or source.language_pair) if row['id'] in source_month_ids]
    if not source_prices or any(row['amount'] is None for row in source_prices):raise HTTPException(422,'请先保存来源订单的单价及账单月份，再进行同步')
    directions={row['language_pair'] for row in source_prices}
    targets=[];versions={str(source.id):finance.version(source)}
    owners={}
    for root in projects:
        root_owners,_,parents=finance.hierarchy(root)
        explicit_months={str(owner.id):{row.billing_month for row in owner.customer_charge_items if row.billing_month} for owner in root_owners}
        all_months=set().union(*explicit_months.values())
        def order_months(owner_id):
            if explicit_months[owner_id]:return explicit_months[owner_id]
            parent=parents.get(owner_id)
            return order_months(parent) if parent else all_months if len(all_months)==1 else set()
        for owner in root_owners:
            if owner.id==source_owner.id:continue
            months=order_months(str(owner.id))
            if payload.billing_month not in months:continue
            choices=set(str(owner.language_pair or root.language_pair or '').split('；'))
            selected=[dict(row,id=None,reference_id=None,reference_revision=None) for row in source_prices if row['language_pair'] in choices]
            if not selected:continue
            existing=rates.order_rates(db,owner,owner.language_pair or root.language_pair)
            order_no=root.order_no if owner is root else owner.sub_order_no
            targets.append({'project_id':str(root.id),'order_id':str(owner.id),'order_no':order_no,'project_name':root.project_name if owner is root else owner.sub_project_name,
                            'language_pair':owner.language_pair or root.language_pair,'before':existing,'prices':selected})
            owners[str(owner.id)]=(root,owner)
            versions[str(root.id)]=finance.version(root)
    targets.sort(key=lambda row:(row['project_id'],row['order_no']))
    token=hashlib.sha256(json.dumps({'versions':versions,'month':payload.billing_month,'source':source_prices,'targets':targets},sort_keys=True,default=str).encode()).hexdigest()
    return {'client_id':str(source.client_id),'client_name':source.client_short_name or source.client_name,'billing_month':payload.billing_month,'directions':sorted(directions),'targets':targets,'token':token},owners


def apply(db,user,project_id,payload):
    audit.require_ready(db)
    preview,owners=plan(db,project_id,payload,True)
    if not payload.token or preview['token']!=payload.token:raise HTTPException(409,'匹配订单或单价已变化，请重新预览后确认')
    captured={};roots={};moment=business_now().replace(tzinfo=None)
    for target in preview['targets']:
        root,owner=owners[target['order_id']]
        if root.id not in captured:captured[root.id]=audit.capture(root);roots[root.id]=root
        directions={row['language_pair'] for row in target['prices']}
        old={UUID(row['id']):row for row in target['before']}
        existing=[row for row in owner.customer_charge_items if row.pricing_mode=='metric' and row.billing_month in (None,payload.billing_month) and old.get(row.id,{}).get('language_pair') in directions]
        keys={rates.rate_key(old[row.id]):row for row in existing};kept=set()
        for data in target['prices']:
            charge=keys.get(rates.rate_key(data))
            if charge and charge.id in kept:charge=None
            if charge is None:charge=next((row for row in existing if row.id not in kept and old[row.id]['language_pair']==data['language_pair'] and row.currency==data['currency']),None)
            if charge is None:
                charge=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=root.id if owner is root else None,sub_order_id=None if owner is root else owner.id,
                    sequence_no=max((row.sequence_no or 0 for row in owner.customer_charge_items),default=0)+1,item_name='翻译费',pricing_mode='metric',created_at=moment)
                owner.customer_charge_items.append(charge)
            kept.add(charge.id)
            charge.unit_price=charge.unit_price_excl_tax=Decimal(data['amount']);charge.currency=data['currency'];charge.metric_type=basis.resolve(owner.word_count_matrix,data['metric'])[2] or 'characters_no_spaces';charge.unit_size=Decimal(data['unit_size']);charge.billing_month=payload.billing_month;charge.updated_at=moment
            db.flush();basis.store(db,charge,data['metric'],owner.word_count_matrix)
            meta=db.get(rates.TranslationChargeDirection,charge.id)
            if meta is None:meta=rates.TranslationChargeDirection(charge_id=charge.id);db.add(meta)
            meta.language_pair=data['language_pair'];meta.reference_id=None;meta.reference_revision=None
        for charge in existing:
            if charge.id in kept:continue
            if charge.total_excl_tax is not None or charge.amount_override is not None:raise HTTPException(409,f'订单{target["order_no"]}存在不能合并的手动调价，请先核对该订单')
            meta=db.get(rates.TranslationChargeDirection,charge.id)
            if meta:db.delete(meta)
            if basis.ready(db):
                mode=db.get(basis.TranslationChargeQuantityBasis,charge.id)
                if mode:db.delete(mode)
            owner.customer_charge_items.remove(charge);db.delete(charge)
        owner.updated_at=moment;root.updated_at=moment
    db.flush();rates.invalidate_metadata(db);basis.invalidate(db)
    for root_id,root in roots.items():audit.append(db,user,root,captured[root_id])
    db.commit()
    return {'updated_orders':len(preview['targets'])}


router=APIRouter(prefix='/translation-customer-finance',tags=['translation-customer-finance'])


@router.post('/project/{project_id}/sync-orders/preview',dependencies=[Depends(require_permission('projects:write'))])
def preview(project_id:UUID,payload:SyncScope,db=Depends(get_db)):
    return plan(db,project_id,payload)[0]


@router.post('/project/{project_id}/sync-orders/apply',dependencies=[Depends(require_permission('projects:write'))])
def execute(project_id:UUID,payload:SyncScope,db=Depends(get_db),user=Depends(get_current_user)):
    try:return apply(db,user,project_id,payload)
    except Exception:db.rollback();raise
