"""查账条件与客户汇总共用同一份筛选结果。"""
from decimal import Decimal


def filter_rows(rows,*,word_count_state=None,unit_price_state=None,document_type=None,document_requirement=None,document_presence=None):
    from translation_customer_finance import matches_missing_fields
    def matches(node):
        for state,word,price in ((word_count_state,True,False),(unit_price_state,False,True)):
            if state and matches_missing_fields(node,word,price)!=(state=='missing'):return False
        if document_type:
            required=node.get(document_type+'_required')
            if document_requirement and required is not {'yes':True,'no':False,'unknown':None}[document_requirement]:return False
            if document_presence:
                present=bool(node.get('statement_status')) if document_type=='statement' else bool(node.get('quotation_draft')) if document_type=='quotation' else node.get('invoice_status') in ('issued','partial')
                if present!=(document_presence=='present'):return False
        return True
    for row in rows:
        row['ledger_word_count_filled']=not matches_missing_fields(row,True,False)
        row['ledger_unit_price_filled']=not matches_missing_fields(row,False,True)
    return [row for row in rows if matches(row)]


def summary(rows):
    from invoice_workflow import selected_incl_totals
    from translation_project_invoices import invoice_required
    clients={};totals={};unissued={}
    def add(target,amounts):
        for currency,value in amounts.items():target[currency]=target.get(currency,Decimal(0))+Decimal(str(value))
    for row in rows:
        key=row.get('client_id') or 'unlinked:'+row['id']
        group=clients.setdefault(key,dict(name=row.get('client_short_name') or row.get('client_name') or '未关联客户',project_count=0,invoice_totals={}))
        group['project_count']+=1
        if invoice_required(row) is True:
            amounts=selected_incl_totals(row)
            add(totals,amounts);add(group['invoice_totals'],amounts)
            if row.get('invoice_status')!='issued':add(unissued,amounts)
    def formatted(values):return {key:f'{value:.2f}' for key,value in values.items()}
    for group in clients.values():group['invoice_totals']=formatted(group['invoice_totals'])
    return dict(project_count=len(rows),client_count=len(clients),invoice_totals=formatted(totals),unissued_totals=formatted(unissued),clients=list(clients.values()))
