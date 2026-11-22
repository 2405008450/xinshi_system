from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment


def test_deleted_version_can_be_reactivated_and_same_period_conflicts_require_confirmation(setup):
    http,_,clients,*_=setup
    state=imported(setup,['2026-10']);board=state['documents'][0]
    path=f"/translation-statement-workspaces/{clients[0].id}"
    generated=http.get(path+'/historical-versions').json()['items'][0]
    assert generated['status']=='active'
    state=change(setup,state,'delete_boards',{'board_ids':[board['id']]})
    version=http.get(path+'/historical-versions').json()['items'][0]
    assert version['status']=='void'
    data={'version_id':version['id'],'board_id':board['id'],'status':'active'}
    preview=http.post(path+'/historical-status-preview',json=data)
    assert preview.status_code==200,preview.text
    assert not preview.json()['conflicts']
    state=change(setup,state,'set_historical_status',{**data,'expected_plan':preview.json()['plan']})
    assert state['documents'][0]['status']=='active'
    assert http.get(path+'/historical-versions/'+version['id']).json()['documents'][0]['status']=='active'
    state=change(setup,state,'create_board',{'board_id':board['id'],'name':'本月当前有效单'})
    replacement=state['documents'][-1]
    state=change(setup,state,'set_board_status',{'board_id':board['id'],'status':'void'})
    version=http.get(path+'/historical-versions').json()['items'][0]
    data={**data,'version_id':version['id']}
    state=change(setup,state,'set_board_period',{'board_id':replacement['id'],'period_number':1})
    preview=http.post(path+'/historical-status-preview',json=data)
    assert preview.status_code==200,preview.text
    assert preview.json()['conflicts'][0]['board_id']==replacement['id']
    change(setup,state,'set_historical_status',data,expected=409)
    state=change(setup,state,'set_historical_status',{**data,'expected_plan':preview.json()['plan']})
    active=[item for item in state['documents'] if item['status']=='active']
    assert len(active)==1 and active[0]['id']==board['id']
    state=change(setup,state,'set_historical_status',{**data,'status':'void'})
    assert not [item for item in state['documents'] if item['status']=='active']
