import json
import pytest
from fastapi import HTTPException

from interpretation_finance_filters import matches, parse_filters


def item(**changes):
    return {
        'order_no': 'IP-261101-001', 'project_name': '俄语 展会', 'client_short_name': '客户甲',
        'project_status': 'in_progress', 'directions': [{'label': '中文 ↔ 俄语'}],
        'pricing_mode': 'time', 'billing_month': '2026-11', 'settlement_mode': 'monthly',
        'totals_excl_tax': {'CNY': '3600.00', 'USD': '500.00'},
        'payload': {
            'rates': [{'direction': '中文 ↔ 俄语', 'currency': 'CNY', 'amount': '1800',
                       'quantity': '2', 'unit': '天', 'hours': 8,
                       'tax_prices': {'unit_price_excl_tax': '1800', 'total_excl_tax': '3600'}}],
            'settlement': {'payment_status': 'deposit', 'invoice_required': True},
            'explanation': '含差旅 %_',
        }, **changes,
    }


def test_columns_combine_and_money_range_matches_one_currency():
    filters = parse_filters(json.dumps({
        'project_name': {'op': 'contains', 'value': '展会 俄语'},
        'project_status': {'op': 'in', 'value': ['ended', 'in_progress']},
        'rates': {'op': 'contains', 'value': 'CNY 1800 天'},
        'workload': {'op': 'contains', 'value': '2 8'},
        'documents': {'op': 'in', 'value': ['invoice']},
        'totals_excl_tax': {'op': 'between', 'min': 3700, 'max': 3500},
    }))
    assert matches(item(), filters)
    assert not matches(item(project_status='settled'), filters)
    assert not matches(item(), parse_filters('{"totals_excl_tax":{"op":"between","min":600,"max":3000}}'))
    assert matches(item(), parse_filters('{"explanation":{"op":"contains","value":"%_"}}'))
    assert not matches(item(), parse_filters('{"documents":{"op":"in","value":["none"]}}'))
    assert not matches(item(totals_excl_tax={}), parse_filters('{"totals_excl_tax":{"op":"between","min":0}}'))
    assert matches(item(totals_excl_tax={'CNY': 0}), parse_filters('{"totals_excl_tax":{"op":"between","max":0}}'))


@pytest.mark.parametrize('raw', ['[]', '{"unknown":{}}', '{"rates":{"op":"in","value":[]}}',
                                '{"project_status":{"op":"in","value":["unknown"]}}',
                                '{"totals":{"op":"between","min":"NaN"}}'])
def test_invalid_column_filters_are_rejected(raw):
    with pytest.raises(HTTPException) as error:
        parse_filters(raw)
    assert error.value.status_code == 422
