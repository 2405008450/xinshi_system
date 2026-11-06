from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from statement_project_preview import build
import translation_customer_finance as finance

def test_preview_matches_selected_generation_and_is_read_only(setup):
    http,db,clients,_,actor,root,_=setup
    http.app.include_router(finance.router)
    other=project(db,clients[0],'003','2026-10',fixed=True)
    before=db.query(__import__('customer_statement_workspace').StatementWorkspace).count()
    data=http.post('/translation-customer-finance/statement-preview',json={'client_id':str(clients[0].id),'month':'2026-10','order_ids':[str(root.id)]})
    assert data.status_code==200,data.text
    assert {row['root_id'] for row in data.json()['rows']}=={str(root.id)}
    assert db.query(__import__('customer_statement_workspace').StatementWorkspace).count()==before
    generated=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-10'],'order_ids':[str(root.id)],'revision':0,'confirmed':True})
    assert generated.status_code==200,generated.text
    assert set(generated.json()['payload']['tasks'])=={str(root.id)}
    assert generated.json()['documents'][0]['statement']['totals']==data.json()['totals']
    with pytest.raises(HTTPException):build(db,clients[1].id,'2026-10',[root.id])
    with pytest.raises(HTTPException):build(db,clients[0].id,'2026-10',[uuid4()])

def test_parent_and_child_selection_does_not_duplicate_tasks(context):
    from tests.test_customer_translation_rates import context as tree
    http,db,clients,_,actor=context
    client,root,middle,leaf=tree(db,actor)
    month=finance.order_billing_month(root.order_no)
    parent=build(db,client.id,month,[root.id])
    selected=build(db,client.id,month,[root.id,middle.id,leaf.id])
    assert len(selected['rows'])==len(parent['rows'])
    assert selected['totals']==parent['totals']

def test_pending_only_month_can_preview_and_generate_without_native_projects(setup):
    http,db,clients,_,actor,root,_=setup
    http.app.include_router(finance.router)
    state=imported(setup,['2026-10'])
    state=change(setup,state,'schedule_tasks',{'task_ids':[str(root.id)],'month':'2026-12'})
    preview=http.post('/translation-customer-finance/statement-preview',json={'client_id':str(clients[0].id),'month':'2026-12','months':['2026-11','2026-12'],'order_ids':[]})
    assert preview.status_code==200,preview.text
    assert {row['task_id'] for row in preview.json()['rows']}=={str(root.id)}
    assert preview.json()['rows'][0]['billing_month']=='2026-12'
    result=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-12'],'order_ids':[],'revision':state['revision'],'confirmed':True})
    assert result.status_code==200,result.text
    assert result.json()['accepted_pending_count']==1
    assert not result.json()['pending_tasks']
