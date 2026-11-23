"""查账追账以结算单元计数和计费，所有写操作均在隔离数据库。"""
from decimal import Decimal
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from tests.test_customer_statement_workspace import setup,imported,change
from translation_document_requirements import save as documents
import translation_customer_finance as finance


def query(setup,**params):
    http=setup[0]
    if not any(getattr(route,'path','')=='/translation-customer-finance/page' for route in http.app.routes):http.app.include_router(finance.router)
    response=http.get('/translation-customer-finance/page',params={'ledger_view':True,'include_payment_status':True,**params})
    assert response.status_code==200,response.text
    return response.json()


def test_statement_is_one_unit_and_total_is_all_pages(setup):
    imported(setup)
    data=query(setup,billing_months=['2026-10','2026-11'],limit=1)
    assert data['total']==1
    unit=data['items'][0]
    assert unit['ledger_kind']=='statement'
    assert len(unit['ledger_orders'])==2
    assert unit['ledger_amounts']=={'CNY':'623.40'}
    assert data['settlement_summary']['billing_totals']=={'CNY':'623.40'}
    response=setup[0].get(f"/translation-statement-workspaces/{setup[2][0].id}/ledger-orders",params=[('months','2026-10'),('months','2026-11')])
    assert response.status_code==200,response.text
    assert len(response.json()['items'])==2


def test_monthly_groups_stay_separate_and_individual_is_one_unit(setup):
    _,db,clients,_,actor,first,second=setup
    documents(db,first,payment_method='monthly',actor_id=actor.id)
    documents(db,second,payment_method='monthly',actor_id=actor.id)
    third=project(db,clients[0],'THIRD',fixed=True)
    documents(db,third,payment_method='monthly',actor_id=actor.id)
    single=project(db,clients[0],'SINGLE',fixed=True)
    documents(db,single,payment_method='individual',actor_id=actor.id);db.commit()
    data=query(setup,billing_months=['2026-10','2026-11'],limit=1)
    assert data['total']==3 and len(data['items'])==1
    assert data['settlement_summary']['billing_totals']=={'CNY':'1623.40'}
    all_units=query(setup,billing_months=['2026-10','2026-11'],limit=100)['items']
    assert sorted(len(row['ledger_orders']) for row in all_units)==[1,1,2]
    assert sum(row['ledger_kind']=='project' for row in all_units)==1


def test_collection_terms_persist_for_client_and_guard_stale_edits(setup):
    http,db,clients,_,actor,first,second=setup
    original=first.customer_charge_items[0].unit_price_excl_tax
    path=f'/translation-statement-workspaces/{clients[0].id}/collection-terms'
    response=http.put(path,json={'revision':0,'value':'（验收后）2月结，月底付款'})
    assert response.status_code==200,response.text
    assert response.json()['updated_at'].endswith('+08:00')
    data=query(setup)
    assert all(unit['payment_terms']=='（验收后）2月结，月底付款' for unit in data['items'])
    assert http.put(path,json={'revision':0,'value':'旧窗口覆盖'}).status_code==409
    assert first.customer_charge_items[0].unit_price_excl_tax==original


def test_cross_month_statement_uses_statement_month_in_ledger(setup):
    http,db,clients,_,actor,first,second=setup
    state=imported(setup,['2026-10']);board=state['documents'][0]
    state=change(setup,state,'move_tasks',dict(task_ids=[str(first.id)],board_id=board['id'],month='2026-12'))
    data=query(setup,billing_months=['2026-12'])
    assert data['total']==1 and data['items'][0]['ledger_kind']=='statement'
    assert data['items'][0]['ledger_orders'][0]['order_no']==first.order_no
    detail=http.get(f'/translation-statement-workspaces/{clients[0].id}/ledger-orders',params={'months':'2026-12'})
    assert detail.status_code==200,detail.text
    assert detail.json()['items'][0]['order_no']==first.order_no
    october=query(setup,billing_months=['2026-10'])
    assert october['total']==0


def test_payment_difference_uses_cumulative_receipts_per_currency():
    from finance_settlement_ledger import payment_difference,settlement_summary
    assert payment_difference({'CNY':'120.00','USD':'9.00'},{'CNY':'200.00','USD':'7.00'})=={'CNY':'-80.00','USD':'2.00'}
    units=[{'ledger_amounts':{'CNY':'200.00'},'ledger_received_totals':{'CNY':'120.00'}},
           {'ledger_amounts':{'CNY':'50.00'},'ledger_received_totals':{'CNY':'60.00'}}]
    totals=settlement_summary(units)
    assert totals['received_totals']=={'CNY':'180.00'}
    assert totals['payment_difference_totals']=={'CNY':'-70.00'}


def test_rebate_saved_with_audit_and_stale_guard_without_changing_project(setup):
    http,db,clients,_,actor,first,second=setup
    before=first.customer_charge_items[0].unit_price_excl_tax
    unit=query(setup)['items'][0]
    path=f'/translation-statement-workspaces/{clients[0].id}/ledger-rebate'
    data=dict(unit_id=unit['id'],revision=0,recipient='测试返点人',rate='10',payment_status='partial',paid_amounts={'CNY':'1.00'},note='隔离记账')
    response=http.put(path,json=data)
    assert response.status_code==200,response.text
    value=response.json()
    assert value['amounts']=={key:f'{Decimal(amount)*Decimal("0.10"):.2f}' for key,amount in unit['ledger_amounts'].items()}
    assert value['updated_at'].endswith('+08:00') and value['actor_name']
    assert http.put(path,json=data).status_code==409
    saved=next(row for row in query(setup)['items'] if row['id']==unit['id'])
    assert saved['ledger_rebate']['paid_amounts']=={'CNY':'1.00'}
    data.update(revision=1,payment_status='full')
    full=http.put(path,json=data)
    assert full.status_code==200,full.text
    assert full.json()['paid_amounts']==full.json()['amounts']
    data.update(revision=2,payment_status='partial',paid_amounts={'CNY':'999999'})
    assert http.put(path,json=data).status_code==422
    assert first.customer_charge_items[0].unit_price_excl_tax==before
