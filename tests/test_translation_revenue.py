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


def test_lost_clients_remain_and_keyword_is_multiword_literal():
    entries = [entry('OLD', '2026-10-01', 300), entry('AA BB%', '2026-11-01', 0)]
    data = revenue.report(entries, 'month', date(2026, 11, 10), keyword='BB% AA')
    assert data['total'] == 1 and data['items'][0]['amount'] == '0.00'
    all_rows = revenue.report(entries, 'month', date(2026, 11, 10))['items']
    old = next(row for row in all_rows if row['key'] == 'OLD')
    assert old['mom']['rate'] == '-100.00'


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
