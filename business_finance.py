"""标注与招聘财务账簿；复用已有审计表，项目报价只读，财务保存不改项目管理。"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import re
from types import SimpleNamespace
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import func
from database import get_db
from models import Client, SubClient
from annotation_progress_time import business_now
from interpretation_finance_schemas import StrictInput, InterpretationSettlement, InterpretationInvoice, SettlementAmountAdjustment
import project_customer_finance as source
from business_finance_payment import Registration, registration, apply_registration, history_snapshot

Module = source.Module
router = APIRouter(prefix='/business-finance', tags=['标注招聘财务'])


class Price(StrictInput):
    direction: str = Field(default='客户收费', max_length=500)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')
    unit: str = Field(default='个', min_length=1, max_length=30)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    tax_prices: dict | None = None


class Write(StrictInput):
    revision: int = Field(ge=0)
    rates: list[Price] = Field(default_factory=list, max_length=100)
    settlement: InterpretationSettlement = Field(default_factory=InterpretationSettlement)
    settlement_adjustments: list[SettlementAmountAdjustment] = Field(default_factory=list, max_length=20)
    explanation: str = Field(default='', max_length=5000)
    salary_basis: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    payment_registration: Registration | None = None


def latest(db, module, uid):
    return db.query(source.ProjectCustomerFinanceHistory).filter(
        source.ProjectCustomerFinanceHistory.module == module,
        source.ProjectCustomerFinanceHistory.project_id == uid,
        source.ProjectCustomerFinanceHistory.after['_ledger'].as_string().is_not(None)
    ).order_by(source.ProjectCustomerFinanceHistory.created_at.desc(), source.ProjectCustomerFinanceHistory.id.desc()).first()


def initial(module, project):
    rates=[]
    if module == 'annotation':
        rates=[dict(direction=row['language_display'] or row['project_type'] or '标注', amount=row['amount'],
                    currency=row['currency'], unit=row['unit'] or '个', quantity=None) for row in source.prices(project)]
    else:
        rates=[dict(direction=project.position_title or '招聘服务费', amount=str(project.service_fee_amount) if project.service_fee_type=='fixed' and project.service_fee_amount is not None else None,
                    currency=project.service_fee_currency or 'CNY', unit='人', quantity=None)]
    return dict(revision=0, rates=rates, settlement=InterpretationSettlement().model_dump(mode='json'), settlement_adjustments=[], explanation='', salary_basis=None)


def record(db,module,uid):
    project=source.owner(db,module,uid)
    row=latest(db,module,uid)
    return SimpleNamespace(payload=deepcopy(row.after['_ledger'] if row else initial(module,project)),revision=row.after['_ledger']['revision'] if row else 0)


def month(project,payload):
    if payload.get('settlement',{}).get('billing_month'):return payload['settlement']['billing_month']
    match=re.match(r'^[A-Z]+-(\d{4}|\d{2})(\d{2})\d{2}-',project.order_no or '')
    if match:return (match[1] if len(match[1])==4 else '20'+match[1])+'-'+match[2]
    from annotation_progress_time import business_datetime
    return business_datetime(project.created_at).strftime('%Y-%m') if project.created_at else None


def normalized(module,project,payload):
    result=deepcopy(payload)
    if module=='recruitment' and project.service_fee_type in ('annual_salary_rate','monthly_salary_multiple'):
        basis=payload.get('salary_basis')
        factor=project.service_fee_rate if project.service_fee_type=='annual_salary_rate' else project.service_fee_multiplier
        for row in result['rates']:
            row['amount']=str(Decimal(str(basis))*Decimal(str(factor))/(100 if project.service_fee_type=='annual_salary_rate' else 1)) if basis is not None and factor is not None else None
    # 不把未填写的验收量/单价伪装为已确定的零。
    for row in result['rates']:
        basis=result['settlement'].get('tax_basis','legacy')
        if basis!='legacy' and row.get('amount') is not None:
            row['tax_prices']={'unit_price_'+basis:row['amount']}
    return result


def totals(payload):
    from interpretation_customer_finance import calculate
    valid=deepcopy(payload);valid['rates']=[row for row in valid['rates'] if row.get('amount') is not None and row.get('quantity') is not None]
    values=calculate(valid)
    missing={row['currency'] for row in payload['rates'] if row.get('amount') is None or row.get('quantity') is None}
    for key in ('totals','adjusted_totals','totals_excl_tax','totals_incl_tax'):
        for currency in missing:values[key].pop(currency,None)
    return values


def records(db,module,projects):
    if not projects:return {}
    from sqlalchemy import select,func
    History=source.ProjectCustomerFinanceHistory
    ranked=select(History.id,func.row_number().over(partition_by=History.project_id,order_by=(History.created_at.desc(),History.id.desc())).label('position')).where(
        History.module==module,History.project_id.in_([item.id for item in projects]),History.after['_ledger'].as_string().is_not(None)).subquery()
    values={row.project_id:row.after['_ledger'] for row in db.query(History).join(ranked,History.id==ranked.c.id).filter(ranked.c.position==1).all()}
    return {item.id:SimpleNamespace(payload=deepcopy(values.get(item.id) or initial(module,item)),revision=(values.get(item.id) or {}).get('revision',0)) for item in projects}


def context(db,module,project,payload=None,stored=None):
    stored=stored or record(db,module,project.id)
    payload=payload or stored.payload
    if module == 'annotation':
        payload=deepcopy(payload)
        payload['payment_registration']=registration(payload)
    actual=normalized(module,project,payload)
    amounts=totals(actual)
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    kind=payload['settlement'].get('tax_basis','legacy')
    billing=amounts['adjusted_totals' if kind=='legacy' else 'totals_'+kind]
    received={}
    for entry in payload['settlement'].get('payments',[]):received[entry['currency']]=received.get(entry['currency'],Decimal(0))+Decimal(str(entry['amount']))
    return dict(id=str(project.id),module=module,order_no=project.order_no,project_name=project.project_name,
                client_id=str(client.id) if client else None,sub_client_id=str(project.sub_client_id) if project.sub_client_id else None,
                client_name=(client.client_short_name or client.client_name) if client else '-',client_manager_name=project.client_manager_name,
                project_status=project.project_status,billing_month=month(project,payload),settlement_mode=payload['settlement']['payment_method'],
                revision=stored.revision,payload=payload,source_price=source.snapshot(module,project),
                service_fee_type=getattr(project,'service_fee_type',None),service_fee_rate=str(project.service_fee_rate) if getattr(project,'service_fee_rate',None) is not None else None,
                service_fee_multiplier=str(project.service_fee_multiplier) if getattr(project,'service_fee_multiplier',None) is not None else None,
                position_title=getattr(project,'position_title',None),**amounts,billing_totals=billing,
                received_totals={code:format(value,'.2f') for code,value in received.items()},
                payment_difference={code:format(received.get(code,Decimal(0))-Decimal(value),'.2f') for code,value in billing.items()})


def append(db,module,project,payload,user):
    previous=record(db,module,project.id)
    payload=deepcopy(payload);payload['revision']=previous.revision+1
    db.add(source.ProjectCustomerFinanceHistory(module=module,project_id=project.id,order_no=project.order_no,
           actor_id=user.id,actor_name=user.full_name or user.username,before={'_ledger':previous.payload},after={'_ledger':payload},created_at=business_now()))
    db.flush()
    return payload


@router.get('/{module}/page')
def page(module:Module,keyword:str='',client_id:UUID|None=None,only_mine:bool=False,client_manager:str='',
         skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=1000),db=Depends(get_db),user=Depends(source.access)):
    from search_matching import keyword_any
    model=source.MODELS[module]
    query=source.project_query(db,module).outerjoin(SubClient,model.sub_client_id==SubClient.id).outerjoin(Client,func.coalesce(model.client_id,SubClient.parent_client_id)==Client.id)
    if client_id:query=query.filter(Client.id==client_id)
    if only_mine:query=query.filter(model.client_manager_id==user.id)
    query=query.filter(keyword_any([model.order_no,model.project_name,Client.client_name,Client.client_short_name],keyword))
    projects=query.order_by(model.order_no.desc(),model.id.desc()).all()
    if client_manager:
        from search_matching import matches_keywords
        projects=[row for row in projects if matches_keywords(row.client_manager_name or '',client_manager)]
    selected=projects[skip:skip+limit];saved=records(db,module,selected)
    return dict(items=[context(db,module,project,stored=saved[project.id]) for project in selected],total=len(projects))


@router.get('/{module}/project/{uid}')
def read(module:Module,uid:UUID,db=Depends(get_db),user=Depends(source.access)):
    return context(db,module,source.owner(db,module,uid))


@router.put('/{module}/project/{uid}')
def put(module:Module,uid:UUID,data:Write,db=Depends(get_db),user=Depends(source.access)):
    from permission_service import user_has_permission
    if not user_has_permission(db,user.id,'projects:write'):raise HTTPException(403,'没有项目财务编辑权限')
    project=source.owner(db,module,uid,True);previous=record(db,module,uid)
    if data.revision!=previous.revision:raise HTTPException(409,'财务数据已更新，请重新加载')
    payload=data.model_dump(mode='json');payload['invoice']=previous.payload.get('invoice',{})
    if data.payment_registration is not None:
        if module != 'annotation':raise HTTPException(422,'该付款表单仅用于标注项目')
        amounts=totals(normalized(module,project,payload))
        basis=payload['settlement'].get('tax_basis','legacy')
        apply_registration(payload,amounts['adjusted_totals' if basis=='legacy' else 'totals_'+basis])
    elif previous.payload.get('payment_registration') is not None:
        # 旧窗口不能覆盖新表单登记的付款。
        payload['payment_registration']=previous.payload['payment_registration']
        for key in ('payments','payment_status','payment_note'):
            payload['settlement'][key]=previous.payload['settlement'][key]
    if len({row.currency for row in data.settlement_adjustments})!=len(data.settlement_adjustments):raise HTTPException(422,'同币种不能重复调整')
    append(db,module,project,payload,user);db.commit()
    return context(db,module,project)


@router.get('/{module}/project/{uid}/payment-history')
def payment_history(module:Module,uid:UUID,page:int=Query(1,ge=1),db=Depends(get_db),user=Depends(source.access)):
    from chat_time import api_time
    source.owner(db,module,uid)
    query=db.query(source.ProjectCustomerFinanceHistory).filter_by(module=module,project_id=uid).order_by(
        source.ProjectCustomerFinanceHistory.created_at.desc(),source.ProjectCustomerFinanceHistory.id.desc())
    items=[]
    for row in query:
        before,after=row.before.get('_ledger'),row.after.get('_ledger')
        if after is None:continue
        old=history_snapshot(before or {})
        new=history_snapshot(after)
        if old!=new:items.append(api_time(dict(id=str(row.id),actor_name=row.actor_name,created_at=row.created_at,before=old,after=new)))
    return dict(items=items[(page-1)*10:page*10],total=len(items))


def invoice_scope(db,module,uid):
    project=source.owner(db,module,uid);anchor=context(db,module,project);mode=anchor['settlement_mode']
    model=source.MODELS[module]
    query=source.project_query(db,module).outerjoin(SubClient,model.sub_client_id==SubClient.id).filter(func.coalesce(model.client_id,SubClient.parent_client_id)==UUID(anchor['client_id'])) if anchor['client_id'] else source.project_query(db,module).filter(model.id==uid)
    projects=query.order_by(model.order_no).all();saved=records(db,module,projects)
    rows=[context(db,module,item,stored=saved[item.id]) for item in projects]
    rows=[item for item in rows if (item['id']==str(uid) if mode in ('individual','special') else item['settlement_mode']==mode and item['billing_month']==anchor['billing_month'] and (mode!='sub_client' or item['sub_client_id']==anchor['sub_client_id']))]
    items=[dict(id=item['id'],order_no=item['order_no'],project_name=item['project_name'],client_id=item['client_id'],sub_client_id=item['sub_client_id'],revision=item['revision'],required=item['payload']['settlement']['invoice_required'],totals=item['totals_incl_tax'],invoice_status=item['payload'].get('invoice',{}).get('invoice_status','unissued'),proofs=item['payload'].get('invoice',{}).get('proofs',''),**{key:item['payload'].get('invoice',{}).get(key) for key in ('subject_key','invoice_type','buyer_index')}) for item in rows]
    total={}
    for item in items:
        if item['required']:
            for code,value in item['totals'].items():total[code]=total.get(code,Decimal(0))+Decimal(value)
    return dict(mode=mode,month=anchor['billing_month'],client_name=anchor['client_name'],items=items,totals={code:format(value,'.2f') for code,value in total.items()})


@router.get('/{module}/project/{uid}/invoice')
def invoice(module:Module,uid:UUID,db=Depends(get_db),user=Depends(source.access)):
    return invoice_scope(db,module,uid)


class InvoiceWrite(InterpretationInvoice):
    revision:int=Field(ge=0)


@router.put('/{module}/project/{uid}/invoice')
def save_invoice(module:Module,uid:UUID,data:InvoiceWrite,db=Depends(get_db),user=Depends(source.access)):
    from permission_service import user_has_permission
    if not user_has_permission(db,user.id,'projects:write'):raise HTTPException(403,'没有项目财务编辑权限')
    from statement_special_documents import validate_invoice_proofs
    validate_invoice_proofs(db,data.proofs)
    project=source.owner(db,module,uid,True);row=record(db,module,uid)
    if row.revision!=data.revision:raise HTTPException(409,'发票已变化，请重新加载')
    row.payload['invoice']=data.model_dump(mode='json',exclude={'revision'});append(db,module,project,row.payload,user);db.commit()
    return next(item for item in invoice_scope(db,module,uid)['items'] if item['id']==str(uid))


@router.get('/{module}/ledger')
def ledger(module:Literal['interpretation','annotation','recruitment'],client_id:UUID|None=None,only_mine:bool=True,client_manager:str='',db=Depends(get_db),user=Depends(source.access)):
    import interpretation_customer_finance as oral
    from interpretation_models import InterpretationProject
    from search_matching import matches_keywords
    Model=InterpretationProject if module=='interpretation' else source.MODELS[module]
    query=db.query(Model).outerjoin(SubClient,Model.sub_client_id==SubClient.id)
    if client_id:query=query.filter(func.coalesce(Model.client_id,SubClient.parent_client_id)==client_id)
    if module=='interpretation':
        from project_client_manager import manager_self_expression,manager_name_expression
        from search_matching import keyword_contains
        query=query.outerjoin(Client,Model.client_id==Client.id)
        fallback=func.coalesce(SubClient.client_manager,Client.client_manager)
        if only_mine:query=query.filter(manager_self_expression(module,Model.id,user.id,[user.full_name,user.username],fallback))
        elif client_manager:query=query.filter(keyword_contains(manager_name_expression(module,Model.id,fallback),client_manager))
    elif only_mine:query=query.filter(Model.client_manager_id==user.id)
    projects=query.order_by(Model.order_no).all()
    if client_manager and module!='interpretation':projects=[item for item in projects if matches_keywords(item.client_manager_name or '',client_manager)]
    saved=oral.finance_records(db,projects,True)[0] if module=='interpretation' else records(db,module,projects)
    result=[]
    for project in projects:
        row=saved.get(project.id)
        item=oral.finance_context('project',project,True,row) if module=='interpretation' else context(db,module,project,stored=row)
        result.append(item)
    if module=='interpretation':
        from interpretation_board_payments import ledger_units
        units,covered=ledger_units(db,result)
        return {'items':result,'units':units,'covered_project_ids':covered}
    return {'items':result}
