from tests.test_customer_statement_workspace import setup
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from customer_statement_progress import StatementProgress,StatementProgressEvent
from tools.apply_statement_progress_migration import apply_migration
import translation_customer_finance as finance

def test_customer_progress_month_scope_filter_concurrency_and_history(setup):
    http,db,clients,_,_,first,_=setup
    http.app.include_router(finance.router)
    apply_migration(db.connection());apply_migration(db.connection())
    first.project_status='已确认';db.commit()
    url=f'/translation-customer-finance/statement-customer-groups/{clients[0].id}/progress'
    body={'billing_month':'2026-10','progress':'partial','revision':0}
    result=http.put(url,json=body);assert result.status_code==200,result.text
    assert result.json()=={'progress':'partial','progress_revision':1}
    assert db.query(StatementProgressEvent).count()==1
    assert http.put(url,json={**body,'progress':'completed'}).status_code==409
    assert http.put(url,json={**body,'revision':1}).status_code==200
    assert db.query(StatementProgressEvent).count()==1
    assert db.get(StatementProgress,(clients[0].id,'2026-11')) is None
    from statement_customer_groups import customers
    rows=customers(db,'2026-10',True,None,0,20,progress='partial')
    assert str(clients[0].id) in {item['id'] for item in rows['items']}
    assert customers(db,'2026-10',True,None,0,20,progress='completed')['total']==0
    assert customers(db,'2026-11',True,None,0,20,progress='not_started')['total']>=1
    assert http.put(url,json={**body,'billing_month':'2027-02'}).status_code==422
