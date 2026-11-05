"""跨客户项目合并出账：复用现有工作区、归属约束和审计，项目档案不变。"""
import copy
import re
from decimal import Decimal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from models import Client,TranslationProject,TranslationSubOrder
import statement_access as access

class MergedProjects(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_ids:list[UUID]=Field(min_length=2,max_length=30)
    source_client_ids:list[UUID]|None=Field(default=None,min_length=1,max_length=30)
    target_client_id:UUID
    month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    order_ids:list[UUID]=Field(max_length=2000)
    versions:dict[UUID,int]=Field(default_factory=dict)
    name:str=Field(default='',max_length=100)
    confirmed:bool=False
    manager_ids:list[UUID]=Field(default_factory=list,max_length=2000)
    only_mine:bool=False
    client_manager:str|None=None

def prepare(db,user,data):
    from statement_project_preview import build
    from customer_statement_workspace import workspace
    from statement_customer_groups import project_query
    from finance_manager_scope import manager_fields
    ids=set(data.client_ids)
    if len(ids)!=len(data.client_ids) or data.target_client_id not in ids:raise HTTPException(422,'请选择不重复的客户，并从中选择账单归属客户')
    active_clients=set(data.source_client_ids or data.client_ids)
    if not active_clients<=ids:raise HTTPException(422,'客户筛选超出合并范围')
    access.require(db,user,ids,'cross_client')
    clients={row.id:row for row in db.query(Client).filter(Client.id.in_(ids)).all()}
    if set(clients)!=ids:raise HTTPException(422,'所选客户不存在')
    orders=set(data.order_ids)
    roots=db.query(TranslationProject).filter(TranslationProject.id.in_(orders)).all()
    children=db.query(TranslationSubOrder).filter(TranslationSubOrder.id.in_(orders)).all()
    owners={row.id:row for row in [*roots,*children]}
    if set(owners)!=orders:raise HTTPException(422,'所选项目已变化，请重新加载')
    root_ids={row.id if isinstance(row,TranslationProject) else row.parent_project_id for row in owners.values()}
    scope=manager_fields(db,user,data.manager_ids,data.only_mine,data.client_manager)
    allowed={row.id for row in project_query(db,None,scope).filter(TranslationProject.id.in_(root_ids)).all()} if root_ids else set()
    if allowed!=root_ids:raise HTTPException(422,'所选项目已不属于当前客户经理筛选范围，请重新加载')
    selected={uid:[] for uid in ids}
    for key,row in owners.items():
        root=row if isinstance(row,TranslationProject) else db.get(TranslationProject,row.parent_project_id)
        client=root.client or (root.sub_client.parent_client if root.sub_client else None)
        if not client or client.id not in active_clients:raise HTTPException(422,'所选项目不属于合并客户筛选范围')
        selected[client.id].append(key)
    parts=[]
    for uid in data.client_ids:
        part=build(db,uid,data.month,selected[uid],'children')
        if uid not in active_clients:part['rows']=[]
        for line in part['rows']:
            line['origin_client_id']=str(uid);line['origin_client_name']=clients[uid].client_short_name or clients[uid].client_name
        parts.append(part)
    taxes={part['tax_included'] for part in parts if part['rows']}
    if len(taxes)>1:raise HTTPException(422,'所选客户的含税／不含税口径不同，请先在对账单设置中统一口径后合并')
    result=copy.deepcopy(parts[data.client_ids.index(data.target_client_id)])
    result.update(client_name=clients[data.target_client_id].client_name,client_code=clients[data.target_client_id].client_code or '')
    if taxes:result['tax_included']=next(iter(taxes))
    lines={};existing=set();waiting={}
    workspaces={uid:workspace(db,uid) for uid in ids}
    for uid,row in workspaces.items():
        if uid not in active_clients:continue
        for key,task in (row.payload.get('tasks',{}) if row else {}).items():
            if task.get('pending') and task['month']==data.month:waiting[key]=(uid,task)
    if scope and waiting:
        pending_roots={UUID(line['root_id']) for _,task in waiting.values() for line in task['rows']}
        pending_allowed={str(row.id) for row in project_query(db,None,scope).filter(TranslationProject.id.in_(pending_roots)).all()}
        waiting={key:item for key,item in waiting.items() if all(line['root_id'] in pending_allowed for line in item[1]['rows'])}
    access.require(db,user,{task.get('origin_client_id',str(uid)) for uid,task in waiting.values()},'cross_client')
    for part in parts:
        for line in part['rows']:
            key=line['task_id'];owner=db.get(access.StatementTaskOwner,key) if access.ready(db) else None
            if owner and key not in waiting:existing.add(key);continue
            if key in waiting:
                uid,task=waiting[key]
                source=next((item for item in task['rows'] if item['line_id']==line['line_id']),line)
                line={**line,'origin_client_id':task.get('origin_client_id',str(uid)),'origin_client_name':task.get('origin_client_name') or clients[uid].client_short_name or clients[uid].client_name,**source}
            lines[line['line_id']]=line
    result['rows']=list(lines.values());result['pending']=[];sums={}
    for line in result['rows']:
        if line['subtotal'] is None:result['pending'].append(f"{line['order_no']}：金额待补录")
        elif line.get('counted_in_total',True):sums[line['currency']]=sums.get(line['currency'],Decimal(0))+Decimal(str(line['subtotal']))
    result['totals']={key:f'{value:.2f}' for key,value in sums.items()}
    return dict(statement=result,existing_count=len(existing),versions={str(uid):row.revision if row else 0 for uid,row in workspaces.items()}),workspaces,waiting

def generate(db,user,data):
    from customer_statement_workspace import workspace,check_revision,empty_payload,new_board,imported_fields,outline,save,serialize
    import customer_statements as source
    if not data.confirmed or not data.name.strip():raise HTTPException(422,'请填写对账单名称并确认生成')
    if set(data.versions)!=set(data.client_ids):raise HTTPException(422,'请先预览，确认各客户账单版本')
    try:
        db.query(Client).filter(Client.id.in_(data.client_ids)).order_by(Client.id).with_for_update().all()
        for uid in data.client_ids:check_revision(workspace(db,uid,True),data.versions[uid])
        preview,rows,waiting=prepare(db,user,data);statement=preview['statement']
        if not statement['rows']:raise HTTPException(422,'当前项目均已入账或没有可生成内容，请查看已有对账单')
        before={uid:copy.deepcopy(row.payload if row else empty_payload()) for uid,row in rows.items()};payloads=copy.deepcopy(before)
        target=payloads[data.target_client_id];board=new_board(target,imported_fields(statement),data.name.strip());board['tax_included']=statement['tax_included'];board['billing_months']=[data.month]
        grouped={}
        for line in statement['rows']:grouped.setdefault(line['task_id'],[]).append(line)
        # 待入账转移和最终唯一归属在同一事务内完成。
        pending_ids=set(grouped)&set(waiting)
        if pending_ids and access.ready(db):db.query(access.StatementTaskOwner).filter(access.StatementTaskOwner.task_id.in_(pending_ids)).delete(synchronize_session=False);db.flush()
        changed={data.target_client_id};moved=[]
        for key,lines in grouped.items():
            origin=lines[0]['origin_client_id'];origin_name=lines[0]['origin_client_name']
            if key in waiting:
                uid,task=waiting[key];task=copy.deepcopy(task);payloads[uid]['tasks'].pop(key);changed.add(uid)
            else:task={'id':key,'original':{'rows':copy.deepcopy(lines),'month':data.month,'board_id':board['id']}}
            task.update(board_id=board['id'],month=data.month,rows=lines,origin_client_id=origin,origin_client_name=origin_name,pending=False)
            target['tasks'][key]=task
            for line in lines:
                root=line['root_id']
                if root not in target['roots']:target['roots'][root]=outline(source.finance.read(db,UUID(root))['item'])
            moved.append({'order_no':lines[0]['order_no'],'origin_client_name':origin_name})
        for uid in sorted(changed,key=str):
            payload=payloads[uid]
            row=save(db,user,uid,rows[uid],before[uid],payload,'合并客户项目生成对账单',{'board_name':board['name'],'target_client_name':statement['client_name'],'month':data.month,'tasks':moved,'existing_tasks_kept':preview['existing_count']},commit=False)
            if uid==data.target_client_id:target_row=row
        db.commit()
        return {**serialize(target_row,user=user,db=db),'target_board_id':board['id'],'imported':len(grouped),'existing':preview['existing_count']}
    except Exception:
        db.rollback();raise
