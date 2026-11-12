"""价格匹配只比较语种、实际单位、币种与计价数量，不把不同来源当成不同单位。"""
from decimal import Decimal
import translation_quantity_basis as basis

def unit(mode,matrix=None,reference=False):
    if mode=='customer_auto':return None if reference else basis.resolve(matrix,mode)[2]
    return str(mode or '').removeprefix('customer_auto:').removeprefix('company_') or None

def matches(left,right,left_matrix=None,right_matrix=None,left_reference=False):
    a,b=unit(left['metric'],left_matrix,left_reference),unit(right['metric'],right_matrix)
    return bool(a and b and a==b and left['language_pair']==right['language_pair'] and left.get('currency','CNY')==right.get('currency','CNY') and Decimal(str(left.get('unit_size') or 1))==Decimal(str(right.get('unit_size') or 1)))

def automatic_reference(references, price, matrix):
    _, dimension, metric, _ = basis.resolve(matrix, price['metric'])
    if not metric:
        return None
    candidates = [
        reference for reference in references
        if ('company' if str(reference['metric']).startswith('company_') else 'customer') == dimension
        and matches(reference, price, right_matrix=matrix, left_reference=True)
    ]
    return candidates[0] if len(candidates) == 1 else None
