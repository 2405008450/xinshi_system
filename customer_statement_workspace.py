"""客户对账单独立编排、唯一项目归属、版本审计和恢复；不修改项目收费。"""
import copy
import base64
import json
import hashlib
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
from routers.auth import require_permission,require_any_permission
from annotation_progress_time import business_now, business_datetime
import customer_statements as source
import statement_pending_tasks as pending_tasks
import statement_access as access
from translation_document_requirements import StatementScope, matches_statement_scope
from invoice_parties import SUBJECTS
from translation_payment_confirmation import PaymentConfirmationWrite
from translation_payment_service import PaymentWrite
import translation_statement_number as statement_number
import statement_document_status as document_status
import statement_customer_notes as statement_notes

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
    sub_client_id:UUID|None=None
    months:list[str]=Field(min_length=1,max_length=36)
    scope:Literal['project','customer']='customer'
    revision:int=Field(ge=0)
    board_id:str|None=None
    required_only:bool=False
    confirmed:bool=False
    order_ids:list[UUID]|None=Field(default=None,max_length=2000)
    settlement_scope:StatementScope|None=None
    period_number:int|None=Field(default=None,ge=1)


def generation_key(data):
    selection = {
        'months':sorted(set(data.months)), 'scope':data.scope,
        'project_id':str(data.project_id) if data.project_id and not data.client_id else None,
        'order_ids':sorted({str(uid) for uid in data.order_ids}) if data.order_ids is not None else None,
        'period_number':data.period_number,'settlement_scope':data.settlement_scope,
        'required_only':data.required_only,'board_id':data.board_id,
    }
    if data.sub_client_id:
        selection['sub_client_id']=str(data.sub_client_id)
    return hashlib.sha256(json.dumps(selection,sort_keys=True).encode()).hexdigest()


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    action:Literal['set_special_invoice','remove_special_projects','restore_special_projects','set_board_period','set_historical_status','edit_customer_note','accept_pending','set_board_status','create_board','add_billing_period','delete_boards','edit_board','edit_row','edit_document','change_company_subject','sync_customer_notes','rename_board','merge_boards','split_board','move_tasks','schedule_tasks','cancel_pending','reorder_boards','position_board','restore_task','restore_history']
    data:dict
    confirmed:bool=False


class PendingPeriodPreview(BaseModel):
    month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    task_ids:list[str]=Field(min_length=1)


class SpecialStatementInvoiceWrite(BaseModel):
    revision:int=Field(ge=1)
    status:Literal['unissued','partial','issued']='unissued'
    proofs:str=Field(default='',max_length=20000)
    receipt_proofs:str=Field(default='',max_length=20000)
    subject_key:Literal['guangzhou','shenzhen','shanghai']|None=None


class CollectionTermsWrite(BaseModel):
    revision:int=Field(ge=0)
    value:str=Field(max_length=300)


class ProjectCoverageRequest(BaseModel):
    months:list[str]=Field(min_length=1,max_length=36)
    period_number:int|None=Field(default=None,ge=1)
    sub_client_id:UUID|None=None
    manager_ids:list[UUID]=Field(default_factory=list,max_length=2000)
    only_mine:bool=False
    client_manager:str|None=None


class HistoricalStatusRequest(BaseModel):
    version_id:str
    board_id:str
    status:Literal['active','void']


def require_ready(db):
    schema=inspect(db.connection())
    if not all(schema.has_table(model.__tablename__) for model in (StatementWorkspace,StatementWorkspaceHistory)):
        raise HTTPException(503,'对账单编排存储尚未初始化')


def empty_payload():return {'boards':[],'tasks':{},'roots':{}}


def workspace(db,client_id,lock=False):
    require_ready(db)
    client=db.query(Client.id).filter(Client.id==client_id)
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


def restore_direction_metadata(root, rows):
    from translation_direction_service import stored_directions

    parents = {}
    names = {}
    def visit(node):
        children = node['children']
        names[node['order_no']] = node.get('project_name')
        pairs = {pair.casefold() for pair in stored_directions(node.get('language_pair'))}
        name = (node.get('project_name') or '').strip().casefold()
        if name and len(pairs)>1 and all(
            (child.get('project_name') or '').strip().casefold()==name
            and len(directions := stored_directions(child.get('language_pair')))==1
            and directions[0].casefold() in pairs for child in children
        ):
            parents.update({child['order_no']:node for child in children})
        for child in children:
            visit(child)
    visit(root)
    for line in rows:
        if 'direction_parent_no' not in line and (parent := parents.get(line['order_no'])):
            line['direction_parent_no'] = parent['order_no']
        if line.get('direction_parent_no') and not line.get('direction_parent_name'):
            line['direction_parent_name'] = names.get(line['direction_parent_no'])


def display_rows(payload,board,mode='children',*,group_directions=True):
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
        if group_directions and any('direction_parent_no' not in line or
                                    line['direction_parent_no'] and not line.get('direction_parent_name') for line in rows):
            restore_direction_metadata(root, rows)
        for line in source.statement_display_rows(root,rows,mode):
            origins={(item.get('origin_client_id'),item.get('origin_client_name')) for item in rows if item.get('origin_client_id')}
            if len(origins)==1:
                origin_id,origin_name=next(iter(origins));line={**line,'origin_client_id':origin_id,'origin_client_name':origin_name}
            # 汇总行可覆盖不同项目，不沿用首条项目的身份。
            if line.get('basis','').startswith('订单汇总'):
                line={**line,'_row_id':f"summary:{root_id}:{line['order_no']}:{line['currency']}",
                      'task_ids':list(dict.fromkeys(item['task_id'] for item in rows if item['order_no']==line['order_no'] or item['order_no'].startswith(line['order_no']+'.')))}
                line['billing_month']='、'.join(sorted({item['billing_month'] for item in rows if item['task_id'] in line['task_ids']}))
            displayed={**line,**board.get('overrides',{}).get(line['_row_id'],{})}
            if displayed.get('ordinary_parent_reference'):displayed.update(unit_price=None,subtotal=None,quantity=None,counted_in_total=False)
            rendered.append(displayed)
    return tasks,source.direction_statement_rows(rendered,include_members=True) if group_directions else rendered


def display_data(payload,board,mode='children',issue_date='',*,group_directions=True):
    tasks,rendered=display_rows(payload,board,mode,group_directions=group_directions)
    totals={};pending=[]
    for line in rendered:
        if line.get('counted_in_total',True):
            if line['subtotal'] is None:pending.append(f"{line['order_no']}：金额待补录")
            else:totals[line['currency']]=totals.get(line['currency'],Decimal(0))+Decimal(str(line['subtotal']))
    fields=board['fields'];months=sorted({task['month'] for task in tasks} or set(board.get('billing_months',[])))
    if document_status.number(board):months=sorted(set(months)|set(board.get('billing_months',[])))
    period_month=board.get('period_month')
    if period_month and period_month not in months:months=sorted([*months,period_month])
    number=document_status.number(board) if board.get('settlement_scope')!='special' else None
    period_label=(billing_period_name(months[0],number) if len(months)==1 else f"{'、'.join(months)} · 第 {number} 期") if number else ''
    private_settings=source.private_statement_settings_available()
    subject_key=next((key for key,(_,company) in SUBJECTS.items() if company==fields['company']),None)
    return dict(company=fields['company'],title='对账单' if fields['title']=='特殊结算单' else fields['title'],client_name=fields['client_name'],client_code=fields['client_code'],
                subject_key=subject_key,
                sub_client_name=board.get('sub_client_name'),sub_client_code=board.get('sub_client_code'),
                month=period_label or fields.get('billing_label') or '、'.join(months),issue_date=fields.get('issue_date') or issue_date,months=months,rows=rendered,totals={key:source.money(value) for key,value in totals.items()},pending=pending,
                private_settings_available=private_settings,
                settings={key:fields.get(key,'') for key in source.PAYMENT_ACCOUNT_FIELDS} if private_settings else {},
                stamp_image=(fields.get('stamp_image') or source.default_stamp(fields['company'] if fields['company'] in source.COMPANIES else source.COMPANY)) if private_settings else None,tax_included=board['tax_included'])


def board_issue_dates(db,row):
    if not row or db is None:return {}
    missing={board['id'] for board in row.payload['boards'] if not board['fields'].get('issue_date')}
    if not missing:return {}
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy import JSON,column,true,func
        # 历史 boards 也含印章等大字段；在库内按账单 ID 求首次出现时间，只返回 ID 和日期。
        boards=func.json_array_elements(StatementWorkspaceHistory.after['boards']).table_valued(column('value',JSON)).alias('history_boards')
        board_id=boards.c.value['id'].as_string()
        dates=db.query(board_id,func.min(StatementWorkspaceHistory.created_at)).select_from(
            StatementWorkspaceHistory).join(boards,true()).filter(
                StatementWorkspaceHistory.client_id==row.client_id,board_id.in_(missing)).group_by(board_id)
        return {key:business_datetime(created_at).date().isoformat() for key,created_at in dates}
    result={}
    # 只取开具日期所需的账单元数据，不能为此下载每个历史版本的全部订单快照。
    for boards,created_at in db.query(StatementWorkspaceHistory.after['boards'],StatementWorkspaceHistory.created_at).filter(StatementWorkspaceHistory.client_id==row.client_id).order_by(StatementWorkspaceHistory.revision):
        for board in boards or []:
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
    boards=[board for board in payload['boards'] if board.get('status')!='void' and (board.get('period_number') or board.get('status_period_number'))==number and
            (months is None or set(document_status.months(payload,board)) & set(months))]
    ids={board['id'] for board in boards}
    return {**payload,'boards':boards,'tasks':{
        key:task for key,task in payload['tasks'].items() if task['board_id'] in ids
    }}


def preview_statement_number(db, client_id, months, rows, *, period_number=None, settlement_scope=None):
    if not statement_number.ready(db) or not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return None
    workspace_row = db.get(StatementWorkspace, client_id)
    if not workspace_row:
        return None
    payload = scoped_payload(db, workspace_row.payload, settlement_scope)
    board_months = {}
    for task in payload['tasks'].values():
        board_months.setdefault(task['board_id'], set()).add(task['month'])
    target_months = set(months)
    candidates = {
        board['id'] for board in period_payload(payload, period_number, months)['boards']
        if target_months <= (board_months.get(board['id'], set()) |
                             set(board.get('billing_months', [])) | {board.get('period_month')})
    }
    task_ids = {task_id for row in rows for task_id in row.get('task_ids', [row['task_id']])}
    assigned = {task['board_id'] for task_id in task_ids if (task := payload['tasks'].get(task_id))
                and task['board_id']}
    if assigned:
        if not assigned <= candidates:
            return None
        if all(payload['tasks'].get(task_id, {}).get('board_id') for task_id in task_ids):
            candidates = assigned
        elif candidates != assigned:
            return None
    if len(candidates) != 1:
        return None
    return statement_number.numbers(db, client_id).get(next(iter(candidates)))


def invoice_subjects_by_order(db, client_id, *, special=False):
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return {}
    row=db.get(StatementWorkspace,client_id)
    if not row:
        return {}
    boards={}
    payload = scoped_payload(db, row.payload, 'special') if special else row.payload
    for board in payload['boards']:
        fields=board['fields']
        key=fields.get('subject_key')
        if key in SUBJECTS and SUBJECTS[key][1]==fields['company']:
            boards[board['id']]=key
    subjects={}
    for task in payload['tasks'].values():
        key=boards.get(task['board_id'])
        if key:
            for line in task['rows']:
                subjects.setdefault(line['root_id'],set()).add(key)
    return subjects


def project_billing_assignments(db, roots):
    from translation_document_requirements import TranslationProjectDocuments, ready
    if not roots or not ready(db):
        return {}
    return {str(root):(data or {}).get('_billing_period') or {} for root,data in
            db.query(TranslationProjectDocuments.project_id,TranslationProjectDocuments.quotation_data)
            .filter(TranslationProjectDocuments.project_id.in_(roots))}


def pending_periods(db,payload):
    tasks={key:task for key,task in payload['tasks'].items() if pending_tasks.pending(task)}
    roots={UUID(task['rows'][0]['root_id']) for task in tasks.values()}
    assignments=project_billing_assignments(db,roots)
    boards={board['id']:board for board in payload['boards']}
    periods={}
    for key,task in tasks.items():
        if task.get('pending_target_board_id'):
            periods[key]=boards.get(task['pending_target_board_id'],{}).get('period_number')
            continue
        assignment=assignments.get(task['rows'][0]['root_id'],{})
        board=boards.get(assignment.get('board_id'),{})
        if task['month']==assignment.get('month')==board.get('period_month') and board.get('period_number'):
            periods[key]=board['period_number']
    return periods


def serialize(row,mode='children',user=None,db=None,settlement_scope=None):
    payload=copy.deepcopy(row.payload) if row else empty_payload()
    document_status.normalize(payload)
    payload={key:value for key,value in payload.items() if key!='special_payments'}
    payload=scoped_payload(db,payload,settlement_scope)
    statement_notes.refresh(db or (object_session(row) if row else None),payload)
    private_settings=source.private_statement_settings_available()
    periods=pending_periods(db or object_session(row),payload) if row else {}
    dates=board_issue_dates(db or (object_session(row) if row else None),row)
    numbers=statement_number.numbers(db or object_session(row),row.client_id) if row else {}
    if not private_settings:payload=without_private_fields(payload)
    return {'client_id':str(row.client_id) if row else None,'revision':row.revision if row else 0,'payload':payload,
            'private_settings_available':private_settings,
            'capabilities':access.capabilities(db or object_session(row),user,row.client_id,payload) if row and user else {'edit_content':False,'cross_client':False},
            'pending_tasks':[{**task,'period_number':periods.get(task['id'])} for task in pending_tasks.summaries(payload)],
            'documents':[{**board,'period_number':board.get('period_number') or board.get('status_period_number'),'period_month':board.get('period_month') or board.get('status_period_month'),'name':board['name'].replace('特殊结算单','对账单'),'statement':{**display_data(payload,board,mode,dates.get(board['id'],'')),
                                                'statement_number':numbers.get(board['id'])}} for board in payload['boards']]}


def save(db,user,client_id,row,before,payload,action,changes,commit=True,*,generation=None):
    history_uid=uuid4()
    status_changes=document_status.normalize(payload)
    from statement_project_uniqueness import validate as validate_project_membership
    validate_project_membership(db,client_id,payload)
    if status_changes:changes={**(changes if isinstance(changes,dict) else {'items':changes}),'status_changes':status_changes}
    old_boards={board['id']:board for board in before['boards']}
    current_boards={board['id']:board for board in payload['boards']}
    archived=list(changes.get('archive',{}).get('documents',[])) if isinstance(changes,dict) else []
    archive_before=None;archive_payload=None
    for uid,board in {**old_boards,**current_boards}.items():
        removed=uid not in current_boards
        void=board.get('status')=='void' and not board.get('archived_revision')
        if not removed and not void:continue
        if removed:
            if archive_before is None:
                archive_before=copy.deepcopy(before);statement_notes.refresh(db,archive_before)
            snapshot=archive_before
        else:
            if archive_payload is None:
                archive_payload=copy.deepcopy(payload)
                for item in archive_payload['boards']:
                    if item.get('status')=='void' and not item.get('archived_revision'):item['status']='active'
                statement_notes.refresh(db,archive_payload)
            snapshot=archive_payload
        snapshot_board=next(item for item in snapshot['boards'] if item['id']==uid)
        archived.append({'id':uid,'name':board['name'],'status':'void','reason':'删除对账单' if removed else action,
            'settlement_scope':board.get('settlement_scope'),
            'statement':display_data(snapshot,snapshot_board),'period_number':board.get('period_number') or board.get('status_period_number')})
        if not removed:board['archived_revision']=(row.revision if row else 0)+1
    if archived:
        numbers=statement_number.numbers(db,client_id) if statement_number.ready(db) else {}
        for board in archived:board['statement']['statement_number']=numbers.get(board['id'])
        changes={**(changes if isinstance(changes,dict) else {'items':changes}),'archive':{'documents':archived,'scopes':sorted({board.get('settlement_scope') or 'standard' for board in archived}),'months':sorted({month for board in archived for month in board['statement']['months']}),
            'orders':sorted({line['order_no'] for board in archived for line in board['statement']['rows']})}}
    from statement_subject_sync import apply_defaults
    apply_defaults(db,payload)
    ids=[board['id'] for board in payload['boards']]
    if len(ids)!=len(set(ids)) or not 0<=len(ids)<=12:raise HTTPException(422,'对账单最多12份，编号不能重复')
    if len(payload['tasks'])>10000:raise HTTPException(422,'客户编排最多保留10000项项目，请缩小导入范围')
    if any((task['board_id'] is not None if pending_tasks.pending(task) else task['board_id'] not in ids) or not MONTH.fullmatch(str(task.get('month',''))) or task_id!=task.get('id') for task_id,task in payload['tasks'].items()):raise HTTPException(422,'项目归属或待入账状态无效')
    if access.ready(db):
        keys=set(payload['tasks'])|set(before.get('tasks',{}))
        owners={item.task_id:item for item in db.query(access.StatementTaskOwner).filter(access.StatementTaskOwner.task_id.in_(keys)).with_for_update().all()} if keys else {}
        for task_id in payload['tasks']:
            owner=owners.get(task_id)
            if owner and owner.client_id!=client_id:raise HTTPException(409,'项目已归属其他客户对账单，不能重复纳入或恢复；请使用跨客户调配')
            if not owner:db.add(access.StatementTaskOwner(task_id=task_id,client_id=client_id))
        for task_id in set(before.get('tasks',{}))-set(payload['tasks']):
            if task_id in owners and owners[task_id].client_id==client_id:db.delete(owners[task_id])
    if statement_number.ready(db):
        boards={board['id']:board for board in [*before['boards'],*payload['boards']]}
        dates={}
        existing_numbers=statement_number.numbers(db,client_id)
        if row and any(board['id'] not in existing_numbers for board in before['boards']):
            historical,dates=statement_number.historical_boards(db,client_id)
            for key in boards.keys() & historical.keys():
                if historical[key].get('number_parent_id'):
                    boards[key]={**boards[key],'number_parent_id':historical[key]['number_parent_id']}
            for board in before['boards']:
                dates.setdefault(board['id'],row.updated_at)
        statement_number.issue(db,client_id,boards.values(),dates)
    if generation is not None:
        data, mode, selected = generation
        generation_payload = {**payload,'tasks':selected}
        numbers = statement_number.numbers(db,client_id)
        board_ids = {task['board_id'] for task in selected.values()}
        for board in payload['boards']:
            if board['id'] in board_ids and board.get('status')!='void' and not board.get('active_history_id'):board['active_history_id']=str(history_uid)
        documents = [{
            'id':board['id'], 'name':board['name'],
            'statement':{**display_data(generation_payload,{**board,'overrides':{}},mode),
                         'statement_number':numbers.get(board['id'])},
        } for board in payload['boards'] if board['id'] in board_ids]
        orders = sorted({line['order_no'] for task in selected.values() for line in task['rows']})
        changes = {**changes,'generation':{
            'key':generation_key(data),'settlement_scope':data.settlement_scope or '',
            'period_number':data.period_number,'months':sorted(set(data.months)),
            'orders':orders,'documents':documents,
        }}
    if row is None:row=StatementWorkspace(client_id=client_id,revision=0);db.add(row)
    row.payload=copy.deepcopy(payload);row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'对账单项目归属同时变化，请重新加载')
    db.add(StatementWorkspaceHistory(id=history_uid,client_id=client_id,revision=row.revision,actor_id=user.id,
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
    document_status.activate(payload,board)
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
    return [board for board in payload['boards'] if not board.get('sub_client_id') and (
        board.get('period_month') == month or not board.get('period_month') and
        (task_months.get(board['id']) or set(board.get('billing_months', []))) == {month}
    )]


def import_board_matches(payload, months):
    task_months = {}
    for task in payload['tasks'].values():
        task_months.setdefault(task['board_id'],set()).add(task['month'])
    return [board for board in payload['boards'] if board.get('status')!='void' and not board.get('sub_client_id')
            and months & (set(board.get('billing_months',[])) | task_months.get(board['id'],set()))]


def sub_client_board(payload, line, month, number, fields, *, settlement_scope='standard'):
    sub_id = line['sub_client_id']
    scope = (sub_id, month, number)
    for board in payload['boards']:
        if ((board.get('sub_client_id'),board.get('period_month'),board.get('period_number')) == scope
                and board.get('settlement_scope','standard') == settlement_scope and not board.get('number_parent_id')):
            return board
    label = billing_period_name(month, number) if number else month
    name = line['sub_client_name'] or line['sub_client_code']
    board = new_board(payload, fields, f'{name} · {label}')
    board.update(sub_client_id=sub_id,sub_client_name=name,sub_client_code=line['sub_client_code'],
                 period_month=month,period_number=number,billing_months=[month],
                 settlement_scope=settlement_scope,tax_included=line.get('unit_label')=='含税')
    return board


def assigned_month_board(payload, month, assignment):
    return next((board for board in month_boards(payload,month) if board['id']==assignment.get('board_id')),None)


class BillingPeriodWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    month: str = Field(pattern=source.MONTH)
    board_id: str | None = None
    create_period: bool = False
    period_number: int | None = Field(default=None, ge=1)
    revision: int = Field(ge=0)
    version: str


def place_unpaid_orders_after_paid_period(db,projects,user):
    """Assign newly registered, unpaid projects to the period following the latest payment."""
    from translation_document_requirements import TranslationProjectDocuments,attach,ready

    if not projects or not ready(db):
        return None
    attach(db,projects)
    project=projects[0]
    client_id=source.finance.statement_client_id(project)
    month=source.finance.effective_billing_month(project)
    if not client_id or not month or not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return None
    if any(source.finance.statement_client_id(order)!=client_id or source.finance.effective_billing_month(order)!=month
           or getattr(order,'billing_period',{}).get('number') or getattr(order,'billing_period',{}).get('board_id')
           or (getattr(order,'recorded_payment_method',None) or getattr(order,'customer_payment_method',None)) in ('individual','special')
           for order in projects):
        return None
    row=workspace(db,client_id,True)
    candidates=source.finance.settlement_candidates(db,{(client_id,month)})
    project_ids={order.id for order in projects}
    if any(uid in project_ids and paid for uid,_,_,_,paid,_,_,_ in candidates):
        return None
    sub_client_id=project.sub_client_id
    if any(order.sub_client_id!=sub_client_id for order in projects):
        return None
    paid_periods=[period if isinstance(period,int) else 1 for _,_,_,period,paid,mode,_,sub_id in candidates
                  if paid and mode!='special' and sub_id==sub_client_id]
    if not paid_periods:
        return None
    latest=max(paid_periods)
    number=latest+1
    before=copy.deepcopy(row.payload if row else empty_payload())
    payload=copy.deepcopy(before)
    boards=month_boards(scoped_payload(db,payload,'standard'),month)
    order_ids={str(owner.id) for order in projects for owner in source.finance.hierarchy(order)[0]}
    if access.ready(db) and db.query(access.StatementTaskOwner).filter(
        access.StatementTaskOwner.task_id.in_(order_ids),access.StatementTaskOwner.client_id!=client_id,
    ).first():
        raise HTTPException(409,'有订单已调配至其他客户，请先处理跨客户归属')
    template=next((item for item in boards if item.get('period_number')==latest),None)
    if not template and latest==1:
        unnumbered=[item for item in boards if not item.get('period_number')]
        if len(unnumbered)==1:
            template=unnumbered[0]
            template.update(name=billing_period_name(month,1),period_month=month,period_number=1,billing_months=[month])
            template['fields']['billing_label']=''
    if not template:
        statement=source.build_statement(db,project.id,None,month,'project')
        template=new_board(payload,imported_fields(statement),billing_period_name(month,latest))
        template.update(period_month=month,period_number=latest,billing_months=[month],tax_included=statement['tax_included'],
                        settlement_scope='standard')
    target=next((item for item in boards if item.get('period_number')==number),None)
    if target is None:
        target=new_board(payload,template['fields'],billing_period_name(month,number))
        target.update(period_month=month,period_number=number,billing_months=[month],tax_included=template['tax_included'],
                      settlement_scope='standard')
        target['fields']['billing_label']=''
    assignment={'month':month,'number':number,'board_id':target['id']}
    moment=business_now()
    for order in projects:
        document=db.get(TranslationProjectDocuments,order.id)
        if document is None:
            document=TranslationProjectDocuments(project_id=order.id,quotation_revision=0)
            db.add(document)
        document.quotation_data={**(document.quotation_data or {}),'_billing_period':assignment}
        document.updated_at=moment
        document.updated_by=user.id
        order.billing_period=assignment
    for task_id in order_ids & payload['tasks'].keys():
        task=payload['tasks'][task_id]
        if not pending_tasks.pending(task):
            task.update(month=month,board_id=target['id'])
            pending_tasks.invalidate_overrides(payload,task)
    save(db,user,client_id,row,before,payload,'自动分配账期',{'orders':[order.order_no for order in projects],'after':assignment},commit=False)
    db.info.pop('translation_monthly_tax_projects',None)
    db.info.pop('translation_monthly_tax_modes',None)
    return assignment


@router.put('/project/{project_id}/billing-period')
def assign_billing_period(project_id: UUID, data: BillingPeriodWrite, db=Depends(get_db), user=Depends(write_access)):
    from translation_document_requirements import TranslationProjectDocuments, payment_method, ready as documents_ready

    if sum((bool(data.board_id), data.create_period, data.period_number is not None)) > 1:
        raise HTTPException(422, '请选择一种账期设置方式')
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
        raise HTTPException(409, '该订单已有项目调配到其他客户，请先处理跨客户归属')
    scope = 'special' if payment_method(project)=='special' else 'standard'
    candidates = month_boards(scoped_payload(db,payload,scope), data.month)
    created = None
    if data.period_number is not None:
        if any(board.get('period_number') == data.period_number for board in candidates):
            raise HTTPException(422, f'第{data.period_number}期已存在，请在账期中直接选择')
        numbered = [board for board in candidates if board.get('period_number')]
        template = max(numbered, key=lambda board: board['period_number']) if numbered else (
            candidates[0] if len(candidates) == 1 else None
        )
        if template:
            fields, tax_included = template['fields'], template['tax_included']
        else:
            statement = source.build_statement(db, project_id, None, data.month, 'project')
            fields, tax_included = imported_fields(statement), statement['tax_included']
        board = new_board(payload, fields, billing_period_name(data.month, data.period_number))
        board.update(period_month=data.month, period_number=data.period_number, billing_months=[data.month],
                     tax_included=tax_included)
        board['fields']['billing_label'] = ''
        created = {'board_id': board['id'], 'name': board['name']}
    elif data.create_period:
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
    from sub_client_finance import period_party
    party = period_party(payload, project.sub_client_id, data.month, assignment['number'])
    previous = getattr(project, 'billing_period', {})
    document.quotation_data = {**(document.quotation_data or {}), '_billing_period': assignment}
    moment = business_now()
    document.updated_at = moment
    document.updated_by = user.id
    project.updated_at = moment.replace(tzinfo=None)
    for task_id in order_ids & payload['tasks'].keys():
        task = payload['tasks'][task_id]
        target=board
        if payment_method(project)=='sub_client' and party == 'sub_client' and not pending_tasks.pending(task):
            target=sub_client_board(payload,{**task['rows'][0],'sub_client_id':str(project.sub_client_id),
                'sub_client_name':project.sub_client.client_name,'sub_client_code':project.sub_client.sub_client_code},
                data.month,board.get('period_number'),board['fields'])
        task.update(month=data.month, board_id=None if pending_tasks.pending(task) else target['id'])
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
    current_board=next((board for board in payload['boards'] if current_task and board['id']==current_task['board_id']),{})
    return {
        'revision': row.revision if row else 0,
        'board_id': assignment.get('board_id') or next((board['id'] for board in boards
            if current_board.get('sub_client_id') and board.get('period_number')==current_board.get('period_number')),
            current_task and current_task['board_id']),
        'can_create': len(payload['boards']) < 12 and (
            len(boards) < 2 or any(board.get('period_number') for board in boards)
        ),
        'can_create_custom': len(payload['boards']) < 12,
        'boards': [{'id': board['id'], 'name': board['name'], 'number': board.get('period_number')}
                   for board in sorted(boards, key=lambda board: board.get('period_number') or 0)],
    }


@router.get('/special-invoice-documents')
def special_invoice_documents(months:list[str]|None=Query(None),client_id:UUID|None=None,manager_ids:list[UUID]|None=Query(None),only_mine:bool=False,client_manager:str|None=None,db=Depends(get_db),user=Depends(read_access)):
    from statement_invoice_documents import StatementInvoiceRef,read_documents
    from statement_customer_groups import project_query
    from finance_manager_scope import manager_fields
    from translation_special_settlement import apply_settings,settings_by_project,order_nodes
    query=db.query(StatementWorkspace)
    if client_id:query=query.filter_by(client_id=client_id)
    allowed={str(uid) for uid, in project_query(db,None,manager_fields(db,user,manager_ids,only_mine,client_manager)).with_entities(TranslationProject.id).all()}
    eligible=[];rows={};root_ids=set();board_lines={}
    for row in query:
        rows[row.client_id]=row
        for board in row.payload.get('boards',[]):
            if board.get('settlement_scope')!='special' or board.get('status')=='void':continue
            if months and not set(months)&set(document_status.months(row.payload,board)):continue
            lines=[line for task in row.payload['tasks'].values() if task.get('board_id')==board['id'] for line in task['rows']]
            if not lines or not any(line['root_id'] in allowed for line in lines):continue
            eligible.append(StatementInvoiceRef(client_id=row.client_id,board_id=board['id'],revision=row.revision))
            board_lines[board['id']]=lines
            root_ids.update(line['root_id'] for line in lines)
    projects=source.crud.get_translation_projects(db,limit=None,field_filters={'finance_invoice_project_ids':{'value':list(root_ids)}}) if root_ids else []
    source.finance.attach_monthly_payment_peers(db,projects)
    source.finance.load_finance_details(db,projects)
    settings=settings_by_project(db,[project.id for project in projects]);nodes={}
    for project in projects:
        node=source.finance.tree(project,include_version=False)['item']
        apply_settings(node,settings.get(project.id,{}))
        nodes[str(project.id)]={item['id']:item.get('invoice_required') for item in order_nodes(node)}
    items=read_documents(db,eligible,workspace_rows=rows)
    for entry in items:
        requirements=[nodes.get(line['root_id'],{}).get(line['task_id']) for line in board_lines[entry['board_id']]]
        if entry['invoice_required'] is None:entry['invoice_required']=True if True in requirements else None if None in requirements else False
    return dict(items=items,total=len(items))


@router.get('/{client_id}')
def read_client_workspace(client_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access),settlement_scope:StatementScope|None=None):
    row=workspace(db,client_id)
    client_name=db.query(Client.client_name).filter(Client.id==client_id).scalar()
    return {**serialize(row,mode,user=user,db=db,settlement_scope=settlement_scope),'client_id':str(client_id),'client_name':client_name}


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


@router.post('/{client_id}/historical-status-preview')
def historical_status_preview(client_id:UUID,data:HistoricalStatusRequest,db=Depends(get_db),user=Depends(read_access),settlement_scope:StatementScope|None=None):
    from statement_history_status import proposal
    row=workspace(db,client_id)
    if row is None:raise HTTPException(404,'对账单工作区不存在')
    payload=copy.deepcopy(row.payload);document_status.normalize(payload)
    result=proposal(db,user,client_id,payload,data.model_dump(),settlement_scope)
    return {**{key:value for key,value in result.items() if key!='superseded'},'will_replace_current':bool(result.get('superseded'))}


@router.post('/{client_id}/project-coverage')
def project_coverage(client_id:UUID,data:ProjectCoverageRequest,db=Depends(get_db),user=Depends(read_access),settlement_scope:StatementScope|None=None):
    from sqlalchemy import func
    from models import SubClient
    from statement_customer_groups import project_query
    from finance_manager_scope import manager_fields
    from translation_document_requirements import attach,matches_statement_scope
    from translation_customer_finance import attach_monthly_payment_peers
    if any(not MONTH.fullmatch(month) for month in data.months):raise HTTPException(422,'请选择有效的账单月份')
    current=workspace(db,client_id)
    payload=copy.deepcopy(current.payload) if current else empty_payload()
    document_status.normalize(payload)
    payload=scoped_payload(db,payload,settlement_scope)
    boards={board['id']:board for board in payload['boards'] if board.get('status')!='void'}
    scope=manager_fields(db,user,data.manager_ids,data.only_mine,data.client_manager)
    items=[];waiting={}
    for month in dict.fromkeys(data.months):
        eligible_boards={uid for uid,board in boards.items() if month in document_status.months(payload,board) and (not data.period_number or (board.get('period_number') or board.get('status_period_number'))==data.period_number)}
        if not eligible_boards:continue
        represented={line['root_id'] for task in payload['tasks'].values() if task.get('board_id') in eligible_boards and task['month']==month for line in task['rows']}
        pending_by_root={line['root_id']:task for task in payload['tasks'].values() if pending_tasks.pending(task) for line in task['rows']}
        query=project_query(db,month,scope).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id)
        if data.sub_client_id:query=query.filter(TranslationProject.sub_client_id==data.sub_client_id)
        projects=query.all()
        attach(db,projects);attach_monthly_payment_peers(db,projects)
        for project in projects:
            if not matches_statement_scope(project,settlement_scope) or data.period_number and project.settlement_period_number!=data.period_number:continue
            uid=str(project.id)
            if uid in represented:continue
            item=dict(id=uid,order_no=project.order_no,project_name=project.project_name,month=month,period_number=project.settlement_period_number)
            if uid in pending_by_root:
                waiting[uid]={**item,'target_month':pending_by_root[uid]['month']}
            else:items.append(item)
    return dict(items=items,pending=list(waiting.values()))




@router.post('/{client_id}/pending-period-preview')
def pending_period_preview(client_id:UUID,data:PendingPeriodPreview,db=Depends(get_db),
                           user=Depends(read_access),settlement_scope:StatementScope|None=None):
    row=workspace(db,client_id)
    if row is None:
        raise HTTPException(404,'请先导入对账单项目')
    payload=scoped_payload(db,copy.deepcopy(row.payload),settlement_scope)
    statement_notes.refresh(db,payload)
    ids=list(dict.fromkeys(data.task_ids))
    tasks=payload['tasks']
    if any(key not in tasks for key in ids):
        raise HTTPException(422,'请选择当前结算范围内的项目')
    roots={UUID(tasks[key]['rows'][0]['root_id']) for key in ids}
    assignments=project_billing_assignments(db,roots)
    boards={board['id']:board for board in payload['boards']}
    months={data.month,*(tasks[key]['month'] for key in ids)}
    matches={month:import_board_matches(payload,{month}) for month in months}

    def target_period(task,month):
        if pending_tasks.pending(task) and task['month']==month and task.get('pending_target_board_id'):
            target=boards.get(task['pending_target_board_id'])
            return (target.get('period_number'),False) if target else (None,True)
        assignment=assignments.get(task['rows'][0]['root_id'],{})
        if assignment.get('month')==month:
            board=assigned_month_board(payload,month,assignment)
            return board.get('period_number') if board else None, board is None
        candidates=matches[month]
        if len(candidates)!=1:
            return None,len(candidates)>1
        board=candidates[0]
        if board.get('period_month') and board['period_month']!=month:
            return None,True
        return board.get('period_number'),False

    result=[]
    for key in ids:
        task=tasks[key]
        current_month=task['month']
        waiting=pending_tasks.pending(task)
        if waiting:
            current_number,current_needs_period=target_period(task,current_month)
        else:
            board=boards.get(task['board_id'],{})
            current_number=board.get('period_number') if board.get('period_month')==current_month else None
            current_needs_period=False
        target_number,target_needs_period=target_period(task,data.month)
        result.append({
            'id':key,'current_month':current_month,'current_period':current_number,
            'current_pending':waiting,'current_needs_period':current_needs_period,
            'target_period':target_number,'target_needs_period':target_needs_period,
        })
    return result


@router.post('/import')
def import_months(data:ImportRequest,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(write_access)):
    if not data.confirmed:raise HTTPException(422,'请确认后导入对账单')
    generation_request=data
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
    statements=[source.build_statement(db,project_id,None,month,data.scope,'children',special=special,group_directions=False) for month in months]
    if data.order_ids is not None:
        from statement_project_preview import build
        if data.client_id is None:raise HTTPException(422,'按所选项目生成时需指定客户')
        allowed={line['task_id'] for month in months for line in build(
            db,data.client_id,month,data.order_ids,special=special,group_directions=False
        )['rows']}
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
    if data.sub_client_id:
        from models import SubClient
        child=db.get(SubClient,data.sub_client_id)
        if child is None or child.parent_client_id!=client.id:
            raise HTTPException(422,'子客户不属于当前客户')
        root_ids={str(uid) for uid, in db.query(TranslationProject.id).filter_by(sub_client_id=data.sub_client_id)}
        for statement in statements:
            statement['rows']=[line for line in statement['rows'] if line['root_id'] in root_ids]
    row=workspace(db,client.id,True);check_revision(row,data.revision)
    before=copy.deepcopy(row.payload if row else empty_payload());payload=copy.deepcopy(before)
    if special:
        from statement_special_documents import import_documents
        return import_documents(db,user,client,row,before,payload,data,statements,mode)
    document_status.normalize(payload)
    scoped = scoped_payload(db,payload,data.settlement_scope)
    ordinary_rows=any(not line.get('sub_client_id') for statement in statements for line in statement['rows']) or (
        not data.sub_client_id and any(pending_tasks.pending(task) and task['month'] in months and
        not task['rows'][0].get('sub_client_id') for task in scoped['tasks'].values())
    )
    if data.period_number:
        period = period_payload(scoped,data.period_number,months)
        targets = [item for item in period['boards'] if not item.get('sub_client_id')]
        if len(months)!=1 or len(targets)>1 or not targets and ordinary_rows:
            raise HTTPException(422,'未找到唯一对应账期，请在价格与付款中核对账期')
        if not data.board_id and targets:
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
        matches=import_board_matches(scoped,set(months))
        board=matches[0] if len(matches)==1 else None
        if not matches and ordinary_rows:
            title='对账单'
            fields={**imported_fields(statements[0]),'title':title}
            board=new_board(payload,fields,'、'.join(months)+' '+title)
            if data.settlement_scope:board['settlement_scope']=data.settlement_scope
    if board and board.get('period_month') and months != [board['period_month']]:
        raise HTTPException(422,'只能将所属月份的订单导入该账期')
    if data.board_id and board not in scoped['boards']:
        raise HTTPException(422,'所选对账单属于另一种结算范围')
    if board and not before['boards']:board['tax_included']=statements[0]['tax_included']
    roots = {UUID(line['root_id']) for statement in statements for line in statement['rows']}
    roots.update(UUID(line['root_id']) for task in payload['tasks'].values() if pending_tasks.pending(task)
                 and task['month'] in months for line in task['rows'])
    assignments=project_billing_assignments(db,roots)
    if not board and ordinary_rows and not any(assignment.get('month') in months for assignment in assignments.values()):
        waiting=[task for task in scoped['tasks'].values() if pending_tasks.pending(task) and task['month'] in months and not task['rows'][0].get('sub_client_id')]
        new_unassigned=any(not line.get('sub_client_id') and line['task_id'] not in payload['tasks'] for statement in statements for line in statement['rows'])
        if not waiting or any(not task.get('pending_target_board_id') for task in waiting) or new_unassigned:
            raise HTTPException(422,'所选月份有多份有效对账单，请先选择具体账期')

    def target_board(month, root_id, line):
        assignment=assignments.get(root_id, {})
        sub_id=line.get('sub_client_id')
        if not sub_id and board and board.get('sub_client_id'):
            raise HTTPException(422,'请选择该子客户同期的订单')
        if sub_id:
            number=data.period_number or line.get('settlement_period_number')
            if board and board.get('sub_client_id') and (board['sub_client_id'],board.get('period_month'),board.get('period_number'))!=(sub_id,month,number):
                raise HTTPException(422,'请选择该子客户同期的订单')
            template=board['fields'] if board else imported_fields(statements[months.index(month)])
            return sub_client_board(payload,line,month,number,template,settlement_scope=data.settlement_scope or 'standard')
        if assignment.get('month') == month:
            assigned=assigned_month_board(scoped,month,assignment)
            if not assigned or assigned.get('status')=='void':
                raise HTTPException(409,'订单选择的账期已变更，请在价格与付款中重新选择')
            return assigned
        if not board:
            raise HTTPException(422,'所选月份有多份有效对账单，请先在价格与付款为订单选择账期')
        board['billing_months']=sorted(set(board.get('billing_months',[]))|{month})
        return board
    added=0;existing=0;generated={}
    for month,statement in zip(months,statements):
        grouped={}
        for line in statement['rows']:grouped.setdefault(line['task_id'],[]).append(line)
        for task_id,lines in grouped.items():
            if task_id in payload['tasks']:
                existing+=1
                task=payload['tasks'][task_id]
                if task.get('board_id') and task_id in scoped['tasks']:
                    current_board = board_by_id(payload, task['board_id'])
                    if current_board.get('status')=='void' or current_board.get('sub_client_id') != lines[0].get('sub_client_id') and task['month'] == month:
                        target = target_board(month, lines[0]['root_id'], lines[0])
                        pending_tasks.invalidate_overrides(payload, task)
                        task.update(board_id=target['id'], rows=lines,month=month)
                    generated.setdefault(task_id,{**task,'rows':lines})
                continue
            if access.ready(db):
                owner=db.get(access.StatementTaskOwner,task_id)
                if owner and owner.client_id!=client.id:existing+=1;continue
            root_id=lines[0]['root_id']
            target=target_board(month,root_id,lines[0])
            if root_id not in payload['roots']:payload['roots'][root_id]=outline(source.finance.read(db,UUID(root_id))['item'])
            original={'rows':copy.deepcopy(lines),'month':month,'board_id':target['id']}
            payload['tasks'][task_id]={'id':task_id,'board_id':target['id'],'month':month,'rows':lines,'original':original}
            generated[task_id]=payload['tasks'][task_id]
            added+=1
    pending_scope = scoped
    if data.period_number:
        pending_scope = {**scoped,'tasks':{key:task for key,task in scoped['tasks'].items()
                         if (task.get('pending_target_board_id') or assignments.get(task['rows'][0]['root_id'],{}).get('board_id'))==data.board_id}}
    if data.sub_client_id:
        pending_scope={**pending_scope,'tasks':{key:task for key,task in pending_scope['tasks'].items()
            if task['rows'][0]['root_id'] in root_ids}}
    def pending_target(task):
        if task.get('pending_target_board_id'):
            target=next((item for item in scoped['boards'] if item['id']==task['pending_target_board_id']),None)
            if target is None or target.get('status')=='void':raise HTTPException(409,'待入账项目指定的账期已删除、废除或不在当前范围，请重新选择账期')
            return target
        return target_board(task['month'],task['rows'][0]['root_id'],task['rows'][0])
    accepted=pending_tasks.accept(pending_scope,months,pending_target)
    if data.order_ids is not None and not added and not existing and not accepted:raise HTTPException(422,'当前筛选没有可生成的项目或待入账项目')
    if any(pending_tasks.pending(task) and task['month'] in months for task in pending_scope['tasks'].values()):raise HTTPException(409,'仍有待入账项目未纳入，本次生成已取消，请重新加载')
    for task_id,task in pending_scope['tasks'].items():
        if pending_tasks.pending(before['tasks'].get(task_id,{})) and not pending_tasks.pending(task):
            generated[task_id]=task
    requirement_changes=mark_generated_statement_required(db,user,generated)
    row=save(db,user,client.id,row,before,payload,'导入月份',{'months':months,'added_tasks':added,'existing_tasks_kept':existing,'excluded_tasks':excluded,'accepted_pending':accepted,
             'statement_requirements':requirement_changes},
             generation=(generation_request,mode,generated) if generated else None)
    return {**serialize(row,mode,user=user,db=db,settlement_scope=data.settlement_scope),'imported':added,'existing':existing,'excluded':excluded,'accepted_pending_count':len(accepted),'generation_saved':bool(generated)}


def mark_generated_statement_required(db,user,tasks):
    """仅标记实际纳入本次对账单的项目，与生成结果一起提交。"""
    from translation_document_requirements import TranslationProjectDocuments,save as save_documents
    roots={UUID(line['root_id']) for task in tasks.values() if task.get('board_id') for line in task.get('rows',[]) if line.get('root_id')}
    if not roots:return []
    projects=db.query(TranslationProject).filter(TranslationProject.id.in_(roots)).order_by(TranslationProject.id).with_for_update().all()
    records={record.project_id:record for record in db.query(TranslationProjectDocuments).filter(TranslationProjectDocuments.project_id.in_(roots))}
    changes=[]
    for project in projects:
        record=records.get(project.id)
        if record and record.statement_required is True:continue
        previous=record.statement_required if record else None
        save_documents(db,project,statement_required=True,actor_id=user.id)
        project.updated_at=business_now().replace(tzinfo=None)
        changes.append({'project_id':str(project.id),'order_no':project.order_no,'before':previous,'after':True})
    return changes


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
    if not isinstance(edits,list) or len(edits)>10000:raise HTTPException(422,'项目修改格式错误')
    visible={line['_row_id']:line for line in display_data(payload,board,mode,group_directions=False)['rows']}
    seen=set();months={}
    for edit in edits:
        if not isinstance(edit,dict) or not isinstance(edit.get('row_id'),str) or edit['row_id'] in seen:raise HTTPException(422,'项目修改编号无效或重复')
        seen.add(edit['row_id']);line=visible.get(edit['row_id'])
        if line is None:raise HTTPException(409,'项目已变化，请重新加载后编辑')
        values=edit.get('fields')
        if not isinstance(values,dict) or not values:raise HTTPException(422,'请选择修改字段')
        values=dict(values);month=values.pop('billing_month',None)
        if month is not None:
            if not isinstance(month,str) or not MONTH.fullmatch(month):raise HTTPException(422,'账单月份格式应为YYYY-MM')
            if board.get('period_month') and board['period_month']!=month:
                raise HTTPException(422,'跨月项目请通过“调整月份 / 移到另一份”移至目标月份对账单')
            for task_id in line['task_ids']:
                if task_id in months and months[task_id]!=month:raise HTTPException(422,'同一项目的各行账单月份必须一致')
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
    content_action=request.action in ('set_historical_status','edit_customer_note','edit_document','edit_row','edit_board','change_company_subject','sync_customer_notes','restore_task','restore_history')
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
    if row is None:raise HTTPException(404,'请先导入对账单项目')
    check_revision(row,request.revision);before=copy.deepcopy(row.payload);payload=copy.deepcopy(before);data=request.data
    if settlement_scope:
        visible = scoped_payload(db,payload,settlement_scope)
        board_ids = set(data.get('board_ids') or [])
        if data.get('board_id') and request.action!='set_historical_status':
            board_ids.add(data['board_id'])
        visible_ids = {board['id'] for board in visible['boards']}
        hidden_board_ids = {task['board_id'] for key,task in payload['tasks'].items() if key not in visible['tasks']}
        if board_ids - visible_ids or set(data.get('task_ids') or []) - visible['tasks'].keys():
            raise HTTPException(422,'请选择当前结算范围内的对账单或项目')
        if request.action in ('delete_boards','merge_boards','edit_document','edit_board','sync_customer_notes') and board_ids & hidden_board_ids:
            raise HTTPException(422,'该账单含另一种结算范围的项目，请通过对账单（备份）处理整份账单')
        if request.action=='restore_history':
            raise HTTPException(422,'请通过对账单（备份）恢复客户的完整历史版本')
    if content_action:
        access.require(db,user,access.content_clients(client_id,payload),'edit_content')
    changes={};label=request.action
    if request.action=='set_special_invoice':
        board=board_by_id(payload,data.get('board_id'))
        if board.get('settlement_scope')!='special' or board.get('status')=='void':raise HTTPException(422,'请选择有效特殊结算对账单')
        status=data.get('status');proofs=data.get('proofs','')
        if status not in ('unissued','partial','issued') or not isinstance(proofs,str) or len(proofs)>20000:raise HTTPException(422,'请填写有效的发票状态及资料')
        from statement_special_documents import validate_invoice_proofs
        validate_invoice_proofs(db,proofs)
        if data.get('subject_key') not in (*SUBJECTS,None):raise HTTPException(422,'请选择有效的开票主体')
        changes={'board_id':board['id'],'before':copy.deepcopy(board.get('invoice',{}))}
        board['invoice']={key:data.get(key) for key in ('status','proofs','subject_key')}
        board['invoice'].update(actor_name=user.full_name or user.username,updated_at=business_now().isoformat())
        changes['after']=board['invoice'];label='登记特殊结算单发票'
    elif request.action=='remove_special_projects':
        from statement_special_documents import remove_projects
        changes=remove_projects(payload,data.get('board_id'),data.get('task_ids'),user);label='从特殊结算单移除项目'
    elif request.action=='restore_special_projects':
        from statement_special_documents import restore_projects
        changes=restore_projects(payload,data.get('board_id'),data.get('removed_project_ids'));label='恢复特殊结算单已移除项目'
    elif request.action=='set_board_period':
        board=board_by_id(payload,data.get('board_id'))
        changes={'board_id':board['id'],'before':document_status.number(board),'after':data.get('period_number')}
        document_status.set_period(payload,board,data.get('period_number'))
        label='调整对账单账期'
    elif request.action=='set_historical_status':
        from statement_history_status import proposal
        document_status.normalize(payload)
        changes=proposal(db,user,client_id,payload,data,settlement_scope)
        if data.get('status')=='active' and (changes['conflicts'] or changes.get('superseded')) and data.get('expected_plan')!=changes['plan']:
            raise HTTPException(409,'该月份/账期已有有效对账单，请查看冲突清单并确认后再调整')
        if changes.get('superseded'):changes['archive']={'documents':changes.pop('superseded')}
        label='调整历史版本状态'
    elif request.action=='edit_customer_note':
        changes=statement_notes.edit(db,user,payload,data.get('board_id'),data.get('row_id'),data.get('customer_note'),mode);label='同步对账单客户说明'
    elif request.action=='accept_pending':
        ids=data.get('task_ids');target=board_by_id(payload,data.get('board_id'))
        if not isinstance(ids,list) or not ids or any(not isinstance(uid,str) or uid not in payload['tasks'] or not pending_tasks.pending(payload['tasks'][uid]) for uid in ids):raise HTTPException(422,'请选择有效的待入账项目')
        if target.get('status')=='void':raise HTTPException(422,'不能将项目加入废除的对账单')
        months=document_status.months(payload,target)
        for uid in ids:
            task=payload['tasks'][uid]
            if task['month'] not in months:raise HTTPException(422,'待入账项目与目标账单月份不匹配')
            expected=next((board for board in payload['boards'] if board['id']==task.get('pending_target_board_id')),None)
            if expected and (expected.get('period_number') or expected.get('status_period_number'))!=(target.get('period_number') or target.get('status_period_number')):raise HTTPException(422,'待入账项目与目标账期不匹配')
            if (task['rows'][0].get('sub_client_id') or None)!=(target.get('sub_client_id') or None):raise HTTPException(422,'待入账项目与目标客户或子客户不匹配')
        selected={**payload,'tasks':{uid:payload['tasks'][uid] for uid in dict.fromkeys(ids)}}
        if any(not pending_tasks.pending(task) for task in selected['tasks'].values()):raise HTTPException(409,'项目已纳入对账单，请刷新后操作')
        changes={'accepted_pending':pending_tasks.accept(selected,months,lambda task:target)};label='拖入待入账项目'
    elif request.action=='set_board_status':
        board=board_by_id(payload,data.get('board_id'));status=data.get('status')
        if status not in ('active','void'):raise HTTPException(422,'请选择有效或废除状态')
        changes={'board_id':board['id'],'name':board['name'],'before':board.get('status','active'),'after':status}
        if status=='active':
            document_status.activate(payload,board)
            board.pop('archived_revision',None)
        else:board['status']='void'
        label='调整对账单状态'
    elif request.action=='sync_customer_notes':
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
        for line in display_data(payload,board,mode,group_directions=False)['rows']:
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
        from statement_reorganization import inherit_sub_client_period
        candidates=visible['boards'] if settlement_scope else payload['boards']
        if not candidates:raise HTTPException(422,'请先选择月份重新生成对账单')
        template=board_by_id(payload,data['board_id']) if data.get('board_id') else candidates[0]
        special_board=template.get('settlement_scope')=='special'
        next_number=None if special_board else document_status.next_period(payload,template)
        name=str(data.get('name','新对账单')).strip()[:100]
        board=new_board(payload,template['fields'],name or '新对账单');board['tax_included']=template['tax_included'];label='新增对账单';changes={'name':board['name'],'parent_board_id':template['id']}
        board['number_parent_id']=template['id']
        inherit_sub_client_period(board,template)
        board['billing_months']=document_status.months(payload,template)
        if settlement_scope:board['settlement_scope']=settlement_scope
        else:board['settlement_scope']=template.get('settlement_scope') or 'standard'
        if next_number is not None:document_status.set_period(payload,board,next_number)
        else:
            for key in ('period_number','period_month','status_period_number','status_period_month'):board.pop(key,None)
        changes.update(period_number=next_number,original_period_number=document_status.number(template))
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
        from statement_subject_sync import apply
        if board.get('settlement_scope')!='special':apply(db,payload,subject_key,board.get('sub_client_id'))
        label='调整公司主体并同步客户设置'
    elif request.action=='edit_document':
        for edit in data.get('rows',[]):
            if 'remarks' in edit.get('fields',{}):statement_notes.edit(db,user,payload,data.get('board_id'),edit.get('row_id'),edit['fields']['remarks'],mode)
        changes=edit_document(payload,data,mode);label='直接编辑对账单'
    elif request.action=='edit_board':
        board=board_by_id(payload,data.get('board_id'));values=clean_fields(data.get('fields',{}),HEADER_FIELDS|{'name'})
        for key,value in values.items():
            target=board if key in ('name','tax_included') else board['fields'];changes[key]={'before':target.get(key),'after':value};target[key]=value
        label='修改对账单内容'
    elif request.action=='edit_row':
        board=board_by_id(payload,data.get('board_id'));row_id=data.get('row_id')
        visible=display_data(payload,board,mode,group_directions=False)['rows'];line=next((line for line in visible if line['_row_id']==row_id),None)
        if not line:raise HTTPException(409,'该项目已变化，请重新加载')
        values=clean_fields(data.get('fields',{}),ROW_FIELDS)
        if 'remarks' in values:changes['customer_note_sync']=statement_notes.edit(db,user,payload,board['id'],row_id,values['remarks'],mode)
        for key,value in values.items():changes[key]={'before':line.get(key),'after':value}
        found=False
        for task in payload['tasks'].values():
            if task['board_id']!=board['id']:continue
            for stored in task['rows']:
                if stored['line_id']==row_id:
                    if source.is_fixed_statement_row(stored):stored['pricing_mode']='fixed'
                    stored.update(values);found=True
        if not found:board['overrides'].setdefault(row_id,{}).update(values)
        label='修改项目内容';changes={'order_no':line['order_no'],'fields':changes}
    elif request.action in ('schedule_tasks','cancel_pending'):
        ids=data.get('task_ids')
        if not isinstance(ids,list) or not ids or not all(isinstance(uid,str) and uid in payload['tasks'] for uid in ids):raise HTTPException(422,'请选择有效项目')
        ids=list(dict.fromkeys(ids))
        if request.action=='schedule_tasks':
            month=data.get('month')
            if not isinstance(month,str) or not MONTH.fullmatch(month):raise HTTPException(422,'请选择目标账单月份')
            target=board_by_id(payload,data['board_id']) if data.get('board_id') else None
            if target:
                target_months={target['period_month']} if target.get('period_month') else set(target.get('billing_months',[]))|{task['month'] for task in payload['tasks'].values() if task.get('board_id')==target['id']}
                if month not in target_months:raise HTTPException(422,'目标账期与所选账单月份不一致')
                if any((payload['tasks'][key]['rows'][0].get('sub_client_id') or None)!=(target.get('sub_client_id') or None) for key in ids):raise HTTPException(422,'请选择同一客户或子客户的目标账期')
            changes=pending_tasks.schedule(payload,ids,month,user,target);label='调整待入账月份'
        else:changes=pending_tasks.cancel(payload,ids);label='撤销待入账调整'
    elif request.action in ('move_tasks','restore_task'):
        submitted=data.get('task_ids',[])
        if not isinstance(submitted,list) or not all(isinstance(item,str) for item in submitted):raise HTTPException(422,'项目选择格式错误')
        ids=list(dict.fromkeys(submitted))
        if not ids or any(task_id not in payload['tasks'] for task_id in ids):raise HTTPException(422,'请选择有效项目')
        if request.action=='move_tasks':
            target=board_by_id(payload,data.get('board_id'));month=data.get('month')
            if not isinstance(month,str) or not MONTH.fullmatch(month):raise HTTPException(422,'请选择目标账单月份')
            if target.get('period_month') and target['period_month']!=month:
                raise HTTPException(422,'目标账期与所选账单月份不一致')
        changes=[]
        for task_id in ids:
            task=payload['tasks'][task_id]
            if pending_tasks.pending(task):raise HTTPException(409,'项目正在待入账，请在待入账列表调整或撤销')
            if request.action=='move_tasks':
                from statement_reorganization import ensure_same_sub_client_period
                ensure_same_sub_client_period([board_by_id(payload,task['board_id']),target])
            old={'month':task['month'],'board_id':task['board_id'],'board_name':board_by_id(payload,task['board_id'])['name']}
            old_rows=copy.deepcopy(task['rows'])
            if request.action=='restore_task':
                original=task['original']
                if not any(board['id']==original['board_id'] for board in payload['boards']):raise HTTPException(409,'原对账单已不在当前版本，请从修改记录恢复')
                task.update(copy.deepcopy(original))
                for key in ('pending','pending_from','pending_actor','pending_at','pending_target_board_id'):task.pop(key,None)
            else:task.update(board_id=target['id'],month=month)
            # 清除涉及该项目的展示汇总覆盖，防止移动后留下旧金额。
            root_ids={line['root_id'] for line in task['rows']}
            for board in payload['boards']:
                board['overrides']={key:value for key,value in board['overrides'].items() if not any(key.startswith('summary:'+root_id+':') for root_id in root_ids)}
            item={'task_id':task_id,'order_no':task['rows'][0]['order_no'],'before':old,'after':{'month':task['month'],'board_id':task['board_id'],'board_name':board_by_id(payload,task['board_id'])['name']}}
            if request.action=='restore_task':item['content']={'before':old_rows,'after':copy.deepcopy(task['rows'])}
            changes.append(item)
        label='恢复项目原始内容' if request.action=='restore_task' else '调配项目月份及对账单'
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
        from sub_client_finance import DOCUMENT_SETTINGS, PERIOD_PARTIES
        for key in (PERIOD_PARTIES, DOCUMENT_SETTINGS):
            if key in before:
                payload[key] = before[key]
            else:
                payload.pop(key, None)
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


@router.get('/{client_id}/special-invoice-originals/{board_id}')
def special_invoice_originals(client_id:UUID,board_id:str,db=Depends(get_db),user=Depends(read_access)):
    import translation_project_invoices as invoices
    row=workspace(db,client_id)
    if row is None:raise HTTPException(404,'对账单不存在')
    board=board_by_id(row.payload,board_id)
    if board.get('settlement_scope')!='special':raise HTTPException(422,'请选择特殊结算对账单')
    items=[];seen=set()
    for task in row.payload['tasks'].values():
        if task.get('board_id')!=board_id:continue
        for line in task['rows']:
            root=UUID(line['root_id']);uid=UUID(line['task_id'])
            if (root,uid) in seen:continue
            seen.add((root,uid))
            for special in (False,True):
                value=invoices.read(db,root,uid,special=special)
                if value.get('proofs') or value.get('invoice_status')!='unissued':items.append(dict(order_no=line['order_no'],kind='原特殊结算发票' if special else '原项目发票',proofs=value.get('proofs',''),status=value.get('invoice_status','unissued')))
    return dict(items=items)


@router.put('/{client_id}/special-invoice/{board_id}')
def write_special_statement_invoice(client_id:UUID,board_id:str,data:SpecialStatementInvoiceWrite,db=Depends(get_db),user=Depends(require_any_permission('projects:write','finance:write','clients:write'))):
    return action(client_id,ActionRequest(revision=data.revision,action='set_special_invoice',confirmed=True,
        data={'board_id':board_id,**data.model_dump(exclude={'revision'})}),mode='children',db=db,user=user,settlement_scope='special')


@router.put('/{client_id}/collection-terms')
def write_collection_terms(client_id:UUID,data:CollectionTermsWrite,db=Depends(get_db),user=Depends(require_any_permission('projects:write','finance:write','clients:write'))):
    row=workspace(db,client_id,True)
    before=copy.deepcopy(row.payload if row else empty_payload());payload=copy.deepcopy(before)
    current=payload.get('collection_terms') or {}
    if data.revision!=current.get('revision',0):raise HTTPException(409,'客户付款账期已更新，请重新查询后编辑')
    result=dict(value=data.value.strip(),revision=data.revision+1,actor_name=user.full_name or user.username,updated_at=business_now().isoformat())
    payload['collection_terms']=result
    save(db,user,client_id,row,before,payload,'设置客户付款账期',dict(before=current,after=result))
    return result


def client_ledger_units(db,user,client_id,months=None,manager_ids=None,only_mine=False):
    from finance_manager_scope import manager_fields
    from finance_settlement_ledger import build
    from translation_statement_status import attach
    fields={'finance_client_ids':{'value':[str(client_id)]},**manager_fields(db,user,manager_ids,only_mine,None)}
    if months:
        if any(not MONTH.fullmatch(month) for month in months):raise HTTPException(422,'请选择有效月份')
        fields['finance_billing_month']={'value':months}
    projects=source.crud.get_translation_projects(db,limit=None,field_filters=fields)
    from finance_settlement_ledger import statement_root_ids
    extra=statement_root_ids(db,fields,months)-{str(project.id) for project in projects}
    if extra:
        extra_fields={key:value for key,value in fields.items() if key not in ('finance_billing_month','finance_client_ids')}
        extra_fields['finance_invoice_project_ids']={'value':list(extra)}
        projects.extend(source.crud.get_translation_projects(db,limit=None,field_filters=extra_fields))
    source.finance.attach_monthly_payment_peers(db,projects);source.finance.load_finance_details(db,projects);attach(db,projects)
    nodes=[source.finance.tree(project,include_version=False)['item'] for project in projects]
    units,summary=build(db,nodes,nodes,months=months)
    return units,summary


@router.get('/{client_id}/ledger-orders')
def client_ledger_orders(client_id:UUID,months:list[str]|None=Query(None),manager_ids:list[UUID]|None=Query(None),only_mine:bool=False,db=Depends(get_db),user=Depends(read_access)):
    units,summary=client_ledger_units(db,user,client_id,months,manager_ids,only_mine)
    return dict(items=[{**order,'settlement_label':unit['ledger_label']} for unit in units for order in unit['ledger_orders']],summary=summary)


class LedgerRebateWrite(BaseModel):
    unit_id:str=Field(min_length=1,max_length=500)
    revision:int=Field(ge=0)
    recipient:str=Field(max_length=200)
    rate:Decimal=Field(ge=0,le=100,max_digits=9,decimal_places=6)
    payment_status:Literal['unpaid','partial','full']='unpaid'
    paid_amounts:dict[str,Decimal]=Field(default_factory=dict,max_length=20)
    note:str=Field(default='',max_length=5000)


@router.put('/{client_id}/ledger-rebate')
def write_ledger_rebate(client_id:UUID,data:LedgerRebateWrite,db=Depends(get_db),user=Depends(require_any_permission('projects:write','finance:write','clients:write'))):
    from finance_settlement_ledger import rebate_amounts
    units,_=client_ledger_units(db,user,client_id)
    unit=next((unit for unit in units if unit['id']==data.unit_id and unit.get('client_id')==str(client_id)),None)
    if unit is None:raise HTTPException(409,'结算单元已调整或不存在，请重新查询')
    if unit.get('ledger_pending'):raise HTTPException(422,'请先补全项目计费金额，再登记返点')
    row=workspace(db,client_id,True);before=copy.deepcopy(row.payload if row else empty_payload());payload=copy.deepcopy(before)
    records=payload.setdefault('ledger_rebates',{});current=records.get(data.unit_id,{})
    if data.revision!=current.get('revision',0):raise HTTPException(409,'返点记录已更新，请重新查询后编辑')
    if not data.recipient.strip():raise HTTPException(422,'请填写返点人')
    amounts=rebate_amounts(unit['ledger_amounts'],data.rate)
    paid={currency:format(value,'.2f') for currency,value in data.paid_amounts.items()}
    if any(not value.is_finite() or value<0 or value.as_tuple().exponent < -2 for value in data.paid_amounts.values()):raise HTTPException(422,'已支付金额应为非负金额，最多两位小数')
    if data.payment_status=='unpaid':paid={currency:'0.00' for currency in amounts}
    elif data.payment_status=='full':paid=amounts.copy()
    elif not any(Decimal(value)>0 for value in paid.values()) or any(currency not in amounts or Decimal(value)>Decimal(amounts[currency]) for currency,value in paid.items()) or all(Decimal(paid.get(currency,0))==Decimal(value) for currency,value in amounts.items()):
        raise HTTPException(422,'部分支付须填写大于零且未付清的返点金额，不能超过应付返点金额')
    result=dict(recipient=data.recipient.strip(),rate=str(data.rate),amounts=amounts,payment_status=data.payment_status,paid_amounts=paid,note=data.note.strip(),revision=data.revision+1,actor_name=user.full_name or user.username,updated_at=business_now().isoformat())
    records[data.unit_id]=result
    save(db,user,client_id,row,before,payload,'登记返点',dict(unit_id=data.unit_id,before=current,after=result))
    return result


@router.get('/{client_id}/history')
def history(client_id:UUID,skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    query=db.query(StatementWorkspaceHistory).filter_by(client_id=client_id).filter(
        StatementWorkspaceHistory.action!='登记特殊结算付款')
    private_settings=source.private_statement_settings_available()
    return {'total':query.count(),'items':[{'id':str(row.id),'revision':row.revision,'actor_name':row.actor_name,'action':row.action,'changes':history_changes(row.changes,private_settings),'created_at':business_datetime(row.created_at).isoformat(),'restorable':row.action!='跨客户对账单调配' and isinstance(row.before.get('boards'),list) and access.allowed_ids(db,user,access.content_clients(client_id,row.before),'edit_content')==access.content_clients(client_id,row.before)} for row in query.order_by(StatementWorkspaceHistory.revision.desc()).offset(skip).limit(limit)]}


def history_changes(changes, private_settings=True):
    if isinstance(changes,dict) and 'archive' in changes:
        changes={**changes,'archive':{key:value for key,value in changes['archive'].items() if key!='documents'}}
    if isinstance(changes,dict) and 'generation' in changes:
        changes={key:value for key,value in changes.items() if key!='generation'}
    return changes if private_settings else without_private_fields(changes)


def generation_records(db, client_id):
    model = StatementWorkspaceHistory
    return db.query(model).filter(
        model.client_id==client_id,model.changes['generation']['key'].as_string().is_not(None),
    )


@router.post('/{client_id}/generation-status')
def generation_status(client_id:UUID,data:ImportRequest,db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    model=StatementWorkspaceHistory
    match=generation_records(db,client_id).with_entities(model.id).filter(
        model.changes['generation']['key'].as_string()==generation_key(data),
    ).first()
    return {'exists':match is not None}


@router.get('/{client_id}/generation-versions')
def generation_versions(client_id:UUID,settlement_scope:StatementScope|None=None,skip:int=Query(0,ge=0),
                        limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    model=StatementWorkspaceHistory
    generation=model.changes['generation']
    query=generation_records(db,client_id).filter(generation['settlement_scope'].as_string()==(settlement_scope or ''))
    records=query.with_entities(model.id,model.revision,model.created_at,model.actor_name,
                               generation['months'],generation['period_number'],generation['orders'])
    return {'total':query.count(),'items':[
        dict(id=str(uid),revision=revision,created_at=business_datetime(created_at).isoformat(),
             actor_name=actor,months=months,period_number=period,orders=orders)
        for uid,revision,created_at,actor,months,period,orders in records.order_by(model.revision.desc()).offset(skip).limit(limit)
    ]}


@router.get('/{client_id}/generation-versions/{history_id}')
def generation_version(client_id:UUID,history_id:UUID,db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    row=generation_records(db,client_id).filter_by(id=history_id).first()
    if not row:
        raise HTTPException(404,'未找到对账单生成版本')
    result={'revision':row.revision,'created_at':business_datetime(row.created_at).isoformat(),
            'documents':row.changes['generation']['documents']}
    if source.private_statement_settings_available():
        return result
    result=without_private_fields(result)
    for board in result['documents']:
        board['statement']['private_settings_available']=False
    return result


@router.get('/{client_id}/historical-versions')
def historical_versions(client_id:UUID,settlement_scope:StatementScope|None=None,skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(read_access)):
    from sqlalchemy import or_
    current=workspace(db,client_id)
    payload=copy.deepcopy(current.payload) if current else empty_payload()
    document_status.normalize(payload)
    virtual=[board for board in scoped_payload(db,payload,settlement_scope)['boards'] if board.get('status')=='void' and not board.get('archived_revision')]
    active_versions={board.get('active_history_id') for board in payload['boards'] if board.get('status')!='void'}
    model=StatementWorkspaceHistory
    query=db.query(model).filter(model.client_id==client_id,or_(model.changes['archive']['months'].as_string().is_not(None),
        model.changes['deleted_boards'].as_string().is_not(None),model.changes['generation']['key'].as_string().is_not(None)))
    # 归档记录按各自快照再做结算范围隔离；列表不下载 roots 或项目全文。
    items=[dict(id='current:'+board['id'],revision=current.revision,created_at=business_datetime(current.updated_at).isoformat(),actor_name='',
        months=document_status.months(payload,board),period_number=board.get('period_number'),orders=[],name=board['name'],status='void',action='已废除') for board in virtual]
    records=query.with_entities(model.id,model.revision,model.created_at,model.actor_name,model.action,model.changes['archive']['months'],
        model.changes['archive']['orders'],model.changes['generation']['months'],model.changes['generation']['orders'],model.changes['generation']['period_number'],model.changes['generation']['settlement_scope'])
    if settlement_scope:
        records=records.filter(or_(model.changes['archive']['scopes'].as_string().contains('"'+settlement_scope+'"'),model.changes['deleted_boards'].as_string().is_not(None),
            model.changes['generation']['settlement_scope'].as_string().in_([settlement_scope,''])))
    total=len(items)+records.count()
    available=items[skip:skip+limit]
    remaining=limit-len(available)
    if remaining:
        for uid,revision,created_at,actor,action,archive_months,archive_orders,months,orders,period,scope in records.order_by(model.revision.desc()).offset(max(0,skip-len(items))).limit(remaining):
            available.append(dict(id=str(uid),revision=revision,created_at=business_datetime(created_at).isoformat(),actor_name=actor,
                months=sorted(set((archive_months or [])+(months or []))),orders=sorted(set((archive_orders or [])+(orders or []))),period_number=period,status='active' if str(uid) in active_versions else 'void',action=action))
    return {'items':available,'total':total}


@router.get('/{client_id}/historical-versions/{version_id}')
def historical_version(client_id:UUID,version_id:str,settlement_scope:StatementScope|None=None,db=Depends(get_db),user=Depends(read_access)):
    current=workspace(db,client_id)
    if version_id.startswith('current:'):
        payload=copy.deepcopy(current.payload) if current else empty_payload()
        document_status.normalize(payload)
        board=board_by_id(scoped_payload(db,payload,settlement_scope),version_id.removeprefix('current:'))
        if board.get('status')!='void' and board.get('active_history_id')!=version_id:raise HTTPException(409,'该对账单当前有效，请刷新历史版本')
        numbers=statement_number.numbers(db,client_id)
        result=dict(revision=current.revision,created_at=business_datetime(current.updated_at).isoformat(),documents=[dict(id=board['id'],name=board['name'],status=board.get('status','void'),statement={**display_data(payload,board),'statement_number':numbers.get(board['id'])})])
    else:
        try:uid=UUID(version_id)
        except ValueError:raise HTTPException(404,'历史版本不存在')
        row=db.query(StatementWorkspaceHistory).filter_by(id=uid,client_id=client_id).first()
        if not row:raise HTTPException(404,'历史版本不存在')
        archived=row.changes.get('archive',{}).get('documents')
        if archived is not None:
            docs=copy.deepcopy(archived)+copy.deepcopy(row.changes.get('generation',{}).get('documents',[]))
        elif row.changes.get('deleted_boards'):
            payload=scoped_payload(db,row.before,settlement_scope)
            ids={board['id'] for board in row.changes['deleted_boards']}
            docs=[dict(id=board['id'],name=board['name'],statement=display_data(payload,board)) for board in payload['boards'] if board['id'] in ids]
        else:docs=copy.deepcopy(row.changes.get('generation',{}).get('documents',[]))
        if settlement_scope:
            allowed={board['id'] for board in scoped_payload(db,row.after,settlement_scope)['boards']}|{board['id'] for board in scoped_payload(db,row.before,settlement_scope)['boards']}
            docs=[board for board in docs if board['id'] in allowed]
        result=dict(revision=row.revision,created_at=business_datetime(row.created_at).isoformat(),documents=[{**board,'status':'active' if current and any(item['id']==board['id'] and item.get('status')!='void' and item.get('active_history_id')==version_id for item in current.payload['boards']) else 'void'} for board in docs])
    if source.private_statement_settings_available():return result
    result=without_private_fields(result)
    for board in result['documents']:board['statement']['private_settings_available']=False
    return result


@router.get('/{client_id}/history/{history_id}')
def history_entry(client_id:UUID,history_id:UUID,db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    record=db.query(StatementWorkspaceHistory).filter_by(id=history_id,client_id=client_id).first()
    if not record:raise HTTPException(404,'调整记录不存在')
    result=dict(id=str(record.id),revision=record.revision,actor_name=record.actor_name,action=record.action,created_at=business_datetime(record.created_at).isoformat(),changes=history_changes(record.changes),before=record.before,after=record.after)
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
    numbers=statement_number.numbers(db,client_id)
    payload=scoped_payload(db,copy.deepcopy(row.payload),settlement_scope)
    statement_notes.refresh(db,payload)
    for index,uid in enumerate(board_ids):
        board=board_by_id(payload,uid);statement={**display_data(payload,board,mode,dates.get(uid,'')),'statement_number':numbers.get(uid)}
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有项目")
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
    numbers=statement_number.numbers(db,client_id)
    payload=scoped_payload(db,copy.deepcopy(row.payload),settlement_scope)
    statement_notes.refresh(db,payload)
    for uid in board_ids:
        board=board_by_id(payload,uid);statement={**display_data(payload,board,mode,dates.get(uid,'')),'statement_number':numbers.get(uid)}
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有项目")
        statements.append(statement)
    from statement_pdf import pdf_bytes
    return Response(pdf_bytes(statements),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=customer-statements.pdf'})
