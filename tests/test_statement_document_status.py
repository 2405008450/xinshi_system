from copy import deepcopy
from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment
from statement_document_status import normalize,activate


def test_one_active_per_month_period_and_subclient_including_merged_months():
    def board(uid,months,period=None,child=None):
        return dict(id=uid,billing_months=months,period_number=period,sub_client_id=child)
    payload={'boards':[board('a',['2026-10']),board('merged',['2026-10','2026-11']),
        board('b',['2026-11'],1),board('c',['2026-11'],2),board('d',['2026-11'],1),board('child',['2026-11'],1,'child')],'tasks':{}}
    normalize(payload)
    statuses={b['id']:b['status'] for b in payload['boards']}
    assert statuses==dict(a='void',merged='active',b='void',c='active',d='active',child='active')
    original=deepcopy(payload)
    assert normalize(payload)==[] and original==payload
    payload['boards'][2]['status']='active'
    activate(payload,payload['boards'][2])
    normalize(payload)
    assert payload['boards'][2]['status']=='active' and payload['boards'][4]['status']=='void'


def test_void_and_deleted_statements_have_readable_immutable_archives(setup):
    http,_,clients,*_=setup
    state=imported(setup,['2026-10'])
    original=state['documents'][0]
    path=f"/translation-statement-workspaces/{clients[0].id}"
    state=change(setup,state,'set_board_status',{'board_id':original['id'],'status':'void'})
    assert state['documents'][0]['status']=='void'
    versions=http.get(path+'/historical-versions').json()
    assert versions['total']==2 and versions['items'][0]['status']=='void'
    snapshot=http.get(path+'/historical-versions/'+versions['items'][0]['id']).json()['documents'][0]
    assert snapshot['statement']['totals']==original['statement']['totals'] and snapshot['status']=='void'
    state=change(setup,state,'delete_boards',{'board_ids':[original['id']]})
    assert not state['documents']
    versions=http.get(path+'/historical-versions').json()
    assert versions['total']==3
    deleted=http.get(path+'/historical-versions/'+versions['items'][0]['id']).json()['documents'][0]
    assert deleted['statement']['rows']==original['statement']['rows']
    assert http.get(path+'/historical-versions/'+versions['items'][1]['id']).json()['documents'][0]==snapshot


def test_new_board_advances_period_without_voiding_previous(setup):
    http,_,clients,*_=setup
    state=imported(setup,['2026-11'])
    state=change(setup,state,'add_billing_period',{'month':'2026-11'})
    first,second=state['documents']
    state=change(setup,state,'create_board',{'board_id':second['id'],'name':'第二期替换账单'})
    by_id={board['id']:board for board in state['documents']}
    assert by_id[first['id']]['status']=='active'
    assert by_id[second['id']]['status']=='active'
    replacement=state['documents'][-1]
    assert replacement['status']=='active' and replacement['period_number']==3
    change(setup,state,'set_board_period',{'board_id':replacement['id'],'period_number':2},expected=422)
    state=change(setup,state,'set_board_status',{'board_id':second['id'],'status':'void'})
    state=change(setup,state,'set_board_period',{'board_id':replacement['id'],'period_number':2})
    state=change(setup,state,'set_board_status',{'board_id':second['id'],'status':'active'})
    by_id={board['id']:board for board in state['documents']}
    assert by_id[second['id']]['status']=='active' and by_id[replacement['id']]['status']=='void'
    versions=http.get(f"/translation-statement-workspaces/{clients[0].id}/historical-versions").json()
    assert versions['total']==3
