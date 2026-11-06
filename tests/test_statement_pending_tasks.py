from copy import deepcopy
from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment
import translation_document_requirements as documents
import statement_customer_groups as groups


def generate(setup,state,months,**extra):
    http,_,clients,*_=setup
    result=http.post('/translation-statement-workspaces/import',json=dict(client_id=str(clients[0].id),scope='customer',months=months,revision=state['revision'],confirmed=True,**extra))
    assert result.status_code==200,result.text
    return result.json()


def test_future_month_auto_accepts_preserves_edits_and_never_duplicates(setup):
    http,db,clients,_,user,first,_=setup
    state=imported(setup,['2026-10']);board=state['documents'][0];task_id=str(first.id)
    line=board['statement']['rows'][0]
    state=change(setup,state,'edit_row',dict(board_id=board['id'],row_id=line['_row_id'],fields={'project_name':'对账专用名称','subtotal':'66.00'}))
    stored=deepcopy(state['payload']['tasks'][task_id]['rows'])
    state=change(setup,state,'schedule_tasks',dict(task_ids=[task_id],month='2026-11'))
    assert len(state['pending_tasks'])==1 and not state['documents'][0]['statement']['rows']
    assert state['payload']['tasks'][task_id]['board_id'] is None
    assert state['pending_tasks'][0]['created_at'].endswith('+08:00')
    # 原月份重新导入不会使待入账任务回流。
    state=generate(setup,state,['2026-10'])
    assert len(state['pending_tasks'])==1 and not state['documents'][0]['statement']['rows']
    # 显式待入账不被“仅导入需对账单”排除。
    documents.save(db,first,statement_required=False,actor_id=user.id);db.commit()
    state=generate(setup,state,['2026-11'],required_only=True)
    assert state['accepted_pending_count']==1 and not state['pending_tasks']
    target=next(board for board in state['documents'] if board['id']!=state['documents'][0]['id'])
    task=state['payload']['tasks'][task_id]
    assert task['board_id']==target['id'] and task['rows']==stored
    assert task['month']=='2026-11' and first.customer_charge_items[0].billing_month=='2026-10'
    again=generate(setup,state,['2026-11'],required_only=True)
    assert again['accepted_pending_count']==0
    assert sum(task_id in row['task_ids'] for board in again['documents'] for row in board['statement']['rows'])==1
    history=http.get(f"/translation-statement-workspaces/{clients[0].id}/history").json()['items']
    assert any(row['action']=='调整待入账月份' for row in history)
    assert any(row['changes'].get('accepted_pending') for row in history if isinstance(row['changes'],dict))


def test_reschedule_cancel_stale_and_source_deletion_keep_queue(setup):
    state=imported(setup,['2026-10']);task_id=str(setup[5].id);original=state['documents'][0]['id']
    queued=change(setup,state,'schedule_tasks',dict(task_ids=[task_id],month='2026-12'))
    change(setup,state,'schedule_tasks',dict(task_ids=[task_id],month='2026-11'),expected=409)
    queued=change(setup,queued,'schedule_tasks',dict(task_ids=[task_id],month='2027-01'))
    restored=change(setup,queued,'cancel_pending',dict(task_ids=[task_id]))
    assert not restored['pending_tasks'] and restored['payload']['tasks'][task_id]['board_id']==original
    queued=change(setup,restored,'schedule_tasks',dict(task_ids=[task_id],month='2027-01'))
    removed=change(setup,queued,'delete_boards',dict(board_ids=[original]))
    assert len(removed['pending_tasks'])==1
    change(setup,removed,'cancel_pending',dict(task_ids=[task_id]),expected=409)
    state=generate(setup,removed,['2027-01'])
    assert state['accepted_pending_count']==1
    # 删除生成的目标账单后自动回到待入账，重新生成仍会纳入。
    deleted=change(setup,state,'delete_boards',dict(board_ids=[state['documents'][0]['id']]))
    assert len(deleted['pending_tasks'])==1
    regenerated=generate(setup,deleted,['2027-01'])
    assert regenerated['accepted_pending_count']==1 and not regenerated['pending_tasks']


def test_client_with_only_cross_month_pending_still_appears_in_target_month(setup):
    _,db,clients,_,_,first,second=setup
    # 12月没有任何原生项目，跨月任务仍必须显示在需对账单客户栏。
    state=imported(setup,['2026-10'])
    change(setup,state,'schedule_tasks',dict(task_ids=[str(first.id)],month='2026-12'))
    result=groups.customers(db,'2026-12',True,None,0,20)
    assert result['total']==1 and result['items'][0]['pending_count']==1
    assert result['items'][0]['project_count']==0
    assert groups.customers(db,'2026-12',False,None,0,20)['total']==0
