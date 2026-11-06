"""从直接下级逐级汇总单价展示，不把父级统计再次计费。"""
from decimal import Decimal
from hashlib import sha256
import json
import translation_quantity_basis as basis


def price_rows(node):
    if node.get('prices'):return node['prices']
    if node.get('pricing_mode')=='fixed':
        return [dict(id=None,language_pair=node.get('language_pair') or '',currency=node.get('currency') or 'CNY',metric='fixed',pricing_mode='fixed',unit_size='1',amount=None,
                     tax_prices=None,quantity=None,quantity_metric='fixed',total=node.get('adjusted_total'),
                     fixed_excl_total=node.get('adjusted_total'),fixed_incl_total=node.get('adjusted_total_incl_tax'))]
    quantity,dimension,metric,error=basis.resolve(node.get('word_count_matrix'),'customer_auto')
    return [dict(id=None,language_pair=direction,currency='CNY',metric='customer_auto',unit_size='1',amount=None,tax_prices=None,
                 quantity=quantity,quantity_dimension=dimension,quantity_metric=metric,quantity_error=error,total=None)
            for direction in str(node.get('language_pair') or '').split('；') if direction]


def aggregate_prices(children):
    groups={}
    for child in children:
        for price in price_rows(child):
            metric=price.get('quantity_metric') or basis.resolve(child.get('word_count_matrix'),price.get('metric'))[2]
            tax=price.get('tax_prices') or {}
            signature=[price.get('language_pair'),price.get('currency','CNY'),metric,str(Decimal(str(price.get('unit_size') or 1)).normalize()),
                       str(tax.get('unit_price_excl_tax')),str(tax.get('unit_price_incl_tax')),str(price.get('amount')),price.get('pricing_mode')]
            key=sha256(json.dumps(signature,ensure_ascii=False).encode()).hexdigest()
            if key not in groups:
                groups[key]={**price,'id':None,'summary_only':True,'aggregate_key':key,'metric':'customer_auto:'+metric if metric else 'customer_auto',
                             'quantity_metric':metric,'quantity':None,'quantity_dimension':'suborder_aggregate','total':None,'source_orders':[],
                             '_quantity':Decimal(0),'_total':Decimal(0),'_has_quantity':False,'_has_total':False,'_missing_quantity':False,'_missing_total':False,'_fixed_excl':None,'_fixed_incl':None}
            result=groups[key]
            sources=price.get('source_orders') or [dict(id=child['id'],order_no=child['order_no'],quantity=price.get('quantity'),metric=metric)]
            result['source_orders'].extend(sources)
            if price.get('quantity') is None:result['_missing_quantity']=True
            else:result['_quantity']+=Decimal(str(price['quantity']));result['_has_quantity']=True
            if price.get('total') is None:result['_missing_total']=True
            else:result['_total']+=Decimal(str(price['total']));result['_has_total']=True
            for kind in ('excl','incl'):
                if price.get('fixed_'+kind+'_total') is not None:result['_fixed_'+kind]=(result['_fixed_'+kind] or Decimal(0))+Decimal(str(price['fixed_'+kind+'_total']))
    for row in groups.values():
        row['quantity']=float(row['_quantity']) if row['_has_quantity'] and not row['_missing_quantity'] else None
        row['total']=str(row['_total']) if row['_has_total'] and not row['_missing_total'] else None
        row['quantity_error']='子订单累计，部分数量待补录' if row['_missing_quantity'] else None
        for kind in ('excl','incl'):row['fixed_'+kind+'_total']=str(row['_fixed_'+kind]) if row['_fixed_'+kind] is not None else None
        row['source_orders']=list({source['id']:source for source in row['source_orders']}.values())
        for key in list(row):
            if key.startswith('_'):del row[key]
    return list(groups.values())


def aggregate_node(node,children):
    totals={field:{} for field in ('totals','adjusted_totals','totals_excl_tax','totals_incl_tax','calculated_totals_excl_tax','calculated_totals_incl_tax')}
    for child in children:
        for field,values in totals.items():
            for currency,amount in child.get(field,{}).items():values[currency]=values.get(currency,Decimal(0))+Decimal(str(amount))
    node.update(recorded_prices=node['prices'],recorded_pricing_mode=node['pricing_mode'],recorded_adjusted_total=node.get('adjusted_total'),
                recorded_adjusted_total_incl_tax=node.get('adjusted_total_incl_tax'),price_aggregate=True,pricing_mode='aggregate',
                prices=aggregate_prices(children),adjusted_total=None,adjusted_total_incl_tax=None,quantity=None,own_total=None,
                incomplete=any(child['incomplete'] for child in children),children=children)
    node.update({field:{currency:str(amount.quantize(Decimal('.01'))) for currency,amount in values.items()} for field,values in totals.items()})
