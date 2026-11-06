from copy import deepcopy
import pytest
from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from tests.test_statement_reorganization import register,allow
import customer_statement_workspace as service
import statement_access as access
import translation_customer_finance as finance

def body(setup):
    http,db,clients,_,user,first,_=setup
    register(setup);allow(db,user,clients)
    other=project(db,clients[1],'MERGED','2026-10',fixed=True)
    return dict(client_ids=[str(client.id) for client in clients],target_client_id=str(clients[0].id),month='2026-10',order_ids=[str(first.id),str(other.id)],name='十月合并账单',confirmed=True)

def preview(http,data):
    response=http.post('/statement-reorganization/project-preview',json=data)
    assert response.status_code==200,response.text
    return response.json()

def test_merged_preview_generation_is_atomic_unique_and_keeps_sources(setup):
    http,db,clients,_,user,first,_=setup;data=body(setup)
    result=preview(http,data)
    assert db.query(service.StatementWorkspace).count()==0
    assert result['statement']['totals']=={'CNY':'623.40'}
    assert {line['origin_client_id'] for line in result['statement']['rows']}==set(data['client_ids'])
    response=http.post('/statement-reorganization/generate-projects',json={**data,'versions':result['versions']})
    assert response.status_code==200,response.text
    saved=response.json();assert saved['imported']==2
    assert len(saved['documents'])==1 and saved['documents'][0]['name']=='十月合并账单'
    assert saved['documents'][0]['statement']['totals']==result['statement']['totals']
    assert first.client_id==clients[0].id and first.customer_charge_items[0].billing_month=='2026-10'
    owners=db.query(access.StatementTaskOwner).all();assert len(owners)==2 and {row.client_id for row in owners}=={clients[0].id}
    repeated=preview(http,data);assert repeated['existing_count']==2 and repeated['statement']['rows']==[]
    response=http.post('/statement-reorganization/generate-projects',json={**data,'versions':result['versions']})
    assert response.status_code==409
    assert db.query(service.StatementWorkspaceHistory).count()==1

def test_merged_requires_every_client_grant_and_matches_selected_orders(setup):
    http,db,clients,_,user,*_=setup;data=body(setup)
    allow(db,user,[clients[1]],cross=False)
    assert http.post('/statement-reorganization/project-preview',json=data).status_code==403
    allow(db,user,clients)
    outside=project(db,clients[0],'NEW','2026-10');outside.client_id=None;db.commit()
    assert http.post('/statement-reorganization/project-preview',json={**data,'order_ids':[str(outside.id)]}).status_code==422
    assert db.query(service.StatementWorkspace).count()==0

def test_merged_accepts_pending_task_once_and_audits_both_workspaces(setup):
    http,db,clients,_,user,first,_=setup;data=body(setup)
    state=imported(setup,['2026-10'])
    state=change(setup,state,'schedule_tasks',{'task_ids':[str(first.id)],'month':'2026-12'})
    data.update(month='2026-12',order_ids=[],target_client_id=str(clients[1].id))
    result=preview(http,data);assert len(result['statement']['rows'])==1
    filtered=preview(http,{**data,'source_client_ids':[str(clients[1].id)]})
    assert filtered['statement']['rows']==[]  # 客户筛选不能接收另一客户的待入账任务。
    response=http.post('/statement-reorganization/generate-projects',json={**data,'versions':result['versions']})
    assert response.status_code==200,response.text
    assert response.json()['imported']==1
    assert str(first.id) not in db.get(service.StatementWorkspace,clients[0].id).payload['tasks']
    task=response.json()['payload']['tasks'][str(first.id)]
    assert task['month']=='2026-12' and not task['pending'] and task['origin_client_id']==str(clients[0].id)
    assert db.get(access.StatementTaskOwner,str(first.id)).client_id==clients[1].id
    events=db.query(service.StatementWorkspaceHistory).filter_by(action='合并客户项目生成对账单').all()
    assert len(events)==2 and {event.client_id for event in events}=={client.id for client in clients}

def test_project_list_multi_client_filter_combines_with_project_status(setup):
    http,db,clients,_,_,first,_=setup;data=body(setup);http.app.include_router(finance.router)
    first.project_status='已确认';db.commit()
    response=http.get('/translation-customer-finance/page',params=[('client_ids',str(clients[0].id)),('client_ids',str(clients[1].id)),('project_statuses','已确认')])
    assert response.status_code==200,response.text
    assert str(first.id) in {row['id'] for row in response.json()['items']}
    only=http.get('/translation-customer-finance/page',params={'client_ids':str(clients[1].id)})
    assert only.status_code==200,only.text
    assert all(row['client_id']==str(clients[1].id) for row in only.json()['items'])
