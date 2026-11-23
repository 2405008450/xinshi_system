from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest

from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context, project
import translation_revenue as revenue


def entry(client, day, amount, incl=None, currency='CNY'):
    return {'key': client, 'client_id': client, 'client_name': '客户' + client,
            'client_short_name': client, 'day': date.fromisoformat(day),
            'billing_totals': {currency: str(amount)}, 'totals_excl_tax': {currency: str(amount)},
            'totals_incl_tax': {currency: str(incl if incl is not None else amount)}}


def test_revenue_keeps_order_month_after_statement_moves_to_another_month(context):
    from customer_statement_workspace import StatementWorkspace
    http,db,clients,_,_=context;http.app.include_router(revenue.router)
    order=project(db,clients[0],'REVENUE-MOVED',month='2026-11',fixed=True)
    db.add(StatementWorkspace(client_id=clients[0].id,revision=1,payload={
        'boards':[{'id':'moved','name':'十二月对账单','billing_months':['2026-12']}],
        'roots':{},'tasks':{str(order.id):{'id':str(order.id),'board_id':'moved','month':'2026-12','rows':[{'root_id':str(order.id)}]}}}))
    db.commit()
    response=http.get('/translation-revenue',params={'anchor':'2026-11-15','client_id':str(clients[0].id)})
    assert response.status_code==200,response.text
    assert response.json()['overall']['amount']=='500.00'


def test_client_specific_tax_selections_add_together_and_apply_to_comparisons():
    entries = [entry('A', '2026-11-01', 100, 106), entry('B', '2026-11-02', 200, 212),
               entry('A', '2026-10-01', 50, 53), entry('B', '2026-10-02', 100, 106),
               entry('A', '2025-11-01', 25, 26.5), entry('B', '2025-11-02', 50, 53)]
    result = revenue.report(entries, 'month', date(2026, 11, 10), modes={'A': 'excl', 'B': 'incl'})
    assert result['overall']['amount'] == '312.00'
    assert result['overall']['mom']['amount'] == '156.00'
    assert result['overall']['mom']['rate'] == '100.00'
    assert result['overall']['yoy']['amount'] == '78.00'
    assert result['overall']['yoy']['rate'] == '300.00'
    assert result['items'][0]['client_id'] == 'B'
    focus = revenue.report(entries, 'month', date(2026, 11, 10), modes={'B': 'incl'}, focus_client='B')
    assert focus['timeline'][-1]['amount'] == '212.00'
    assert focus['timeline'][-1]['mom']['rate'] == '100.00'


@pytest.mark.parametrize('period,day,start,previous,yoy', [
    ('week', '2026-01-01', '2025-12-29', '2025-12-22', '2024-12-30'),
    ('month', '2026-01-31', '2026-01-01', '2025-12-01', '2025-01-01'),
    ('quarter', '2026-02-28', '2026-01-01', '2025-10-01', '2025-01-01'),
    ('year', '2026-11-10', '2026-01-01', '2025-01-01', '2025-01-01'),
])
def test_calendar_comparisons(period, day, start, previous, yoy):
    result = revenue.report([], period, date.fromisoformat(day))
    assert result['period']['start'] == start
    assert result['previous']['start'] == previous
    assert result['last_year']['start'] == yoy
    assert len(result['timeline']) == 12


def test_week53_no_fake_last_year_week_and_zero_baselines():
    result = revenue.report([entry('A', '2020-12-31', 100)], 'week', date(2020, 12, 31))
    assert result['last_year'] is None
    assert result['overall']['yoy']['state'] == 'unavailable'
    assert result['overall']['mom']['rate'] is None
    assert revenue.comparison(Decimal(0), Decimal(0))['state'] == 'zero'
    assert revenue.comparison(Decimal(0), Decimal(100))['rate'] == '-100.00'
    assert revenue.bounds(date(2024, 2, 1), 'month')['end'] == '2024-02-29'


def test_rank_before_range_and_pagination_with_currency_separation():
    entries = [entry(str(i), '2026-11-01', i * 100) for i in range(1, 31)]
    entries += [entry('外币', '2026-11-01', 999999, currency='USD')]
    data = revenue.report(entries, 'month', date(2026, 11, 10), rank_min=20, rank_max=25,
                          amount_min=Decimal(800), amount_max=Decimal(1100), skip=1, limit=2)
    assert data['total'] == 4 and data['ranked_customers'] == 30
    assert [row['rank'] for row in data['items']] == [21, 22]
    assert data['filtered_amount'] == '3800.00'
    assert data['overall']['amount'] == '46500.00'
    assert revenue.report(entries, 'month', date(2026, 11, 10), currency='USD')['overall']['amount'] == '999999.00'


def test_only_current_period_clients_rank_and_keyword_is_multiword_literal():
    entries = [entry('OLD', '2026-10-01', 300), entry('AA BB%', '2026-11-01', 0)]
    data = revenue.report(entries, 'month', date(2026, 11, 10), keyword='BB% AA')
    assert data['total'] == 1 and data['items'][0]['amount'] == '0.00'
    all_rows = revenue.report(entries, 'month', date(2026, 11, 10))['items']
    assert all(row['key']!='OLD' for row in all_rows)


def test_amount_shortcuts_count_all_keyword_matches_before_range_and_pagination():
    entries = [entry('Alpha A', '2026-11-01', 45000, 50000),
               entry('Alpha B', '2026-11-01', 12000),
               entry('Alpha C', '2026-10-01', 300),
               entry('Other', '2026-11-01', 80000)]
    args = {'modes': {'Alpha A': 'incl'}, 'keyword': 'Alpha', 'limit': 1}
    data = revenue.report(entries, 'month', date(2026, 11, 10), rank_max=1, **args)
    assert data['total'] == 0 and data['amount_shortcut_total'] == 2
    assert data['amount_shortcuts'][:2] == [
        {'min': 50000, 'max': None, 'customers': 1},
        {'min': 10000, 'max': 50000, 'customers': 2},
    ]
    selected = revenue.report(entries, 'month', date(2026, 11, 10), amount_min=10000, amount_max=50000, **args)
    assert selected['amount_shortcuts'] == data['amount_shortcuts']
    assert selected['total'] == 2 and len(selected['items']) == 1


def test_month_year_and_all_history_use_the_selected_date_scope():
    entries=[entry('CURRENT','2026-11-01',100),entry('EARLIER','2026-10-01',200),entry('OLD','2024-11-01',300)]
    monthly=revenue.report(entries,'month',date(2026,11,22))
    assert [row['key'] for row in monthly['items']]==['CURRENT']
    yearly=revenue.report(entries,'year',date(2026,11,22))
    assert yearly['overall']['amount']=='300.00' and {row['key'] for row in yearly['items']}=={'CURRENT','EARLIER'}
    lifetime=revenue.report(entries,'all',date(2026,11,22))
    assert lifetime['overall']['amount']=='600.00' and lifetime['total']==3
    assert lifetime['period']=={'start':'2024-11-01','end':'2026-11-01','label':'历史全部'}
    assert lifetime['previous'] is None and lifetime['last_year'] is None
    assert lifetime['overall']['mom']['state']=='unavailable'


def test_all_history_endpoint_includes_undated_projects(context):
    from sqlalchemy import update
    from models import TranslationProject
    http,db,clients,_,_=context
    http.app.include_router(revenue.router)
    dated=project(db,clients[0],'DATED','2024-11',fixed=True)
    undated=project(db,clients[1],'UNKNOWN','2026-11',fixed=True)
    db.execute(update(TranslationProject).where(TranslationProject.id==undated.id).values(order_no='UNKNOWN',customer_reception_time=None,created_at=None));db.commit()
    response=http.get('/translation-revenue',params={'period':'all','anchor':'2026-11-22','project_type':'translation'})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['total']==2 and data['overall']['amount']=='1000.00'
    assert data['undated_included']==1 and data['missing_date']==0
    assert data['period']['start']=='2024-11-01' and data['partial_period'] is False


def test_order_dates_and_business_timezone_fallback():
    for number, expected in [('TP-261110-001', date(2026,11,10)), ('TP-20240229-001', date(2024,2,29))]:
        assert revenue.order_date(SimpleNamespace(order_no=number,customer_reception_time=None)) == (expected, False)
    fallback = datetime(2026,10,31,20,tzinfo=timezone.utc)
    assert revenue.order_date(SimpleNamespace(order_no='TP-261332-001',customer_reception_time=fallback)) == (date(2026,11,1), True)


def test_endpoint_tax_overrides_ranges_client_scope_and_read_only(context):
    http, db, clients, grants, actor = context
    http.app.include_router(revenue.router)
    a = project(db, clients[0], '001', fixed=True)
    b = project(db, clients[1], '002', fixed=True)
    project(db, clients[0], '003', month='2026-10', fixed=True)
    base = {'anchor':'2026-11-10','client_basis':__import__('json').dumps({str(clients[0].id):'excl',str(clients[1].id):'incl'})}
    response = http.get('/translation-revenue', params=base)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['overall']['amount'] == '1030.00'
    assert data['items'][0]['client_id'] == str(clients[1].id)
    assert data['items'][0]['basis'] == 'incl'
    assert data['generated_at'].endswith('+08:00')
    filtered = http.get('/translation-revenue', params={**base,'amount_min':600,'amount_max':510}).json()
    assert filtered['total'] == 1 and filtered['overall']['amount'] == '1030.00'
    scoped = http.get('/translation-revenue', params={**base,'client_id':str(clients[0].id)}).json()
    assert scoped['overall']['amount'] == '500.00'
    assert http.get('/translation-revenue',params={**base,'client_basis':'[]'}).status_code == 422
    assert http.get('/translation-revenue',params={**base,'amount_min':'NaN'}).status_code == 422
    assert a.customer_charge_items[0].total_excl_tax == 500
    assert b.customer_charge_items[0].total_incl_tax == 530
    grants.clear()
    assert http.get('/translation-revenue',params=base).status_code == 403


def test_hierarchy_counts_only_root_aggregate(environment):
    db, users = environment
    from tests.test_translation_customer_finance import setup, write
    root, child, leaf = setup(db, users[0])
    write(db, users[0], root, root, '0.5')
    result = revenue.revenue(anchor=date(2026,11,10), db=db, user=users[0], client_basis='{}',
                             currency='CNY', period='month', keyword='', rank_min=None,rank_max=None,
                             amount_min=None,amount_max=None,focus_client=None,skip=0,limit=20,
                             manager_ids=None, only_mine=False, client_id=None)
    assert result['overall']['amount'] == '10.00'
    assert sum(row['projects'] for row in result['items']) == 1
    assert result['items'][0]['missing'] == 0
    assert revenue.translation_missing_orders({
        'prices': [{'currency': 'CNY', 'tax_prices': {'unit_price_incl_tax': '0.5'}, 'quantity': None}],
        'word_count_matrix': {'company': {'documents': 1}},
        'children': [], 'pricing_mode': 'metric',
    }, 'totals_excl_tax') == []


def test_current_period_order_details_and_project_type_comparison(context):
    http, db, clients, _, _ = context
    http.app.include_router(revenue.router)
    current = project(db, clients[0], '001', fixed=True)
    project(db, clients[0], '002', month='2026-10', fixed=True)
    project(db, clients[1], '003', fixed=True)
    base = {'anchor': '2026-11-10', 'project_type': 'all'}
    comparison = http.get('/translation-revenue', params=base).json()['project_type_totals']
    assert comparison[0] == {'module': 'translation', 'customers': 2, 'orders': 2, 'amount': '1000.00'}
    assert [item['module'] for item in comparison[1:]] == ['interpretation', 'annotation', 'recruitment']
    assert all(item['orders'] == 0 for item in comparison[1:])
    params = {**base, 'detail_client': str(clients[0].id)}
    response = http.get('/translation-revenue', params=params)
    assert response.status_code == 200, response.text
    [order] = response.json()['items']
    assert order['order_no'] == current.order_no
    assert Decimal(order['totals_excl_tax']['CNY']) == 500
    assert Decimal(order['totals_incl_tax']['CNY']) == 530
    assert http.get('/translation-revenue', params={**params, 'client_id': str(clients[1].id)}).json()['items'] == []


def test_ranking_details_follow_current_period_and_selected_basis(context):
    http, db, clients, _, _ = context
    http.app.include_router(revenue.router)
    client = clients[0]
    current = project(db, client, '001', fixed=True)
    previous = project(db, client, '002', month='2026-10', fixed=True)
    for order in (current, previous):
        order.customer_charge_items[0].total_incl_tax = None
    db.commit()
    params = {'anchor':'2026-11-10','client_id':str(client.id)}
    response = http.get('/translation-revenue', params={
        **params, 'client_basis':__import__('json').dumps({str(client.id):'incl'}),
    })
    assert response.status_code == 200, response.text
    row = response.json()['items'][0]
    assert row['missing'] == 1
    assert row['missing_orders'] == [{
        'order_no':current.order_no, 'project_name':current.project_name,
        'reasons':['固定收费的含税金额未填写'],
    }]
    assert http.get('/translation-revenue', params=params).json()['items'][0]['missing_orders'] == []


@pytest.mark.parametrize('module, prefix', [('interpretation', 'IP'), ('annotation', 'AP'), ('recruitment', 'HP')])
def test_other_modules_load_finance_only_for_selected_dates(context, monkeypatch, module, prefix):
    from interpretation_models import InterpretationProject
    from tests.test_project_customer_finance import project as other_project

    _, db, clients, _, _ = context
    def create(number):
        if module == 'interpretation':
            row = InterpretationProject(id=uuid4(), order_no=number, project_name='测试口译', client_id=clients[0].id)
            db.add(row)
            return row
        row = other_project(db, module, clients[0], number)
        row.order_no = number
        return row

    selected = create(f'{prefix}-261110-001')
    create(f'{prefix}-251110-001')
    fallback = create(f'{prefix}-INVALID-001')
    fallback.customer_confirmation_time = datetime(2026, 11, 12)
    db.commit()
    processed = []
    calculate = revenue.other_amounts

    def track(module, row, record):
        processed.append(row.id)
        return calculate(module, row, record)

    monkeypatch.setattr(revenue, 'other_amounts', track)
    entries, _, fallback_count = revenue.other_entries(db, module, clients[0].id, {}, date(2026, 11, 1), date(2026, 12, 1))
    assert set(processed) == {selected.id, fallback.id}
    assert {entry['day'] for entry in entries} == {date(2026, 11, 10), date(2026, 11, 12)}
    assert fallback_count == 1
