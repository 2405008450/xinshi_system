"""客户计价及订单树汇总；复用既有收费表，不更改数据库结构。"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import re
from hashlib import sha256
import json
from uuid import UUID, uuid4
from typing import Literal, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, joinedload, selectinload, object_session
from database import get_db
from models import TranslationProject, TranslationSubOrder, TranslationSubOrderChargeItem, Client, SubClient, AppUser
from routers.auth import get_current_user, require_permission, require_module_access, require_any_permission
from annotation_progress_time import business_now, business_datetime
import crud
import customer_translation_rates as rates
import translation_finance_audit as audit
import translation_quantity_basis as quantity_basis
import translation_rate_matching as rate_matching
import translation_payment_confirmation as confirmations
import translation_finance_notes as finance_notes
import translation_billing_tax_mode as billing_tax
from translation_payment_confirmation import PaymentConfirmationWrite
from translation_payment_service import ProjectPayment
from permission_service import user_has_permission
from statement_customer_groups import CustomerGroupMove
from customer_statement_progress import Progress,ProgressWrite

METRICS = {'characters_no_spaces','words','foreign_words','cjk_chars_korean_words','documents','pages'}


from translation_document_requirements import QuotationDraft,DocumentNotes,order_pricing_modes,save_order_pricing_mode
from translation_project_invoices import InvoiceWrite, InvoiceCustomerSentWrite

class StatementSyncScope(BaseModel):
    client_id: UUID
    billing_month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


class StatementCustomerSync(BaseModel):
    client_id: UUID
    revision: int = Field(ge=0)


class PriceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clear_finance: bool = False
    payment_confirmation: PaymentConfirmationWrite | None = None
    payment_draft: list[ProjectPayment] | None = Field(default=None,max_length=100)
    payment_version: str | None = None
    billing_tax_mode: Literal['excl_tax','incl_tax'] | None = None
    quotation_required: bool | None = None
    statement_required: bool | None = None
    statement_sync: StatementSyncScope | None = None
    statement_customer_sync: StatementCustomerSync | None = None
    quotation_draft: QuotationDraft | None = None
    document_notes: DocumentNotes | None = None
    documents_only: bool = False
    version: str
    order_id: UUID
    pricing_mode: Literal['metric','fixed'] = 'metric'
    order_pricing_mode: Literal['aggregate','metric','fixed'] | None = None
    amount: Decimal | None = Field(default=None,ge=0, max_digits=14, decimal_places=4)
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')
    metric: str = 'characters_no_spaces'
    unit_size: Decimal = Field(default=Decimal('1'), gt=0, max_digits=14, decimal_places=4)
    adjusted_total: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    adjusted_total_incl_tax: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    explanation: str = Field(default='', max_length=5000)
    customer_explanation:str|None=Field(default=None,max_length=5000)
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
    return (rates.order_unit_amount(row),
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
    fields.append(getattr(project,'document_notes',{}))
    fields.append(order_pricing_modes(object_session(project), project))
    fields.append([bool(getattr(project,'quotation_required',False)),bool(getattr(project,'statement_required',True)),getattr(project,'quotation_draft',None)])
    for owner in owners:
        fields.append([str(owner.id), numbers[str(owner.id)], parents.get(str(owner.id)), str(owner.updated_at),
                       owner.word_count_matrix,
                       [[str(row.id), str(signature(row)),str(row.unit_price_excl_tax),str(row.unit_price_incl_tax),str(Decimal(str(row.total_excl_tax)).normalize()) if row.total_excl_tax is not None else None,str(Decimal(str(row.total_incl_tax)).normalize()) if row.total_incl_tax is not None else None,row.billing_month,row.remarks,str(row.updated_at)] for row in owner.customer_charge_items]])
    db=object_session(project)
    if db:
        fields.append(billing_tax.modes(db,project.id))
        fields.append([rates.order_rates(db,owner,owner.language_pair or project.language_pair) for owner in owners])
        fields.append([(key,row.internal_note,row.customer_note,row.revision) for key,row in sorted(finance_notes.rows(db,project.id).items())])
    return sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def order_billing_month(order_no):
    match=re.match(r'^TP-(\d{8}|\d{6})-',str(order_no or '').strip().upper())
    if not match:return None
    digits=match[1]
    year,month=(digits[:4],digits[4:6]) if len(digits)==8 else ('20'+digits[:2],digits[2:4])
    return f'{year}-{month}' if 1<=int(month)<=12 else None


def effective_billing_month(project,owner=None):
    """财务主表按母订单编号归月；无法识别的历史编号才回退到原收费月份。"""
    month=order_billing_month(project.order_no)
    if month:return month
    row=primary(owner or project)
    if row and row.billing_month:return row.billing_month
    row=primary(project)
    return row.billing_month if row else None


def statement_client_id(project):
    return project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)


def project_statement_client_id(db, project_id):
    return db.query(func.coalesce(TranslationProject.client_id, SubClient.parent_client_id)).outerjoin(
        SubClient, SubClient.id == TranslationProject.sub_client_id).filter(TranslationProject.id == project_id).scalar()


def statement_month_projects(db, client_id, month):
    query = db.query(TranslationProject).outerjoin(Client, TranslationProject.client_id == Client.id).outerjoin(
        SubClient, SubClient.id == TranslationProject.sub_client_id).filter(
        TranslationProject.annotation_migrated_at.is_(None),
        func.coalesce(TranslationProject.client_id, SubClient.parent_client_id) == client_id)
    return crud._apply_translation_project_filters(query, field_filters={'finance_billing_month': {'value': month}})


def sync_statement_month(db, project, scope, value, actor_id):
    from translation_document_requirements import TranslationProjectDocuments, save as save_documents

    if statement_client_id(project) != scope.client_id or effective_billing_month(project) != scope.billing_month:
        raise HTTPException(409, '项目客户或账单月份已变化，请重新确认同步范围')
    targets = statement_month_projects(db, scope.client_id, scope.billing_month).filter(
        TranslationProject.id != project.id).order_by(TranslationProject.id).with_for_update(of=TranslationProject).populate_existing().all()
    if not targets:
        return 0
    saved = dict(db.query(TranslationProjectDocuments.project_id, TranslationProjectDocuments.statement_required).filter(
        TranslationProjectDocuments.project_id.in_([target.id for target in targets])).all())
    changed = 0
    for target in targets:
        if saved.get(target.id) is value:
            continue
        save_documents(db, target, statement_required=value, actor_id=actor_id)
        target.updated_at = business_now().replace(tzinfo=None)
        changed += 1
    return changed


def sync_statement_customer(db, project, scope, value, user, locked_client):
    from customer_statements import sync_project_statement_default

    if scope.client_id != locked_client or statement_client_id(project) != scope.client_id:
        raise HTTPException(409, '项目客户已变化，请重新确认客户默认设置')
    sync_project_statement_default(db, scope.client_id, scope.revision, value, user)


def tree(project, billing_month=None, *, summary_only=False, include_billing_tax_mode=True, include_version=True):
    owners, numbers, parents = hierarchy(project)
    db=object_session(project)
    explicit_modes=order_pricing_modes(db,project)
    meta=rates.metadata(db,[charge.id for owner in owners for charge in owner.customer_charge_items]) if db else {}
    nodes = {}
    for owner in owners:
        key = str(owner.id); row = primary(owner)
        rate = signature(row)
        nodes[key] = dict(id=key,root_id=str(project.id),order_no=numbers[key],project_name=(project.source_file_name or project.project_name) if owner is project else owner.sub_project_name,
            pricing_mode=row.pricing_mode if row else 'metric',
            direct_pricing=False, fixed_pricing_from=None, _has_fixed_charge=bool(row and row.pricing_mode=='fixed'),
            client_short_name=project.client_short_name or project.client_name or '-',project_status=project.project_status if owner is project else owner.status,
            language_pair=owner.language_pair or project.language_pair, children=[], amount=str(rate[0]) if rate and rate[0] is not None else None,
            currency=rate[1] if rate else 'CNY',metric=rate[2] if rate else 'characters_no_spaces',unit_size=str(rate[3] or 1) if rate else '1',
            adjusted_total=str(row.total_excl_tax) if row and row.total_excl_tax is not None else None,
            adjusted_total_incl_tax=str(row.total_incl_tax) if row and row.total_incl_tax is not None else None,
            billing_month=effective_billing_month(project,owner),recorded_billing_month=row.billing_month if row else None,statement_required=bool(getattr(project,'statement_required',True)),
            quotation_required=bool(getattr(project,'quotation_required',False)),quotation_draft=getattr(project,'quotation_draft',None),document_notes=dict(getattr(project,'document_notes',{}) or {}),invoice_data=getattr(project,'invoice_data',{}),statement_required_explicit=bool(getattr(project,'statement_required_explicit',False)),
            explanation=row.remarks or '' if row else '',word_count_matrix=owner.word_count_matrix)
        nodes[key]['word_count_matrix_source']=getattr(owner,'word_count_matrix_source','project' if owner is project else 'suborder')
        if not summary_only:nodes[key].update(finance_notes.values(db,project,owner,row))
        nodes[key]['word_count_sub_order_count']=getattr(owner,'word_count_sub_order_count',0)
        nodes[key]['prices']=rates.order_rates(db,owner,owner.language_pair or project.language_pair,meta) if db else []
        effective_client_id=project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
        nodes[key]['client_id']=str(effective_client_id) if effective_client_id else None
        nodes[key]['client_manager']=getattr(project,'client_manager',None) or ''
        nodes[key]['statement_status']=getattr(owner,'statement_status',[])
        if owner is project:
            nodes[key]['customer_statements']=getattr(project,'customer_statements',[])
            nodes[key]['payment_confirmation']=confirmations.read(db,project.id) if db and not summary_only else None
            nodes[key]['statement_required']=bool(getattr(project,'statement_required',True))
            nodes[key]['updated_at']=business_datetime(project.updated_at).isoformat() if project.updated_at else None
    for key, parent in parents.items():
        nodes[parent]['children'].append(nodes[key])

    def calculate(node, inherited=None, fixed_from=None):
        requested = explicit_modes.get(node['id'])
        if node['children'] and requested == 'fixed':
            node.update(pricing_mode='fixed',direct_pricing=True)
        if fixed_from:
            node['fixed_pricing_from'] = fixed_from
            node['pricing_mode'] = 'fixed'
            node['direct_pricing'] = True
            node['prices'] = []
            if not node.pop('_has_fixed_charge'):
                node.update(adjusted_total=None, adjusted_total_incl_tax=None)
        else:
            node.pop('_has_fixed_charge')
        if node['children'] and not node['direct_pricing']:
            from translation_price_rollup import aggregate_node
            original_children=node['children'];included=[]
            legacy_source=node if node['prices'] and requested!='aggregate' else inherited
            for child in original_children:
                calculate(child,legacy_source)
                if not billing_month or child['matches_month']:included.append(child)
            matches=not billing_month or order_billing_month(project.order_no)==billing_month
            aggregate_node(node,included)
            node['matches_month']=matches or bool(included)
            return
        if node['pricing_mode']=='fixed':
            included=[]
            for child in node['children']:
                calculate(child, fixed_from=fixed_from or node['order_no'])
                if not billing_month or child['matches_month']:included.append(child)
            matches=not billing_month or order_billing_month(project.order_no)==billing_month
            excl={node['currency']:node['adjusted_total']} if node['adjusted_total'] is not None and matches else {}
            incl={node['currency']:node['adjusted_total_incl_tax']} if node['adjusted_total_incl_tax'] is not None and matches else {}
            node.update(children=included,matches_month=matches or bool(included),totals=excl,adjusted_totals=excl,totals_excl_tax=excl,totals_incl_tax=incl,incomplete=not excl and not incl,quantity=None,own_total=None)
            node.update(calculated_totals_excl_tax=excl,calculated_totals_incl_tax=incl)
            return
        if not node['direct_pricing'] and not node['prices'] and inherited:
            choices=set(str(node['language_pair'] or '').split('；'))
            node['prices']=[
                {**row,'id':None,'inherited':True,
                 'tax_prices':{**(row.get('tax_prices') or {}),'total_excl_tax':None,'total_incl_tax':None}}
                for row in inherited['prices'] if not node['language_pair'] or row['language_pair'] in choices
            ]
        amounts={};missing=False
        tax_amounts={'excl_tax':{},'incl_tax':{}}
        computed_tax={'excl_tax':{},'incl_tax':{}}
        adjusted_currencies={kind:set() for kind in tax_amounts}
        for price in node['prices']:
            quantity,dimension,actual_metric,quantity_error=quantity_basis.resolve(node['word_count_matrix'],price['metric'])
            price['quantity']=quantity
            price['quantity_dimension']=dimension;price['quantity_metric']=actual_metric;price['quantity_error']=quantity_error
            amount=None if quantity is None or price['amount'] is None else (Decimal(str(quantity))*Decimal(price['amount'])/Decimal(price['unit_size'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            price['total']=str(amount) if amount is not None else None
            for kind, values in tax_amounts.items():
                tax = price.get('tax_prices') or {}
                total = tax.get('total_'+kind)
                if total is not None:
                    adjusted_currencies[kind].add(price['currency'])
                unit = tax.get('unit_price_'+kind)
                if unit is not None and quantity is not None:computed_tax[kind][price['currency']]=computed_tax[kind].get(price['currency'],Decimal(0))+Decimal(str(quantity))*Decimal(str(unit))/Decimal(price['unit_size'])
                if total is None and unit is not None and quantity is not None:
                    total = Decimal(str(quantity))*Decimal(str(unit))/Decimal(price['unit_size'])
                if total is not None:
                    values[price['currency']] = values.get(price['currency'],Decimal(0))+Decimal(str(total))

            if amount is None:missing=True
            else:amounts[price['currency']]=amounts.get(price['currency'],Decimal(0))+amount
        if not node['direct_pricing'] and node['amount'] is None and inherited and (not inherited['prices'] or node['prices']):
            for key in ('amount','currency','metric','unit_size'):
                node[key] = inherited[key]
            node['inherited'] = True
            node['billing_month'] = node['billing_month'] or inherited.get('billing_month')
        count = node['word_count_matrix'].get('customer', {}).get(node['metric'])
        node['quantity'] = count
        own = None if count is None or node['amount'] is None else (Decimal(str(count))*Decimal(node['amount'])/Decimal(node['unit_size'])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        node['own_total'] = str(own) if own is not None else None
        totals, adjusted, incomplete = {}, {}, False
        original_children=[] if node['direct_pricing'] else node['children']
        included=[]
        if node['direct_pricing']:
            for child in node['children']:
                calculate(child,inherited)
                if not billing_month or child['matches_month']:included.append(child)
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
            node['calculated_totals_'+kind]={currency:str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for currency,value in computed_tax[kind].items()}
            values = {} if original_children else tax_amounts[kind]
            if original_children:
                for child in included:
                    for currency, value in child.get('totals_'+kind,{}).items():
                        values[currency]=values.get(currency,Decimal(0))+Decimal(value)
            override=node.get('adjusted_total' if kind=='excl_tax' else 'adjusted_total_incl_tax')
            if override is not None and matches:
                values[node['currency']]=Decimal(override)
                adjusted_currencies[kind].add(node['currency'])
            node['totals_'+kind]={currency:str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for currency,value in values.items()}
            node['adjusted_totals_'+kind]={currency:value for currency,value in node['totals_'+kind].items()
                                          if matches and currency in adjusted_currencies[kind]}
        node.update(children=included,matches_month=matches or bool(included),totals={k:str(v) for k,v in totals.items()},adjusted_totals={k:str(v) for k,v in adjusted.items()},incomplete=incomplete)
    root=nodes[str(project.id)];calculate(root)
    if root['children']:
        order_directions={str(owner.id):owner.language_pair for owner in owners}
        root['missing_child_orders']=missing_child_order_fields(root,order_directions)
    if include_billing_tax_mode:
        from customer_statements import client_preference
        default_mode='incl_tax' if db and project.client_id and client_preference(db,project.client_id)['tax_included'] else 'excl_tax'
        billing_tax.attach(root,billing_tax.modes(db,project.id),default_mode)
    return {'item':root,'version':version(project) if include_version and not summary_only else None}


def missing_child_order_fields(root, order_directions):
    missing = {'language_pair': [], 'word_count': [], 'unit_price': []}

    def visit(node):
        if node['children']:
            for child in node['children']:
                visit(child)
            return

        directions = {value.strip() for value in (order_directions.get(node['id']) or '').split('；') if value.strip()}
        order_no = node['order_no']
        if not directions:
            missing['language_pair'].append(order_no)
        if matches_missing_fields(node, word_count=True):
            missing['word_count'].append(order_no)
        if node['pricing_mode'] != 'fixed':
            priced_directions = set()
            has_empty_rate = False
            for price in node['prices']:
                tax = price.get('tax_prices') or {}
                if any(value is not None for value in (price.get('amount'), tax.get('unit_price_excl_tax'), tax.get('unit_price_incl_tax'))):
                    priced_directions.add(price.get('language_pair'))
                else:
                    has_empty_rate = True
            if not priced_directions or has_empty_rate or directions - priced_directions:
                missing['unit_price'].append(order_no)

    for child in root['children']:
        visit(child)
    return missing


def read(db, project_id):
    # 保存后也会复用当前会话：通过公共查询批量刷新订单、收费及统计，避免逐个子单查询。
    project=crud.get_translation_project(db,project_id,refresh=True)
    if not project: raise HTTPException(404,'笔译项目不存在')
    result=tree(project)
    from translation_payment_service import read as read_payments
    result['payment']=read_payments(db,project)
    result['reference_prices']=rates.library(db,project.client_id) if project.client_id else {'ready':rates.ready(db),'items':[],'version':''}
    return result


def load_charge_metadata(db,projects):
    ids=[charge.id for project in projects for owner in [project,*project.sub_orders] for charge in owner.customer_charge_items]
    for offset in range(0,len(ids),4000):
        batch=ids[offset:offset+4000]
        rates.metadata(db,batch)
        quantity_basis.metadata(db,batch)


def client_subtotals(db, filters):
    query=db.query(TranslationProject).options(joinedload(TranslationProject.client),selectinload(TranslationProject.customer_charge_items),
        selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items)).outerjoin(Client,TranslationProject.client_id==Client.id).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id).filter(TranslationProject.annotation_migrated_at.is_(None))
    projects=crud._apply_translation_project_filters(query,**filters).all()
    crud._attach_word_count_matrices(db,projects=projects)
    load_charge_metadata(db,projects)
    groups={}
    for project in projects:
        project.client_short_name=(project.client.client_short_name or project.client.client_name) if project.client else '-'
        project.client_name=project.client.client_name if project.client else '-'
        key=str(project.client_id) if project.client_id else 'unassigned'
        group=groups.setdefault(key,{'client_id':key,'client_name':project.client_short_name,'project_count':0,'totals':{},'adjusted_totals':{},'totals_excl_tax':{},'totals_incl_tax':{},'incomplete':False})
        month=(filters.get('field_filters') or {}).get('finance_billing_month',{}).get('value')
        node=tree(project,month,summary_only=True,include_billing_tax_mode=False)['item'];group['project_count']+=1;group['incomplete']|=node['incomplete']
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
    if references and any(data['amount'] is None for data in values):
        quotes=[rates.serialize(reference) for reference in references.values()]
        for data in values:
            if data['amount'] is not None or data.get('reference_id'):
                continue
            reference=rate_matching.automatic_reference(quotes,data,target.word_count_matrix)
            if reference:
                tax=reference.get('tax_prices') or {'unit_price_excl_tax':reference['amount']}
                data.update(amount=Decimal(reference['amount']),
                            tax_prices={key:Decimal(value) if value is not None else None for key,value in tax.items()},
                            reference_id=UUID(reference['id']),reference_revision=reference['revision'])
    for data in values:
        ref_id=data.get('reference_id')
        if ref_id:
            old_meta=db.get(rates.TranslationChargeDirection,data['id']) if data.get('id') in own_ids else None
            old_price=next((row for row in rates.order_rates(db,target,target.language_pair or project.language_pair) if row.get('id')==str(data.get('id'))),None)
            if old_meta and old_meta.reference_id==ref_id and old_meta.reference_revision==data.get('reference_revision') and old_price and rates.rate_key(old_price)==rates.rate_key(data):continue
            ref=references.get(ref_id)
            if not ref or ref.revision!=data.get('reference_revision') or not rate_matching.matches(rates.serialize(ref),data,right_matrix=target.word_count_matrix,left_reference=True):raise HTTPException(409,'所采用的客户参考价已变化或不匹配，请重新选择')
    if payload.update_library:
        if not user_has_permission(db,user.id,'clients:write'):raise HTTPException(403,'同步客户参考价需要客户管理编辑权限')
        if not payload.sync_confirmed:raise HTTPException(422,'请点击并确认同步客户参考价')
        if not project.client_id:raise HTTPException(422,'请先为项目选择客户')
        from translation_rate_matching import matches,unit
        library_items=[]
        for data in values:
            metric=unit(data['metric'],target.word_count_matrix)
            if not metric:raise HTTPException(422,'同步客户报价前，请先明确项目计量单位')
            candidates=[ref for ref in references.values() if matches(rates.serialize(ref),data,right_matrix=target.word_count_matrix,left_reference=True)]
            if len(candidates)>1:raise HTTPException(422,'客户报价存在多条完整匹配项，请先编辑客户报价消除重复')
            library_items.append(rates.RateInput(**{**data,'id':None,'reference_id':None,'reference_revision':None,'metric':candidates[0].metric if candidates else 'customer_auto:'+metric}))
        rates.write_library(db,user,project.client_id,library_items,payload.library_version,origin='project',merge=True)
        references={row.id:row for row in db.query(rates.CustomerTranslationRate).filter_by(client_id=project.client_id,active=True).all()}
        by_key={row.rate_key:row for row in references.values()}
        for data,library_item in zip(values,library_items):data.update(reference_id=by_key[rates.rate_key(library_item.model_dump())].id,reference_revision=by_key[rates.rate_key(library_item.model_dump())].revision)
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
            tax=data.get('tax_prices')
            row.unit_price_excl_tax=tax.get('unit_price_excl_tax') if tax is not None else data['amount']
            if tax is not None:row.unit_price_incl_tax=tax.get('unit_price_incl_tax')
            row.unit_price=row.unit_price_excl_tax
            if row.unit_price_excl_tax is None and row.unit_price_incl_tax is None:
                row.unit_price=data['amount']
            row.currency=data['currency'];row.metric_type=quantity_basis.storage_metric(quantity_basis.resolve(owner.word_count_matrix,data['metric'])[2]);row.unit_size=data['unit_size']
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
    direct_modes={key for key,mode in order_pricing_modes(db,project).items() if mode=='fixed'}
    for uid,owner in owners.items():
        parent=parents.get(uid)
        if parent not in changed or parent in direct_modes or uid in direct_modes:continue
        before=comparable(old[uid]);parent_before=comparable(old[parent])
        if before and not all(k in parent_before and parent_before[k]==value for k,value in before.items()):continue
        choices=set(str(owner.language_pair or project.language_pair or '').split('；'))
        inherited=[item for item in changed[parent] if not choices or choices=={''} or item['language_pair'] in choices]
        if inherited:write(owner,inherited,False);changed[uid]=inherited
    project.updated_at=moment
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)


def save_payment_changes(db,project,payload,actor_id):
    if payload.payment_draft is not None:
        if not payload.payment_version:raise HTTPException(422,'请先加载付款明细，再保存修改')
        from translation_payment_service import save as save_payments
        save_payments(db,project,payload.payment_draft,payload.payment_version,actor_id,payload.payment_confirmation)
    elif payload.payment_confirmation is not None:
        confirmations.save(db,project.id,payload.payment_confirmation,actor_id)
    else:
        confirmations.recheck_after_fee_change(db,project.id,actor_id)


def inherits_fixed_pricing(project, parents, order_key):
    modes = order_pricing_modes(object_session(project), project)
    parent = parents.get(order_key)
    while parent:
        if modes.get(parent) == 'fixed':
            return True
        parent = parents.get(parent)
    return False


def _write_finance(db, user, project_id, payload, *, allow_incomplete=False):
    audit.require_ready(db)
    if payload.metric not in METRICS: raise HTTPException(422,'请选择有效的计价单位')
    payment_fields={'version','order_id','documents_only','payment_confirmation','payment_draft','payment_version'}
    payment_only=payload.documents_only and payload.model_fields_set <= payment_fields and (
        payload.payment_confirmation is not None or payload.payment_draft is not None
    )
    client_id=None if payment_only else project_statement_client_id(db,project_id)
    if client_id:db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().first()
    project=db.query(TranslationProject).filter_by(id=project_id).filter(TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if not project: raise HTTPException(404,'笔译项目不存在')
    db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.id).with_for_update().populate_existing().all()
    project=crud.get_translation_project(db,project_id)
    if version(project)!=payload.version: raise HTTPException(409,'订单价格、字数或下级订单已变化，请重新打开后编辑')
    owners,numbers,parents=hierarchy(project);by_id={str(row.id):row for row in owners};key=str(payload.order_id)
    if key not in by_id: raise HTTPException(422,'订单不属于该笔译项目')
    if key in parents.values() and (payload.adjusted_total is not None or payload.adjusted_total_incl_tax is not None):
        mode=payload.order_pricing_mode or order_pricing_modes(db,project).get(key)
        if mode!='fixed':
            raise HTTPException(422,'子订单汇总的调整后金额请在子订单填写')
    if inherits_fixed_pricing(project, parents, key) and (
        not payload.documents_only or payload.order_pricing_mode is not None or 'billing_tax_mode' in payload.model_fields_set
    ):
        raise HTTPException(422,'该订单继承上级固定收费，请在上级订单调整计价方式及金额')
    if payment_only:
        save_payment_changes(db,project,payload,user.id)
        return
    month=order_billing_month(project.order_no)
    if month:payload=payload.model_copy(update={'billing_month':month})
    before=audit.capture(project)
    if payload.order_pricing_mode is not None:
        if key not in parents.values():
            raise HTTPException(422,'仅有下级的订单可切换汇总计价方式')
        if payload.order_pricing_mode == 'metric':
            raise HTTPException(422,'有子订单的订单只能选择子订单汇总或固定收费')
        if payload.order_pricing_mode != 'aggregate' and payload.order_pricing_mode != payload.pricing_mode:
            raise HTTPException(422,'订单计价方式与收费明细不一致')
        save_order_pricing_mode(db,project,by_id[key].id,payload.order_pricing_mode,user.id)
        if payload.order_pricing_mode == 'aggregate':
            payload=payload.model_copy(update={'documents_only':True})
    from translation_document_requirements import save as save_documents
    if 'billing_tax_mode' in payload.model_fields_set:billing_tax.save(db,user,project,by_id[key],payload.billing_tax_mode)
    if payload.quotation_required is not None:project.quotation_required=payload.quotation_required
    save_documents(db,project,statement_required=payload.statement_required,quotation_draft=payload.quotation_draft,document_notes=payload.document_notes,actor_id=user.id)
    if payload.statement_required is not None:
        project.statement_required=payload.statement_required
        project.statement_required_explicit=True
    if payload.statement_sync is not None:
        if payload.statement_required is None:
            raise HTTPException(422, '请先选择是否需对账单')
        if payload.statement_sync.client_id != client_id:
            raise HTTPException(409, '项目客户已变化，请重新确认同步范围')
        sync_statement_month(db, project, payload.statement_sync, payload.statement_required, user.id)
    if payload.statement_customer_sync is not None:
        if payload.statement_required is None:
            raise HTTPException(422, '请先选择是否需对账单')
        sync_statement_customer(db, project, payload.statement_customer_sync, payload.statement_required, user, client_id)
    if payload.quotation_draft is not None:project.quotation_draft=payload.quotation_draft.model_dump(mode='json')
    if payload.documents_only:
        finance_notes.apply(db,user,project,by_id[key],internal=payload.explanation if 'explanation' in payload.model_fields_set else None,customer=payload.customer_explanation)
        save_payment_changes(db,project,payload,user.id)
        project.updated_at=business_now().replace(tzinfo=None)
        audit.append(db,user,project,before)
        return
    finance_notes.apply(db,user,project,by_id[key],internal=payload.explanation if 'explanation' in payload.model_fields_set else None,customer=payload.customer_explanation)
    if payload.clear_finance:
        if payload.update_library or payload.prices or payload.adjusted_total is not None or payload.adjusted_total_incl_tax is not None:
            raise HTTPException(422,'清空价格时不能同时提交单价或金额')
        owner=by_id[key]
        for charge in list(owner.customer_charge_items):owner.customer_charge_items.remove(charge);db.delete(charge)
        owner.updated_at=project.updated_at=business_now().replace(tzinfo=None)
        db.flush();rates.invalidate_metadata(db);quantity_basis.invalidate(db)
        save_payment_changes(db,project,payload,user.id)
        audit.append(db,user,project,before)
        return
    if payload.pricing_mode=='fixed':
        if payload.update_library:raise HTTPException(422,'固定收费不能同步为客户参考单价')
        if not allow_incomplete and payload.adjusted_total is None and payload.adjusted_total_incl_tax is None:
            raise HTTPException(422,'请填写固定收费的不含税金额或含税金额')
        owner=by_id[key]
        for charge in list(owner.customer_charge_items):owner.customer_charge_items.remove(charge);db.delete(charge)
        moment=business_now().replace(tzinfo=None)
        owner.customer_charge_items.append(TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='翻译费',pricing_mode='fixed',currency=payload.currency,total_excl_tax=payload.adjusted_total,total_incl_tax=payload.adjusted_total_incl_tax,amount_override=payload.adjusted_total,remarks=payload.explanation,billing_month=payload.billing_month,created_at=moment,updated_at=moment))
        owner.updated_at=project.updated_at=moment
        db.flush();
        save_payment_changes(db,project,payload,user.id)
        audit.append(db,user,project,before)
        return
    if payload.prices is not None:
        save_prices(db,user,project,by_id,parents,key,payload)
        db.flush();
        save_payment_changes(db,project,payload,user.id)
        audit.append(db,user,project,before)
        return
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
    db.flush()
    save_payment_changes(db,project,payload,user.id)
    audit.append(db,user,project,before)


def save(db, user, project_id, payload, *, allow_incomplete=False):
    _write_finance(db,user,project_id,payload,allow_incomplete=allow_incomplete)
    db.commit()
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)
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
    _,currency,metric,size=signature(source)
    owner=ancestor if ancestor and primary(ancestor) else db.get(TranslationProject,child.parent_project_id)
    entries=rates.order_rates(db,owner,owner.language_pair or '') if rates.ready(db) else []
    choices=set(str(child.language_pair or '').split('；'))
    entries=[entry for entry in entries if not child.language_pair or entry['language_pair'] in choices]
    if entries:
        for index,entry in enumerate(entries):
            tax=entry['tax_prices']
            excl=tax['unit_price_excl_tax']
            incl=tax['unit_price_incl_tax']
            if excl is None and incl is None:
                excl=entry['amount']
            excl=Decimal(excl) if excl is not None else None
            incl=Decimal(incl) if incl is not None else None
            row=TranslationSubOrderChargeItem(
                id=uuid4(),sub_order_id=child.id,sequence_no=index+1,item_name='翻译费',pricing_mode='metric',
                metric_type=quantity_basis.storage_metric(quantity_basis.resolve(getattr(child,'word_count_matrix',{}),entry['metric'])[2]),
                unit_size=Decimal(entry['unit_size']),unit_price=excl,unit_price_excl_tax=excl,unit_price_incl_tax=incl,
                currency=entry['currency'],billing_month=source.billing_month,created_at=moment,updated_at=moment,
            )
            child.customer_charge_items.append(row);db.flush();quantity_basis.store(db,row,entry['metric'],getattr(child,'word_count_matrix',{}));db.add(rates.TranslationChargeDirection(charge_id=row.id,language_pair=entry['language_pair'],reference_id=UUID(entry['reference_id']) if entry['reference_id'] else None,reference_revision=entry['reference_revision']))
        rates.invalidate_metadata(db)
    elif not rates.ready(db):
        excl=source.unit_price_excl_tax
        incl=source.unit_price_incl_tax
        if excl is None and incl is None:
            excl=source.unit_price
        child.customer_charge_items.append(TranslationSubOrderChargeItem(
            id=uuid4(),sub_order_id=child.id,sequence_no=1,item_name='翻译费',pricing_mode='metric',
            metric_type=metric,unit_size=size,unit_price=excl,unit_price_excl_tax=excl,unit_price_incl_tax=incl,
            currency=currency,billing_month=source.billing_month,created_at=moment,updated_at=moment,
        ))


router=APIRouter(prefix='/translation-customer-finance',tags=['translation-customer-finance'])

class StatementProjectPreview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_id:UUID
    month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    order_ids:list[UUID]=Field(max_length=2000)
    months:list[str]|None=Field(default=None,min_length=1,max_length=36)
    mode:Literal['parents','all','children']='children'

@router.post('/statement-preview',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_project_preview(data:StatementProjectPreview,db:Session=Depends(get_db)):
    from statement_project_preview import build
    months=sorted(set(data.months or [data.month]))
    if any(not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month) for month in months):raise HTTPException(422,'账单月份格式应为YYYY-MM')
    parts=[build(db,data.client_id,month,data.order_ids,data.mode) for month in months]
    result=parts[0];lines={line['line_id']:line for part in parts for line in part['rows']}
    result['rows']=list(lines.values());result['month']='、'.join(months)
    if not result['rows']:raise HTTPException(422,'当前筛选没有项目，也没有目标月份的待入账任务')
    result['pending']=list(dict.fromkeys(issue for part in parts for issue in part['pending']))
    sums={}
    for line in result['rows']:
        if line.get('counted_in_total',True) and line['subtotal'] is not None:sums[line['currency']]=sums.get(line['currency'],Decimal(0))+Decimal(line['subtotal'])
    result['totals']={key:str(value.quantize(Decimal('.01'))) for key,value in sums.items()}
    return result


def matches_missing_fields(node, word_count=False, unit_price=False, total=None):
    """以列表实际展示的母订单汇总值判断，0 是已填值。"""
    if word_count:
        matrix=node.get('word_count_matrix') or {}
        if any(value is not None and value!='' for dimension in ('company','customer') for value in (matrix.get(dimension) or {}).values()):
            return False
    if unit_price:
        if node.get('pricing_mode')=='fixed':
            return False
        prices=[price for price in (node.get('prices') or [{'amount':node.get('amount')}]) if price.get('pricing_mode')!='fixed']
        if not any(price.get('amount') is None and all((price.get('tax_prices') or {}).get(key) is None for key in ('unit_price_excl_tax','unit_price_incl_tax')) for price in prices):
            return False
    if total:
        excl=not node.get('totals_excl_tax')
        incl=not node.get('totals_incl_tax')
        if not {'excl':excl,'incl':incl,'both':excl and incl,'either':excl or incl,'fixed':node.get('pricing_mode')=='fixed' and excl and incl}[total]:
            return False
    return True


def subtotal_nodes(nodes):
    groups={}
    amount_fields=('totals','adjusted_totals','totals_excl_tax','totals_incl_tax')
    for node in nodes:
        key=node.get('client_id') or 'unassigned'
        group=groups.setdefault(key,dict(client_id=key,client_name=node.get('client_short_name') or '-',project_count=0,incomplete=False,**{field:{} for field in amount_fields}))
        group['project_count']+=1
        group['incomplete']|=node['incomplete']
        for field in amount_fields:
            for currency,amount in node.get(field,{}).items():
                group[field][currency]=group[field].get(currency,Decimal(0))+Decimal(amount)
    for group in groups.values():
        for field in amount_fields:group[field]={currency:str(amount) for currency,amount in group[field].items()}
    return sorted(groups.values(),key=lambda group:group['client_name'])


def paginate_child_orders(roots,skip,limit):
    position=0
    display_offset=0

    def select(node,counted):
        nonlocal position,display_offset
        first=position+1
        index=None
        if counted:
            position+=1
            if skip<position<=skip+limit:index=position
        children=[selected for child in node['children'] if (selected:=select(child,True)) is not None]
        last=min(position,skip)
        if first<=last:
            # Each previous page overlapping this subtree displayed its ancestor row once.
            display_offset+=(last-1)//limit-(first-1)//limit+1
        if index is None and not children:return None
        return dict(id=node['id'],page_index=index,children=children)

    rows=[selected for root in roots if (selected:=select(root,not root['children'])) is not None]
    return rows,position,display_offset


def apply_order_page(node,selection):
    children={child['id']:child for child in node['children']}
    return {**node,'has_children':bool(children),'page_index':selection['page_index'],
        'children':[apply_order_page(children[child['id']],child) for child in selection['children']]}


@router.get('/page',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def page(skip:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100),keyword:str|None=None,project_status:str|None=None,billing_month:str|None=Query(None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),client:str|None=None,client_manager:str|None=None,client_id:UUID|None=None,db:Session=Depends(get_db),only_mine:bool=False,user=Depends(get_current_user),manager_ids:list[UUID]|None=Query(None,max_length=2000),statement_required:bool|None=None,sort:Literal['client_short_name_asc','client_short_name_desc']|None=None,missing_word_count:bool=False,missing_unit_price:bool=False,missing_total:Literal['excl','incl','both','either','fixed']|None=None,project_statuses:list[str]|None=Query(None,max_length=100),client_order_count:Literal['single','multiple']|None=None,group_clients:bool=True,selected_client_ids:list[UUID]|None=Query(None,alias='client_ids',max_length=100),payment_status:Literal['unpaid','deposit','mid','full','paid','full_mismatch']|None=None,include_payment_status:bool=False,exclude_full:bool=False,payment_project_id:UUID|None=None,include_invoice_status:bool=False,invoice_status:Literal['unissued','partial','issued','not_required']|None=None,invoice_required:Literal['yes','no','unknown']|None=None,statement_customers:Literal['include','exclude']|None=None,payment_amount_mismatch:bool=False,pricing_mode:Literal['metric','fixed','aggregate']|None=None,billing_months:list[Annotated[str,Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')]]|None=Query(None,max_length=1200),paginate_children:bool=False):
    filter_amount_mismatch = payment_amount_mismatch or payment_status == 'full_mismatch'
    filter_invoice = invoice_status is not None or invoice_required is not None

    def finish(result):
        if include_invoice_status:
            from translation_project_invoices import attach
            attach(db,result)
            result['invoice_filter_applied']=True
        if filter_amount_mismatch:result['payment_amount_mismatch_filter_applied']=True
        if include_payment_status:
            from translation_payment_filters import attach_payment_status
            return attach_payment_status(db,result)
        return result
    if payment_amount_mismatch:
        # 独立核对入口，不叠加左侧月份、客户名称与付款状态。
        billing_month=None;billing_months=None;client=None
    if filter_amount_mismatch:payment_status='full'
    fields={}
    if invoice_status and invoice_status != 'not_required':
        fields['finance_invoice_status']={'value':invoice_status}
    if exclude_full:fields['finance_payment_exclude_full']={'value':True}
    if payment_project_id:fields['finance_payment_project_id']={'value':str(payment_project_id)}
    if payment_status:fields['finance_payment_status']={'value':payment_status}
    if client_id: fields['finance_client_id']={'value':str(client_id)}
    if isinstance(selected_client_ids,list):fields['finance_client_ids']={'value':[str(uid) for uid in selected_client_ids]}
    months=list(dict.fromkeys(billing_months)) if isinstance(billing_months,list) else []
    if months:
        fields['finance_billing_month']={'value':months}
        billing_month=months[0] if len(months)==1 else None
    elif billing_month: fields['finance_billing_month']={'value':billing_month}
    from finance_manager_scope import manager_fields
    fields.update(manager_fields(db,user,manager_ids,only_mine,client_manager))
    if client and client.strip(): fields['finance_client']={'value':client.strip()}
    if statement_required is not None:fields['finance_statement_required']={'value':statement_required}
    if statement_customers is not None:
        fields['finance_statement_customers'] = {'value':statement_customers}
    status_values=project_statuses if isinstance(project_statuses,list) else []
    statuses=list(dict.fromkeys(status.strip() for status in status_values if status.strip()))
    if statuses:fields['project_status']={'value':statuses}
    filters=dict(keyword=keyword,project_status=None if statuses else project_status,field_filters=fields)
    missing_filters=missing_word_count or missing_unit_price or missing_total is not None
    all_matches=paginate_children or missing_filters or client_order_count is not None or filter_amount_mismatch or pricing_mode is not None or filter_invoice
    projects=crud.get_translation_projects(db,skip=0 if all_matches else skip,limit=None if all_matches else limit,sort=sort,**filters)
    load_charge_metadata(db,projects)
    from translation_statement_status import customer_boards
    client_ids={project.id:(project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)) for project in projects}
    def attach_boards(visible):
        monthly=customer_boards(db,{client_ids[project.id] for project in visible if client_ids[project.id]})
        for project in visible:project.customer_statements=monthly.get(str(client_ids[project.id]),[])

    if not paginate_children:attach_boards(projects)
    if all_matches:
        matched=[tree(project,billing_month,summary_only=paginate_children,include_version=False,
            include_billing_tax_mode=not paginate_children or filter_amount_mismatch or filter_invoice)['item'] for project in projects]
        matched=[node for node in matched if matches_missing_fields(node,missing_word_count,missing_unit_price,missing_total)]
        if pricing_mode is not None:matched=[node for node in matched if node.get('pricing_mode')==pricing_mode]
        if filter_invoice:
            from translation_project_invoices import invoice_required as order_requires_invoice
            expected = {'yes': True, 'no': False, 'unknown': None}
            filtered = []
            for node in matched:
                required = order_requires_invoice(node)
                if invoice_required is not None and required is not expected[invoice_required]:
                    continue
                if invoice_status is not None and (required is False) != (invoice_status == 'not_required'):
                    continue
                filtered.append(node)
            matched = filtered
        if filter_amount_mismatch:
            from translation_payment_filters import attach_payment_status
            attach_payment_status(db,{'items':matched})
            matched=[node for node in matched if node['payment_status']=='full' and node['payment_amount_mismatch']]
        if client_order_count:
            owners={str(project.id):project for project in projects}
            groups={}
            for node in matched:
                owner=owners[node['id']]
                identity=node.get('client_id') or ('name:'+owner.client_name.strip().casefold() if owner.client_name and owner.client_name.strip() else 'unlinked:'+node['id'])
                node['client_group_key']=identity
                groups.setdefault(identity,[]).append(node)
            groups={key:values for key,values in groups.items() if (len(values)==1 if client_order_count=='single' else len(values)>1)}
            filtered=[node for values in groups.values() for node in values]
            if client_order_count=='multiple' and group_clients and not paginate_children:
                ordered=sorted(groups.items(),key=lambda pair:((pair[1][0].get('client_short_name') or '').casefold(),pair[0]))
                selected=ordered[skip:skip+limit]
                return finish({'items':[node for _,values in selected for node in values],'total':len(ordered),'order_total':len(filtered),'pagination_unit':'clients','client_subtotals':subtotal_nodes(filtered),'client_groups':[{'key':key,'name':values[0].get('client_short_name') or '未关联客户','count':len(values)} for key,values in selected]})
            matched=filtered
        if paginate_children:
            selected,total,display_offset=paginate_child_orders(matched,skip,limit)
            by_id={str(project.id):project for project in projects}
            attach_boards([by_id[row['id']] for row in selected])
            items=[apply_order_page(tree(by_id[row['id']],billing_month,include_version=False)['item'],row) for row in selected]
            return finish({'items':items,'total':total,'pagination_unit':'child_orders','display_offset':display_offset,'client_subtotals':subtotal_nodes(matched)})
        return finish({'items':matched[skip:skip+limit],'total':len(matched),'client_subtotals':subtotal_nodes(matched)})
    return finish({'items':[tree(project,billing_month,include_version=False)['item'] for project in projects],'total':crud.count_translation_projects(db,**filters),'client_subtotals':client_subtotals(db,filters)})



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
    statement_sync: StatementSyncScope | None = None
    statement_customer_sync: StatementCustomerSync | None = None
    billing_month:str|None=Field(default=None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


@router.get('/statement-requirement-context', dependencies=[Depends(require_permission('projects:read'))])
def statement_requirement_context(
    project_id: UUID | None = None,
    client_id: UUID | None = None,
    billing_month: str | None = Query(None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from customer_statements import client_preference

    if project_id:
        project = db.query(TranslationProject).filter_by(id=project_id, annotation_migrated_at=None).first()
        if project is None:
            raise HTTPException(404, '笔译项目不存在')
        client_id, billing_month = statement_client_id(project), effective_billing_month(project)
    preference = client_preference(db, client_id) if client_id else {'statement_default': 'unknown', 'revision': 0}
    other_count = 0
    if client_id and billing_month:
        projects = statement_month_projects(db, client_id, billing_month)
        if project_id:
            projects = projects.filter(TranslationProject.id != project_id)
        other_count = projects.count()
    return dict(statement_default=preference['statement_default'], client_id=client_id,
                billing_month=billing_month, other_count=other_count, preference_revision=preference['revision'],
                can_update_customer=bool(client_id and user_has_permission(db, user.id, 'clients:write')))


@router.put('/project/{project_id}/statement-required',dependencies=[Depends(require_permission('projects:write'))])
def update_statement_required(project_id:UUID,payload:StatementRequiredWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    import translation_document_requirements as documents
    locked_client=None
    if payload.copy_to_same_month or payload.statement_sync or payload.statement_customer_sync:
        locked_client=project_statement_client_id(db,project_id)
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
        scope = payload.statement_sync
        if payload.copy_to_same_month:
            if not payload.billing_month or effective_billing_month(project) != payload.billing_month:
                raise HTTPException(422, '同步对账单设置时必须指定当前订单所属账单月份')
            client_id = statement_client_id(project)
            if not client_id:
                raise HTTPException(422, '请先为当前项目关联客户')
            scope = StatementSyncScope(client_id=client_id, billing_month=payload.billing_month)
        changed = 0
        if scope:
            if scope.client_id != locked_client:
                raise HTTPException(409, '项目客户已变化，请重新确认同步范围')
            changed = sync_statement_month(db, project, scope, payload.statement_required, user.id)
        if before != payload.statement_required or not project.statement_required_explicit:
            documents.save(db, project, statement_required=payload.statement_required, actor_id=user.id)
            project.updated_at = business_now().replace(tzinfo=None)
            changed += 1
        if payload.statement_customer_sync:
            sync_statement_customer(db, project, payload.statement_customer_sync, payload.statement_required, user, locked_client)
        if changed or payload.statement_customer_sync:
            db.commit()
        return {'id':str(project.id),'statement_required':payload.statement_required,'updated_at':business_datetime(project.updated_at).isoformat() if project.updated_at else None,'previous_updated_at':previous_updated_at,'affected_count':changed}
    except Exception:
        db.rollback();raise


@router.get('/statement-customer-groups',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_customer_groups(billing_month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),statement_required:bool=True,keyword:str|None=None,skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),manager_ids:list[UUID]|None=Query(None,max_length=2000),only_mine:bool=False,client_manager:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user),progress:Progress|None=None):
    from statement_customer_groups import customers
    from finance_manager_scope import manager_fields
    return customers(db,billing_month,statement_required,keyword,skip,limit,manager_fields(db,user,manager_ids,only_mine,client_manager),progress)


@router.put('/statement-customer-groups/{client_id}',dependencies=[Depends(require_permission('projects:write'))])
def move_statement_customer(client_id:UUID,payload:CustomerGroupMove,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from statement_customer_groups import move
    return move(db,user,client_id,payload)


@router.get('/statement-customers',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_customers(keyword:str|None=None,required_only:bool=True,skip:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),db:Session=Depends(get_db)):
    from sqlalchemy import or_, select
    from search_matching import keyword_any
    import translation_document_requirements as documents
    from customer_statement_workspace import StatementWorkspace
    if required_only and not documents.ready(db):
        raise HTTPException(503,'项目单据存储尚未初始化')
    candidates = documents.statement_customer_ids(db, required_only=required_only)
    query=db.query(Client).filter(Client.id.in_(candidates))
    if not required_only:
        from sqlalchemy import inspect
        if inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
            query=db.query(Client).filter(or_(Client.id.in_(candidates),Client.id.in_(select(StatementWorkspace.client_id))))
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
    project=crud.get_translation_project(db,project_id)
    order_key=str(payload.order_id)
    if project and order_key in hierarchy(project)[2].values() and not (
        payload.documents_only or payload.order_pricing_mode in ('aggregate','fixed')
        or (payload.pricing_mode=='fixed' and order_pricing_modes(db,project).get(order_key)=='fixed')
    ):
        raise HTTPException(422,'有子订单的订单只能选择子订单汇总或固定收费')
    attempts=2 if payload.payment_draft is not None or payload.payment_confirmation is not None else 1
    for attempt in range(attempts):
        try:
            _write_finance(db,user,project_id,payload)
            db.commit()
            break
        except OperationalError as error:
            db.rollback()
            if getattr(error.orig,'pgcode',None)!='55P03':
                raise
            rates.invalidate_metadata(db)
            quantity_basis.invalidate(db)
            if attempt+1==attempts:
                raise HTTPException(409,'数据库正在处理其他修改，当前填写已保留，请稍后重新保存') from error
        except Exception:
            db.rollback()
            raise
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)
    return read(db,project_id)


class TableRateDraft(rates.RateInput):
    amount: Decimal | None = Field(default=None,ge=0,max_digits=14,decimal_places=4)


class TablePriceWrite(PriceWrite):
    prices: list[TableRateDraft] | None = Field(default=None,min_length=1,max_length=100)


class TablePatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:str
    billing_tax_mode:Literal['excl_tax','incl_tax']|None=None
    order_id:UUID
    pricing_mode:Literal['metric','fixed','aggregate']|None=None
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    prices:list[TableRateDraft]|None=Field(default=None,max_length=100)
    adjusted_total:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    adjusted_total_incl_tax:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    billing_month:str|None=Field(default=None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    explanation:str=Field(default='',max_length=5000)
    customer_explanation:str=Field(default='',max_length=5000)


def save_table_cell(db,user,project_id,payload):
    changes=payload.model_dump(exclude_unset=True,exclude={'version','order_id'})
    if not changes:raise HTTPException(422,'没有需要保存的字段')
    guard=crud.get_translation_project(db,project_id)
    order_key=str(payload.order_id)
    has_children=bool(guard and order_key in hierarchy(guard)[2].values())
    direct=bool(guard and order_pricing_modes(db,guard).get(order_key)=='fixed')
    requested_mode=changes.get('pricing_mode')
    if has_children and requested_mode=='metric':
        raise HTTPException(422,'有子订单的订单只能选择子订单汇总或固定收费')
    if requested_mode=='aggregate':
        if not has_children or set(changes)!={'pricing_mode'}:
            raise HTTPException(422,'子订单汇总须单独选择，且订单必须有下级')
        return save(db,user,project_id,TablePriceWrite(version=payload.version,order_id=payload.order_id,
                    order_pricing_mode='aggregate',documents_only=True),allow_incomplete=True)
    if has_children and not direct and not requested_mode and any(field not in {'explanation','customer_explanation'} for field in changes):
        raise HTTPException(422,'子订单汇总模式下，请在子订单编辑收费')
    if any(key in changes and changes[key] is None for key in ('pricing_mode','currency','prices')):
        raise HTTPException(422,'计价模式、货币和单价明细不能为 null')
    if changes.get('prices') or 'pricing_mode' in changes:
        current=read(db,project_id)
        def find(node):
            if node['id']==str(payload.order_id):return node
            return next((found for child in node['children'] if (found:=find(child))),None)
        node=find(current['item'])
        if not node:raise HTTPException(422,'订单不属于该笔译项目')
        values={key:node.get(key) for key in ('pricing_mode','currency','adjusted_total','adjusted_total_incl_tax','billing_month','explanation')}
        # 状态切换不把原有的一口价误当成另一计价模式的调整额。
        if 'pricing_mode' in changes and changes['pricing_mode']!=node['pricing_mode']:
            values.update(adjusted_total=None,adjusted_total_incl_tax=None,billing_tax_mode=None)
        values.update(changes)
        if has_children and requested_mode:
            values['order_pricing_mode']=requested_mode
        if values['pricing_mode']=='metric':
            if 'prices' not in changes:
                keys=set(TableRateDraft.model_fields)
                existing_prices=[] if node.get('price_aggregate') else node['prices']
                values['prices']=[{key:value for key,value in price.items() if key in keys} for price in existing_prices] or [
                    dict(language_pair=direction,metric='customer_auto',amount=None)
                    for direction in str(node['language_pair'] or '').split('；') if direction]
            if not values['prices']:
                if not requested_mode:raise HTTPException(422,'请先填写订单的翻译方向')
                values.update(prices=None,clear_finance=True)
        else:values['prices']=None
        return save(db,user,project_id,TablePriceWrite(version=payload.version,order_id=payload.order_id,**values),allow_incomplete=True)

    audit.require_ready(db)
    client_id=db.query(TranslationProject.client_id).filter_by(id=project_id).scalar()
    if client_id:db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().first()
    project=db.query(TranslationProject).filter_by(id=project_id).filter(TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if not project:raise HTTPException(404,'笔译项目不存在')
    db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.id).with_for_update().populate_existing().all()
    project=crud.get_translation_project(db,project_id)
    if version(project)!=payload.version:raise HTTPException(409,'订单财务已变化，请刷新后重试')
    if 'billing_month' in changes and order_billing_month(project.order_no):changes['billing_month']=order_billing_month(project.order_no)
    owners,_,parents=hierarchy(project)
    owner=next((item for item in owners if item.id==payload.order_id),None)
    if owner is None:raise HTTPException(422,'订单不属于该笔译项目')
    if inherits_fixed_pricing(project, parents, str(owner.id)) and set(changes)-{'explanation','customer_explanation'}:
        raise HTTPException(422,'该订单继承上级固定收费，请在上级订单调整计价方式及金额')
    before=audit.capture(project)
    if 'billing_tax_mode' in changes:billing_tax.save(db,user,project,owner,changes.pop('billing_tax_mode'))
    if not changes:
        db.flush();audit.append(db,user,project,before);db.commit();return read(db,project_id)
    if set(changes)<={'explanation','customer_explanation'}:
        finance_notes.apply(db,user,project,owner,internal=changes.get('explanation'),customer=changes.get('customer_explanation'))
        db.flush();audit.append(db,user,project,before);db.commit();return read(db,project_id)
    if 'customer_explanation' in changes:finance_notes.apply(db,user,project,owner,customer=changes.pop('customer_explanation'))
    row=primary(owner)
    moment=business_now().replace(tzinfo=None)
    if 'prices' in changes:
        changes.pop('prices')
        if row and row.pricing_mode=='fixed':raise HTTPException(422,'固定收费不涉及单价')
        retained={key:getattr(row,key) if row is not None else None for key in ('currency','billing_month','remarks','total_excl_tax','total_incl_tax','amount_override')}
        for old in list(owner.customer_charge_items):
            if quantity_basis.ready(db):
                basis=db.get(quantity_basis.TranslationChargeQuantityBasis,old.id)
                if basis:db.delete(basis)
            meta=db.get(rates.TranslationChargeDirection,old.id)
            if meta:db.delete(meta)
            owner.customer_charge_items.remove(old);db.delete(old)
        row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='财务信息',pricing_mode='metric',metric_type='words',unit_size=1,created_at=moment,**{**retained,'currency':retained['currency'] or 'CNY'})
        owner.customer_charge_items.append(row)
        rates.invalidate_metadata(db);quantity_basis.invalidate(db)
    if row is None:
        pending=[tree(project)['item']]
        effective=None
        while pending:
            candidate=pending.pop()
            if candidate['id']==str(owner.id):effective=candidate;break
            pending.extend(candidate['children'])
        if effective and effective['prices']:
            # 子订单备注等修改不能用空收费行遮蔽已经继承的单价。
            rate_keys=set(TableRateDraft.model_fields)
            values={key:effective.get(key) for key in ('currency','adjusted_total','adjusted_total_incl_tax','billing_month','explanation')}
            values.update(changes)
            values['prices']=[{key:value for key,value in price.items() if key in rate_keys} for price in effective['prices']]
            merged=TablePriceWrite(version=payload.version,order_id=payload.order_id,**values)
            save_prices(db,user,project,{str(item.id):item for item in owners},parents,str(owner.id),merged)
            db.flush();confirmations.recheck_after_fee_change(db,project.id,user.id);audit.append(db,user,project,before);db.commit()
            return read(db,project_id)
        row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='财务信息',pricing_mode='metric',currency='CNY',metric_type='words',unit_size=1,created_at=moment)
        owner.customer_charge_items.append(row)
    if 'adjusted_total' in changes and changes['adjusted_total'] is not None and len({item.currency for item in owner.customer_charge_items})>1:
        raise HTTPException(422,'存在多个币种时请分别在下级订单调整金额')
    mapping={'adjusted_total':'total_excl_tax','adjusted_total_incl_tax':'total_incl_tax','explanation':'remarks','billing_month':'billing_month','currency':'currency'}
    for key,value in changes.items():
        targets=owner.customer_charge_items if key in {'billing_month','explanation'} else [row]
        for target in targets:setattr(target,mapping[key],value);target.updated_at=moment
        if key=='adjusted_total':row.amount_override=value
    row.updated_at=owner.updated_at=project.updated_at=moment
    db.flush();confirmations.recheck_after_fee_change(db,project.id,user.id);audit.append(db,user,project,before);db.commit()
    return read(db,project_id)


@router.patch('/project/{project_id}/table',dependencies=[Depends(require_permission('projects:write'))])
def update_table(project_id:UUID,payload:TablePatch,db:Session=Depends(get_db),user=Depends(get_current_user)):
    try:return save_table_cell(db,user,project_id,payload)
    except Exception:
        db.rollback();raise

@router.put('/statement-customer-groups/{client_id}/progress',dependencies=[Depends(require_permission('projects:write'))])
def set_statement_progress(client_id:UUID,payload:ProgressWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from customer_statement_progress import write
    return write(db,user,client_id,payload)


@router.get('/project/{project_id}/invoice',dependencies=[Depends(require_any_permission('projects:read','finance:read','clients:read','clients:write'))])
def read_invoice(project_id:UUID,order_id:UUID|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from translation_project_invoices import read
    from invoice_workflow import pending_invoice_requests
    return {**read(db,project_id,order_id), 'can_notify_requester':bool(pending_invoice_requests(db,project_id,user))}


@router.put('/project/{project_id}/invoice',dependencies=[Depends(require_any_permission('projects:write','finance:write'))])
def save_invoice(project_id:UUID,payload:InvoiceWrite,order_id:UUID|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from translation_project_invoices import save
    try:return save(db,project_id,payload,user.id,order_id)
    except Exception:
        db.rollback();raise


@router.put('/project/{project_id}/invoice/customer-sent', dependencies=[Depends(require_any_permission('projects:write','finance:write'))])
def update_invoice_customer_sent(project_id: UUID, payload: InvoiceCustomerSentWrite, db=Depends(get_db), user=Depends(get_current_user)):
    from translation_project_invoices import set_customer_sent
    return set_customer_sent(db, project_id, user, payload.sent)
