"""特殊结算单独立快照；仅在隔离数据库验证。"""
from copy import deepcopy
from tests.test_customer_statement_workspace import setup,change
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment
from translation_document_requirements import save as save_documents
import customer_statement_workspace as service


def generate(setup,state=None,board=None):
    http,db,clients,_,actor,first,_=setup
    save_documents(db,first,payment_method='special',actor_id=actor.id);db.commit()
    result=http.post('/translation-statement-workspaces/import',json=dict(client_id=str(clients[0].id),months=['2026-10'],revision=state['revision'] if state else 0,scope='customer',confirmed=True,settlement_scope='special',board_id=board))
    assert result.status_code==200,result.text
    return result.json()


def test_same_month_duplicate_projects_are_independent_and_never_sync_finance(setup):
    http,db,clients,_,actor,first,_=setup
    state=generate(setup);original=deepcopy(first.customer_charge_items[0].unit_price_excl_tax)
    state=generate(setup,state)
    assert len(state['documents'])==2
    assert all(board['status']=='active' and board['period_number'] is None for board in state['documents'])
    assert len(state['payload']['tasks'])==2
    assert len({line['task_id'] for task in state['payload']['tasks'].values() for line in task['rows']})==1
    first_board,second_board=state['documents']
    line=first_board['statement']['rows'][0]
    state=change(setup,state,'edit_row',dict(board_id=first_board['id'],row_id=line['_row_id'],fields={'subtotal':'999.00','remarks':'仅本单备注'}))
    assert state['documents'][0]['statement']['totals']=={'CNY':'999.00'}
    assert state['documents'][1]['statement']['totals']!=state['documents'][0]['statement']['totals']
    refreshed=http.get(f"/translation-statement-workspaces/{clients[0].id}",params={'settlement_scope':'special'}).json()
    assert refreshed['documents'][0]['statement']['rows'][0]['remarks']=='仅本单备注'
    assert first.customer_charge_items[0].unit_price_excl_tax==original
    assert service.source.finance.read(db,first.id)['item'].get('customer_explanation','')!='仅本单备注'
    ids=[key for key,task in state['payload']['tasks'].items() if task['board_id']==first_board['id']]
    state=change(setup,state,'remove_special_projects',dict(board_id=first_board['id'],task_ids=ids))
    assert not state['documents'][0]['statement']['rows'] and state['documents'][1]['statement']['rows']
    state=generate(setup,state,first_board['id'])
    assert all(board['statement']['rows'] for board in state['documents'])


def test_special_new_board_has_no_period_and_invoice_is_board_local(setup):
    state=generate(setup);board=state['documents'][0]
    state=change(setup,state,'create_board',{'board_id':board['id'],'name':'另一份'})
    assert [board['period_number'] for board in state['documents']]==[None,None]
    state=change(setup,state,'set_special_invoice',dict(board_id=board['id'],status='issued',proofs='本单发票',subject_key='shenzhen'))
    assert state['payload']['boards'][0]['invoice']['proofs']=='本单发票'
    assert 'invoice' not in state['payload']['boards'][1]
    assert state['payload']['boards'][0]['invoice']['updated_at'].endswith('+08:00')


def test_invoice_preview_uses_statement_amount_and_rejects_stale_document(setup):
    import invoice_workflow
    from tools.apply_invoice_parties_migration import apply_migration
    http,db,clients,_,actor,first,_=setup
    apply_migration(db.connection());db.commit();http.app.include_router(invoice_workflow.router)
    state=generate(setup);board=state['documents'][0]
    line=board['statement']['rows'][0]
    state=change(setup,state,'edit_row',dict(board_id=board['id'],row_id=line['_row_id'],fields={'subtotal':'333.00'}))
    ref=dict(client_id=state['client_id'],board_id=board['id'],revision=state['revision'])
    data=dict(project_ids=[str(first.id)],statement_refs=[ref],settlement_scope='special')
    response=http.post('/invoice-workflow/requests/preview',json=data)
    assert response.status_code==200,response.text
    assert response.json()['statements'][0]['totals']=={'CNY':'333.00'}
    assert response.json()['projects'][0]['totals']=={'CNY':'333.00'}
    from uuid import uuid4
    db.merge(invoice_workflow.InvoiceSettings(key='invoice',user_ids=[str(actor.id)],revision=1));db.commit()
    sent=http.post('/invoice-workflow/requests/batch',json={**data,'subject_key':'guangzhou','invoice_type':'electronic_normal','settings_revision':1,'expected_user_ids':[str(actor.id)],'idempotency_key':str(uuid4())})
    assert sent.status_code==200,sent.text
    assert sent.json()['snapshot']['statements'][0]['totals']=={'CNY':'333.00'}
    listed=http.get('/translation-statement-workspaces/special-invoice-documents',params={'client_id':state['client_id']})
    assert listed.status_code==200,listed.text
    assert listed.json()['items'][0]['totals']=={'CNY':'333.00'}
    state=change(setup,state,'rename_board',dict(board_id=board['id'],name='新版'))
    assert http.post('/invoice-workflow/requests/preview',json=data).status_code==409
