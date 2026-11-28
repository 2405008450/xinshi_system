"""口译同方向小计及组合合计，逐行保留分币种和独立税口径。"""
from decimal import Decimal, ROUND_HALF_UP

def cents(value):
    return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def apply_adjustments(values, adjustments, basis):
    prefix={'excl_tax':'excl','incl_tax':'incl','legacy':'legacy'}[basis]
    for row in adjustments or []:
        currency=row['currency'];manual=row.get(prefix+'_amount');discount=row.get(prefix+'_discount')
        if manual is not None:values[currency]=cents(manual)
        elif discount is not None and currency in values:values[currency]=cents(values[currency]*Decimal(str(discount))/100)
    return values

def rate_totals(rows,basis,adjust=True):
    groups={}
    for row in rows:groups.setdefault(row['direction'],[]).append(row)
    result={}
    for group in groups.values():
        values={}
        for row in group:
            prices=row.get('tax_prices') or {}
            value=prices.get('total_'+basis) if basis!='legacy' else None
            unit=row.get('amount') if basis=='legacy' else prices.get('unit_price_'+basis)
            if value is None and unit is not None:value=Decimal(str(unit))*Decimal(str(row['quantity']))
            if value is not None:values[row['currency']]=values.get(row['currency'],Decimal(0))+cents(value)
        if adjust:apply_adjustments(values,group[0].get('group_adjustments'),basis)
        for currency,value in values.items():result[currency]=result.get(currency,Decimal(0))+value
    if adjust and rows:apply_adjustments(result,rows[0].get('combined_adjustments'),basis)
    return result

def has_adjustments(rows):
    return any(row.get('group_adjustments') or row.get('combined_adjustments') for row in rows)
