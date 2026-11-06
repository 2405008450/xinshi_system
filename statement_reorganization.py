"""历史账单重组：同客户布局调整与授权跨客户事务。"""
import copy
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import Client
from routers.auth import get_current_user,require_permission
import statement_access as access

def name(value):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>100:raise HTTPException(422,'请填写100字以内的对账单名称')
    return value.strip()

def board(payload,uid):
    from customer_statement_workspace import board_by_id
    return board_by_id(payload,uid)

def copy_overrides(payload,source,target,ids):
    selected=set(ids);tasks=[task for task in payload['tasks'].values() if task['board_id']==source['id']]
    lines={row['line_id'] for task in tasks if task['id'] in selected for row in task['rows']}
    for key,value in list(source.get('overrides',{}).items()):
        applies=key in lines
        if key.startswith('summary:'):
            root=key.split(':')[1];members={task['id'] for task in tasks if any(row['root_id']==root for row in task['rows'])}
            if members&selected and members-selected:raise HTTPException(422,'所选任务涉及整组汇总调整，无法自动分配；请选择该汇总的全部任务后分拆')
            applies=bool(members&selected)
        if applies:
            if key in target.get('overrides',{}) and target['overrides'][key]!=value:raise HTTPException(422,'账单存在相互冲突的汇总调整，未进行合并，请先核对')
            target.setdefault('overrides',{})[key]=copy.deepcopy(value);source['overrides'].pop(key,None)

def reorganize(payload,action,data):
    from customer_statement_workspace import new_board
    if action=='rename_board':
        item=board(payload,data.get('board_id'));before=item['name'];item['name']=name(data.get('name'))
        return '重命名对账单',{'board_id':item['id'],'before':before,'after':item['name']}
    if action=='merge_boards':
        ids=data.get('board_ids')
        if not isinstance(ids,list) or not all(isinstance(uid,str) for uid in ids) or len(set(ids))<2 or len(set(ids))!=len(ids):raise HTTPException(422,'请选择至少两份不重复的对账单')
        sources=[board(payload,uid) for uid in ids];target=sources[0]
        before=copy.deepcopy(sources)
        for source in sources[1:]:
            task_ids=[task['id'] for task in payload['tasks'].values() if task['board_id']==source['id']]
            copy_overrides(payload,source,target,task_ids)
            for task_id in task_ids:payload['tasks'][task_id]['board_id']=target['id']
        target['name']=name(data.get('name') or target['name'])
        target['billing_months']=sorted({month for item in sources for month in item.get('billing_months',[])})
        payload['boards']=[item for item in payload['boards'] if item['id'] not in ids[1:]]
        return '合并历史对账单',{'before':before,'after':copy.deepcopy(target),'task_ids':[task['id'] for task in payload['tasks'].values() if task['board_id']==target['id']]}
    ids=data.get('task_ids')
    if not isinstance(ids,list) or not ids or not all(isinstance(uid,str) and uid in payload['tasks'] for uid in ids) or len(set(ids))!=len(ids):raise HTTPException(422,'请选择有效且不重复的任务')
    if any(payload['tasks'][uid].get('pending') for uid in ids):raise HTTPException(422,'待入账任务请先生成目标月份账单')
    sources=[board(payload,uid) for uid in dict.fromkeys(payload['tasks'][key]['board_id'] for key in ids)]
    target=new_board(payload,sources[0]['fields'],name(data.get('name')));target['tax_included']=sources[0]['tax_included']
    before={uid:payload['tasks'][uid]['board_id'] for uid in ids}
    for source in sources:copy_overrides(payload,source,target,ids)
    for uid in ids:payload['tasks'][uid]['board_id']=target['id']
    return '分拆历史对账单',{'before':before,'after':{'board_id':target['id'],'name':target['name']},'task_ids':ids}

router=APIRouter(prefix='/statement-reorganization',tags=['历史对账单重组'])
from statement_merged_projects import MergedProjects

@router.post('/project-preview',dependencies=[Depends(require_permission('projects:read'))])
def merged_project_preview(data:MergedProjects,db=Depends(get_db),user=Depends(get_current_user)):
    from statement_merged_projects import prepare
    return prepare(db,user,data)[0]

@router.post('/generate-projects',dependencies=[Depends(require_permission('projects:write'))])
def generate_merged_projects(data:MergedProjects,db=Depends(get_db),user=Depends(get_current_user)):
    from statement_merged_projects import generate
    return generate(db,user,data)

@router.get('/clients',dependencies=[Depends(require_permission('projects:read'))])
def authorized_clients(db=Depends(get_db),user=Depends(get_current_user)):
    query=db.query(Client)
    if not access.manager(user):
        if not access.ready(db):return dict(items=[])
        query=query.join(access.StatementGrant,access.StatementGrant.client_id==Client.id).filter(access.StatementGrant.user_id==user.id,access.StatementGrant.cross_client.is_(True))
    return dict(items=[dict(id=str(item.id),name=item.client_short_name or item.client_name,code=item.client_code) for item in query.order_by(Client.client_short_name,Client.id).all()])

@router.get('/workspaces',dependencies=[Depends(require_permission('projects:read'))])
def selected_workspaces(client_ids:list[UUID]=Query(...,min_length=1,max_length=30),db=Depends(get_db),user=Depends(get_current_user)):
    from customer_statement_workspace import workspace,serialize
    access.require(db,user,client_ids,'cross_client')
    return dict(items=[dict(**serialize(workspace(db,uid),user=user,db=db),owner_client_id=str(uid),client_name=db.get(Client,uid).client_short_name or db.get(Client,uid).client_name) for uid in dict.fromkeys(client_ids)])

class BoardSelection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_id:UUID
    board_id:str

class CrossWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    versions:dict[UUID,int]
    boards:list[BoardSelection]=Field(min_length=1,max_length=30)
    target_client_id:UUID
    target_board_id:str|None=None
    name:str=Field(default='',max_length=100)
    task_ids:list[str]|None=None
    confirmed:bool=False

@router.post('/apply',dependencies=[Depends(require_permission('projects:write'))])
def cross_apply(data:CrossWrite,db=Depends(get_db),user=Depends(get_current_user)):
    from customer_statement_workspace import workspace,check_revision,new_board,save,serialize,empty_payload,StatementWorkspace
    if not data.confirmed:raise HTTPException(422,'请确认跨客户调配')
    if not access.ready(db):raise HTTPException(503,'对账单授权与唯一归属存储尚未初始化')
    clients=sorted({item.client_id for item in data.boards}|{data.target_client_id},key=str)
    if set(data.versions)!=set(clients):raise HTTPException(422,'客户版本范围不完整，请重新加载')
    if len({(item.client_id,item.board_id) for item in data.boards})!=len(data.boards):raise HTTPException(422,'对账单选择重复')
    try:
        discovered=db.query(StatementWorkspace).filter(StatementWorkspace.client_id.in_(clients)).all()
        selected={(item.client_id,item.board_id) for item in data.boards}
        origins={UUID(task['origin_client_id']) for row in discovered for task in row.payload['tasks'].values() if row.client_id!=data.target_client_id and task.get('origin_client_id') and (row.client_id,task['board_id']) in selected and (data.task_ids is None or task['id'] in data.task_ids)}
        locked=set(clients)|origins
        db.query(Client).filter(Client.id.in_(locked)).order_by(Client.id).with_for_update().all()
        access.require(db,user,locked,'cross_client')
        rows={uid:workspace(db,uid,True) for uid in clients}
        for uid,row in rows.items():check_revision(row,data.versions[uid])
        before={uid:copy.deepcopy(row.payload if row else empty_payload()) for uid,row in rows.items()}
        payloads=copy.deepcopy(before)
        source_boards=[(item.client_id,board(payloads[item.client_id],item.board_id)) for item in data.boards]
        available={key for uid,item in source_boards for key,task in payloads[uid]['tasks'].items() if task['board_id']==item['id']}
        ids=available if data.task_ids is None else set(data.task_ids)
        if not ids or not ids<=available or data.task_ids is not None and len(ids)!=len(data.task_ids):raise HTTPException(422,'请选择有效且不重复的账单任务')
        fresh_origins={UUID(task['origin_client_id']) for uid,payload in payloads.items() for key,task in payload['tasks'].items() if uid!=data.target_client_id and key in ids and task.get('origin_client_id')}
        if not fresh_origins<=locked:raise HTTPException(409,'任务来源客户已变化，请重新加载')
        target_payload=payloads[data.target_client_id];target_client=db.get(Client,data.target_client_id)
        if data.target_board_id:target=board(target_payload,data.target_board_id)
        else:
            template=source_boards[0][1]
            if data.task_ids is None:
                merged={item.board_id for item in data.boards if item.client_id==data.target_client_id}
                target_payload['boards']=[item for item in target_payload['boards'] if item['id'] not in merged]
            target=new_board(target_payload,template['fields'],name(data.name));target['tax_included']=template['tax_included']
            target['fields'].update(client_name=target_client.client_name,client_code=target_client.client_code or '')
        operation_id=str(uuid4());moved=[]
        # 先释放本次涉及的已登记归属，最终归属在同一事务内重建。
        db.query(access.StatementTaskOwner).filter(access.StatementTaskOwner.task_id.in_(ids)).delete(synchronize_session=False);db.flush()
        for uid,item in source_boards:
            payload=payloads[uid]
            selected=[key for key in ids if key in payload['tasks'] and payload['tasks'][key]['board_id']==item['id']]
            if uid==data.target_client_id and item['id']==target['id']:continue
            copy_overrides(payload,item,target,selected)
            for key in selected:
                task=payload['tasks'][key]
                if uid!=data.target_client_id:
                    if key in target_payload['tasks']:raise HTTPException(409,'目标客户已包含该任务，不能重复调配')
                    task=payload['tasks'].pop(key);target_payload['tasks'][key]=task
                    source_client=db.get(Client,uid)
                    task.setdefault('origin_client_id',str(uid));task.setdefault('origin_client_name',source_client.client_short_name or source_client.client_name)
                    for line in task['rows']:target_payload['roots'][line['root_id']]=copy.deepcopy(payload['roots'][line['root_id']])
                source_client=db.get(Client,uid)
                moved.append(dict(task_id=key,order_no=task['rows'][0]['order_no'],origin_client_id=task.get('origin_client_id',str(uid)),before={'client_id':str(uid),'client_name':source_client.client_short_name or source_client.client_name,'board_id':task['board_id'],'board_name':item['name']},after={'client_id':str(data.target_client_id),'client_name':target_client.client_short_name or target_client.client_name,'board_id':target['id'],'board_name':target['name']}))
                task['board_id']=target['id']
        for uid,payload in payloads.items():
            if data.task_ids is None:
                selected_board_ids={item.board_id for item in data.boards if item.client_id==uid}
                payload['boards']=[item for item in payload['boards'] if item['id']==target['id'] or item['id'] not in selected_board_ids or any(task['board_id']==item['id'] for task in payload['tasks'].values())]
            roots={line['root_id'] for task in payload['tasks'].values() for line in task['rows']}
            payload['roots']={key:value for key,value in payload['roots'].items() if key in roots}
            save(db,user,uid,rows[uid],before[uid],payload,'跨客户对账单调配',dict(operation_id=operation_id,tasks=moved,target_client_id=str(data.target_client_id),target_board_id=target['id']),commit=False)
        db.commit()
        return dict(operation_id=operation_id,moved_count=len(moved),target_client_id=str(data.target_client_id),target_board_id=target['id'])
    except IntegrityError:
        db.rollback();raise HTTPException(409,'任务归属发生并发变化，请刷新后重试')
    except Exception:
        db.rollback();raise
