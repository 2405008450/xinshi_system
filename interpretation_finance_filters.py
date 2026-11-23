"""口译财务列筛选，在分页与金额汇总之前应用。"""
import json
from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
from search_matching import matches_keywords

TEXT_FIELDS = {'order_no', 'project_name', 'client_short_name', 'directions',
               'workload', 'rates', 'billing_month', 'explanation'}
ENUM_FIELDS = {
    'project_status': {'initial_follow_up', 'deal_pending_execution', 'in_progress', 'cancelled', 'partially_cancelled', 'ended', 'settled'},
    'pricing_mode': {'time', 'fixed'},
    'settlement_mode': {'individual', 'monthly', 'sub_client', 'special'},
    'payment_status': {'unrecorded', 'deposit', 'partial', 'full'},
    'documents': {'quotation', 'invoice', 'none'},
}
MONEY_FIELDS = {'totals_excl_tax', 'totals_incl_tax', 'billing_totals', 'totals', 'adjusted_totals','received_totals','payment_difference'}


class TextFilter(BaseModel):
    model_config = ConfigDict(extra='forbid')
    op: Literal['contains']
    value: str = Field(max_length=500)


class EnumFilter(BaseModel):
    model_config = ConfigDict(extra='forbid')
    op: Literal['in']
    value: list[str] = Field(max_length=30)


class MoneyFilter(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    op: Literal['between']
    min: Decimal | None = None
    max: Decimal | None = None


def parse_filters(raw):
    if not raw:
        return {}
    try:
        if len(raw) > 16000:
            raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict) or len(value) > 18:
            raise ValueError()
        result = {}
        for key, spec in value.items():
            if key in TEXT_FIELDS:
                result[key] = TextFilter.model_validate(spec)
            elif key in ENUM_FIELDS:
                result[key] = EnumFilter.model_validate(spec)
                if not set(result[key].value) <= ENUM_FIELDS[key]:
                    raise ValueError()
            elif key in MONEY_FIELDS:
                result[key] = MoneyFilter.model_validate(spec)
            else:
                raise ValueError()
        return result
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(422, '口译财务筛选条件无效，请清除后重试')


def text_value(item, key):
    payload = item['payload']
    if key == 'client_short_name':
        return '\n'.join(str(item.get(field) or '') for field in (
            'client_short_name', 'parent_client_short_name', 'sub_client_name'))
    if key == 'directions':
        return '\n'.join(row['label'] for row in item.get('directions', []))
    if key in ('workload', 'rates'):
        if item.get('pricing_mode') == 'fixed':
            return '固定收费'
        rows = []
        for row in payload.get('rates', []):
            if key == 'workload':
                rows.append(f"{row['direction']} {row['quantity']} {row['unit']} 每{row['unit']} {row.get('hours') or ''} 小时 "
                            + ('含中午 午餐' if row.get('includes_lunch') else ''))
            else:
                tax = row.get('tax_prices') or {}
                units = [(label, tax.get(field)) for label, field in (
                    ('不含税单价', 'unit_price_excl_tax'), ('含税单价', 'unit_price_incl_tax')) if tax.get(field) is not None]
                if not units:
                    units = [('原单价 税口径未确认', row.get('amount'))]
                rows.extend(f"{row['direction']} {label} {row['currency']} {amount}/{row['unit']}" for label, amount in units)
        return '\n'.join(rows)
    if key == 'explanation':
        return payload.get('explanation') or ''
    return item.get(key) or ''


def matches(item, filters):
    for key, spec in filters.items():
        if key in TEXT_FIELDS:
            if not matches_keywords(text_value(item, key), spec.value):
                return False
        elif key in ENUM_FIELDS:
            setting = item['payload'].get('settlement') or {}
            if key == 'documents':
                values = [label for label, flag in (('quotation', 'quotation_required'), ('invoice', 'invoice_required'))
                          if setting.get(flag)] or ['none']
            elif key == 'payment_status':
                values = [setting.get(key) or 'unrecorded']
            else:
                values = [item.get(key)]
            if spec.value and not set(values).intersection(spec.value):
                return False
        else:
            low, high = spec.min, spec.max
            if low is not None and high is not None and low > high:
                low, high = high, low
            # 各币种分别比较，同一金额必须同时满足上下界。
            if (low is not None or high is not None) and not any(
                (low is None or Decimal(str(amount)) >= low) and (high is None or Decimal(str(amount)) <= high)
                for amount in item.get(key, {}).values()
            ):
                return False
    return True
