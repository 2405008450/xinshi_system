"""客户计价及订单树汇总；复用既有收费表，不更改数据库结构。"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import re
from hashlib import sha256
import json
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session, joinedload, selectinload, object_session
from database import get_db
from models import TranslationProject, TranslationSubOrder, TranslationSubOrderChargeItem, Client, SubClient, AppUser
from routers.auth import get_current_user, require_permission, require_module_access
from annotation_progress_time import business_now, business_datetime
import crud
import customer_translation_rates as rates
import translation_finance_audit as audit
import translation_quantity_basis as quantity_basis
import translation_payment_confirmation as confirmations
from translation_payment_confirmation import PaymentConfirmationWrite
from permission_service import user_has_permission

METRICS = {'characters_no_spaces','words','foreign_words','cjk_chars_korean_words','documents','pages'}


class PriceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    payment_confirmation: PaymentConfirmationWrite | None = None
    version: str
    order_id: UUID
    pricing_mode: Literal['metric','fixed'] = 'metric'
    amount: Decimal | None = Field(default=None,ge=0, max_digits=14, decimal_places=4)
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')
    metric: str = 'characters_no_spaces'
    unit_size: Decimal = Field(default=Decimal('1'), gt=0, max_digits=14, decimal_places=4)
    adjusted_total: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    adjusted_total_incl_tax: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    explanation: str = Field(default='', max_length=5000)
    billing_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    prices: list[rates.RateInput] | None = Field(default=None,min_length=1,max_length=100)
    update_library: bool = False
    sync_confirmed: bool = False
    library_version: str | None = None


def primary(owner):
    rows = sorted(owner.customer_charge_items or [], key=lambda row: row.sequence_no or 0)
    return next((row for row in rows if row.item_name == '翻译费' and row.pricing_mode == 'metric'), next((row for row in rows if row.pricing_mode == 'metric'), next((row for row in rows if row.pricing_mode=='fixed'),None)))


def signature(row):
    if row is None:
        return None
    amount=row.unit_price_excl_tax if row.unit_price_excl_tax is not None else row.unit_price
    return (Decimal(str(amount)).normalize() if amount is not None else None,
            row.currency or 'CNY', row.metric_type, Decimal(str(row.unit_size)).normalize() if row.unit_size is not None else None)


def hierarchy(project):
    owners = [project, *sorted(project.sub_orders or [], key=lambda row: row.sub_order_no)]
    numbers = {str(project.id): project.order_no, **{str(row.id): row.sub_order_no for row in owners[1:]}}
    by_number = {number: key for key, number in numbers.items()}
    parents = {str(row.id): by_number.get(row.sub_order_no.rsplit('.', 1)[0], str(project.id)) for row in owners[1:]}
    return owners, numbers, parents


def version(project):
    owners, numbers, parents = hierarchy(project)
    fields = []
    for owner in owners:
        fields.append([str(owner.id), numbers[str(owner.id)], parents.get(str(owner.id)), str(owner.updated_at),
                       owner.word_count_matrix,
                       [[str(row.id), str(signature(row)),str(row.unit_price_incl_tax),str(Decimal(str(row.total_excl_tax)).normalize()) if row.total_excl_tax is not None else None,str(Decimal(str(row.total_incl_tax)).normalize()) if row.total_incl_tax is not None else None,row.billing_month,row.remarks,str(row.updated_at)] for row in owner.customer_charge_items]])
    db=object_session(project)
    if db:
        fields.append([rates.order_rates(db,owner,owner.language_pair or project.language_pair) for owner in owners])
    return sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def order_billing_month(order_no):
    match=re.match(r'^TP-(\d{8}|\d{6})-',str(order_no or '').strip().upper())
    if not match:return None
    digits=match[1]
    year,month=(digits[:4],digits[4:6]) if len(digits)==8 else ('20'+digits[:2],digits[2:4])
    return f'{year}-{month}' if 1<=int(month)<=12 else None


def tree(project, billing_month=None):
    owners, numbers, parents = hierarchy(project)
    db=object_session(project)
    meta=rates.metadata(db,[charge.id for owner in owners for charge in owner.customer_charge_items]) if db else {}
    nodes = {}
    for owner in owners:
        key = str(owner.id); row = primary(owner)
        rate = signature(row)
        nodes[key] = dict(id=key,root_id=str(project.id),order_no=numbers[key],project_name=(project.source_file_name or project.project_name) if owner is project else owner.sub_project_name,
            pricing_mode=row.pricing_mode if row else 'metric',
            client_short_name=project.client_short_name or project.client_name or '-',project_status=project.project_status if owner is project else owner.status,
            language_pair=owner.language_pair or project.language_pair, children=[], amount=str(rate[0]) if rate and rate[0] is not None else None,
            currency=rate[1] if rate else 'CNY',metric=rate[2] if rate else 'characters_no_spaces',unit_size=str(rate[3] or 1) if rate else '1',
            adjusted_total=str(row.total_excl_tax) if row and row.total_excl_tax is not None else None,
            adjusted_total_incl_tax=str(row.total_incl_tax) if row and row.total_incl_tax is not None else None,
            billing_month=row.billing_month if row else None,
            explanation=row.remarks or '' if row else '',word_count_matrix=owner.word_count_matrix)
        nodes[key]['prices']=rates.order_rates(db,owner,owner.language_pair or project.language_pair,meta) if db else []
        effective_client_id=project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
        nodes[key]['client_id']=str(effective_client_id) if effective_client_id else None
        if owner is project:
            nodes[key]['payment_confirmation']=confirmations.read(db,project.id) if db else PaymentConfirmationWrite().model_dump()
            nodes[key]['statement_required']=bool(getattr(project,'statement_required',True))
            nodes[key]['client_manager']=getattr(project,'client_manager',None) or ''
            nodes[key]['updated_at']=business_datetime(project.updated_at).isoformat() if project.updated_at else None
    for key, parent in parents.items():
        nodes[parent]['children'].append(nodes[key])

    def calculate(node, inherited=None):
        if node['pricing_mode']=='fixed':
            included=[]
            for child in node['children']:
                calculate(child)
                if not billing_month or child['matches_month']:included.append(child)
            matches=not billing_month or order_billing_month(project.order_no)==billing_month
            excl={node['currency']:node['adjusted_total']} if node['adjusted_total'] is not None and matches else {}
            incl={node['currency']:node['adjusted_total_incl_tax']} if node['adjusted_total_incl_tax'] is not None and matches else {}
            node.update(children=included,matches_month=matches or bool(included),totals=excl,adjusted_totals=excl,totals_excl_tax=excl,totals_incl_tax=incl,incomplete=not excl and not incl,quantity=None,own_total=None)
            return
        if not node['prices'] and inherited:
            choices=set(str(node['language_pair'] or '').split('；'))
            node['prices']=[{**row,'id':None,'inherited':True} for row in inherited['prices'] if not node['language_pair'] or row['language_pair'] in choices]
        amounts={};missing=False
        tax_amounts={'excl_tax':{},'incl_tax':{}}
        for price in node['prices']:
            quantity,dimension,actual_metric,quantity_error=quantity_basis.resolve(node['word_count_matrix'],price['metric'])
            price['quantity']=quantity
            price['quantity_dimension']=dimension;price['quantity_metric']=actual_metric;price['quantity_error']=quantity_error
            amount=None if quantity is None or price['amount'] is None else (Decimal(str(quantity))*Decimal(price['amount'])/Decimal(price['unit_size'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            price['total']=str(amount) if amount is not None else None
            for kind, values in tax_amounts.items():
                tax = price.get('tax_prices') or {}
                total = tax.get('total_'+kind)
                unit = tax.get('unit_price_'+kind)
                if total is None and unit is not None and quantity is not None:
                    total = Decimal(str(quantity))*Decimal(str(unit))/Decimal(price['unit_size'])
                if total is not None:
                    values[price['currency']] = values.get(price['currency'],Decimal(0))+Decimal(str(total))

            if amount is None:missing=True
            else:amounts[price['currency']]=amounts.get(price['currency'],Decimal(0))+amount
        if node['amount'] is None and inherited and (not inherited['prices'] or node['prices']):
            for key in ('amount','currency','metric','unit_size'):
                node[key] = inherited[key]
            node['inherited'] = True
            node['billing_month'] = node['billing_month'] or inherited.get('billing_month')
        count = node['word_count_matrix'].get('customer', {}).get(node['metric'])
        node['quantity'] = count
        own = None if count is None or node['amount'] is None else (Decimal(str(count))*Decimal(node['amount'])/Decimal(node['unit_size'])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        node['own_total'] = str(own) if own is not None else None
        totals, adjusted, incomplete = {}, {}, False
        original_children=node['children']
        included=[]
        for child in original_children:
            calculate(child, node if node['amount'] is not None else None)
            if billing_month and not child['matches_month']: continue
            included.append(child)
            incomplete |= child['incomplete']
            for key, value in child['totals'].items(): totals[key] = totals.get(key, Decimal(0))+Decimal(value)
            for key, value in child['adjusted_totals'].items(): adjusted[key] = adjusted.get(key, Decimal(0))+Decimal(value)
        matches=not billing_month or order_billing_month(project.order_no)==billing_month
        if not original_children:
            incomplete = matches and (missing if node['prices'] else own is None)
            if matches and node['prices']:totals.update(amounts)
            elif matches and own is not None: totals[node['currency']] = own
            effective = Decimal(node['adjusted_total']) if node['adjusted_total'] is not None else own
            if matches and node['prices']:adjusted.update(amounts)
            if matches and effective is not None and (node['adjusted_total'] is not None or not node['prices']): adjusted[node['currency']] = effective
        elif node['adjusted_total'] is not None and matches:
            # 父级明确调整金额只覆盖本币种；其他币种仍单列。
            adjusted[node['currency']] = Decimal(node['adjusted_total'])
        for kind in tax_amounts:
            values = {} if original_children else tax_amounts[kind]
            if original_children:
                for child in included:
                    for currency, value in child.get('totals_'+kind,{}).items():
                        values[currency]=values.get(currency,Decimal(0))+Decimal(value)
            override=node.get('adjusted_total' if kind=='excl_tax' else 'adjusted_total_incl_tax')
            if override is not None and matches: values[node['currency']]=Decimal(override)
            node['totals_'+kind]={currency:str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for currency,value in values.items()}
        node.update(children=included,matches_month=matches or bool(included),totals={k:str(v) for k,v in totals.items()},adjusted_totals={k:str(v) for k,v in adjusted.items()},incomplete=incomplete)
    root=nodes[str(project.id)];calculate(root)
    return {'item':root,'version':version(project)}


def read(db, project_id):
    project=crud.get_translation_project(db,project_id)
    if not project: raise HTTPException(404,'笔译项目不存在')
    db.expire(project,['sub_orders','customer_charge_items'])
    for child in project.sub_orders: db.expire(child,['customer_charge_items'])
    crud._attach_word_count_matrices(db,projects=[project])
    result=tree(project)
    result['reference_prices']=rates.library(db,project.client_id) if project.client_id else {'ready':rates.ready(db),'items':[],'version':''}
    return result


def client_subtotals(db, filters):
    query=db.query(TranslationProject).options(joinedload(TranslationProject.client),selectinload(TranslationProject.customer_charge_items),
        selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items)).outerjoin(Client,TranslationProject.client_id==Client.id).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id).filter(TranslationProject.annotation_migrated_at.is_(None))
    projects=crud._apply_translation_project_filters(query,**filters).all()
    crud._attach_word_count_matrices(db,projects=projects)
    rates.metadata(db,[charge.id for project in projects for owner in [project,*project.sub_orders] for charge in owner.customer_charge_items])
    quantity_basis.metadata(db,[charge.id for project in projects for owner in [project,*project.sub_orders] for charge in owner.customer_charge_items])
    groups={}
    for project in projects:
        project.client_short_name=(project.client.client_short_name or project.client.client_name) if project.client else '-'
        project.client_name=project.client.client_name if project.client else '-'
        key=str(project.client_id) if project.client_id else 'unassigned'
        group=groups.setdefault(key,{'client_id':key,'client_name':project.client_short_name,'project_count':0,'totals':{},'adjusted_totals':{},'totals_excl_tax':{},'totals_incl_tax':{},'incomplete':False})
        month=(filters.get('field_filters') or {}).get('finance_billing_month',{}).get('value')
        node=tree(project,month)['item'];group['project_count']+=1;group['incomplete']|=node['incomplete']
        for field in ('totals','adjusted_totals','totals_excl_tax','totals_incl_tax'):
            for currency,amount in node[field].items():group[field][currency]=group[field].get(currency,Decimal(0))+Decimal(amount)
    for group in groups.values():
        for field in ('totals','adjusted_totals','totals_excl_tax','totals_incl_tax'):group[field]={key:str(value) for key,value in group[field].items()}
    return sorted(groups.values(),key=lambda row:row['client_name'])


def save_prices(db,user,project,owners,parents,key,payload):
    if not rates.ready(db):raise HTTPException(503,'客户语种单价存储尚未初始化')
    values=[rates.normalize(db,item) for item in payload.prices]
    keys=[rates.rate_key(item) for item in values]
    if len(set(keys))!=len(keys):raise HTTPException(422,'同语种、货币、计价口径的单价不能重复')
    if payload.adjusted_total is not None and len({item['currency'] for item in values})>1:raise HTTPException(422,'存在多个币种时请分别在下级订单调整金额')
    target=owners[key]
    own_ids={row.id for row in target.customer_charge_items if row.pricing_mode=='metric'}
    submitted_ids=[item.id for item in payload.prices if item.id]
    if len(set(submitted_ids))!=len(submitted_ids):raise HTTPException(422,'同一收费项不能重复提交，请删除重复单价')
    if any(item.id and item.id not in own_ids for item in payload.prices):raise HTTPException(422,'单价不属于当前订单，请重新打开后编辑')
    references={row.id:row for row in db.query(rates.CustomerTranslationRate).filter_by(client_id=project.client_id,active=True).all()} if project.client_id else {}
    for data in values:
        ref_id=data.get('reference_id')
        if ref_id:
            old_meta=db.get(rates.TranslationChargeDirection,data['id']) if data.get('id') in own_ids else None
            if old_meta and old_meta.reference_id==ref_id and old_meta.reference_revision==data.get('reference_revision'):continue
            ref=references.get(ref_id)
            if not ref or ref.revision!=data.get('reference_revision') or ref.rate_key!=rates.rate_key(data):raise HTTPException(409,'所采用的客户参考价已变化或不匹配，请重新选择')
    if payload.update_library:
        if not user_has_permission(db,user.id,'clients:write'):raise HTTPException(403,'同步客户参考价需要客户管理编辑权限')
        if not payload.sync_confirmed:raise HTTPException(422,'请点击并确认同步客户参考价')
        if not project.client_id:raise HTTPException(422,'请先为项目选择客户')
        rates.write_library(db,user,project.client_id,payload.prices,payload.library_version,origin='project',merge=True)
        references={row.id:row for row in db.query(rates.CustomerTranslationRate).filter_by(client_id=project.client_id,active=True).all()}
        by_key={row.rate_key:row for row in references.values()}
        for data in values:data.update(reference_id=by_key[rates.rate_key(data)].id,reference_revision=by_key[rates.rate_key(data)].revision)
    old={uid:rates.order_rates(db,owner,owner.language_pair or project.language_pair) for uid,owner in owners.items()}
    def comparable(items):
        from customer_finance_sync import tax_signature
        return {rates.rate_key(item):((str(Decimal(str(item['amount'])).normalize()) if item['amount'] is not None else None), tax_signature(item)) for item in items}
    moment=business_now().replace(tzinfo=None)
    def write(owner,items,explicit):
        for fixed in list(owner.customer_charge_items):
            if fixed.pricing_mode=='fixed':owner.customer_charge_items.remove(fixed);db.delete(fixed)
        existing=[row for row in owner.customer_charge_items if row.pricing_mode=='metric'];by_id={row.id:row for row in existing}
        by_key={rates.rate_key(item):by_id[UUID(item['id'])] for item in rates.order_rates(db,owner,owner.language_pair or project.language_pair)}
        kept=set()
        for index,data in enumerate(items):
            row=by_id.get(data.get('id')) if explicit else None
            row=row or by_key.get(rates.rate_key(data))
            if row is None:
                row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,created_at=moment)
                owner.customer_charge_items.append(row)
            kept.add(row.id)
            row.item_name='翻译费';row.pricing_mode='metric';row.sequence_no=index+1
            row.unit_price=data['amount'];
            tax=data.get('tax_prices')
            row.unit_price_excl_tax=tax.get('unit_price_excl_tax') if tax is not None else data['amount']
            if tax is not None:row.unit_price_incl_tax=tax.get('unit_price_incl_tax')
            row.currency=data['currency'];row.metric_type=quantity_basis.resolve(owner.word_count_matrix,data['metric'])[2] or 'characters_no_spaces';row.unit_size=data['unit_size']
            row.billing_month=payload.billing_month
            if explicit:row.total_excl_tax=row.amount_override=payload.adjusted_total if index==0 else None
            if explicit:row.total_incl_tax=payload.adjusted_total_incl_tax if index==0 else None
            if explicit:row.remarks=payload.explanation
            row.updated_at=moment
            db.flush()
            quantity_basis.store(db,row,data['metric'],owner.word_count_matrix)
            meta=db.get(rates.TranslationChargeDirection,row.id)
            if meta is None:meta=rates.TranslationChargeDirection(charge_id=row.id);db.add(meta)
            meta.language_pair=data['language_pair'];meta.reference_id=data.get('reference_id');meta.reference_revision=data.get('reference_revision')
        for row in existing:
            if row.id not in kept:
                if quantity_basis.ready(db):
                    basis=db.get(quantity_basis.TranslationChargeQuantityBasis,row.id)
                    if basis:db.delete(basis)
                meta=db.get(rates.TranslationChargeDirection,row.id)
                if meta:db.delete(meta)
                owner.customer_charge_items.remove(row);db.delete(row)
        owner.updated_at=moment
    write(target,values,True);changed={key:values}
    for uid,owner in owners.items():
        parent=parents.get(uid)
        if parent not in changed:continue
        before=comparable(old[uid]);parent_before=comparable(old[parent])
        if before and not all(k in parent_before and parent_before[k]==value for k,value in before.items()):continue
        choices=set(str(owner.language_pair or project.language_pair or '').split('；'))
        inherited=[item for item in changed[parent] if not choices or choices=={''} or item['language_pair'] in choices]
        if inherited:write(owner,inherited,False);changed[uid]=inherited
    project.updated_at=moment
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)


def save(db, user, project_id, payload):
    audit.require_ready(db)
    if payload.metric not in METRICS: raise HTTPException(422,'请选择有效的计价单位')
    client_id=db.query(TranslationProject.client_id).filter_by(id=project_id).scalar()
    if client_id:db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().first()
    project=db.query(TranslationProject).filter_by(id=project_id).filter(TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if not project: raise HTTPException(404,'笔译项目不存在')
    db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.id).with_for_update().populate_existing().all()
    project=crud.get_translation_project(db,project_id)
    if version(project)!=payload.version: raise HTTPException(409,'订单价格、字数或下级订单已变化，请重新打开后编辑')
    owners,numbers,parents=hierarchy(project);by_id={str(row.id):row for row in owners};key=str(payload.order_id)
    if key not in by_id: raise HTTPException(422,'订单不属于该笔译项目')
    before=audit.capture(project)
    if payload.payment_confirmation is not None:confirmations.save(db,project.id,payload.payment_confirmation,user.id)
    if payload.pricing_mode=='fixed':
        if payload.update_library:raise HTTPException(422,'固定收费不能同步为客户参考单价')
        if payload.adjusted_total is None and payload.adjusted_total_incl_tax is None:
            raise HTTPException(422,'请填写固定收费的不含税金额或含税金额')
        owner=by_id[key]
        for charge in list(owner.customer_charge_items):owner.customer_charge_items.remove(charge);db.delete(charge)
        moment=business_now().replace(tzinfo=None)
        owner.customer_charge_items.append(TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='翻译费',pricing_mode='fixed',currency=payload.currency,total_excl_tax=payload.adjusted_total,total_incl_tax=payload.adjusted_total_incl_tax,amount_override=payload.adjusted_total,remarks=payload.explanation,billing_month=payload.billing_month,created_at=moment,updated_at=moment))
        owner.updated_at=project.updated_at=moment
        db.flush();audit.append(db,user,project,before);db.commit()
        rates.invalidate_metadata(db);quantity_basis.invalidate(db)
        return read(db,project_id)
    if payload.prices is not None:
        save_prices(db,user,project,by_id,parents,key,payload)
        db.flush();audit.append(db,user,project,before);db.commit();return read(db,project_id)
    if payload.amount is None:raise HTTPException(422,'请填写单价')
    old={uid:signature(primary(owner)) for uid,owner in by_id.items()}
    moment=business_now().replace(tzinfo=None)

    def write(owner, explicit=False):
        row=primary(owner)
        if row is None:
            row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,
                sequence_no=len(owner.customer_charge_items or [])+1,item_name='翻译费',pricing_mode='metric',created_at=moment)
            owner.customer_charge_items.append(row)
        row.unit_price=row.unit_price_excl_tax=payload.amount
        row.currency=payload.currency;row.metric_type=payload.metric;row.unit_size=payload.unit_size;row.billing_month=payload.billing_month
        row.amount_override=row.total_excl_tax=payload.adjusted_total if explicit else None
        if explicit: row.remarks=payload.explanation.strip()
        row.updated_at=moment;owner.updated_at=moment
        return row
    write(by_id[key],True)
    changed={key}
    for owner in owners:
        uid=str(owner.id);parent=parents.get(uid)
        if parent in changed and (old[uid] is None or old[uid][0] is None or old[uid]==old[parent]):
            write(owner);changed.add(uid)
    project.updated_at=moment
    db.flush();audit.append(db,user,project,before);db.commit()
    return read(db,project_id)


def inherit_new_order(db, child):
    """新增下级订单时，继承最近上级的单价；显式收费明细优先。"""
    if child.customer_charge_items: return
    number=child.sub_order_no.rsplit('.',1)[0]
    ancestor=db.query(TranslationSubOrder).filter_by(parent_project_id=child.parent_project_id,sub_order_no=number).first()
    source=primary(ancestor) if ancestor else None
    if source is None:
        root=db.get(TranslationProject,child.parent_project_id)
        source=primary(root) if root else None
    if source is None: return
    moment=business_now().replace(tzinfo=None)
    amount,currency,metric,size=signature(source)
    owner=ancestor if ancestor and primary(ancestor) else db.get(TranslationProject,child.parent_project_id)
    entries=rates.order_rates(db,owner,owner.language_pair or '') if rates.ready(db) else []
    choices=set(str(child.language_pair or '').split('；'))
    entries=[entry for entry in entries if not child.language_pair or entry['language_pair'] in choices]
    if entries:
        for index,entry in enumerate(entries):
            row=TranslationSubOrderChargeItem(id=uuid4(),sub_order_id=child.id,sequence_no=index+1,item_name='翻译费',pricing_mode='metric',metric_type=quantity_basis.resolve(getattr(child,'word_count_matrix',{}),entry['metric'])[2] or 'characters_no_spaces',unit_size=Decimal(entry['unit_size']),unit_price=Decimal(entry['amount']) if entry['amount'] is not None else None,unit_price_excl_tax=Decimal(entry['amount']) if entry['amount'] is not None else None,currency=entry['currency'],billing_month=source.billing_month,created_at=moment,updated_at=moment)
            child.customer_charge_items.append(row);db.flush();quantity_basis.store(db,row,entry['metric'],getattr(child,'word_count_matrix',{}));db.add(rates.TranslationChargeDirection(charge_id=row.id,language_pair=entry['language_pair'],reference_id=UUID(entry['reference_id']) if entry['reference_id'] else None,reference_revision=entry['reference_revision']))
        rates.invalidate_metadata(db)
    elif not rates.ready(db):
        child.customer_charge_items.append(TranslationSubOrderChargeItem(id=uuid4(),sub_order_id=child.id,sequence_no=1,item_name='翻译费',pricing_mode='metric',metric_type=metric,unit_size=size,unit_price=amount,unit_price_excl_tax=amount,currency=currency,billing_month=source.billing_month,created_at=moment,updated_at=moment))


router=APIRouter(prefix='/translation-customer-finance',tags=['translation-customer-finance'])


@router.get('/page',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def page(skip:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100),keyword:str|None=None,project_status:str|None=None,billing_month:str|None=Query(None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),client:str|None=None,client_manager:str|None=None,client_id:UUID|None=None,db:Session=Depends(get_db),only_mine:bool=False,user=Depends(get_current_user),manager_ids:list[UUID]|None=Query(None,max_length=2000),statement_required:bool|None=None,sort:Literal['client_short_name_asc','client_short_name_desc']|None=None):
    fields={}
    if client_id: fields['finance_client_id']={'value':str(client_id)}
    if billing_month: fields['finance_billing_month']={'value':billing_month}
    ids=list(dict.fromkeys(manager_ids)) if isinstance(manager_ids,list) else []
    if ids:
        people=db.query(AppUser).filter(AppUser.id.in_(ids)).all()
        fields['finance_manager_ids']={'value':{'ids':[str(uid) for uid in ids],'names':[name for person in people for name in (person.full_name,person.username)]}}
    elif only_mine:fields['finance_manager_self']={'value':{'id':str(user.id),'names':[user.full_name,user.username]}}
    elif client_manager and client_manager.strip(): fields['client_manager']={'op':'contains','value':client_manager.strip()}
    if client and client.strip(): fields['finance_client']={'value':client.strip()}
    if statement_required is not None:fields['finance_statement_required']={'value':statement_required}
    filters=dict(keyword=keyword,project_status=project_status,field_filters=fields)
    projects=crud.get_translation_projects(db,skip=skip,limit=limit,sort=sort,**filters)
    return {'items':[tree(project,billing_month)['item'] for project in projects],'total':crud.count_translation_projects(db,**filters),'client_subtotals':client_subtotals(db,filters)}


@router.get('/manager-options',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def manager_options(db:Session=Depends(get_db)):
    from organization_service import department_condition
    people=db.query(AppUser).filter(AppUser.is_deleted.is_(False),department_condition(db,['客户部'])).order_by(AppUser.full_name,AppUser.username,AppUser.id).all()
    return {'items':[{'id':str(person.id),'name':person.full_name or person.username,'username':person.username,'active':bool(person.is_active)} for person in people]}


class StatementRequiredWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    statement_required:bool
    expected_statement_required:bool
    expected_updated_at:datetime|None=None
    copy_to_same_month:bool=False
    billing_month:str|None=Field(default=None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


@router.put('/project/{project_id}/statement-required',dependencies=[Depends(require_permission('projects:write'))])
def update_statement_required(project_id:UUID,payload:StatementRequiredWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    import translation_document_requirements as documents
    locked_client=None
    if payload.copy_to_same_month:
        from sqlalchemy import func
        locked_client=db.query(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(TranslationProject.id==project_id).scalar()
        if locked_client:db.query(Client).filter_by(id=locked_client).with_for_update().first()
    project=db.query(TranslationProject).filter(TranslationProject.id==project_id,TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if project is None:raise HTTPException(404,'笔译项目不存在')
    from concurrency import assert_fresh, StaleUpdateError
    try:assert_fresh(project,payload.expected_updated_at)
    except StaleUpdateError:raise HTTPException(409,'项目已被其他人修改，请刷新后重试')
    crud._attach_project_client_fields(project)
    from translation_customer_type import attach as attach_customer_types
    attach_customer_types(db,[project])
    documents.attach(db,[project])
    before=bool(project.statement_required)
    previous_updated_at=business_datetime(project.updated_at).isoformat() if project.updated_at else None
    if before!=payload.expected_statement_required:raise HTTPException(409,'是否需对账单已被其他人修改，请刷新后重试')
    try:
        targets=[project]
        if payload.copy_to_same_month:
            if not payload.statement_required or not payload.billing_month or order_billing_month(project.order_no)!=payload.billing_month:raise HTTPException(422,'同步需对账单时必须指定当前订单所属账单月份')
            client_id=project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
            if not client_id:raise HTTPException(422,'请先为当前项目关联客户')
            if client_id!=locked_client:raise HTTPException(409,'项目客户已变化，请刷新后重试')
            fields={'finance_billing_month':{'value':payload.billing_month}}
            from sqlalchemy import func
            query=db.query(TranslationProject).outerjoin(Client,TranslationProject.client_id==Client.id).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id).filter(TranslationProject.annotation_migrated_at.is_(None),func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id)
            # 只锁母订单，避免 PostgreSQL 外连接的可空侧无法加锁。
            targets=crud._apply_translation_project_filters(query,field_filters=fields).order_by(TranslationProject.id).with_for_update(of=TranslationProject).all()
            from translation_customer_type import attach as attach_types
            attach_types(db,targets);documents.attach(db,targets)
        changed=0
        for target in targets:
            if bool(target.statement_required)==payload.statement_required:continue
            documents.save(db,target,statement_required=payload.statement_required,actor_id=user.id)
            target.updated_at=business_now().replace(tzinfo=None);changed+=1
        if changed:
            db.commit()
        return {'id':str(project.id),'statement_required':payload.statement_required,'updated_at':business_datetime(project.updated_at).isoformat() if project.updated_at else None,'previous_updated_at':previous_updated_at,'affected_count':changed}
    except Exception:
        db.rollback();raise


@router.get('/statement-customers',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_customers(keyword:str|None=None,required_only:bool=True,skip:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),db:Session=Depends(get_db)):
    from sqlalchemy import and_, or_, func, select
    from search_matching import keyword_any
    import translation_document_requirements as documents
    from translation_customer_type import ClientCustomerType,ready as customer_types_ready
    from customer_statement_workspace import StatementWorkspace
    candidates=db.query(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id).label('client_id')).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(TranslationProject.annotation_migrated_at.is_(None))
    if required_only:
        if not documents.ready(db):raise HTTPException(503,'项目单据存储尚未初始化')
        candidates=candidates.outerjoin(documents.TranslationProjectDocuments,documents.TranslationProjectDocuments.project_id==TranslationProject.id)
        explicit=documents.TranslationProjectDocuments.statement_required
        inherited=True
        if customer_types_ready(db):
            candidates=candidates.outerjoin(ClientCustomerType,or_(and_(TranslationProject.sub_client_id.is_(None),ClientCustomerType.client_id==TranslationProject.client_id),ClientCustomerType.sub_client_id==TranslationProject.sub_client_id))
            inherited=or_(ClientCustomerType.customer_type.is_(None),ClientCustomerType.customer_type!='个人客户')
        candidates=candidates.filter(or_(explicit.is_(True),and_(explicit.is_(None),inherited)))
    query=db.query(Client).filter(Client.id.in_(select(candidates.subquery().c.client_id)))
    if not required_only:
        from sqlalchemy import inspect
        if inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
            query=db.query(Client).filter(or_(Client.id.in_(select(candidates.subquery().c.client_id)),Client.id.in_(select(StatementWorkspace.client_id))))
    if keyword and keyword.strip():query=query.filter(keyword_any([Client.client_name,Client.client_short_name,Client.client_code],keyword.strip()))
    total=query.count()
    return {'items':[{'id':str(client.id),'name':client.client_name or client.client_short_name,'short_name':client.client_short_name or client.client_name,'code':client.client_code or ''} for client in query.order_by(Client.client_short_name,Client.client_name,Client.id).offset(skip).limit(limit).all()],'total':total}


@router.get('/project/{project_id}',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def detail(project_id:UUID,db:Session=Depends(get_db)):
    return read(db,project_id)


@router.get('/project/{project_id}/history',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def price_history(project_id:UUID,order_id:UUID|None=None,page:int=Query(1,ge=1),db:Session=Depends(get_db)):
    if not db.get(TranslationProject,project_id):raise HTTPException(404,'笔译项目不存在')
    return audit.history(db,project_id,order_id,page)


@router.put('/project/{project_id}',dependencies=[Depends(require_permission('projects:write'))])
def update(project_id:UUID,payload:PriceWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    try: return save(db,user,project_id,payload)
    except Exception:
        db.rollback();raise
