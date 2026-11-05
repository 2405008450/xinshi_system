"""财务缺填筛选使用隔离内存库；分页、总数和客户小计沿用相同口径。"""
from uuid import uuid4

import pytest

from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context, project
from word_count_models import WordCountMetric
import translation_customer_finance as finance


@pytest.fixture
def data(context):
    http, db, clients, granted, user = context
    http.app.include_router(finance.router)
    rows = {name: project(db, clients[index % 2], str(index + 1).zfill(3), fixed=name == 'fixed')
            for index, name in enumerate(('empty', 'no_count', 'no_price', 'zero', 'excl', 'incl', 'fixed', 'legacy'))}
    for name in ('empty', 'no_count'):
        db.query(WordCountMetric).filter(WordCountMetric.project_id == rows[name].id).delete(synchronize_session=False)
        db.add(WordCountMetric(id=uuid4(), project_id=rows[name].id, dimension='preliminary', metric_type='words', count_value=999))
    for name in ('empty', 'no_price', 'legacy'):
        charge = rows[name].customer_charge_items[0]
        charge.unit_price = None
        charge.unit_price_excl_tax = None
        charge.unit_price_incl_tax = None
    rows['legacy'].customer_charge_items[0].unit_price = 12
    charge = rows['zero'].customer_charge_items[0]
    charge.unit_price_excl_tax = 0
    charge.unit_price_incl_tax = 0
    db.query(WordCountMetric).filter(WordCountMetric.project_id == rows['zero'].id).update({'count_value': 0}, synchronize_session=False)
    rows['excl'].customer_charge_items[0].unit_price_incl_tax = None
    rows['incl'].customer_charge_items[0].unit_price_excl_tax = None
    db.commit()
    return http, rows


@pytest.mark.parametrize('params,names', [
    ({'missing_word_count': True}, {'empty', 'no_count'}),
    ({'missing_unit_price': True}, {'empty', 'no_price'}),
    ({'missing_word_count': True, 'missing_unit_price': True}, {'empty'}),
    # 历史单价沿用现有不含税计算口径，不能误报为不含税总价为空。
    ({'missing_total': 'excl'}, {'empty', 'no_count', 'no_price', 'incl'}),
    ({'missing_total': 'incl'}, {'empty', 'no_count', 'no_price', 'excl', 'legacy'}),
    ({'missing_total': 'both'}, {'empty', 'no_count', 'no_price'}),
    ({'missing_total': 'either'}, {'empty', 'no_count', 'no_price', 'excl', 'incl', 'legacy'}),
])
def test_missing_finance_fields(data, params, names):
    http, rows = data
    response = http.get('/translation-customer-finance/page', params=params)
    assert response.status_code == 200, response.text
    result = response.json()
    assert {item['id'] for item in result['items']} == {str(rows[name].id) for name in names}
    assert result['total'] == len(names)
    assert sum(group['project_count'] for group in result['client_subtotals']) == len(names)


def test_missing_filters_apply_before_pagination_and_combine_with_keyword(data):
    http, rows = data
    pages = [http.get('/translation-customer-finance/page', params={'missing_unit_price': True, 'skip': skip, 'limit': 1}).json() for skip in (0, 1)]
    assert all(page['total'] == 2 and len(page['items']) == 1 for page in pages)
    assert pages[0]['items'][0]['id'] != pages[1]['items'][0]['id']
    assert pages[0]['client_subtotals'] == pages[1]['client_subtotals']
    result = http.get('/translation-customer-finance/page', params={'missing_unit_price': True, 'keyword': rows['no_price'].order_no}).json()
    assert result['total'] == 1 and result['items'][0]['id'] == str(rows['no_price'].id)


def test_company_statistics_and_fixed_zero_are_not_missing():
    node = {'word_count_matrix': {'company': {'words': 0}, 'customer': {}}, 'pricing_mode': 'fixed', 'totals_excl_tax': {'CNY': '0.00'}, 'totals_incl_tax': {'CNY': '0.00'}}
    assert not finance.matches_missing_fields(node, word_count=True)
    assert not finance.matches_missing_fields(node, unit_price=True)
    assert not finance.matches_missing_fields(node, total='either')


def test_multiple_statuses_share_pagination_totals_and_missing_filters(data):
    from sqlalchemy.orm import object_session
    http, rows = data
    rows['empty'].project_status = 'confirmed'
    rows['no_count'].project_status = 'sent_to_client'
    rows['no_price'].project_status = 'cancelled'
    object_session(rows['empty']).commit()
    params = [('project_statuses', 'confirmed'), ('project_statuses', 'sent_to_client'), ('limit', '1')]
    first = http.get('/translation-customer-finance/page', params=params).json()
    second = http.get('/translation-customer-finance/page', params=params + [('skip', '1')]).json()
    assert first['total'] == second['total'] == 2
    assert {first['items'][0]['id'], second['items'][0]['id']} == {str(rows[name].id) for name in ('empty', 'no_count')}
    assert first['client_subtotals'] == second['client_subtotals']
    assert sum(group['project_count'] for group in first['client_subtotals']) == 2
    missing = http.get('/translation-customer-finance/page', params=params + [('missing_unit_price', 'true')]).json()
    assert missing['total'] == 1 and missing['items'][0]['id'] == str(rows['empty'].id)
    legacy = http.get('/translation-customer-finance/page', params={'project_status': 'confirmed'}).json()
    assert legacy['total'] == 1 and legacy['items'][0]['id'] == str(rows['empty'].id)


@pytest.mark.parametrize('excl,incl,expected', [(None, None, 1), (0, None, 0), (None, 0, 0), (500, None, 0), (None, 530, 0)])
def test_missing_fixed_fee_only_matches_fixed_orders_with_both_amounts_empty(data, excl, incl, expected):
    from sqlalchemy.orm import object_session
    http, rows = data
    charge = rows['fixed'].customer_charge_items[0]
    charge.total_excl_tax = excl
    charge.total_incl_tax = incl
    object_session(charge).commit()
    result = http.get('/translation-customer-finance/page', params={'missing_total': 'fixed'}).json()
    assert result['total'] == expected
    assert {item['id'] for item in result['items']} == ({str(rows['fixed'].id)} if expected else set())
    assert sum(group['project_count'] for group in result['client_subtotals']) == expected
