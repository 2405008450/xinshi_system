from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
import translation_customer_finance as finance


def test_membership_filters_return_matching_rows_and_totals_including_unassigned(setup):
    http,db,clients,_,_,first,_=setup
    http.app.include_router(finance.router)
    state=imported(setup,['2026-10'])
    board=state['documents'][0]
    project(db,clients[0],'UNBILLED','2026-10')
    def read(**filters):
        response=http.get('/translation-customer-finance/page',params={'client_ids':[str(clients[0].id)],'group_clients':False,**filters})
        assert response.status_code==200,response.text
        return response.json()
    included=read(statement_presence='present')
    assert included['total']==1 and included['items'][0]['id']==str(first.id)
    assert included['items'][0]['statement_status'][0]['board_id']==board['id']
    absent=read(statement_presence='absent')
    assert absent['total']==2 and all(not row['statement_status'] for row in absent['items'])
    assert read(statement_period_state='assigned')['total']==0
    assert read(statement_period_state='unassigned')['total']==3
    state=change(setup,state,'add_billing_period',{'month':'2026-10'})
    assigned=read(statement_period_state='assigned')
    assert assigned['total']==1 and assigned['items'][0]['statement_status'][0]['period_number']==1
    assert read(statement_board_ids=[board['id']])['total']==1
    state=change(setup,state,'set_board_status',{'board_id':board['id'],'status':'void'})
    assert read(statement_presence='present')['total']==0
    assert read(statement_presence='absent')['total']==3
