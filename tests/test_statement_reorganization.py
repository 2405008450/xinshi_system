from copy import deepcopy
from uuid import uuid4
import pytest
from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from routers import auth
import statement_access as access
import statement_reorganization as reorg
import customer_statement_workspace as service
from tools.apply_statement_access_migration import apply_migration

def register(setup):
    http,db,clients,granted,user,*_=setup
    http.app.include_router(access.router);http.app.include_router(reorg.router)
    return http,db,clients,granted,user

def allow(db,user,clients,edit=False,cross=True):
    for client in clients:
        row=db.get(access.StatementGrant,(user.id,client.id))
        if row is None:row=access.StatementGrant(user_id=user.id,client_id=client.id,revision=1);db.add(row)
        row.edit_content=edit;row.cross_client=cross
    db.commit()

def second_workspace(setup):
    http,db,clients,_,_,*_=setup
    second=project(db,clients[1],'CROSS','2026-11')
    result=http.post('/translation-statement-workspaces/import',json=dict(client_id=str(clients[1].id),months=['2026-11'],scope='customer',revision=0,confirmed=True))
    assert result.status_code==200,result.text
    return result.json()

def test_authorization_manager_identity_and_audit(setup):
    http,db,clients,_,user=register(setup)
    assert http.get('/statement-access/configuration').status_code==403
    user.username='williamzhao';db.commit()
    assert http.get('/statement-access/configuration').status_code==200
    member=db.query(access.AppUser).filter(access.AppUser.id!=user.id).first()
    data=dict(user_id=str(member.id),client_id=str(clients[0].id),revision=0,edit_content=True,cross_client=True)
    assert http.put('/statement-access/grant',json=data).status_code==200
    assert http.put('/statement-access/grant',json=data).status_code==409
    result=http.get('/statement-access/history').json()['items'][0]
    assert not result['before']['edit_content'] and result['after']['edit_content']
    assert result['created_at'].endswith('+08:00')
    assert http.put('/statement-access/grant',json={**data,'revision':1,'edit_content':False}).status_code==200
    assert not access.flags(db,member,clients[0].id)['edit_content']
    apply_migration(db.connection());apply_migration(db.connection())

def test_same_client_layout_without_content_permission(setup):
    http,db,clients,_,user=register(setup)
    state=imported(setup);allow(db,user,clients,edit=False,cross=False)
    board=state['documents'][0];task_id=str(setup[5].id);original=deepcopy(state['payload']['tasks'][task_id]['rows'])
    change(setup,state,'edit_row',dict(board_id=board['id'],row_id=board['statement']['rows'][0]['_row_id'],fields={'project_name':'不能修改'}),expected=403)
    state=change(setup,state,'split_board',dict(task_ids=[task_id],name='手动分拆名称'))
    assert state['documents'][-1]['name']=='手动分拆名称'
    assert state['payload']['tasks'][task_id]['rows']==original
    state=change(setup,state,'merge_boards',dict(board_ids=[item['id'] for item in state['documents']],name='重新合并'))
    assert len(state['documents'])==1 and state['documents'][0]['name']=='重新合并'
    assert state['payload']['tasks'][task_id]['rows']==original
    change(setup,state,'restore_task',dict(task_ids=[task_id]),expected=403)

def test_cross_customer_atomic_unique_ownership_and_revocation(setup):
    http,db,clients,_,user=register(setup)
    first=imported(setup,['2026-10']);second=second_workspace(setup)
    body=dict(versions={first['client_id']:first['revision'],second['client_id']:second['revision']},boards=[dict(client_id=first['client_id'],board_id=first['documents'][0]['id']),dict(client_id=second['client_id'],board_id=second['documents'][0]['id'])],target_client_id=second['client_id'],name='跨客户合并',confirmed=True)
    assert http.post('/statement-reorganization/apply',json=body).status_code==403
    allow(db,user,clients,edit=False,cross=True)
    result=http.post('/statement-reorganization/apply',json=body)
    assert result.status_code==200,result.text
    result=result.json();assert result['moved_count']==2
    source=http.get(f"/translation-statement-workspaces/{first['client_id']}").json()
    target=http.get(f"/translation-statement-workspaces/{second['client_id']}").json()
    task_id=str(setup[5].id)
    assert task_id not in source['payload']['tasks'] and task_id in target['payload']['tasks']
    assert target['payload']['tasks'][task_id]['origin_client_id']==first['client_id']
    assert target['payload']['tasks'][task_id]['rows']==first['payload']['tasks'][task_id]['rows']
    assert db.get(access.StatementTaskOwner,task_id).client_id==clients[1].id
    assert not target['capabilities']['edit_content']
    # 重复请求的版本校验阻止重复迁移。
    assert http.post('/statement-reorganization/apply',json=body).status_code==409
    # 来源客户重新生成也不会把已转出的任务再次纳入。
    regen=http.post('/translation-statement-workspaces/import',json=dict(client_id=first['client_id'],months=['2026-10'],scope='customer',revision=source['revision'],confirmed=True))
    assert regen.status_code==200 and task_id not in regen.json()['payload']['tasks']
    histories=[http.get(f"/translation-statement-workspaces/{client.id}/history").json()['items'][0] for client in clients]
    cross_history=[row for row in db.query(service.StatementWorkspaceHistory).all() if row.action=='跨客户对账单调配']
    assert len(cross_history)==2 and len({row.changes['operation_id'] for row in cross_history})==1
    assert all(row.before is not None and row.after is not None and row.actor_id==user.id for row in cross_history)
    record=cross_history[0]
    detail=http.get(f'/translation-statement-workspaces/{record.client_id}/history/{record.id}')
    assert detail.status_code==200 and detail.json()['before']==record.before and detail.json()['after']==record.after
    other=clients[1].id if record.client_id==clients[0].id else clients[0].id
    assert http.get(f'/translation-statement-workspaces/{other}/history/{record.id}').status_code==404
    allow(db,user,[clients[0]],edit=False,cross=False)
    assert http.get('/statement-reorganization/workspaces',params=[('client_ids',first['client_id']),('client_ids',second['client_id'])]).status_code==403

def test_cross_failure_rolls_back_all_workspaces(setup,monkeypatch):
    http,db,clients,_,user=register(setup)
    first=imported(setup,['2026-10']);second=second_workspace(setup);allow(db,user,clients,edit=True)
    old=service.save;calls=[]
    def fail(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:raise ValueError('隔离测试事务失败')
        return old(*args,**kwargs)
    monkeypatch.setattr(service,'save',fail)
    data=reorg.CrossWrite(versions={first['client_id']:first['revision'],second['client_id']:second['revision']},boards=[dict(client_id=first['client_id'],board_id=first['documents'][0]['id'])],target_client_id=second['client_id'],name='事务测试',confirmed=True)
    with pytest.raises(ValueError):reorg.cross_apply(data,db,user)
    assert service.workspace(db,clients[0].id).payload==first['payload']
    assert service.workspace(db,clients[1].id).payload==second['payload']


def test_drag_between_customers_and_origin_permission_cannot_be_bypassed(setup):
    from models import Client
    http,db,clients,_,user=register(setup)
    first=imported(setup,['2026-10']);second=second_workspace(setup);allow(db,user,clients,edit=False)
    task_id=str(setup[5].id)
    data=dict(versions={first['client_id']:first['revision'],second['client_id']:second['revision']},boards=[dict(client_id=first['client_id'],board_id=first['documents'][0]['id'])],target_client_id=second['client_id'],target_board_id=second['documents'][0]['id'],task_ids=[task_id],confirmed=True)
    result=http.post('/statement-reorganization/apply',json=data)
    assert result.status_code==200,result.text
    target=service.serialize(service.workspace(db,clients[1].id))
    assert target['payload']['tasks'][task_id]['board_id']==second['documents'][0]['id']
    # 获得归属客户内容权限也不能越过原客户的内容权限。
    allow(db,user,[clients[1]],edit=True)
    line=next(row for row in target['documents'][0]['statement']['rows'] if row['order_no']==setup[5].order_no)
    change(setup,target,'edit_row',dict(board_id=second['documents'][0]['id'],row_id=line['_row_id'],fields={'project_name':'越权'}),expected=403)
    third=Client(id=uuid4(),client_name='第三归属客户');db.add(third);db.commit();allow(db,user,[third],edit=False)
    allow(db,user,[clients[0]],edit=False,cross=False)
    retry=dict(versions={second['client_id']:target['revision'],str(third.id):0},boards=[dict(client_id=second['client_id'],board_id=second['documents'][0]['id'])],target_client_id=str(third.id),name='继续跨客户',task_ids=[task_id],confirmed=True)
    assert http.post('/statement-reorganization/apply',json=retry).status_code==403
