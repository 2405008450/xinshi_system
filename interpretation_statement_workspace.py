"""口译独立单据快照，复用既有口译客户财务 JSON 存储及审计，不修改项目收费。"""
from copy import deepcopy
from decimal import Decimal
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel,Field
from sqlalchemy import func
from database import get_db
from routers.auth import get_current_user
from annotation_progress_time import business_now
from models import Client,SubClient
from interpretation_models import InterpretationProject
import interpretation_customer_finance as finance
import interpretation_statements as statements

from business_finance_source import MODULE,select_module
import business_finance_source as sources
router=APIRouter(prefix='/statement-workspace',tags=['财务对账单工作区'],dependencies=[Depends(select_module)])
Mode=Literal['individual','monthly','sub_client','special']
MONTH=r'^\d{4}-(0[1-9]|1[0-2])$'


def context(db,target,mode=None,lock=False):
    project=sources.owner(db,target)
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先关联客户，再制作对账单')
    row=sources.record(db,target)
    mode=mode or finance.settlement_mode(row.payload if row else {})
    if mode=='sub_client' and not project.sub_client_id:raise HTTPException(422,'请先选择已关联子客户的项目')
    if lock:db.query(Client).filter_by(id=client.id).with_for_update().one()
    storage=finance.record(db,'client',client.id)
    payload=deepcopy(storage.payload if storage else {})
    ws=deepcopy(payload.get('_oral_workspace') or {'revision':0,'boards':[],'pending':[],'history':[]})
    group=f'{MODULE.get()}:{mode}:{project.sub_client_id if mode=="sub_client" else project.id if mode=="individual" else client.id}'
    return project,client,storage,payload,ws,group,mode


def rendered(board):
    value=deepcopy(board['statement']);totals={};pending=[]
    for row in value['rows']:
        if not row.get('counted_in_total',True):continue
        if row.get('subtotal') is None:pending.append(row['order_no']+'：金额待补')
        else:totals[row['currency']]=totals.get(row['currency'],Decimal(0))+Decimal(str(row['subtotal']))
    value.update(totals={key:format(amount,'.2f') for key,amount in totals.items()},pending=pending,months=board['months'],month='、'.join(board['months'])+(f' · 第{board["period_number"]}期' if board.get('period_number') else ''),statement_number=board['number'])
    return {**deepcopy(board),'statement':value}


def result(client,ws,group,mode,candidates=None):
    return dict(client_id=str(client.id),client_name=client.client_short_name or client.client_name,revision=ws['revision'],mode=mode,group=group,
                documents=[rendered(board) for board in ws['boards'] if board['group']==group],
                pending=[item for item in ws['pending'] if item['group']==group],
                history=[item for item in ws['history'] if item['group']==group],candidates=candidates or [])


def candidates(db,project,client,mode,months):
    Model=sources.model()
    query=db.query(Model).outerjoin(SubClient,Model.sub_client_id==SubClient.id).filter(func.coalesce(Model.client_id,SubClient.parent_client_id)==client.id)
    if mode=='individual':query=query.filter(Model.id==project.id)
    if mode=='sub_client':query=query.filter(Model.sub_client_id==project.sub_client_id)
    rows=[];projects=query.order_by(Model.order_no).all()
    if MODULE.get()=='interpretation':saved=finance.finance_records(db,projects,True)[0]
    else:
        from business_finance import records
        saved=records(db,MODULE.get(),projects)
    for item in projects:
        row=saved.get(item.id);payload=row.payload if row else {}
        if finance.settlement_mode(payload)!=mode or months and sources.billing_month(item,payload) not in months:continue
        rows.append(sources.context(db,item,row))
    return rows


def store(db,user,client,storage,payload,ws,group,action,before):
    before_payload=deepcopy(payload)
    ws['revision']+=1
    ws['history'].insert(0,dict(id=str(uuid4()),revision=ws['revision'],group=group,action=action,actor_name=user.full_name or user.username,created_at=business_now().isoformat(),before=[deepcopy(board) for board in before['boards'] if board['group']==group],before_pending=[deepcopy(item) for item in before['pending'] if item['group']==group]))
    ws['history']=ws['history'][:50]
    payload['_oral_workspace']=ws
    if storage:
        storage.payload=payload;storage.revision+=1
    else:
        storage=finance.InterpretationCustomerFinance(client_id=client.id,revision=1,payload=payload);db.add(storage);db.flush()
    db.add(finance.InterpretationCustomerFinanceHistory(finance_id=storage.id,revision=storage.revision,actor_id=user.id,actor_name=user.full_name or user.username,before=before_payload,after=deepcopy(payload)))
    db.commit()


def validate(ws,group,mode):
    boards=[board for board in ws['boards'] if board['group']==group and board['status']=='active']
    if mode=='special':return
    occupied=set();projects=set()
    for board in boards:
        slots={(month,board.get('period_number')) for month in board['months']}
        if occupied&slots:raise HTTPException(409,'同月份、同账期只能有一份有效对账单，请先废除冲突账单')
        occupied|=slots
        roots={line['root_id'] for line in board['statement']['rows']}
        if projects&roots:raise HTTPException(409,'项目不能同时在两份有效对账单中，请先在财务主表改为特殊结算')
        projects|=roots
    namespace=group.split(':',1)[0]+':'
    other_projects={line['root_id'] for board in ws['boards'] if board['group'].startswith(namespace) and board['group']!=group and board['status']=='active' for line in board['statement']['rows']}
    if projects&other_projects:raise HTTPException(409,'项目已在其他结算范围的有效对账单中，请先废除原账单或在财务主表调整为特殊结算')


class Write(BaseModel):
    revision:int=Field(ge=0)
    mode:Mode
    action:Literal['generate','new_board','set_status','set_period','merge','remove_projects','restore_project','add_projects','move_projects','schedule','cancel_pending','edit_row','edit_header','restore_version','reorder']
    months:list[str]=Field(default_factory=list,max_length=36)
    period_number:int|None=Field(default=None,ge=1,le=999)
    project_ids:list[UUID]=Field(default_factory=list,max_length=500)
    board_id:str|None=None
    data:dict=Field(default_factory=dict)


@router.get('/project/{target}')
def read(target:UUID,mode:Mode|None=None,months:list[str]|None=Query(None),db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project')
    project,client,_,_,ws,group,mode=context(db,target,mode)
    return result(client,ws,group,mode,candidates(db,project,client,mode,months))


@router.post('/project/{target}')
def write(target:UUID,data:Write,db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project',True)
    import re
    if any(not re.fullmatch(MONTH,month) for month in data.months):raise HTTPException(422,'账单月份无效')
    project,client,storage,payload,ws,group,mode=context(db,target,data.mode,True)
    if data.revision!=ws['revision']:raise HTTPException(409,'对账单已变化，请重新加载')
    before=deepcopy(ws);board=next((item for item in ws['boards'] if item['id']==data.board_id and item['group']==group),None)
    action=data.action;details=data.data
    if action in ('generate','add_projects'):
        months=data.months or ([sources.billing_month(project,sources.record(db,target).payload)] if sources.record(db,target) else [])
        if not months:raise HTTPException(422,'请选择月份')
        available=candidates(db,project,client,mode,months)
        selected={str(uid) for uid in data.project_ids} or {item['id'] for item in available}
        waiting=[item for item in ws['pending'] if item['group']==group and item['month'] in months and item.get('period_number')==data.period_number]
        selected.update(item['project_id'] for item in waiting)
        selected_sources={item['id']:item for item in available}
        for item in waiting:
            entity=db.get(sources.model(),UUID(item['project_id']));record=sources.record(db,entity.id)
            if entity:selected_sources[str(entity.id)]=sources.context(db,entity,record)
        if not selected<=selected_sources.keys():raise HTTPException(422,'请选择当前客户、月份和结算模式范围内的项目')
        if not selected:raise HTTPException(422,'当前范围没有项目')
        if action=='add_projects' and (not board or board['status']!='active'):raise HTTPException(422,'请选择有效目标单据')
        if mode!='special' and action=='generate':
            for old in ws['boards']:
                if old['group']==group and old['status']=='active' and set(old['months'])&set(months) and old.get('period_number')==data.period_number:old['status']='void'
        if action=='generate':
            template=sources.template(db,target,months[0])
            template['rows']=[]
            board=dict(id=str(uuid4()),number=f'IB-{business_now():%y%m%d}-{ws["revision"]+1:03d}',name='、'.join(months)+' 对账单',months=months,period_number=None if mode=='special' else data.period_number,status='active',group=group,mode=mode,statement=template,removed_projects=[])
            ws['boards'].append(board)
        existing={line['root_id'] for line in board['statement']['rows']}
        for uid in sorted(selected):
            if uid in existing:continue
            entity=db.get(sources.model(),UUID(uid));record=sources.record(db,entity.id)
            lines=sources.lines(entity,record.payload if record else {},selected_sources[uid]['payload'].get('settlement',{}).get('tax_basis','legacy'))
            board['statement']['rows'].extend(lines)
        board['months']=sorted(set(board['months'])|set(months))
        ws['pending']=[item for item in ws['pending'] if item not in waiting]
    elif action=='merge':
        ids=set(details.get('board_ids',[]));items=[item for item in ws['boards'] if item['id'] in ids and item['group']==group and item['status']=='active']
        if len(items)<2 or len(items)!=len(ids):raise HTTPException(422,'请选择至少两份有效账单')
        board=deepcopy(items[0]);board.update(id=str(uuid4()),number=f'IB-{business_now():%y%m%d}-{ws["revision"]+1:03d}',months=sorted({month for item in items for month in item['months']}),name='合并月份对账单',removed_projects=[])
        board['statement']['rows']=[deepcopy(line) for item in items for line in item['statement']['rows']]
        for item in items:item['status']='void'
        ws['boards'].append(board)
    elif action=='reorder':
        ids=details.get('board_ids',[]);current=[item for item in ws['boards'] if item['group']==group]
        if set(ids)!={item['id'] for item in current}:raise HTTPException(409,'对账单排序范围已变化')
        mapping={item['id']:item for item in current};ws['boards']=[item for item in ws['boards'] if item['group']!=group]+[mapping[uid] for uid in ids]
    elif action=='restore_version':
        entry=next((item for item in ws['history'] if item['id']==details.get('history_id') and item['group']==group),None)
        if not entry:raise HTTPException(404,'历史版本不存在')
        ws['boards']=[item for item in ws['boards'] if item['group']!=group]+deepcopy(entry['before'])
        if 'before_pending' in entry:ws['pending']=[item for item in ws['pending'] if item['group']!=group]+deepcopy(entry['before_pending'])
    else:
        if not board:raise HTTPException(404,'对账单不存在')
        if board['status']!='active' and action!='set_status':raise HTTPException(409,'请先恢复为有效对账单，再编辑')
        if action=='set_status':
            if details.get('status') not in ('active','void'):raise HTTPException(422,'状态无效')
            board['status']=details['status']
        elif action=='set_period':
            if mode=='special':raise HTTPException(422,'特殊结算不区分期数')
            board['period_number']=data.period_number
        elif action=='new_board':
            period=None
            if mode!='special':
                peers=[item for item in ws['boards'] if item['group']==group and item['status']=='active' and set(item['months'])&set(board['months'])]
                for item in peers:
                    if not item.get('period_number'):item['period_number']=1
                period=max([item.get('period_number') or 1 for item in peers],default=1)+1
            new=deepcopy(board);new.update(id=str(uuid4()),number=f'IB-{business_now():%y%m%d}-{ws["revision"]+1:03d}',period_number=period,removed_projects=[]);new['statement']['rows']=[];ws['boards'].append(new)
        elif action in ('remove_projects','schedule','move_projects'):
            ids={str(uid) for uid in data.project_ids};lines=[line for line in board['statement']['rows'] if line['root_id'] in ids]
            if not lines:raise HTTPException(422,'请选择单内项目')
            ids={line['root_id'] for line in lines}
            if action=='remove_projects':board['removed_projects'].append(dict(id=str(uuid4()),rows=deepcopy(lines),actor_name=user.full_name or user.username,created_at=business_now().isoformat()))
            elif action=='move_projects':
                target_board=next((item for item in ws['boards'] if item['id']==details.get('target_board_id') and item['group']==group and item['status']=='active'),None)
                if not target_board:raise HTTPException(422,'目标对账单无效')
                if {line['root_id'] for line in target_board['statement']['rows']}&ids:raise HTTPException(409,'目标单内已存在所选项目')
                target_board['statement']['rows'].extend(deepcopy(lines))
            else:
                if len(data.months)!=1:raise HTTPException(422,'请选择一个待入账月份')
                ws['pending'].extend(dict(id=str(uuid4()),project_id=uid,month=data.months[0],period_number=data.period_number,group=group,source_board_id=board['id'],rows=[deepcopy(line) for line in lines if line['root_id']==uid]) for uid in ids)
            board['statement']['rows']=[line for line in board['statement']['rows'] if line['root_id'] not in ids]
        elif action=='cancel_pending':
            waiting=[item for item in ws['pending'] if item['id']==details.get('pending_id') and item['source_board_id']==board['id']]
            for item in waiting:board['statement']['rows'].extend(item['rows']);ws['pending'].remove(item)
        elif action=='restore_project':
            entry=next((item for item in board['removed_projects'] if item['id']==details.get('removed_id')),None)
            if not entry:raise HTTPException(404,'移除记录不存在')
            if {line['root_id'] for line in entry['rows']}&{line['root_id'] for line in board['statement']['rows']}:raise HTTPException(409,'本单已有该项目，不能重复恢复')
            board['statement']['rows'].extend(deepcopy(entry['rows']));board['removed_projects'].remove(entry)
        elif action=='edit_row':
            line=next((line for line in board['statement']['rows'] if line['line_id']==details.get('row_id')),None)
            if line is None:raise HTTPException(404,'项目行不存在')
            for key,value in details.get('fields',{}).items():
                if key not in ('project_name','remarks','subtotal'):raise HTTPException(422,'不能修改该字段')
                if key=='subtotal':
                    if value is None:line[key]=None;continue
                    try:value=format(Decimal(str(value)).quantize(Decimal('.01')),'.2f')
                    except Exception:raise HTTPException(422,'金额无效')
                    if not Decimal(value).is_finite():raise HTTPException(422,'金额无效')
                elif not isinstance(value,str) or len(value)>5000:raise HTTPException(422,'文字内容无效')
                line[key]=value
        elif action=='edit_header':
            for key,value in details.items():
                if key not in ('company','title','issue_date','bank_name','account_name','account_number'):raise HTTPException(422,'抬头字段无效')
                if not isinstance(value,str) or len(value)>500:raise HTTPException(422,'抬头内容过长')
                if key in ('bank_name','account_name','account_number'):board['statement'].setdefault('settings',{})[key]=value
                else:board['statement'][key]=value
    if len(ws['boards'])>100:raise HTTPException(422,'当前客户已达100份单据，请先核对历史记录')
    validate(ws,group,mode)
    store(db,user,client,storage,payload,ws,group,action,before)
    return result(client,ws,group,mode)


@router.get('/project/{target}/export/{board_id}')
def export(target:UUID,board_id:str,format:Literal['excel','pdf']='excel',db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project')
    *_,ws,group,mode=context(db,target)
    board=next((item for item in ws['boards'] if item['id']==board_id and item['group'].startswith(MODULE.get()+':')),None)
    if not board:raise HTTPException(404,'单据不存在')
    statement=rendered(board)['statement']
    if format=='pdf':
        from statement_pdf import pdf_bytes
        return Response(pdf_bytes([statement]),media_type='application/pdf')
    from customer_statements import excel_bytes
    return Response(excel_bytes(statement),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
