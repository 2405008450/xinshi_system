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
from translation_document_requirements import StatementScope, matches_statement_scope
from invoice_parties import SUBJECTS
from translation_payment_confirmation import PaymentConfirmationWrite
from translation_payment_service import PaymentWrite

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
    settlement_scope:StatementScope|None=None
    period_number:int|None=Field(default=None,ge=1)


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    action:Literal['create_board','add_billing_period','delete_boards','edit_board','edit_row','edit_document','change_company_subject','sync_customer_notes','rename_board','merge_boards','split_board','move_tasks','schedule_tasks','cancel_pending','reorder_boards','position_board','restore_task','restore_history']
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
    period_month=board.get('period_month')
    if period_month and period_month not in months:months=sorted([*months,period_month])
    period_label=billing_period_name(period_month,board['period_number']) if period_month and months==[period_month] else ''
    private_settings=source.private_statement_settings_available()
    return dict(company=fields['company'],title=fields['title'],client_name=fields['client_name'],client_code=fields['client_code'],
                month=fields.get('billing_label') or period_label or '、'.join(months),issue_date=fields.get('issue_date') or issue_date,months=months,rows=rendered,totals={key:source.money(value) for key,value in totals.items()},pending=pending,
                private_settings_available=private_settings,
                settings={key:fields.get(key,'') for key in source.PAYMENT_ACCOUNT_FIELDS} if private_settings else {},
                stamp_image=(fields.get('stamp_image') or source.default_stamp(fields['company'] if fields['company'] in source.COMPANIES else source.COMPANY)) if private_settings else None,tax_included=board['tax_included'])


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


def scoped_root_ids(db, root_ids, scope):
    from translation_document_requirements import attach
    if not root_ids:
        return set()
    projects=db.query(TranslationProject).filter(
        TranslationProject.id.in_([UUID(uid) for uid in root_ids]),
        TranslationProject.annotation_migrated_at.is_(None),
    ).all()
    attach(db,projects)
    return {str(project.id) for project in projects if matches_statement_scope(project,scope)}


def scoped_payload(db, payload, scope):
    if scope is None:
        return payload
    roots = {line['root_id'] for task in payload['tasks'].values() for line in task['rows']}
    allowed = scoped_root_ids(db, roots, scope)
    tasks = {key:task for key,task in payload['tasks'].items()
             if all(line['root_id'] in allowed for line in task['rows'])}
    occupied = {task['board_id'] for task in payload['tasks'].values()}
    visible = {task['board_id'] for task in tasks.values()}
    return {**payload,'tasks':tasks,'roots':{key:root for key,root in payload['roots'].items() if key in allowed},
            'boards':[board for board in payload['boards'] if board['id'] in visible or
                      (board['id'] not in occupied and board.get('settlement_scope') in (None,scope))]}


def period_payload(payload, number, months=None):
    if not number:
        return payload
    boards=[board for board in payload['boards'] if board.get('period_number')==number and
            (months is None or board.get('period_month') in months)]
    ids={board['id'] for board in boards}
    return {**payload,'boards':boards,'tasks':{
        key:task for key,task in payload['tasks'].items() if task['board_id'] in ids
    }}


def invoice_subjects_by_order(db, client_id):
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return {}
    row=db.get(StatementWorkspace,client_id)
    if not row:
        return {}
    boards={}
    for board in row.payload['boards']:
        fields=board['fields']
        key=fields.get('subject_key')
        if key in SUBJECTS and SUBJECTS[key][1]==fields['company']:
            boards[board['id']]=key
    subjects={}
    for task in row.payload['tasks'].values():
        key=boards.get(task['board_id'])
        if key:
            for line in task['rows']:
                subjects.setdefault(line['root_id'],set()).add(key)
    return subjects


def pending_periods(db,payload):
    from translation_document_requirements import TranslationProjectDocuments, ready
    tasks={key:task for key,task in payload['tasks'].items() if pending_tasks.pending(task)}
    if not tasks or not ready(db):
        return {}
    roots={UUID(task['rows'][0]['root_id']) for task in tasks.values()}
    assignments={str(root):(data or {}).get('_billing_period') or {} for root,data in
                 db.query(TranslationProjectDocuments.project_id,TranslationProjectDocuments.quotation_data)
                 .filter(TranslationProjectDocuments.project_id.in_(roots))}
    boards={board['id']:board for board in payload['boards']}
    periods={}
    for key,task in tasks.items():
        assignment=assignments.get(task['rows'][0]['root_id'],{})
        board=boards.get(assignment.get('board_id'),{})
        if task['month']==assignment.get('month')==board.get('period_month') and board.get('period_number'):
            periods[key]=board['period_number']
    return periods


def serialize(row,mode='children',user=None,db=None,settlement_scope=None):
    payload=row.payload if row else empty_payload()
    payload={key:value for key,value in payload.items() if key!='special_payments'}
    payload=scoped_payload(db,payload,settlement_scope)
    private_settings=source.private_statement_settings_available()
    periods=pending_periods(db or object_session(row),payload) if row else {}
    dates=board_issue_dates(db or (object_session(row) if row else None),row)
    if not private_settings:payload=without_private_fields(payload)
    return {'client_id':str(row.client_id) if row else None,'revision':row.revision if row else 0,'payload':payload,
            'private_settings_available':private_settings,
            'capabilities':access.capabilities(db or object_session(row),user,row.client_id,payload) if row and user else {'edit_content':False,'cross_client':False},
            'pending_tasks':[{**task,'period_number':periods.get(task['id'])} for task in pending_tasks.summaries(payload)],
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


def billing_period_name(month, number):
    # Include the year because a customer's workspace can span several years.
    return f'{month[:4]}年{int(month[5:])}月份第{number}期'


def add_billing_period(payload, month, eligible_boards=None):
    if not isinstance(month,str) or not MONTH.fullmatch(month):
        raise HTTPException(422,'请选择有效的账单月份')
    boards=payload['boards']
    task_months={}
    for task in payload['tasks'].values():
        task_months.setdefault(task['board_id'],set()).add(task['month'])
    candidates_for_period = boards if eligible_boards is None else eligible_boards
    periods=sorted((board for board in candidates_for_period if board.get('period_month')==month),
                   key=lambda board:board['period_number'])
    renamed=None
    if periods:
        template=periods[-1]
        number=template['period_number']+1
    else:
        candidates=[board for board in candidates_for_period if not board.get('period_month') and
                    (task_months.get(board['id']) or set(board.get('billing_months',[])))=={month}]
        if len(candidates)!=1:
            raise HTTPException(422,'首次分期需要该月份已有一份独立对账单；请先生成该月对账单或整理现有账单')
        template=candidates[0]
        previous_name=template['name']
        template.update(name=billing_period_name(month,1),period_month=month,period_number=1,billing_months=[month])
        template['fields']['billing_label']=''
        renamed={'board_id':template['id'],'before':previous_name,'after':template['name']}
        number=2
    board=new_board(payload,template['fields'],billing_period_name(month,number))
    board.update(period_month=month,period_number=number,billing_months=[month],tax_included=template['tax_included'])
    board['fields']['billing_label']=''
    return {'month':month,'period_number':number,'board_id':board['id'],'name':board['name'],'renamed':renamed}


def imported_fields(statement):
    return {**{key:statement.get(key,'') for key in ('company','title','client_name','client_code','stamp_image','issue_date')},
            **statement['settings'],'billing_label':''}


def month_boards(payload, month):
    task_months = {}
    for task in payload['tasks'].values():
        task_months.setdefault(task['board_id'], set()).add(task['month'])
    return [board for board in payload['boards'] if (
        board.get('period_month') == month or not board.get('period_month') and
        (task_months.get(board['id']) or set(board.get('billing_months', []))) == {month}
    )]


class BillingPeriodWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    month: str = Field(pattern=source.MONTH)
    board_id: str | None = None
    create_period: bool = False
    revision: int = Field(ge=0)
    version: str


@router.put('/project/{project_id}/billing-period')
def assign_billing_period(project_id: UUID, data: BillingPeriodWrite, db=Depends(get_db), user=Depends(write_access)):
    from translation_document_requirements import TranslationProjectDocuments, payment_method, ready as documents_ready

    if not documents_ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    client_id = source.finance.project_statement_client_id(db, project_id)
    if not client_id:
        raise HTTPException(422, '请先保存项目并关联客户')
    row = workspace(db, client_id, True)
    check_revision(row, data.revision)
    project = db.query(TranslationProject).filter_by(id=project_id, annotation_migrated_at=None).with_for_update().first()
    if not project or source.finance.statement_client_id(project) != client_id:
        raise HTTPException(409, '项目或客户已变化，请重新打开价格与付款')
    project = source.crud.get_translation_project(db, project_id, refresh=True)
    if source.finance.version(project) != data.version:
        raise HTTPException(409, '项目财务已变化，请重新打开价格与付款')
    before = copy.deepcopy(row.payload if row else empty_payload())
    payload = copy.deepcopy(before)
    order_ids = {str(owner.id) for owner in source.finance.hierarchy(project)[0]}
    if access.ready(db) and db.query(access.StatementTaskOwner).filter(
        access.StatementTaskOwner.task_id.in_(order_ids), access.StatementTaskOwner.client_id != client_id,
    ).first():
        raise HTTPException(409, '该订单已有任务调配到其他客户，请先处理跨客户归属')
    scope = 'special' if payment_method(project)=='special' else 'standard'
    candidates = month_boards(scoped_payload(db,payload,scope), data.month)
    created = None
    if data.create_period:
        if not candidates:
            statement = source.build_statement(db, project_id, None, data.month, 'project')
            board = new_board(payload, imported_fields(statement), billing_period_name(data.month, 1))
            board.update(period_month=data.month, period_number=1, billing_months=[data.month],
                         tax_included=statement['tax_included'])
            created = {'board_id': board['id'], 'name': board['name']}
        else:
            created = add_billing_period(payload, data.month, candidates)
            board = board_by_id(payload, created['board_id'])
    else:
        board = next((board for board in candidates if board['id'] == data.board_id), None)
        if not board and (data.board_id or candidates):
            raise HTTPException(422, '请选择该月份的账期')
        if not board:
            statement = source.build_statement(db, project_id, None, data.month, 'project')
            board = new_board(payload, imported_fields(statement), data.month+' 对账单')
            board.update(billing_months=[data.month], tax_included=statement['tax_included'])
    board.setdefault('settlement_scope',scope)
    document = db.get(TranslationProjectDocuments, project_id)
    if document is None:
        document = TranslationProjectDocuments(project_id=project_id, quotation_revision=0)
        db.add(document)
    assignment = {'month': data.month, 'board_id': board['id'], 'number': board.get('period_number')}
    previous = getattr(project, 'billing_period', {})
    document.quotation_data = {**(document.quotation_data or {}), '_billing_period': assignment}
    moment = business_now()
    document.updated_at = moment
    document.updated_by = user.id
    project.updated_at = moment.replace(tzinfo=None)
    for task_id in order_ids & payload['tasks'].keys():
        task = payload['tasks'][task_id]
        task.update(month=data.month, board_id=None if pending_tasks.pending(task) else board['id'])
        pending_tasks.invalidate_overrides(payload, task)
    save(db, user, client_id, row, before, payload, '调整订单账期', {
        'order_no': project.order_no, 'before': previous, 'after': assignment, 'created': created,
    }, commit=False)
    db.info.pop('translation_monthly_tax_projects', None)
    db.info.pop('translation_monthly_tax_modes', None)
    source.finance.confirmations.recheck_after_fee_change(db, project_id, user.id)
    db.commit()
    return source.finance.read(db, project_id)


@router.get('/project/{project_id}')
def read_project_workspace(project_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    project=source.crud.get_translation_project(db,project_id)
    if not project or project.annotation_migrated_at is not None:raise HTTPException(404,'笔译项目不存在')
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先为项目关联客户')
    row=workspace(db,client.id)
    return {**serialize(row,mode,user=user,db=db),'client_id':str(client.id),'client_name':client.client_name}


@router.get('/project/{project_id}/billing-period')
def read_billing_period(project_id: UUID, month: str = Query(pattern=source.MONTH), db=Depends(get_db), user=Depends(read_access)):
    from translation_document_requirements import payment_method
    project = source.crud.get_translation_project(db, project_id)
    if not project:
        raise HTTPException(404, '笔译项目不存在')
    client_id = source.finance.statement_client_id(project)
    if not client_id:
        raise HTTPException(422, '请先关联客户')
    row = workspace(db, client_id)
    payload = row.payload if row else empty_payload()
    scope = 'special' if payment_method(project)=='special' else 'standard'
    boards = month_boards(scoped_payload(db,payload,scope), month)
    assignment = getattr(project, 'billing_period', {})
    current_task = payload['tasks'].get(str(project_id)) or next((
        task for task in payload['tasks'].values() if task['rows'][0]['root_id']==str(project_id)
        and not pending_tasks.pending(task)
    ), None)
    return {
        'revision': row.revision if row else 0,
        'board_id': assignment.get('board_id') or (current_task and current_task['board_id']),
        'can_create': len(payload['boards']) < 12 and (
            len(boards) < 2 or any(board.get('period_number') for board in boards)
        ),
        'boards': [{'id': board['id'], 'name': board['name'], 'number': board.get('period_number')}
                   for board in sorted(boards, key=lambda board: board.get('period_number') or 0)],
    }


@router.get('/{client_id}')
def read_client_workspace(client_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access),settlement_scope:StatementScope|None=None):
    row=workspace(db,client_id)
    return {**serialize(row,mode,user=user,db=db,settlement_scope=settlement_scope),'client_id':str(client_id),'client_name':db.get(Client,client_id).client_name}


class SpecialPaymentWrite(PaymentWrite):
    revision:int=Field(ge=0)
    confirmation:PaymentConfirmationWrite
    version:str=''


def special_payment_key(month,period_number):
    if not MONTH.fullmatch(month):
        raise HTTPException(422,'请选择有效的账单月份')
    return f'{month}:{period_number or 0}'


@router.get('/{client_id}/special-payment/{month}')
def read_special_payment(client_id:UUID,month:str,period_number:int|None=Query(None,ge=1),
                         db=Depends(get_db),user=Depends(read_access)):
    key=special_payment_key(month,period_number)
    row=workspace(db,client_id)
    return (row.payload.get('special_payments',{}).get(key) if row else None) or {
        'revision':0,'confirmation':{},'payments':[],
    }


@router.put('/{client_id}/special-payment/{month}')
def save_special_payment(client_id:UUID,month:str,data:SpecialPaymentWrite,period_number:int|None=Query(None,ge=1),
                         db=Depends(get_db),user=Depends(write_access)):
    key=special_payment_key(month,period_number)
    row=workspace(db,client_id,True)
    projects=source.crud.get_translation_projects(db,limit=None,field_filters={
        'finance_client_ids':{'value':[str(client_id)]},'finance_billing_month':{'value':month},
    })
    if period_number:
        source.finance.attach_monthly_payment_peers(db,projects)
    if not any(matches_statement_scope(project,'special') and
               (period_number is None or project.settlement_period_number==period_number) for project in projects):
        raise HTTPException(422,'这个账期没有特殊结算项目')
    before=copy.deepcopy(row.payload if row else empty_payload())
    payload=copy.deepcopy(before)
    payments=payload.setdefault('special_payments',{})
    previous=payments.get(key,{'revision':0})
    if data.revision!=previous['revision']:
        raise HTTPException(409,'付款情况已更新，请重新加载后编辑')
    confirmation=data.confirmation.model_dump(mode='json',exclude={'revision','clear_details','replace_details'})
    details=data.payments
    if not data.confirmation.is_paid:
        confirmation=PaymentConfirmationWrite().model_dump(mode='json',exclude={'revision','clear_details','replace_details'})
        details=[]
    elif data.confirmation.payment_option=='full':
        if data.confirmation.full_payment_amount is None:
            raise HTTPException(422,'请填写已付全款金额')
        details=[]
    elif data.confirmation.payment_option=='deposit':
        if not details or details[0].stage_type!='deposit' or any(detail.stage_type=='deposit' for detail in details[1:]):
            raise HTTPException(422,'请登记首笔定金，后续可登记中期款和尾款')
        finals=[index for index,detail in enumerate(details) if detail.stage_type=='final']
        if finals and (finals!=[len(details)-1] or any(detail.actual_amount is None for detail in details)):
            raise HTTPException(422,'尾款须为最后一笔，并填写全部实际付款金额')
        if finals:
            confirmation.update(full_payment_source='details',full_payment_amount=str(sum(detail.actual_amount for detail in details)))
    else:
        raise HTTPException(422,'请选择已付定金或已付全款')
    entries=[]
    for index,detail in enumerate(details,1):
        entry=detail.model_dump(mode='json')
        if detail.payment_time:
            entry['payment_time']=business_datetime(detail.payment_time).isoformat()
        entries.append({**entry,'id':str(detail.id or uuid4()),'stage_no':index})
    current={'revision':data.revision+1,'confirmation':confirmation,'payments':entries}
    payments[key]=current
    save(db,user,client_id,row,before,payload,'登记特殊结算付款',{'billing_month':month,'period_number':period_number})
    return current


@router.get('/period-options/{month}')
def period_options(month: str, db=Depends(get_db), user=Depends(read_access),
                   settlement_scope:StatementScope|None=None, client_id:UUID|None=None):
    if not MONTH.fullmatch(month):
        raise HTTPException(422,'请选择有效的账单月份')
    require_ready(db)
    query=db.query(StatementWorkspace.payload)
    if client_id:
        query=query.filter(StatementWorkspace.client_id==client_id)
    numbers={board['period_number'] for (payload,) in query
             if any(board.get('period_month')==month for board in payload['boards'])
             for board in scoped_payload(db,payload,settlement_scope)['boards']
             if board.get('period_month')==month and board.get('period_number')}
    return sorted(numbers)


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
    special=data.settlement_scope=='special'
    statements=[source.build_statement(db,project_id,None,month,data.scope,'children',special=special) for month in months]
    if data.order_ids is not None:
        from statement_project_preview import build
        if data.client_id is None:raise HTTPException(422,'按所选项目生成时需指定客户')
        allowed={line['task_id'] for month in months for line in build(db,data.client_id,month,data.order_ids,special=special)['rows']}
        for statement in statements:statement['rows']=[line for line in statement['rows'] if line['task_id'] in allowed]
    if data.settlement_scope:
        roots={line['root_id'] for statement in statements for line in statement['rows']}
        scoped_roots=scoped_root_ids(db,roots,data.settlement_scope)
        for statement in statements:
            statement['rows']=[line for line in statement['rows'] if line['root_id'] in scoped_roots]
    excluded=0
    if data.required_only:
        excluded=len({line['task_id'] for statement in statements for line in statement['rows'] if not line['statement_required']})
        for statement in statements:
            statement['rows']=[line for line in statement['rows'] if line['statement_required']]
    project=source.crud.get_translation_project(db,project_id)
    client=project.client or project.sub_client.parent_client
    row=workspace(db,client.id,True);check_revision(row,data.revision)
    before=copy.deepcopy(row.payload if row else empty_payload());payload=copy.deepcopy(before)
    scoped = scoped_payload(db,payload,data.settlement_scope)
    if data.period_number:
        period = period_payload(scoped,data.period_number,months)
        targets = period['boards']
        if len(months)!=1 or len(targets)!=1:
            raise HTTPException(422,'未找到唯一对应账期，请在价格与付款中核对账期')
        data=data.model_copy(update={'board_id':targets[0]['id']})
        projects=source.crud.get_translation_projects(db,limit=None,field_filters={
            'finance_client_ids':{'value':[str(client.id)]},'finance_billing_month':{'value':months[0]},
        })
        source.finance.attach_monthly_payment_peers(db,projects)
        allowed={str(project.id) for project in projects if project.settlement_period_number==data.period_number}
        for statement in statements:
            statement['rows']=[line for line in statement['rows'] if line['root_id'] in allowed]
    if data.board_id:board=board_by_id(payload,data.board_id)
    else:
        matches=[board for board in scoped['boards'] if set(months)&(set(board.get('billing_months',[]))|{task['month'] for task in scoped['tasks'].values() if task['board_id']==board['id']})]
        board=matches[0] if len(matches)==1 else None
        if not matches:
            title='特殊结算单' if data.settlement_scope=='special' else '对账单'
            fields={**imported_fields(statements[0]),'title':title}
            board=new_board(payload,fields,'、'.join(months)+' '+title)
            if data.settlement_scope:board['settlement_scope']=data.settlement_scope
    if board and board.get('period_month') and months != [board['period_month']]:
        raise HTTPException(422,'只能将所属月份的订单导入该账期')
    if data.board_id and board not in scoped['boards']:
        raise HTTPException(422,'所选对账单属于另一种结算范围')
    if board and not before['boards']:board['tax_included']=statements[0]['tax_included']
    from translation_document_requirements import TranslationProjectDocuments, ready as documents_ready
    roots = {UUID(line['root_id']) for statement in statements for line in statement['rows']}
    roots.update(UUID(line['root_id']) for task in payload['tasks'].values() if pending_tasks.pending(task)
                 and task['month'] in months for line in task['rows'])
    assignments = {
        str(root_id): (document or {}).get('_billing_period') or {}
        for root_id, document in db.query(TranslationProjectDocuments.project_id, TranslationProjectDocuments.quotation_data)
        .filter(TranslationProjectDocuments.project_id.in_(roots))
    } if roots and documents_ready(db) else {}
    if not board and not any(assignment.get('month') in months for assignment in assignments.values()):
        raise HTTPException(422,'所选月份有多份对账单，请先在价格与付款为订单选择账期')

    def target_board(month, root_id):
        assignment=assignments.get(root_id, {})
        if assignment.get('month') == month:
            assigned=next((candidate for candidate in month_boards(scoped,month)
                           if candidate['id']==assignment.get('board_id')), None)
            if not assigned:
                raise HTTPException(409,'订单选择的账期已变更，请在价格与付款中重新选择')
            return assigned
        if not board:
            raise HTTPException(422,'所选月份有多份对账单，请先在价格与付款为订单选择账期')
        board['billing_months']=sorted(set(board.get('billing_months',[]))|{month})
        return board
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
            target=target_board(month,root_id)
            if root_id not in payload['roots']:payload['roots'][root_id]=outline(source.finance.read(db,UUID(root_id))['item'])
            original={'rows':copy.deepcopy(lines),'month':month,'board_id':target['id']}
            payload['tasks'][task_id]={'id':task_id,'board_id':target['id'],'month':month,'rows':lines,'original':original}
            added+=1
    pending_scope = scoped
    if data.period_number:
        pending_scope = {**scoped,'tasks':{key:task for key,task in scoped['tasks'].items()
                         if assignments.get(task['rows'][0]['root_id'],{}).get('board_id')==data.board_id}}
    accepted=pending_tasks.accept(pending_scope,months,lambda task:target_board(task['month'],task['rows'][0]['root_id']))
    if data.order_ids is not None and not added and not existing and not accepted:raise HTTPException(422,'当前筛选没有可生成的项目或待入账任务')
    if any(pending_tasks.pending(task) and task['month'] in months for task in pending_scope['tasks'].values()):raise HTTPException(409,'仍有待入账任务未纳入，本次生成已取消，请重新加载')
    row=save(db,user,client.id,row,before,payload,'导入月份',{'months':months,'added_tasks':added,'existing_tasks_kept':existing,'excluded_tasks':excluded,'accepted_pending':accepted})
    return {**serialize(row,mode,user=user,db=db,settlement_scope=data.settlement_scope),'imported':added,'existing':existing,'excluded':excluded,'accepted_pending_count':len(accepted)}


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
            if board.get('period_month') and board['period_month']!=month:
                raise HTTPException(422,'跨月任务请通过“调整月份 / 移到另一份”移至目标月份对账单')
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
def action(client_id:UUID,request:ActionRequest,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(write_access),settlement_scope:StatementScope|None=None):
    if not request.confirmed:raise HTTPException(422,'请在弹窗确认后应用修改')
    content_action=request.action in ('edit_document','edit_row','edit_board','change_company_subject','sync_customer_notes','restore_task','restore_history')
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
    if settlement_scope:
        visible = scoped_payload(db,payload,settlement_scope)
        board_ids = set(data.get('board_ids') or [])
        if data.get('board_id'):
            board_ids.add(data['board_id'])
        visible_ids = {board['id'] for board in visible['boards']}
        hidden_board_ids = {task['board_id'] for key,task in payload['tasks'].items() if key not in visible['tasks']}
        if board_ids - visible_ids or set(data.get('task_ids') or []) - visible['tasks'].keys():
            raise HTTPException(422,'请选择当前结算范围内的对账单或任务')
        if request.action in ('delete_boards','merge_boards','edit_document','edit_board','sync_customer_notes') and board_ids & hidden_board_ids:
            raise HTTPException(422,'该账单含另一种结算范围的任务，请通过对账单（备份）处理整份账单')
        if request.action=='restore_history':
            raise HTTPException(422,'请通过对账单（备份）恢复客户的完整历史版本')
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
    elif request.action=='add_billing_period':
        changes=add_billing_period(payload,data.get('month'),visible['boards'] if settlement_scope else None)
        label='新增账期'
    elif request.action=='create_board':
        if not payload['boards']:raise HTTPException(422,'请先选择月份重新生成对账单')
        template=payload['boards'][0]
        name=str(data.get('name','新对账单')).strip()[:100]
        board=new_board(payload,template['fields'],name or '新对账单');board['tax_included']=template['tax_included'];label='新增对账单';changes={'name':board['name']}
        if settlement_scope:board['settlement_scope']=settlement_scope
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
    elif request.action=='change_company_subject':
        source.require_private_statement_settings()
        board=board_by_id(payload,data.get('board_id'))
        subject_key=data.get('subject_key')
        if not isinstance(subject_key,str) or subject_key not in SUBJECTS:
            raise HTTPException(422,'请选择有效的公司主体')
        fields=board['fields']
        company=SUBJECTS[subject_key][1]
        values={'company':company,'subject_key':subject_key}
        settings, _ = source.statement_company_settings(db,subject_key)
        if not settings or not all(getattr(settings,key) for key in source.PAYMENT_ACCOUNT_FIELDS):
            raise HTTPException(422,'请先在「财务管理 → 设置 → 对账单设置 · 笔译」完整维护此主体的收款账户')
        values.update({key:getattr(settings,key) for key in source.PRIVATE_STATEMENT_FIELDS})
        changes={key:{'before':fields.get(key),'after':value} for key,value in values.items() if fields.get(key)!=value}
        if not changes:
            raise HTTPException(422,'本对账单已使用此主体的最新资料')
        fields.update(values)
        label='调整公司主体'
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
            if target.get('period_month') and target['period_month']!=month:
                raise HTTPException(422,'目标账期与所选账单月份不一致')
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
        if 'special_payments' in before:
            payload['special_payments']=before['special_payments']
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
    return serialize(row,mode,user=user,db=db,settlement_scope=settlement_scope)


@router.get('/{client_id}/history')
def history(client_id:UUID,skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    query=db.query(StatementWorkspaceHistory).filter_by(client_id=client_id).filter(
        StatementWorkspaceHistory.action!='登记特殊结算付款')
    private_settings=source.private_statement_settings_available()
    return {'total':query.count(),'items':[{'id':str(row.id),'revision':row.revision,'actor_name':row.actor_name,'action':row.action,'changes':row.changes if private_settings else without_private_fields(row.changes),'created_at':business_datetime(row.created_at).isoformat(),'restorable':row.action!='跨客户对账单调配' and isinstance(row.before.get('boards'),list) and access.allowed_ids(db,user,access.content_clients(client_id,row.before),'edit_content')==access.content_clients(client_id,row.before)} for row in query.order_by(StatementWorkspaceHistory.revision.desc()).offset(skip).limit(limit)]}


@router.get('/{client_id}/history/{history_id}')
def history_entry(client_id:UUID,history_id:UUID,db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    record=db.query(StatementWorkspaceHistory).filter_by(id=history_id,client_id=client_id).first()
    if not record:raise HTTPException(404,'调整记录不存在')
    result=dict(id=str(record.id),revision=record.revision,actor_name=record.actor_name,action=record.action,created_at=business_datetime(record.created_at).isoformat(),changes=record.changes,before=record.before,after=record.after)
    for field in ('before','after'):
        result[field]={key:value for key,value in result[field].items() if key!='special_payments'}
    return result if source.private_statement_settings_available() else without_private_fields(result)


@router.get('/{client_id}/excel')
def export(client_id:UUID,revision:int,board_ids:list[str]=Query(...),mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access),settlement_scope:StatementScope|None=None):
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
    payload=scoped_payload(db,row.payload,settlement_scope)
    for index,uid in enumerate(board_ids):
        board=board_by_id(payload,uid);statement=display_data(payload,board,mode,dates.get(uid,''))
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有任务")
        target=output.create_sheet(f'对账单{index+1}')
        source.write_excel_sheet(target,statement)
    buffer=BytesIO();output.save(buffer)
    return Response(buffer.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename=customer-statements.xlsx"})


@router.get('/{client_id}/pdf')
def export_pdf(client_id:UUID,revision:int,board_ids:list[str]=Query(...),mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access),settlement_scope:StatementScope|None=None):
    row=workspace(db,client_id)
    if not row:raise HTTPException(404,'对账单不存在')
    check_revision(row,revision)
    if not 1<=len(board_ids)<=12 or len(set(board_ids))!=len(board_ids):raise HTTPException(422,'请选择1至12份不同的对账单')
    dates=board_issue_dates(db,row);statements=[]
    payload=scoped_payload(db,row.payload,settlement_scope)
    for uid in board_ids:
        board=board_by_id(payload,uid);statement=display_data(payload,board,mode,dates.get(uid,''))
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有任务")
        statements.append(statement)
    from statement_pdf import pdf_bytes
    return Response(pdf_bytes(statements),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=customer-statements.pdf'})
