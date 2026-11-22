"""查账、追账按实际结算单元展示，单据金额优先于原项目参考价。"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID


def money_sum(values):
    result={}
    for value in values:
        for currency,amount in (value or {}).items():
            if amount is not None:result[currency]=result.get(currency,Decimal(0))+Decimal(str(amount))
    return {currency:f'{amount:.2f}' for currency,amount in result.items()}


def rebate_amounts(amounts, rate):
    return {currency:format((Decimal(str(amount))*Decimal(str(rate))/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') for currency,amount in amounts.items()}


def payment_difference(received, payable):
    """分币种计算累计实付减应付，负数为尚欠金额。"""
    return {currency:f'{Decimal(str((received or {}).get(currency,0)))-Decimal(str((payable or {}).get(currency,0))):.2f}'
            for currency in sorted(set(received or {})|set(payable or {}))}


def settlement_summary(units):
    billed=money_sum(unit['ledger_amounts'] for unit in units)
    received=money_sum(unit.get('ledger_received_totals') for unit in units)
    return dict(unit_count=len(units),billing_totals=billed,received_totals=received,
                payment_difference_totals=payment_difference(received,billed),
                pending_count=sum(unit.get('ledger_pending',False) for unit in units))


def order_details(node):
    if node.get('price_aggregate') and node.get('children'):
        return [entry for child in node['children'] for entry in order_details(child)]
    return [dict(order_no=node['order_no'],project_name=node['project_name'],amounts=node.get('billing_totals',{}),billing_month=node.get('billing_month'))]


def statement_details(rows):
    orders={}
    for line in rows:
        if line.get('counted_in_total',True) is False:continue
        key=line['order_no']
        row=orders.setdefault(key,dict(order_no=key,project_name=line['project_name'],billing_month=line.get('billing_month'),amounts={}))
        if line.get('subtotal') is not None:row['amounts']=money_sum([row['amounts'],{line['currency']:line['subtotal']}])
    return list(orders.values())


def statement_root_ids(db,fields,months):
    """按单据月份补入跨月项目，不把订单月份误当作结算月份。"""
    from customer_statement_workspace import StatementWorkspace
    from statement_document_status import months as board_months,normalize
    from models import Client
    from search_matching import matches_keywords
    query=db.query(StatementWorkspace.client_id,StatementWorkspace.payload['boards'],StatementWorkspace.payload['tasks'])
    ids=None
    for key in ('finance_client_ids','finance_client_id'):
        if key in fields:
            value=fields[key]['value'];ids={UUID(str(uid)) for uid in (value if isinstance(value,list) else [value])}
    if fields.get('finance_client'):
        word=fields['finance_client']['value']
        matched={uid for uid,name,short in db.query(Client.id,Client.client_name,Client.client_short_name) if matches_keywords(' '.join([name or '',short or '']),word)}
        ids=matched if ids is None else ids&matched
    if ids is not None:query=query.filter(StatementWorkspace.client_id.in_(ids))
    result=set()
    for uid,boards,tasks in query:
        payload={'boards':boards or [],'tasks':tasks or {}};normalize(payload)
        eligible={board['id'] for board in payload['boards'] if board.get('status')!='void' and (not months or set(months)&set(board_months(payload,board)))}
        result.update(line['root_id'] for task in payload['tasks'].values() if task.get('board_id') in eligible and not task.get('pending') for line in task['rows'])
    return result


def build(db,all_nodes,matched,*,months=None):
    from customer_statement_workspace import StatementWorkspace,display_data
    from statement_document_status import normalize,months as board_months
    from translation_statement_number import numbers,ready as number_ready
    from models import Client
    by_id={node['id']:node for node in all_nodes};wanted={node['id'] for node in matched}
    clients={UUID(node['client_id']) for node in all_nodes if node.get('client_id')}
    clients.update(UUID(link['client_id']) for node in all_nodes for link in node.get('statement_status',[]) if link.get('client_id'))
    workspace_rows={row.client_id:row for row in db.query(StatementWorkspace).filter(StatementWorkspace.client_id.in_(clients))} if clients else {}
    terms={str(uid):(row.payload.get('collection_terms') or {}) for uid,row in workspace_rows.items()}
    names={str(row.id):row.client_short_name or row.client_name for row in db.query(Client).filter(Client.id.in_(clients))} if clients else {}
    units=[];represented=set()
    for uid,workspace in workspace_rows.items():
        from copy import deepcopy
        payload=deepcopy(workspace.payload);normalize(payload)
        board_numbers=numbers(db,uid) if number_ready(db) else {}
        for board in payload['boards']:
            if board.get('status')=='void':continue
            roots={line['root_id'] for task in payload['tasks'].values() if task.get('board_id')==board['id'] and not task.get('pending') for line in task['rows']}
            represented.update(roots)
            if months and not set(months)&set(board_months(payload,board)):continue
            if not roots&wanted:continue
            members=[by_id[key] for key in sorted(roots) if key in by_id]
            if not members:continue
            data=display_data(payload,board,group_directions=False)
            label=('特殊结算对账单 · ' if board.get('settlement_scope')=='special' else '对账单 · ')+(board_numbers.get(board['id']) or board['name'])
            unit={**members[0], 'id':'statement:'+board['id'],'ledger_anchor_id':members[0]['id'],
                  'ledger_kind':'statement','ledger_root_ids':list(roots),'ledger_label':label,'ledger_orders':statement_details(data['rows']),
                  'ledger_board_id':board['id'],'ledger_board_client_id':str(uid),'ledger_months':data['months'],
                  'ledger_amounts':data['totals'],'ledger_pending':bool(data['pending']),
                  'client_id':str(uid),'client_short_name':names.get(str(uid),data['client_name']),
                  'totals_excl_tax':money_sum(node.get('totals_excl_tax') for node in members),
                  'totals_incl_tax':money_sum(node.get('totals_incl_tax') for node in members)}
            units.append(unit);represented.update(roots)
    groups=defaultdict(list)
    for node in all_nodes:
        if node['id'] in represented:continue
        mode=node.get('payment_method')
        key=('merged',node.get('client_id'),node.get('billing_month'),node.get('settlement_period_number'),mode,node.get('sub_client_id') if mode=='sub_client' else None) if mode in ('monthly','statement','sub_client') else ('project',node['id'])
        groups[key].append(node)
    sequence=defaultdict(int)
    for key,members in sorted(groups.items(),key=lambda item:str(item[0])):
        if not any(node['id'] in wanted for node in members):continue
        first=members[0];merged=key[0]=='merged'
        scope=(first.get('client_id'),first.get('billing_month'));sequence[scope]+=1
        label=f"多单合并 {str(first.get('billing_month') or '').replace('-','')}-{sequence[scope]:02d}" if merged else first['project_name']
        units.append({**first,'id':('merged:'+':'.join(str(value) for value in key[1:])) if merged else first['id'],
            'ledger_anchor_id':first['id'],'ledger_root_ids':[node['id'] for node in members],'ledger_kind':'merged' if merged else 'project','ledger_label':label,
            'ledger_orders':[entry for node in members for entry in order_details(node)],
            'ledger_months':sorted({node['billing_month'] for node in members if node.get('billing_month')}),
            'ledger_amounts':money_sum(node.get('billing_totals') for node in members),
            'ledger_pending':any(not node.get('billing_totals') for node in members),
            'totals_excl_tax':money_sum(node.get('totals_excl_tax') for node in members),
            'totals_incl_tax':money_sum(node.get('totals_incl_tax') for node in members)})
    client_orders=defaultdict(list)
    for unit in units:
        members=[by_id[key] for key in unit['ledger_root_ids'] if key in by_id]
        states={node.get('payment_status','unpaid') for node in members}
        unit['ledger_payment_label']='已付全款' if states and states=={'full'} else '部分已付款' if states-{'unpaid'} else '未付款'
        paid={node.get('ledger_payment_source_id',node['id']):{node.get('payment_currency') or 'CNY':node.get('payment_actual_total') or '0'} for node in members}
        unit['ledger_received_totals']=money_sum(paid.values())
        unit['ledger_payment_difference']=payment_difference(unit['ledger_received_totals'],unit['ledger_amounts'])
        for field in ('ledger_word_count_filled','ledger_unit_price_filled'):unit[field]=all(node.get(field,True) for node in members)
        key=unit.get('client_id') or unit['id']
        term=terms.get(key,{})
        unit.update(payment_terms=term.get('value',''),payment_terms_revision=term.get('revision',0))
        owner=workspace_rows.get(UUID(key)) if unit.get('client_id') else None
        unit['ledger_rebate']=((owner.payload.get('ledger_rebates') or {}).get(unit['id'],{}) if owner else {})
        client_orders[key].extend({**row,'settlement_label':unit['ledger_label']} for row in unit['ledger_orders'])
    for unit in units:unit['ledger_client_orders']=client_orders[unit.get('client_id') or unit['id']]
    return units,settlement_summary(units)
