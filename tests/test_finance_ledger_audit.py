from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
import translation_customer_finance as finance


def test_ledger_filters_and_client_totals_use_same_scope(context):
    http,db,clients,_,_=context;http.app.include_router(finance.router)
    metric=project(db,clients[0],'METRIC')
    project(db,clients[0],'FIXED',fixed=True)
    metric.customer_charge_items[0].unit_price_excl_tax=None
    metric.customer_charge_items[0].unit_price_incl_tax=None;db.commit()
    params=dict(ledger_audit=True,billing_month='2026-11',client_ids=str(clients[0].id),unit_price_state='missing')
    response=http.get('/translation-customer-finance/page',params=params)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['total']==1 and data['items'][0]['id']==str(metric.id)
    assert data['ledger_summary']['project_count']==1 and data['ledger_summary']['client_count']==1
    response=http.get('/translation-customer-finance/page',params={**params,'unit_price_state':'filled','pricing_mode':'fixed'})
    assert response.status_code==200,response.text
    assert response.json()['total']==1
