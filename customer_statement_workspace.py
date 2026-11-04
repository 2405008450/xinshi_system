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

from models import Base, Client, TranslationProject
from database import get_db
from routers.auth import require_permission
from annotation_progress_time import business_now, business_datetime
import customer_statements as source

router=APIRouter(prefix='/translation-statement-workspaces',tags=['对账单编排'])
read_access=require_permission('projects:read')
write_access=require_permission('projects:write')
MONTH=re.compile(source.MONTH)
ROW_FIELDS={'received_date','project_name','language_pair','quantity','basis','unit_price','unit_size','unit_label','currency','subtotal','remarks'}
HEADER_FIELDS={'company','title','client_name','client_code','billing_label','bank_name','account_name','account_number','stamp_image','tax_included'}


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


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    action:Literal['create_board','edit_board','edit_row','move_tasks','reorder_boards','position_board','restore_task','restore_history']
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


def display_data(payload,board,mode='children'):
    tasks=[task for task in payload['tasks'].values() if task['board_id']==board['id']]
    ledger=[]
    for task in tasks:
        for line in task['rows']:
            ledger.append({**line,'billing_month':task['month'],'_row_id':line['line_id'],'task_ids':[task['id']]})
    rendered=[]
    for root_id,root in payload['roots'].items():
        rows=[line for line in ledger if line['root_id']==root_id]
        if not rows:continue
        for line in source.statement_display_rows(root,rows,mode):
            # 汇总行可覆盖不同任务，不沿用首条任务的身份。
            if line.get('basis','').startswith('订单汇总'):
                line={**line,'_row_id':f"summary:{root_id}:{line['order_no']}:{line['currency']}",
                      'task_ids':list(dict.fromkeys(item['task_id'] for item in rows if item['order_no']==line['order_no'] or item['order_no'].startswith(line['order_no']+'.')))}
                line['billing_month']='、'.join(sorted({item['billing_month'] for item in rows if item['task_id'] in line['task_ids']}))
            rendered.append({**line,**board.get('overrides',{}).get(line['_row_id'],{})})
    totals={};pending=[]
    for line in rendered:
        if line.get('counted_in_total',True):
            if line['subtotal'] is None:pending.append(f"{line['order_no']}：金额待补录")
            else:totals[line['currency']]=totals.get(line['currency'],Decimal(0))+Decimal(str(line['subtotal']))
    fields=board['fields'];months=sorted({task['month'] for task in tasks})
    return dict(company=fields['company'],title=fields['title'],client_name=fields['client_name'],client_code=fields['client_code'],
                month=fields.get('billing_label') or '、'.join(months),months=months,rows=rendered,totals={key:source.money(value) for key,value in totals.items()},pending=pending,
                settings={key:fields.get(key,'') for key in ('bank_name','account_name','account_number')},stamp_image=fields.get('stamp_image') or source.default_stamp(),tax_included=board['tax_included'])


def serialize(row,mode='children'):
    payload=row.payload if row else empty_payload()
    return {'client_id':str(row.client_id) if row else None,'revision':row.revision if row else 0,'payload':payload,
            'documents':[{**board,'statement':display_data(payload,board,mode)} for board in payload['boards']]}


def save(db,user,client_id,row,before,payload,action,changes):
    ids=[board['id'] for board in payload['boards']]
    if len(ids)!=len(set(ids)) or not 1<=len(ids)<=12:raise HTTPException(422,'对账单数量应为1至12份，编号不能重复')
    if len(payload['tasks'])>10000:raise HTTPException(422,'客户编排最多保留10000项任务，请缩小导入范围')
    if any(task['board_id'] not in ids for task in payload['tasks'].values()):raise HTTPException(422,'任务归属无效')
    if row is None:row=StatementWorkspace(client_id=client_id,revision=0);db.add(row)
    row.payload=copy.deepcopy(payload);row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    db.flush()
    db.add(StatementWorkspaceHistory(id=uuid4(),client_id=client_id,revision=row.revision,actor_id=user.id,
        actor_name=user.full_name or user.username or '用户',action=action,changes=changes,before=before,after=copy.deepcopy(payload),created_at=business_now()))
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'对账单同时更新，请重新加载')
    return row


def new_board(payload,template,name):
    if len(payload['boards'])>=12:raise HTTPException(422,'同一客户最多保留12份对账单')
    index=len(payload['boards'])
    board={'id':str(uuid4()),'name':name,'fields':copy.deepcopy(template),'overrides':{},'tax_included':False,'x':(index%3)*980,'y':(index//3)*900}
    payload['boards'].append(board);return board


def imported_fields(statement):
    return {**{key:statement.get(key,'') for key in ('company','title','client_name','client_code','stamp_image')},
            **statement['settings'],'billing_label':''}


@router.get('/project/{project_id}')
def read_project_workspace(project_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    project=source.crud.get_translation_project(db,project_id)
    if not project or project.annotation_migrated_at is not None:raise HTTPException(404,'笔译项目不存在')
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先为项目关联客户')
    row=workspace(db,client.id)
    return {**serialize(row,mode),'client_id':str(client.id),'client_name':client.client_name}


@router.get('/{client_id}')
def read_client_workspace(client_id:UUID,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_access)):
    row=workspace(db,client_id)
    return {**serialize(row,mode),'client_id':str(client_id),'client_name':db.get(Client,client_id).client_name}


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
    board=board_by_id(payload,data.board_id) if data.board_id else (payload['boards'][0] if payload['boards'] else new_board(payload,imported_fields(statements[0]),'、'.join(months)+' 对账单'))
    if not before['boards']:board['tax_included']=statements[0]['tax_included']
    added=0;existing=0
    for month,statement in zip(months,statements):
        grouped={}
        for line in statement['rows']:grouped.setdefault(line['task_id'],[]).append(line)
        for task_id,lines in grouped.items():
            if task_id in payload['tasks']:existing+=1;continue
            root_id=lines[0]['root_id']
            if root_id not in payload['roots']:payload['roots'][root_id]=outline(source.finance.read(db,UUID(root_id))['item'])
            original={'rows':copy.deepcopy(lines),'month':month,'board_id':board['id']}
            payload['tasks'][task_id]={'id':task_id,'board_id':board['id'],'month':month,'rows':lines,'original':original}
            added+=1
    row=save(db,user,client.id,row,before,payload,'导入月份',{'months':months,'added_tasks':added,'existing_tasks_kept':existing,'excluded_tasks':excluded})
    return {**serialize(row,mode),'imported':added,'existing':existing,'excluded':excluded}


def clean_fields(values,allowed):
    if not isinstance(values,dict) or not values or set(values)-allowed:raise HTTPException(422,'含不可修改字段；订单号不可修改')
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
            if key=='received_date' and value:
                from datetime import date
                try:date.fromisoformat(value)
                except ValueError:raise HTTPException(422,'来稿日期格式错误')
            result[key]=value
    return result


@router.post('/{client_id}/actions')
def action(client_id:UUID,request:ActionRequest,mode:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(write_access)):
    if not request.confirmed:raise HTTPException(422,'请在弹窗确认后应用修改')
    row=workspace(db,client_id,True)
    if row is None:raise HTTPException(404,'请先导入对账单任务')
    check_revision(row,request.revision);before=copy.deepcopy(row.payload);payload=copy.deepcopy(before);data=request.data
    changes={};label=request.action
    if request.action=='create_board':
        template=payload['boards'][0]
        name=str(data.get('name','新对账单')).strip()[:100]
        board=new_board(payload,template['fields'],name or '新对账单');board['tax_included']=template['tax_included'];label='新增对账单';changes={'name':board['name']}
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
                if stored['line_id']==row_id:stored.update(values);found=True
        if not found:board['overrides'].setdefault(row_id,{}).update(values)
        label='修改任务内容';changes={'order_no':line['order_no'],'fields':changes}
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
            task=payload['tasks'][task_id];old={'month':task['month'],'board_id':task['board_id'],'board_name':board_by_id(payload,task['board_id'])['name']}
            old_rows=copy.deepcopy(task['rows'])
            if request.action=='restore_task':
                original=task['original']
                if not any(board['id']==original['board_id'] for board in payload['boards']):raise HTTPException(409,'原对账单已不在当前版本，请从修改记录恢复')
                task.update(copy.deepcopy(original))
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
        if not history or not history.before.get('boards'):raise HTTPException(422,'该记录之前尚无对账单，无法恢复')
        payload=copy.deepcopy(history.before);label='恢复历史版本';changes={'restored_before_revision':history.revision}
    row=save(db,user,client_id,row,before,payload,label,changes)
    return serialize(row,mode)


@router.get('/{client_id}/history')
def history(client_id:UUID,skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(read_access)):
    workspace(db,client_id)
    query=db.query(StatementWorkspaceHistory).filter_by(client_id=client_id)
    return {'total':query.count(),'items':[{'id':str(row.id),'revision':row.revision,'actor_name':row.actor_name,'action':row.action,'changes':row.changes,'created_at':business_datetime(row.created_at).isoformat(),'restorable':bool(row.before.get('boards'))} for row in query.order_by(StatementWorkspaceHistory.revision.desc()).offset(skip).limit(limit)]}


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
    for index,uid in enumerate(board_ids):
        board=board_by_id(row.payload,uid);statement=display_data(row.payload,board,mode)
        if not statement['rows']:raise HTTPException(422,f"{board['name']}没有任务")
        target=output.create_sheet(f'对账单{index+1}')
        for number,text in [(1,statement['company']),(2,statement['title']),(3,f"客户：{statement['client_name']}　{statement['client_code']}    账单月份：{statement['month']}    {'含税' if statement['tax_included'] else '不含税'}")]:
            target.merge_cells(start_row=number,start_column=1,end_row=number,end_column=9);target.cell(number,1,_safe_text(text))
        target.append([]);target.append(['订单号','账单月份','来稿日期','项目名称','翻译方向','工作量（计价方式）','单价','小计','备注'])
        for line in statement['rows']:
            workload=(str(line['quantity'])+'\n' if line['quantity'] is not None else '')+line['basis']
            unit=f"{line['currency']} {line['unit_price']}（{line['unit_label']}，每{line.get('unit_size') or 1}计价）" if line['unit_price'] is not None else '-'
            remark=('汇总参考，不重复计入合计。' if line.get('counted_in_total') is False else '')+(line.get('remarks') or '')
            target.append([_safe_text(value) for value in [line['order_no'],line.get('billing_month',''),line['received_date'],line['project_name'],line['language_pair'],workload,unit,f"{line['currency']} {line['subtotal']}" if line['subtotal'] is not None else '待补',remark]])
            target.row_dimensions[target.max_row].height=48
        total_row=target.max_row+1;target.merge_cells(start_row=total_row,start_column=1,end_row=total_row,end_column=7)
        target.cell(total_row,1,'合计（已登记金额）' if statement['pending'] else '合计');target.merge_cells(start_row=total_row,start_column=8,end_row=total_row,end_column=9)
        target.cell(total_row,8,'\n'.join(f'{currency} {amount}' for currency,amount in statement['totals'].items()));target.row_dimensions[total_row].height=45
        border=Border(left=Side(style='thin'),right=Side(style='thin'),top=Side(style='thin'),bottom=Side(style='thin'))
        for cells in target:
            for cell in cells:
                cell.font=Font(name='微软雅黑',size=18 if cell.row==1 else 11,bold=cell.row in (1,2,5,total_row));cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
                if cell.row>=5:cell.border=border
        target.append([])
        for text in ['账户信息','开户行：'+statement['settings']['bank_name'],'账户名：'+statement['settings']['account_name'],'账号：'+statement['settings']['account_number']]+(['待补资料：'+'；'.join(statement['pending'])] if statement['pending'] else []):
            target.append([_safe_text(text)]);target.merge_cells(start_row=target.max_row,start_column=1,end_row=target.max_row,end_column=9)
        image=ExcelImage(BytesIO(base64.b64decode(statement['stamp_image'].split(',',1)[1])));image.width=135;image.height=135;target.add_image(image,f'E{max(5,total_row-1)}')
        for key,width in zip('ABCDEFGHI',[25,15,16,34,22,32,30,22,32]):target.column_dimensions[key].width=width
        target.sheet_view.showGridLines=False;target.sheet_properties.pageSetUpPr.fitToPage=True;target.page_setup.orientation='landscape';target.page_setup.paperSize=target.PAPERSIZE_A4;target.page_setup.fitToWidth=1;target.page_setup.fitToHeight=0;target.print_title_rows='1:5'
    buffer=BytesIO();output.save(buffer)
    return Response(buffer.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename=customer-statements.xlsx"})
