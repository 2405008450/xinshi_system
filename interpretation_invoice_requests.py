"""口译开票需求与回执，独立保存于既有口译财务 JSON，复用发票主体和负责人。"""
from copy import deepcopy
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from database import get_db
from models import AppNotification
from routers.auth import get_current_user
from annotation_progress_time import business_now
from invoice_parties import InvoiceType,SubjectKey,profile,subject,SUBJECTS,INVOICE_TYPES
from invoice_workflow import batch_settings,commit_notices
import interpretation_customer_finance as finance

from business_finance_source import MODULE, select_module
import business_finance_source as sources
router=APIRouter(prefix='/invoice-requests',tags=['财务开票需求'],dependencies=[Depends(select_module)])

def request_storage(db,target,create=False):
    if MODULE.get()=='interpretation':return finance.record(db,'project',target)
    project=sources.owner(db,target)
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先关联客户')
    row=finance.record(db,'client',client.id)
    if not row and create:
        row=finance.InterpretationCustomerFinance(client_id=client.id,payload={},revision=0);db.add(row);db.flush()
    return row


def preview(db,user,target):
    finance.permission(db,user,'project')
    if MODULE.get()=='interpretation':scope=finance.get_invoice(target,db=db,user=user)
    else:
        from business_finance import invoice_scope
        scope=invoice_scope(db,MODULE.get(),target)
    items=[item for item in scope['items'] if item['required']]
    for item in items:
        if not item['client_id']:raise HTTPException(422,'请先为项目关联客户')
        info=profile(db,UUID(item['client_id']),UUID(item['sub_client_id']) if item['sub_client_id'] else None)
        item.update(buyer_group=item['sub_client_id'] or item['client_id'],buyer_options=info['parties'] or [info['party']],buyer=info['party'],default_subject=info['subject_key'],invoice_type=info['invoice_type'])
    config=batch_settings(db)
    return dict(projects=items,mode=scope['mode'],month=scope['month'],client_name=scope['client_name'],subjects=[subject(db,key) for key in SUBJECTS],settings_revision=config['revision'],recipients=[item for item in config['users'] if item['id'] in config['user_ids']])


def value(request,user):
    return {**deepcopy(request),'is_sender':request['created_by']==str(user.id),'is_recipient':str(user.id) in request['recipients']}


def save(db,user,row,before,payload):
    row.payload=payload;row.revision+=1
    db.add(finance.InterpretationCustomerFinanceHistory(finance_id=row.id,revision=row.revision,actor_id=user.id,actor_name=user.full_name or user.username,before=deepcopy(before),after=deepcopy(payload)))


def locate(db,uid,user):
    row=db.query(finance.InterpretationCustomerFinance).filter(finance.InterpretationCustomerFinance.payload['_oral_invoice_requests'][str(uid)].as_string().is_not(None)).with_for_update().first()
    request=(row.payload.get('_oral_invoice_requests') or {}).get(str(uid)) if row else None
    if not request:raise HTTPException(404,'开票需求不存在')
    MODULE.set(request.get('module','interpretation'))
    if request['created_by']!=str(user.id) and str(user.id) not in request['recipients']:raise HTTPException(403,'无权查看该开票需求')
    return row,deepcopy(request)


def notice(user_id,request,title,kind):
    return AppNotification(id=uuid4(),recipient_user_id=UUID(user_id),title=title,content=f"{request['snapshot']['client_name']} · {request['snapshot']['month']} · {request['snapshot']['sender']}，请打开核对。",notification_type=kind,related_project_id=None,related_project_type='business_invoice_request',related_entity_id=UUID(request['id']),is_read=False,created_at=business_now().replace(tzinfo=None))


class Send(BaseModel):
    subject_key:SubjectKey
    invoice_type:InvoiceType='electronic_normal'
    tax_rate:Literal[1,3,6]|None=None
    buyer_choices:dict[str,int]=Field(default_factory=dict)
    settings_revision:int=Field(ge=0)
    expected_user_ids:list[UUID]=Field(min_length=1,max_length=500)
    project_revisions:dict[str,int]
    idempotency_key:UUID
    note:str=Field(default='',max_length=2000)


@router.get('/project/{target}/preview')
def read_preview(target:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    return preview(db,user,target)


@router.post('/project/{target}/send')
def send(target:UUID,data:Send,db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project',True)
    project=sources.owner(db,target)
    # 与收费保存保持同一客户→项目锁序。
    from models import Client
    if project.client_id:db.query(Client).filter_by(id=project.client_id).with_for_update().first()
    db.query(sources.model()).filter_by(id=target).with_for_update().one()
    row=request_storage(db,target,True)
    if not row:raise HTTPException(422,'请先保存项目收费资料')
    before=deepcopy(row.payload);payload=deepcopy(before);requests=payload.setdefault('_oral_invoice_requests',{})
    submission=data.model_dump(mode='json')
    existing=next((item for item in requests.values() if item['idempotency_key']==str(data.idempotency_key)),None)
    if existing:
        if existing['created_by']!=str(user.id) or existing['submission']!=submission:raise HTTPException(409,'发送标识不匹配')
        return value(existing,user)
    snapshot=preview(db,user,target)
    if not snapshot['projects']:raise HTTPException(422,'当前结算范围没有需开发票项目，请先确认发票需求')
    if data.settings_revision!=snapshot['settings_revision'] or {str(uid) for uid in data.expected_user_ids}!={item['id'] for item in snapshot['recipients']}:raise HTTPException(409,'开票接收人设置已变化，请重新加载')
    if data.project_revisions!={item['id']:item['revision'] for item in snapshot['projects']}:raise HTTPException(409,'项目开票资料已变化，请重新加载')
    if data.invoice_type.endswith('_special'):
        rate=data.tax_rate or (6 if data.subject_key=='guangzhou' else None)
        if rate not in ({6} if data.subject_key=='guangzhou' else {1,3}):raise HTTPException(422,'请按开票主体选择专票税率')
    else:rate=None
    for item in snapshot['projects']:
        index=data.buyer_choices.get(item['buyer_group'],0)
        if not 0<=index<len(item['buyer_options']):raise HTTPException(409,'客户开票资料已变化')
        item['buyer']=item['buyer_options'][index]
        if not item['buyer'].get('title'):raise HTTPException(422,'请先填写客户开票抬头')
        if not item['totals']:raise HTTPException(422,'请先补全含税结算金额，再发送开票需求')
    snapshot.update(subject=subject(db,data.subject_key),invoice_type=INVOICE_TYPES[data.invoice_type],tax_rate=rate,note=data.note,sender=user.full_name or user.username)
    request=dict(module=MODULE.get(),id=str(uuid4()),anchor_id=str(target),created_by=str(user.id),created_at=business_now().isoformat(),revision=1,recipients=[item['id'] for item in snapshot['recipients']],snapshot=snapshot,request_receipts={},completion_receipts={},completed_by=None,idempotency_key=str(data.idempotency_key),submission=submission)
    requests[request['id']]=request;save(db,user,row,before,payload)
    notices=[notice(uid,request,f"口译开票需求 · {snapshot['projects'][0]['order_no']}",'invoice_request') for uid in request['recipients']]
    db.add_all(notices);commit_notices(db,notices)
    return value(request,user)


@router.get('/project/{target}/history')
def history(target:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project')
    row=request_storage(db,target)
    requests=[item for item in (row.payload.get('_oral_invoice_requests') or {}).values() if item.get('module','interpretation')==MODULE.get() and item.get('anchor_id')==str(target)] if row else []
    return {'items':[value(item,user) for item in sorted(requests,key=lambda item:item['created_at'],reverse=True) if item['created_by']==str(user.id) or str(user.id) in item['recipients']]}


@router.get('/request/{uid}')
def read(uid:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    _,request=locate(db,uid,user)
    return value(request,user)


class Action(BaseModel):
    revision:int=Field(ge=1)
    action:Literal['receive','upload','complete','receive_completion']
    project_id:UUID|None=None
    invoice_status:Literal['unissued','partial','issued']='issued'
    proofs:str=Field(default='',max_length=20000)


@router.post('/request/{uid}')
def update(uid:UUID,data:Action,db=Depends(get_db),user=Depends(get_current_user)):
    row,request=locate(db,uid,user)
    if data.revision!=request['revision']:raise HTTPException(409,'需求已更新，请重新加载')
    recipient=str(user.id) in request['recipients'];sender=str(user.id)==request['created_by']
    if data.action in ('receive','upload','complete') and not recipient:raise HTTPException(403,'仅需求接收人可操作')
    before=deepcopy(row.payload);payload=deepcopy(before);now=business_now().isoformat();who=dict(name=user.full_name or user.username,at=now)
    notices=[]
    if data.action=='receive':
        request['request_receipts'][str(user.id)]=who
        notices=[notice(request['created_by'],request,'口译开票需求已收到','invoice_request_received')]
    elif data.action=='upload':
        if str(user.id) not in request['request_receipts']:raise HTTPException(409,'请先发送收到回执')
        if not data.project_id or str(data.project_id) not in {item['id'] for item in request['snapshot']['projects']}:raise HTTPException(422,'项目不属于该需求')
        from statement_special_documents import validate_invoice_proofs
        validate_invoice_proofs(db,data.proofs)
        target_row=sources.record(db,data.project_id)
        if not target_row:raise HTTPException(404,'项目收费资料不存在')
        target_before=deepcopy(target_row.payload);target_payload=deepcopy(target_before)
        invoice=dict(invoice_status=data.invoice_status,proofs=data.proofs,subject_key=request['submission']['subject_key'],invoice_type=request['submission']['invoice_type'],buyer_index=request['submission']['buyer_choices'].get(next(item['buyer_group'] for item in request['snapshot']['projects'] if item['id']==str(data.project_id)),0))
        target_payload['invoice']=invoice
        if request.get('module','interpretation')!='interpretation':
            import business_finance as business
            target_entity=sources.owner(db,data.project_id)
            business.append(db,MODULE.get(),target_entity,target_payload,user)
        elif target_row.id==row.id:payload['invoice']=invoice
        else:save(db,user,target_row,target_before,target_payload)
        request.setdefault('invoices',{})[str(data.project_id)]={**invoice,**who}
    elif data.action=='complete':
        if str(user.id) not in request['request_receipts']:raise HTTPException(409,'请先发送收到回执')
        if any(request.get('invoices',{}).get(item['id'],{}).get('invoice_status')!='issued' or not request.get('invoices',{}).get(item['id'],{}).get('proofs') for item in request['snapshot']['projects']):raise HTTPException(422,'请先登记所有项目的已开发票及附件')
        request['completed_by']=who;notices=[notice(request['created_by'],request,'口译开票完成','invoice_completed')]
    else:
        if not sender or not request.get('completed_by'):raise HTTPException(403,'仅需求人可在开票完成后回执')
        request['completion_receipts'][str(user.id)]=who;notices=[notice(uid,request,'口译发票已收到','invoice_received') for uid in request['recipients']]
    request['revision']+=1;payload.setdefault('_oral_invoice_requests',{})[str(uid)]=request;save(db,user,row,before,payload)
    db.add_all(notices);commit_notices(db,notices)
    return value(request,user)
