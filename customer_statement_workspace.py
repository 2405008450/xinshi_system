"""客户对账单独立编排、唯一任务归属、版本审计和恢复；不修改项目收费。"""
import copy
import base64
import json
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO
from uuid import UUID, uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Uuid, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import object_session

from models import Base, Client, TranslationProject
from database import get_db
from routers.auth import require_permission
from annotation_progress_time import business_now, business_datetime
import customer_statements as source
import statement_pending_tasks as pending_tasks
import statement_access as access

router=APIRouter(prefix='/translation-statement-workspaces',tags=['对账单编排'])
read_access=require_permission('projects:read')
write_access=require_permission('projects:write')
MONTH=re.compile(source.MONTH)
ROW_FIELDS={'customer_order_no','received_date','project_name','language_pair','quantity','basis','unit_price','unit_size','unit_label','currency','subtotal','remarks'}
HEADER_FIELDS={'company','title','client_name','client_code','billing_label','issue_date','bank_name','account_name','account_number','stamp_image','tax_included'}


class StatementWorkspace(Base):
    __tablename__='customer_statement_workspace'
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
    revision=Column(Integer,nullable=False,default=0)
    payload=Column(JSON,nullable=False)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class StatementWorkspaceHistory(Base):
    __tablename__='customer_statement_workspace_history'
    id=Column(Uuid,primary_key=True,default=uuid4)
    client_id=Column(Uuid,ForeignKey('customer_statement_workspace.client_id',ondelete='CASCADE'),nullable=False,index=True)
    revision=Column(Integer,nullable=False)
    actor_id=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    actor_name=Column(String(255),nullable=False)
    action=Column(String(100),nullable=False)
    changes=Column(JSON,nullable=False)
    before=Column(JSON,nullable=False)
    after=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class ImportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    project_id:UUID|None=None
    client_id:UUID|None=None
    months:list[str]=Field(min_length=1,max_length=36)
    scope:Literal['project','customer']='customer'
    revision:int=Field(ge=0)
    board_id:str|None=None
    required_only:bool=False
    confirmed:bool=False
    order_ids:list[UUID]|None=Field(default=None,max_length=2000)


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    action:Literal['create_board','delete_boards','edit_board','edit_row','edit_document','sync_customer_notes','rename_board','merge_boards','split_board','move_tasks','schedule_tasks','cancel_pending','reorder_boards','position_board','restore_task','restore_history']
    data:dict
    confirmed:bool=False


def require_ready(db):
    schema=inspect(db.connection())
    if not all(schema.has_table(model.__tablename__) for model in (StatementWorkspace,StatementWorkspaceHistory)):
        raise HTTPException(503,'对账单编排存储尚未初始化')


def empty_payload():return {'boards':[],'tasks':{},'roots':{}}


def workspace(db,client_id,lock=False):
    require_ready(db)
    client=db.query(Client).filter_by(id=client_id)
    if lock:client=client.with_for_update()
    if not client.first():raise HTTPException(404,'客户不存在')
    query=db.query(StatementWorkspace).filter_by(client_id=client_id)
    if lock:query=query.with_for_update().populate_existing()
    return query.first()


def check_revision(row,revision):
    if revision!=(row.revision if row else 0):raise HTTPException(409,'对账单已被其他人修改，请重新加载后操作')


def board_by_id(payload,board_id):
    board=next((item for item in payload['boards'] if item['id']==board_id),None)
    if not board:raise HTTPException(404,'对账单不存在')
    return board


def outline(node):
    return {**{key:node.get(key) for key in ('id','order_no','project_name','language_pair','pricing_mode','explanation')},'children':[outline(child) for child in node['children']]}


def display_rows(payload,board,mode='children'):
    tasks=[task for task in payload['tasks'].values() if task['board_id']==board['id']]
    ledger=[]
    for task in tasks:
        for line in task['rows']:
            if source.is_fixed_statement_row(line):
                line = {**line, 'pricing_mode': 'fixed'}
            ledger.append({**line,'origin_client_id':task.get('origin_client_id'),'origin_client_name':task.get('origin_client_name'),'billing_month':task['month'],'_row_id':line['line_id'],'task_ids':[task['id']]})
    rendered=[]
    for root_id,root in payload['roots'].items():
        rows=[line for line in ledger if line['root_id']==root_id]
        if not rows:continue
        for line in source.statement_display_rows(root,rows,mode):
            origins={(item.get('origin_client_id'),item.get('origin_client_name')) for item in rows if item.get('origin_client_id')}
            if len(origins)==1:
                origin_id,origin_name=next(iter(origins));line={**line,'origin_client_id':origin_id,'origin_client_name':origin_name}
            # 汇总行可覆盖不同任务，不沿用首条任务的身份。
            if line.get('basis','').startswith('订单汇总'):
                line={**line,'_row_id':f"summary:{root_id}:{line['order_no']}:{line['currency']}",
                      'task_ids':list(dict.fromkeys(item['task_id'] for item in rows if item['order_no']==line['order_no'] or item['order_no'].startswith(line['order_no']+'.')))}
                line['billing_month']='、'.join(sorted({item['billing_month'] for item in rows if item['task_id'] in line['task_ids']}))
            rendered.append({**line,**board.get('overrides',{}).get(line['_row_id'],{})})
    return tasks,rendered


def display_data(payload,board,mode='children',issue_date=''):
    tasks,rendered=display_rows(payload,board,mode)
    totals={};pending=[]
    for line in rendered:
        if line.get('counted_in_total',True):
            if line['subtotal'] is None:pending.append(f"{line['order_no']}：金额待补录")
            else:totals[line['currency']]=totals.get(line['currency'],Decimal(0))+Decimal(str(line['subtotal']))
    fields=board['fields'];months=sorted({task['month'] for task in tasks} or set(board.get('billing_months',[])))
    private_settings=source.private_statement_settings_available()
    return dict(company=fields['company'],title=fields['title'],client_name=fields['client_name'],client_code=fields['client_code'],
                month=fields.get('billing_label') or '、'.join(months),issue_date=fields.get('issue_date') or issue_date,months=months,rows=rendered,totals={key:source.money(value) for key,value in totals.items()},pending=pending,
                private_settings_available=private_settings,
                settings={key:fields.get(key,'') for key in source.PAYMENT_ACCOUNT_FIELDS} if private_settings else {},
                stamp_image=(fields.get('stamp_image') or source.default_stamp()) if private_settings else None,tax_included=board['tax_included'])


def board_issue_dates(db,row):
    if not row or db is None:return {}
    missing={board['id'] for board in row.payload['boards'] if not board['fields'].get('issue_date')}
    if not missing:return {}
    result={}
    for after,created_at in db.query(StatementWorkspaceHistory.after,StatementWorkspaceHistory.created_at).filter_by(client_id=row.client_id).order_by(StatementWorkspaceHistory.revision):
        for board in after.get('boards',[]):
            if board['id'] in missing and board['id'] not in result:result[board['id']]=business_datetime(created_at).date().isoformat()
        if missing<=result.keys():break
    return result


def without_private_fields(value):
    if isinstance(value,dict):
        return {key:without_private_fields(item) for key,item in value.items() if key not in source.PRIVATE_STATEMENT_FIELDS}
    if isinstance(value,list):
        return [without_private_fields(item) for item in value]
    return value


def serialize(row,mode='children',user=None,db=None):
    payload=row.payload if row else empty_payload()
    private_settings=source.private_statement_settings_available()
    dates=board_issue_dates(db or (object_session(row) if row else None),row)
    if not private_settings:payload=without_private_fields(payload)
    return {'client_id':str(row.client_id) if row else None,'revision':row.revision if row else 0,'payload':payload,
            'private_settings_available':private_settings,
            'capabilities':access.capabilities(db or object_session(row),user,row.client_id,payload) if row and user else {'edit_content':False,'cross_client':False},
            'pending_tasks':pending_tasks.summaries(payload),
            'documents':[{**board,'statement':display_data(payload,board,mode,dates.get(board['id'],''))} for board in payload['boards']]}


def save(db,user,client_id,row,before,payload,action,changes,commit=True):
    ids=[board['id'] for board in payload['boards']]
    if len(ids)!=len(set(ids)) or not 0<=len(ids)<=12:raise HTTPException(422,'对账单最多12份，编号不能重复')
    if len(payload['tasks'])>10000:raise HTTPException(422,'客户编排最多保留10000项任务，请缩小导入范围')
    if any((task['board_id'] is not None if pending_tasks.pending(task) else task['board_id'] not in ids) or not MONTH.fullmatch(str(task.get('month',''))) or task_id!=task.get('id') for task_id,task in payload['tasks'].items()):raise HTTPException(422,'任务归属或待入账状态无效')
    if access.ready(db):
        keys=set(payload['tasks'])|set(before.get('tasks',{}))
        owners={item.task_id:item for item in db.query(access.StatementTaskOwner).filter(access.StatementTaskOwner.task_id.in_(keys)).with_for_update().all()} if keys else {}
        for task_id in payload['tasks']:
            owner=owners.get(task_id)
            if owner and owner.client_id!=client_id:raise HTTPException(409,'任务已归属其他客户对账单，不能重复纳入或恢复；请使用跨客户调配')
            if not owner:db.add(access.StatementTaskOwner(task_id=task_id,client_id=client_id))
        for task_id in set(before.get('tasks',{}))-set(payload['tasks']):
            if task_id in owners and owners[task_id].client_id==client_id:db.delete(owners[task_id])
    if row is None:row=StatementWorkspace(client_id=client_id,revision=0);db.add(row)
    row.payload=copy.deepcopy(payload);row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'对账单任务归属同时变化，请重新加载')
    db.add(StatementWorkspaceHistory(id=uuid4(),client_id=client_id,revision=row.revision,actor_id=user.id,
        actor_name=user.full_name or user.username or '用户',action=action,changes=changes,before=before,after=copy.deepcopy(payload),created_at=business_now()))
    try:
        if commit:db.commit()
        else:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'对账单同时更新，请重新加载')
    return row


def new_board(payload,template,name):
    if len(payload['boards'])>=12:raise HTTPException(422,'同一客户最多保留12份对账单')
    index=len(payload['boards'])
    fields=template if source.private_statement_settings_available() else without_private_fields(template)
    board={'id':str(uuid4()),'name':name,'fields':copy.deepcopy(fields),'overrides':{},'tax_included':False,'x':(index%3)*980,'y':(index//3)*900}
    board['fields']['issue_date']=business_now().date().isoformat()
    payload['boards'].append(board);return board


def imported_fields(statement):
    return {**{key:statement.get(key,'') for key in ('company','title','client_name','client_code','stamp_image','issue_date')},
            **statement['settings'],'billing_label':''}


@router.get('/project/{project_id}')
def read_project_workspace(project_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    project=source.crud.get_translation_project(db,project_id)
    if not project or project.annotation_migrated_at is not None:raise HTTPException(404,'笔译项目不存在')
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先为项目关联客户')
    row=workspace(db,client.id)
    return {**serialize(row,mode,user=user,db=db),'client_id':str(client.id),'client_name':client.client_name}


@router.get('/{client_id}')
def read_client_workspace(client_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    row=workspace(db,client_id)
    return {**serialize(row,mode,user=user,db=db),'client_id':str(client_id),'client_name':db.get(Client,client_id).client_name}


@router.post('/import')
def import_months(data:ImportRequest,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(write_access)):
    if not data.confirmed:raise HTTPException(422,'请确认后导入对账单')
    months=sorted(set(data.months))
    if not all(MONTH.fullmatch(month) for month in months):raise HTTPException(422,'账单月份格式应为YYYY-MM')
    project_id=data.project_id
    if data.client_id:
        from models import SubClient
        from sqlalchemy import func
        if data.scope!='customer':raise HTTPException(422,'按客户导入时请选择该客户全部项目')
        if not db.get(Client,data.client_id):raise HTTPException(404,'客户不存在')
        project_id=db.query(TranslationProject.id).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==data.client_id,TranslationProject.annotation_migrated_at.is_(None)).order_by(TranslationProject.order_no,TranslationProject.id).limit(1).scalar()
        if project_id is None:raise HTTPException(422,'该客户当前没有可导入的笔译项目')
    if project_id is None:raise HTTPException(422,'请选择客户')
    statements=[source.build_statement(db,project_id,None,month,data.scope,'children') for month in months]
    if data.order_ids is not None:
        from statement_project_preview import build
        if data.client_id is None:raise HTTPException(422,'按所选项目生成时需指定客户')
        allowed={line['task_id'] for month in months for line in build(db,data.client_id,month,data.order_ids)['rows']}
        for statement in statements:statement['rows']=[line for line in statement['rows'] if line['task_id'] in allowed]
    excluded=0
    if data.required_only:
        import translation_customer_type as customer_types
        import translation_document_requirements as documents
        roots={UUID(line['root_id']) for statement in statements for line in statement['rows']}
        projects=db.query(TranslationProject).filter(TranslationProject.id.in_(roots)).all() if roots else []
        customer_types.attach(db,projects);documents.attach(db,projects)
        eligible={str(project.id) for project in projects if project.statement_required}
        excluded=len({line['task_id'] for statement in statements for line in statement['rows'] if line['root_id'] not in eligible})
        for statement in statements:statement['rows']=[line for line in statement['rows'] if line['root_id'] in eligible]
    project=source.crud.get_translation_project(db,project_id)
    client=project.client or project.sub_client.parent_client
    row=workspace(db,client.id,True);check_revision(row,data.revision)
    before=copy.deepcopy(row.payload if row else empty_payload());payload=copy.deepcopy(before)
    if data.board_id:board=board_by_id(payload,data.board_id)
    else:
        matches=[board for board in payload['boards'] if set(months)&(set(board.get('billing_months',[]))|{task['month'] for task in payload['tasks'].values() if task['board_id']==board['id']})]
        if len(matches)>1:raise HTTPException(422,'所选月份有多份对账单，请选择具体的导入目标，待入账任务尚未变更')
        board=matches[0] if matches else new_board(payload,imported_fields(statements[0]),'、'.join(months)+' 对账单')
    board['billing_months']=sorted(set(board.get('billing_months',[]))|set(months))
    if not before['boards']:board['tax_included']=statements[0]['tax_included']
    added=0;existing=0
    for month,statement in zip(months,statements):
        grouped={}
        for line in statement['rows']:grouped.setdefault(line['task_id'],[]).append(line)
        for task_id,lines in grouped.items():
            if task_id in payload['tasks']:existing+=1;continue
            if access.ready(db):
                owner=db.get(access.StatementTaskOwner,task_id)
                if owner and owner.client_id!=client.id:existing+=1;continue
            root_id=lines[0]['root_id']
            if root_id not in payload['roots']:payload['roots'][root_id]=outline(source.finance.read(db,UUID(root_id))['item'])
            original={'rows':copy.deepcopy(lines),'month':month,'board_id':board['id']}
            payload['tasks'][task_id]={'id':task_id,'board_id':board['id'],'month':month,'rows':lines,'original':original}
            added+=1
    accepted=pending_tasks.accept(payload,months,board)
    if data.order_ids is not None and not added and not existing and not accepted:raise HTTPException(422,'当前筛选没有可生成的项目或待入账任务')
    if any(pending_tasks.pending(task) and task['month'] in months for task in payload['tasks'].values()):raise HTTPException(409,'仍有待入账任务未纳入，本次生成已取消，请重新加载')
    row=save(db,user,client.id,row,before,payload,'导入月份',{'months':months,'added_tasks':added,'existing_tasks_kept':existing,'excluded_tasks':excluded,'accepted_pending':accepted})
    return {**serialize(row,mode,user=user,db=db),'imported':added,'existing':existing,'excluded':excluded,'accepted_pending_count':len(accepted)}


def clean_fields(values,allowed):
    if not isinstance(values,dict) or not values or set(values)-allowed:raise HTTPException(422,'含不可修改字段；订单号不可修改')
    if source.PRIVATE_STATEMENT_FIELDS.intersection(values):source.require_private_statement_settings()
    result={}
    for key,value in values.items():
        if key in ('quantity','unit_price','unit_size','subtotal'):
            if value is None or value=='':result[key]=None;continue
            try:number=Decimal(str(value))
            except InvalidOperation:raise HTTPException(422,'金额或数量格式错误')
            if not number.is_finite() or abs(number)>Decimal('99999999999999') or (key!='subtotal' and number<0) or (key=='unit_size' and number<=0):raise HTTPException(422,'金额或数量超出范围')
            result[key]=source.money(number) if key=='subtotal' else str(number)
        elif key=='tax_included':
            if not isinstance(value,bool):raise HTTPException(422,'税口径应为含税或不含税')
            result[key]=value
        elif key=='stamp_image':result[key]=source.clean_stamp(value)
        elif key=='currency':
            if not re.fullmatch(r'[A-Z]{3}',str(value)):raise HTTPException(422,'货币须为三位大写代码')
            result[key]=value
        else:
            if not isinstance(value,str) or len(value)>5000:raise HTTPException(422,'字段内容过长或格式错误')
            if key in ('received_date','issue_date') and value:
                from datetime import date
                try:date.fromisoformat(value)
                except ValueError:raise HTTPException(422,'来稿日期格式错误')
            result[key]=value
    return result


def edit_document(payload,data,mode):
    """整份账单直接编辑：一次事务，逐字段审计，不触及项目表。"""
    board=board_by_id(payload,data.get('board_id'))
    changes={'board_id':board['id'],'board_name':board['name'],'fields':{},'rows':[]}
    if data.get('fields'):
        for key,value in clean_fields(data['fields'],HEADER_FIELDS|{'name'}).items():
            if key=='name' and not value.strip():raise HTTPException(422,'请填写对账单名称')
            target=board if key in ('name','tax_included') else board['fields']
            changes['fields'][key]={'before':target.get(key),'after':value};target[key]=value
    edits=data.get('rows',[])
    if not isinstance(edits,list) or len(edits)>10000:raise HTTPException(422,'任务修改格式错误')
    visible={line['_row_id']:line for line in display_data(payload,board,mode)['rows']}
    seen=set();months={}
    for edit in edits:
        if not isinstance(edit,dict) or not isinstance(edit.get('row_id'),str) or edit['row_id'] in seen:raise HTTPException(422,'任务修改编号无效或重复')
        seen.add(edit['row_id']);line=visible.get(edit['row_id'])
        if line is None:raise HTTPException(409,'任务已变化，请重新加载后编辑')
        values=edit.get('fields')
        if not isinstance(values,dict) or not values:raise HTTPException(422,'请选择修改字段')
        values=dict(values);month=values.pop('billing_month',None)
        if month is not None:
            if not isinstance(month,str) or not MONTH.fullmatch(month):raise HTTPException(422,'账单月份格式应为YYYY-MM')
            for task_id in line['task_ids']:
                if task_id in months and months[task_id]!=month:raise HTTPException(422,'同一任务的各行账单月份必须一致')
                months[task_id]=month
        cleaned=clean_fields(values,ROW_FIELDS) if values else {}
        diff={key:{'before':line.get(key),'after':value} for key,value in cleaned.items()}
        if month is not None:diff['billing_month']={'before':line.get('billing_month'),'after':month}
        if cleaned:
            found=False
            for task in payload['tasks'].values():
                if task['board_id']!=board['id']:continue
                for stored in task['rows']:
                    if stored['line_id']==line['_row_id']:
                        if source.is_fixed_statement_row(stored):stored['pricing_mode']='fixed'
                        stored.update(cleaned);found=True
            if not found:board['overrides'].setdefault(line['_row_id'],{}).update(cleaned)
        changes['rows'].append({'order_no':line['order_no'],'row_id':line['_row_id'],'fields':diff})
    for task_id,month in months.items():payload['tasks'][task_id]['month']=month
    if not changes['fields'] and not changes['rows']:raise HTTPException(422,'没有需要保存的修改')
    return changes


@router.post('/{client_id}/actions')
def action(client_id:UUID,request:ActionRequest,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(write_access)):
    if not request.confirmed:raise HTTPException(422,'请在弹窗确认后应用修改')
    content_action=request.action in ('edit_document','edit_row','edit_board','sync_customer_notes','restore_task','restore_history')
    if content_action:
        preliminary=workspace(db,client_id)
        lock_clients=access.content_clients(client_id,preliminary.payload if preliminary else empty_payload())
        if request.action=='restore_history':
            try:requested_history=UUID(str(request.data.get('history_id','')))
            except ValueError:requested_history=None
            previous=db.query(StatementWorkspaceHistory).filter_by(id=requested_history,client_id=client_id).first() if requested_history else None
            if previous:lock_clients|=access.content_clients(client_id,previous.before)
        db.query(Client).filter(Client.id.in_([UUID(uid) for uid in lock_clients])).order_by(Client.id).with_for_update().all()
    row=workspace(db,client_id,True)
    if row is None:raise HTTPException(404,'请先导入对账单任务')
    check_revision(row,request.revision);before=copy.deepcopy(row.payload);payload=copy.deepcopy(before);data=request.data
    if content_action:
        access.require(db,user,access.content_clients(client_id,payload),'edit_content')
    changes={};label=request.action
    if request.action=='sync_customer_notes':
        board=board_by_id(payload,data.get('board_id'));notes={}
        for task in payload['tasks'].values():
            if task.get('board_id')!=board['id']:continue
            for line in task['rows']:
                root_id=line['root_id']
                if root_id not in notes:
                    note_map={}
                    def collect(node):
                        note_map[node['order_no']]=node.get('customer_explanation') or ''
                        for child in node['children']:collect(child)
                    collect(source.finance.read(db,UUID(root_id))['item']);notes[root_id]=note_map
        edits=[]
        for line in display_data(payload,board,mode)['rows']:
            note=notes.get(line.get('root_id'),{}).get(line['order_no'],'')
            if (line.get('remarks') or '')!=note:edits.append({'row_id':line['_row_id'],'fields':{'remarks':note}})
        if not edits:raise HTTPException(422,'备注已与客户说明一致，无需更新')
        changes=edit_document(payload,{'board_id':board['id'],'rows':edits},mode)
        stored_ids={line['line_id'] for task in payload['tasks'].values() if task.get('board_id')==board['id'] for line in task['rows']}
        for edit in edits:
            if edit['row_id'] in stored_ids:board.get('overrides',{}).get(edit['row_id'],{}).pop('remarks',None)
        label='同步客户说明'
    elif request.action in ('merge_boards','split_board','rename_board'):
        from statement_reorganization import reorganize
        label,changes=reorganize(payload,request.action,data)
    elif request.action=='create_board':
        if not payload['boards']:raise HTTPException(422,'请先选择月份重新生成对账单')
        template=payload['boards'][0]
        name=str(data.get('name','新对账单')).strip()[:100]
        board=new_board(payload,template['fields'],name or '新对账单');board['tax_included']=template['tax_included'];label='新增对账单';changes={'name':board['name']}
    elif request.action=='delete_boards':
        ids=data.get('board_ids')
        if not isinstance(ids,list) or not ids or not all(isinstance(uid,str) for uid in ids) or len(ids)!=len(set(ids)):raise HTTPException(422,'请选择有效且不重复的对账单')
        deleted=[board_by_id(payload,uid) for uid in ids]
        if len(ids)>1 and data.get('confirmation')!='删除':raise HTTPException(422,'批量删除请先输入“删除”确认')
        removed={key:task for key,task in payload['tasks'].items() if task['board_id'] in ids}
        payload['boards']=[board for board in payload['boards'] if board['id'] not in ids]
        payload['tasks']={key:task for key,task in payload['tasks'].items() if key not in removed or task.get('pending_from')}
        requeued=[]
        for key,task in removed.items():
            if task.get('pending_from'):
                task.update(board_id=None,pending=True);requeued.append(key)
        roots={line['root_id'] for task in payload['tasks'].values() for line in task['rows']}
        payload['roots']={key:root for key,root in payload['roots'].items() if key in roots}
        label='删除对账单'
        changes={'returned_to_pending':requeued,'deleted_boards':[{'id':board['id'],'name':board['name'],'tasks':sum(task['board_id']==board['id'] for task in before['tasks'].values())} for board in deleted],
                 'removed_tasks':[{'task_id':key,'order_no':task['rows'][0]['order_no'] if task['rows'] else '', 'month':task['month']} for key,task in removed.items()]}
    elif request.action=='edit_document':
        changes=edit_document(payload,data,mode);label='直接编辑对账单'
    elif request.action=='edit_board':
        board=board_by_id(payload,data.get('board_id'));values=clean_fields(data.get('fields',{}),HEADER_FIELDS|{'name'})
        for key,value in values.items():
            target=board if key in ('name','tax_included') else board['fields'];changes[key]={'before':target.get(key),'after':value};target[key]=value
        label='修改对账单内容'
    elif request.action=='edit_row':
        board=board_by_id(payload,data.get('board_id'));row_id=data.get('row_id')
        visible=display_data(payload,board,mode)['rows'];line=next((line for line in visible if line['_row_id']==row_id),None)
        if not line:raise HTTPException(409,'该任务已变化，请重新加载')
        values=clean_fields(data.get('fields',{}),ROW_FIELDS)
        for key,value in values.items():changes[key]={'before':line.get(key),'after':value}
        found=False
        for task in payload['tasks'].values():
            if task['board_id']!=board['id']:continue
            for stored in task['rows']:
                if stored['line_id']==row_id:
                    if source.is_fixed_statement_row(stored):stored['pricing_mode']='fixed'
                    stored.update(values);found=True
        if not found:board['overrides'].setdefault(row_id,{}).update(values)
        label='修改任务内容';changes={'order_no':line['order_no'],'fields':changes}
    elif request.action in ('schedule_tasks','cancel_pending'):
        ids=data.get('task_ids')
        if not isinstance(ids,list) or not ids or not all(isinstance(uid,str) and uid in payload['tasks'] for uid in ids):raise HTTPException(422,'请选择有效任务')
        ids=list(dict.fromkeys(ids))
        if request.action=='schedule_tasks':
            month=data.get('month')
            if not isinstance(month,str) or not MONTH.fullmatch(month):raise HTTPException(422,'请选择目标账单月份')
            changes=pending_tasks.schedule(payload,ids,month,user);label='调整待入账月份'
        else:changes=pending_tasks.cancel(payload,ids);label='撤销待入账调整'
    elif request.action in ('move_tasks','restore_task'):
        submitted=data.get('task_ids',[])
        if not isinstance(submitted,list) or not all(isinstance(item,str) for item in submitted):raise HTTPException(422,'任务选择格式错误')
        ids=list(dict.fromkeys(submitted))
        if not ids or any(task_id not in payload['tasks'] for task_id in ids):raise HTTPException(422,'请选择有效任务')
        if request.action=='move_tasks':
            target=board_by_id(payload,data.get('board_id'));month=data.get('month')
            if not isinstance(month,str) or not MONTH.fullmatch(month):raise HTTPException(422,'请选择目标账单月份')
        changes=[]
        for task_id in ids:
            task=payload['tasks'][task_id]
            if pending_tasks.pending(task):raise HTTPException(409,'任务正在待入账，请在待入账列表调整或撤销')
            old={'month':task['month'],'board_id':task['board_id'],'board_name':board_by_id(payload,task['board_id'])['name']}
            old_rows=copy.deepcopy(task['rows'])
            if request.action=='restore_task':
                original=task['original']
                if not any(board['id']==original['board_id'] for board in payload['boards']):raise HTTPException(409,'原对账单已不在当前版本，请从修改记录恢复')
                task.update(copy.deepcopy(original))
                for key in ('pending','pending_from','pending_actor','pending_at'):task.pop(key,None)
            else:task.update(board_id=target['id'],month=month)
            # 清除涉及该任务的展示汇总覆盖，防止移动后留下旧金额。
            root_ids={line['root_id'] for line in task['rows']}
            for board in payload['boards']:
                board['overrides']={key:value for key,value in board['overrides'].items() if not any(key.startswith('summary:'+root_id+':') for root_id in root_ids)}
            item={'task_id':task_id,'order_no':task['rows'][0]['order_no'],'before':old,'after':{'month':task['month'],'board_id':task['board_id'],'board_name':board_by_id(payload,task['board_id'])['name']}}
            if request.action=='restore_task':item['content']={'before':old_rows,'after':copy.deepcopy(task['rows'])}
            changes.append(item)
        label='恢复任务原始内容' if request.action=='restore_task' else '调配任务月份及对账单'
    elif request.action=='reorder_boards':
        ids=data.get('board_ids',[])
        if not isinstance(ids,list) or not all(isinstance(uid,str) for uid in ids):raise HTTPException(422,'对账单排列无效')
        if len(ids)!=len(set(ids)) or set(ids)!={board['id'] for board in payload['boards']}:raise HTTPException(422,'对账单排列无效')
        by_id={board['id']:board for board in payload['boards']};payload['boards']=[by_id[uid] for uid in ids];label='调整对账单排列';changes={'before':[board['id'] for board in before['boards']],'after':ids}
    elif request.action=='position_board':
        board=board_by_id(payload,data.get('board_id'))
        positions={}
        for key in ('x','y'):
            value=data.get(key)
            if not isinstance(value,(int,float)) or not 0<=value<=20000:raise HTTPException(422,'拖动位置超出画布范围')
            positions[key]=round(value)
        changes={'before':{key:board.get(key,0) for key in positions},'after':positions};board.update(positions);label='移动对账单位置'
    elif request.action=='restore_history':
        if not isinstance(data.get('history_id'),str):raise HTTPException(422,'修改记录无效')
        try:history_id=UUID(data.get('history_id',''))
        except (ValueError,TypeError):raise HTTPException(422,'修改记录无效')
        history=db.query(StatementWorkspaceHistory).filter_by(id=history_id,client_id=client_id).first()
        if not history or not isinstance(history.before.get('boards'),list):raise HTTPException(422,'该记录无法恢复')
        if history.action=='跨客户对账单调配':raise HTTPException(422,'跨客户操作涉及多方账单，请通过跨客户调配移回；不能单独恢复一方版本')
        payload=copy.deepcopy(history.before)
        if not source.private_statement_settings_available():
            current_fields={board['id']:board['fields'] for board in before['boards']}
            for board in payload['boards']:
                saved_fields=current_fields.get(board['id'],{})
                for key in source.PRIVATE_STATEMENT_FIELDS:
                    if key in saved_fields:board['fields'][key]=saved_fields[key]
                    else:board['fields'].pop(key,None)
        label='恢复历史版本';changes={'restored_before_revision':history.revision}
        access.require(db,user,access.content_clients(client_id,payload),'edit_content')
    row=save(db,user,client_id,row,before,payload,label,changes)
    return serialize(row,mode,user=user,db=db)


@router.get('/{client_id}/history')
def history(client_id:UUID,skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    query=db.query(StatementWorkspaceHistory).filter_by(client_id=client_id)
    private_settings=source.private_statement_settings_available()
    return {'total':query.count(),'items':[{'id':str(row.id),'revision':row.revision,'actor_name':row.actor_name,'action':row.action,'changes':row.changes if private_settings else without_private_fields(row.changes),'created_at':business_datetime(row.created_at).isoformat(),'restorable':row.action!='跨客户对账单调配' and isinstance(row.before.get('boards'),list) and access.allowed_ids(db,user,access.content_clients(client_id,row.before),'edit_content')==access.content_clients(client_id,row.before)} for row in query.order_by(StatementWorkspaceHistory.revision.desc()).offset(skip).limit(limit)]}


@router.get('/{client_id}/history/{history_id}')
def history_entry(client_id:UUID,history_id:UUID,db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    record=db.query(StatementWorkspaceHistory).filter_by(id=history_id,client_id=client_id).first()
    if not record:raise HTTPException(404,'调整记录不存在')
    result=dict(id=str(record.id),revision=record.revision,actor_name=record.actor_name,action=record.action,created_at=business_datetime(record.created_at).isoformat(),changes=record.changes,before=record.before,after=record.after)
    return result if source.private_statement_settings_available() else without_private_fields(result)


@router.get('/{client_id}/excel')
def export(client_id:UUID,revision:int,board_ids:list[str]=Query(...),mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    row=workspace(db,client_id)
    if not row:raise HTTPException(404,'对账单不存在')
    check_revision(row,revision)
    if not 1<=len(board_ids)<=12 or len(set(board_ids))!=len(board_ids):raise HTTPException(422,'请选择1至12份不同的对账单')
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side
    from openpyxl.drawing.image import Image as ExcelImage
    from project_export_excel import _safe_text
    output=Workbook();output.remove(output.active)
    dates=board_issue_dates(db,row)
    for index,uid in enumerate(board_ids):
        board=board_by_id(row.payload,uid);statement=display_data(row.payload,board,mode,dates.get(uid,''))
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有任务")
        target=output.create_sheet(f'对账单{index+1}')
        source.write_excel_sheet(target,statement)
    buffer=BytesIO();output.save(buffer)
    return Response(buffer.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename=customer-statements.xlsx"})


@router.get('/{client_id}/pdf')
def export_pdf(client_id:UUID,revision:int,board_ids:list[str]=Query(...),mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    row=workspace(db,client_id)
    if not row:raise HTTPException(404,'对账单不存在')
    check_revision(row,revision)
    if not 1<=len(board_ids)<=12 or len(set(board_ids))!=len(board_ids):raise HTTPException(422,'请选择1至12份不同的对账单')
    dates=board_issue_dates(db,row);statements=[]
    for uid in board_ids:
        board=board_by_id(row.payload,uid);statement=display_data(row.payload,board,mode,dates.get(uid,''))
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有任务")
        statements.append(statement)
    from statement_pdf import pdf_bytes
    return Response(pdf_bytes(statements),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=customer-statements.pdf'})
