from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from tests.test_statement_pending_tasks import generate


def test_coverage_excludes_present_and_pending_projects_and_requires_existing_month(setup):
    http,db,clients,_,_,_,second=setup
    state=imported(setup,['2026-11'])
    missing=project(db,clients[0],'NEW','2026-11')
    other_client=project(db,clients[1],'OTHER','2026-11')
    path=f"/translation-statement-workspaces/{clients[0].id}/project-coverage"
    read=lambda month:http.post(path,json={'months':[month]})
    result=read('2026-11')
    assert result.status_code==200,result.text
    assert {row['id'] for row in result.json()['items']}=={str(missing.id)}
    assert not result.json()['pending']
    assert read('2026-12').json()['items']==[]
    state=change(setup,state,'schedule_tasks',{'task_ids':[str(second.id)],'month':'2026-11'})
    result=read('2026-11').json()
    assert {row['id'] for row in result['items']}=={str(missing.id)}
    assert {row['id'] for row in result['pending']}=={str(second.id)}


def test_pending_drop_preserves_rows_and_checks_month_period_and_revision(setup):
    http,_,_,_,_,_,second=setup
    state=imported(setup,['2026-11'])
    state=change(setup,state,'add_billing_period',{'month':'2026-11'})
    target=next(board for board in state['documents'] if board.get('period_number')==2)
    first=next(board for board in state['documents'] if board.get('period_number')==1)
    state=generate(setup,state,['2026-10'])
    october=state['documents'][-1]
    task_id=str(second.id)
    rows=state['payload']['tasks'][task_id]['rows']
    state=change(setup,state,'schedule_tasks',{'task_ids':[task_id],'month':'2026-11','board_id':target['id']})
    change(setup,state,'accept_pending',{'task_ids':[task_id],'board_id':october['id']},expected=422)
    change(setup,state,'accept_pending',{'task_ids':[task_id],'board_id':first['id']},expected=422)
    old=state
    state=change(setup,state,'accept_pending',{'task_ids':[task_id],'board_id':target['id']})
    assert not state['pending_tasks']
    assert state['payload']['tasks'][task_id]['board_id']==target['id']
    assert state['payload']['tasks'][task_id]['rows']==rows
    change(setup,old,'accept_pending',{'task_ids':[task_id],'board_id':target['id']},expected=409)
    change(setup,state,'accept_pending',{'task_ids':[task_id],'board_id':target['id']},expected=422)
