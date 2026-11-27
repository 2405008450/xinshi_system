"""口译客户/子客户单据与账期设置，使用口译财务 JSON 及原审计表。"""
from copy import deepcopy
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy.orm import object_session
from sqlalchemy import event
from sqlalchemy.orm import Session
from models import Client,SubClient
from database import get_db
from routers.auth import get_current_user
from annotation_progress_time import business_now
from sub_client_finance import PreferenceWrite,PeriodPartyWrite

KEY='_oral_settlement_settings'
router=APIRouter(prefix='/settlement-settings',tags=['口译结算设置'])


@event.listens_for(Session,'after_commit')
@event.listens_for(Session,'after_rollback')
def clear_settings_cache(session):
    session.info.pop('oral_settlement_settings_cache',None)


class SettingsWrite(PreferenceWrite):
    payment_method:Literal['individual','monthly','sub_client','special']|None=None
    collection_terms:str=Field(default='',max_length=300)


def _finance():
    import interpretation_customer_finance as finance
    return finance


def authorize(db,user,write=False):
    finance=_finance()
    if not any(finance.user_has_permission(db,user.id,scope+(':write' if write else ':read')) or
               (not write and finance.user_has_permission(db,user.id,scope+':write')) for scope in ('clients','projects')):
        raise HTTPException(403,'无权操作客户结算设置')


def location(db,kind,target):
    entity=db.get(SubClient if kind=='sub-client' else Client,target)
    if not entity:raise HTTPException(404,'客户或子客户不存在')
    return entity,entity.parent_client_id if kind=='sub-client' else entity.id


def state(db,client_id):
    cache=db.info.setdefault('oral_settlement_settings_cache',{})
    if client_id in cache:return deepcopy(cache[client_id])
    row=_finance().record(db,'client',client_id)
    value=deepcopy((row.payload if row else {}).get(KEY) or {'customer':{},'sub_clients':{},'parties':{}})
    cache[client_id]=value
    return deepcopy(value)


def preferences(values,kind,target):
    return values.get('customer',{}) if kind=='client' else values.get('sub_clients',{}).get(str(target),{})


def party_value(values,sub_id,month,period):
    return values.get('parties',{}).get(f'{sub_id}:{month}:{period or 0}','sub_client')


def effective(db,project,payload):
    """仅覆盖已配置的默认项；特殊结算保留独立的项目单据设置。"""
    result=deepcopy(payload);setting=result.get('settlement') or {}
    if not project.client_id:return result
    values=state(db,project.client_id)
    from interpretation_statements import billing_month
    parent=preferences(values,'client',project.client_id)
    child=preferences(values,'sub-client',project.sub_client_id) if project.sub_client_id else {}
    party=party_value(values,project.sub_client_id,billing_month(project,result),setting.get('period_number')) if project.sub_client_id else 'client'
    selected={**parent,**{key:value for key,value in child.items() if value is not None}} if party=='sub_client' else parent
    if not payload.get('settlement') and selected.get('payment_method'):
        setting['payment_method']=selected['payment_method']
    if setting.get('payment_method')!='special':
        for key in ('quotation_required','statement_required','statement_subject_key','document_notes'):
            if selected.get(key) is not None:setting[key]=deepcopy(selected[key])
        if selected.get('invoice_required') is not None:setting['invoice_requirement_override']=selected['invoice_required']
        if selected.get('tax_mode'):setting['tax_basis']=selected['tax_mode']
    override=setting.get('invoice_requirement_override')
    if isinstance(override,bool):setting['invoice_required']=override
    elif setting.get('tax_basis') in ('incl_tax','excl_tax'):setting['invoice_required']=setting['tax_basis']=='incl_tax'
    result['settlement']=setting
    return result


def store(db,user,client_id,values,action):
    finance=_finance();row=finance.record(db,'client',client_id)
    before=deepcopy(row.payload if row else {})
    after={**before,KEY:deepcopy(values)}
    if row:row.payload=after;row.revision+=1
    else:row=finance.InterpretationCustomerFinance(client_id=client_id,revision=1,payload=after);db.add(row);db.flush()
    db.add(finance.InterpretationCustomerFinanceHistory(finance_id=row.id,revision=row.revision,
        actor_id=user.id,actor_name=user.full_name or user.username,before=before,after=after))
    db.flush()
    db.info.setdefault('oral_settlement_settings_cache',{})[client_id]=deepcopy(values)


def propagate(db,user,client_id,skip=None):
    finance=_finance()
    from interpretation_models import InterpretationProject
    projects=db.query(InterpretationProject).filter_by(client_id=client_id).order_by(InterpretationProject.id).all()
    records=finance.finance_records(db,projects,True)[0]
    for project in projects:
        if project.id==skip:continue
        row=records.get(project.id)
        if not row:continue
        before=deepcopy(row.payload);after=effective(db,project,before)
        if before==after:continue
        row.payload=after;row.revision+=1
        db.add(finance.InterpretationCustomerFinanceHistory(finance_id=row.id,revision=row.revision,
            actor_id=user.id,actor_name=user.full_name or user.username,before=before,after=after))
    db.flush()


def sync_project(db,user,project,before,after):
    if not project.client_id:return
    previous=_finance().settlement(effective(db,project,before)).model_dump(mode='json')
    setting=after.get('settlement') or {}
    if setting.get('payment_method')=='special':return
    mapping={'quotation_required':'quotation_required','statement_required':'statement_required',
             'invoice_requirement_override':'invoice_required','document_notes':'document_notes','statement_subject_key':'statement_subject_key'}
    changes={target:setting.get(source) for source,target in mapping.items() if source in setting and setting.get(source)!=previous.get(source)}
    if not changes:return
    values=state(db,project.client_id)
    from interpretation_statements import billing_month
    party=party_value(values,project.sub_client_id,billing_month(project,after),setting.get('period_number')) if project.sub_client_id else 'client'
    current=values.setdefault('sub_clients',{}).setdefault(str(project.sub_client_id),{}) if party=='sub_client' else values.setdefault('customer',{})
    current.update(changes);current['revision']=current.get('revision',0)+1
    store(db,user,project.client_id,values,'项目单据设置同步客户')
    propagate(db,user,project.client_id,skip=project.id)


@router.get('/{kind}/{target}')
def read(kind:Literal['client','sub-client'],target:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user);entity,client_id=location(db,kind,target)
    value=preferences(state(db,client_id),kind,target)
    return dict(client_id=str(client_id),sub_client_name=entity.client_short_name or entity.client_name,sub_client_code=entity.sub_client_code if kind=='sub-client' else entity.client_code,
        revision=value.get('revision',0),quotation_required=value.get('quotation_required'),statement_required=value.get('statement_required'),
        invoice_required=value.get('invoice_required'),tax_mode=value.get('tax_mode'),statement_subject_key=value.get('statement_subject_key'),
        payment_method=value.get('payment_method'),document_notes=value.get('document_notes') or {},collection_terms=value.get('collection_terms',''))


@router.put('/{kind}/{target}')
def write(kind:Literal['client','sub-client'],target:UUID,data:SettingsWrite,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user,True);_,client_id=location(db,kind,target)
    db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().one()
    values=state(db,client_id);old=preferences(values,kind,target)
    if old.get('revision',0)!=data.revision:raise HTTPException(409,'结算设置已修改，请刷新后重试')
    changes=data.model_dump(mode='json',exclude_unset=True,exclude={'revision'})
    current={**old,**changes,'revision':data.revision+1}
    if kind=='client':values['customer']=current
    else:values.setdefault('sub_clients',{})[str(target)]=current
    store(db,user,client_id,values,'修改客户结算设置');propagate(db,user,client_id)
    db.commit();return read(kind,target,db,user)


@router.get('/sub-client/{target}/party')
def read_party(target:UUID,month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),period:int|None=None,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user);_,client_id=location(db,'sub-client',target)
    return dict(party=party_value(state(db,client_id),target,month,period),client_id=str(client_id))


@router.put('/sub-client/{target}/party')
def write_party(target:UUID,data:PeriodPartyWrite,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user,True);_,client_id=location(db,'sub-client',target)
    db.query(Client).filter_by(id=client_id).with_for_update().one()
    values=state(db,client_id)
    if party_value(values,target,data.month,data.period)!=data.expected_party:raise HTTPException(409,'账期结算对象已修改，请刷新后重试')
    values.setdefault('parties',{})[f'{target}:{data.month}:{data.period or 0}']=data.party
    store(db,user,client_id,values,'切换账期结算对象');propagate(db,user,client_id);db.commit()
    return dict(party=data.party,client_id=str(client_id))


def period_projects(db,project):
    finance=_finance()
    from interpretation_models import InterpretationProject
    from interpretation_statements import billing_month
    current=finance.record(db,'project',project.id)
    setting=finance.settlement(current.payload if current else {})
    month=billing_month(project,current.payload if current else {})
    rows=db.query(InterpretationProject).filter(InterpretationProject.client_id==project.client_id)
    if project.sub_client_id:rows=rows.filter(InterpretationProject.sub_client_id==project.sub_client_id)
    projects=rows.order_by(InterpretationProject.order_no).all()
    records=finance.finance_records(db,projects,True)[0]
    matches=[item for item in projects if billing_month(item,records[item.id].payload if item.id in records else {})==month and finance.settlement(records[item.id].payload if item.id in records else {}).period_number==setting.period_number]
    return dict(month=month,period=setting.period_number,items=[dict(id=str(p.id),orderNo=p.order_no,projectName=p.project_name) for p in matches])


@router.get('/project/{target}/period-projects')
def get_period_projects(target:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user);return period_projects(db,_finance().owner(db,'project',target))


@router.get('/project/{target}/billing-period')
def billing_period(target:UUID,month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user);finance=_finance();project=finance.owner(db,'project',target)
    from interpretation_models import InterpretationProject
    query=db.query(InterpretationProject)
    projects=(query.filter_by(client_id=project.client_id) if project.client_id else query.filter_by(id=target)).all()
    records=finance.finance_records(db,projects,True)[0]
    from interpretation_statements import billing_month
    periods=sorted({finance.settlement(r.payload).period_number for r in records.values() if finance.settlement(r.payload).period_number and billing_month(next(p for p in projects if p.id==r.project_id),r.payload)==month})
    row=finance.record(db,'project',target);setting=finance.settlement(row.payload if row else {})
    return dict(revision=row.revision if row else 0,board_id=f'{month}:{setting.period_number}' if setting.period_number and billing_month(project,row.payload if row else {})==month else None,
        boards=[dict(id=f'{month}:{n}',number=n,name=f'第{n}期') for n in periods],can_create=True,can_create_custom=True)


class BillingWrite(BaseModel):
    month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    revision:int=Field(ge=0)
    board_id:str|None=None
    create_period:bool=False
    period_number:int|None=Field(default=None,ge=1,le=999)
    version:str|None=None


@router.put('/project/{target}/billing-period')
def save_billing_period(target:UUID,data:BillingWrite,db=Depends(get_db),user=Depends(get_current_user)):
    authorize(db,user,True);finance=_finance();project=finance.owner(db,'project',target)
    options=billing_period(target,data.month,db,user)
    if options['revision']!=data.revision:raise HTTPException(409,'项目账期已修改，请重新打开')
    periods=[item['number'] for item in options['boards']]
    number=data.period_number
    if data.board_id:
        board=next((item for item in options['boards'] if item['id']==data.board_id),None)
        if not board:raise HTTPException(422,'所选账期不存在，请重新选择')
        number=board['number']
    elif data.create_period:number=max(periods,default=0)+1
    elif number in periods:raise HTTPException(409,'该期次已存在，请直接选择')
    if number and number>999:raise HTTPException(422,'账期编号不能超过999')
    row=finance.record(db,'project',target)
    payload=deepcopy(row.payload if row else {})
    setting=payload.get('settlement') or {}
    setting.update(billing_month=data.month,period_number=number)
    payload['settlement']=setting
    result=finance.save(db,user,'project',target,finance.FinanceWrite.model_validate({**payload,'revision':data.revision}))
    return result
