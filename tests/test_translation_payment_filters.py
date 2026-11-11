from decimal import Decimal
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from models import FinanceRecord,FinancePayment
import translation_payment_service as service
import translation_payment_confirmation as confirmation
import translation_customer_finance as finance

def paid(db,actor,row,details,option='deposit'):
    data=service.read(db,row)
    result=service.save(db,row,[service.ProjectPayment(**item) for item in details],data['version'],actor.id,
        confirmation.PaymentConfirmationWrite(is_paid=True,payment_option=option,full_payment_amount=500 if option=='full' else None,full_payment_total_key='excl:CNY' if option=='full' else None))
    db.commit();return result

def test_payment_categories_are_exclusive_and_full_includes_final(context):
    http,db,clients,_,actor=context;http.app.include_router(finance.router)
    unpaid=project(db,clients[0],'UNPAID',fixed=True)
    deposit=project(db,clients[0],'DEPOSIT',fixed=True)
    mid=project(db,clients[1],'MID',fixed=True)
    final=project(db,clients[1],'FINAL',fixed=True)
    full=project(db,clients[0],'FULL',fixed=True)
    paid(db,actor,deposit,[{'stage_type':'deposit','actual_amount':100}])
    paid(db,actor,mid,[{'stage_type':'deposit','actual_amount':100},{'stage_type':'mid','actual_amount':100}])
    paid(db,actor,final,[{'stage_type':'deposit','actual_amount':100},{'stage_type':'mid','actual_amount':100},{'stage_type':'final','actual_amount':300}])
    paid(db,actor,full,[],option='full')
    expected={'unpaid':{str(unpaid.id)},'deposit':{str(deposit.id)},'mid':{str(mid.id)},'full':{str(final.id),str(full.id)}}
    for status,ids in expected.items():
        result=http.get('/translation-customer-finance/page',params={'payment_status':status,'include_payment_status':True,'limit':100})
        assert result.status_code==200,result.text
        assert {item['id'] for item in result.json()['items']}==ids
        assert result.json()['total']==len(ids)
        assert all(item['payment_status']==status for item in result.json()['items'])
    overview=http.get('/translation-customer-finance/page',params={'include_payment_status':True,'limit':100}).json()
    amounts={item['id']:item['payment_actual_total'] for item in overview['items']}
    assert amounts[str(unpaid.id)]=='0.00' and amounts[str(mid.id)]=='200.00'
    assert amounts[str(final.id)]==amounts[str(full.id)]=='500.00'
    chase=http.get('/translation-customer-finance/page',params={'exclude_full':True,'include_payment_status':True,'limit':100}).json()
    assert {item['id'] for item in chase['items']}==expected['unpaid']|expected['deposit']|expected['mid']
    assert chase['total']==3
    paid_result=http.get('/translation-customer-finance/page',params={'payment_status':'paid','include_payment_status':True,'limit':100}).json()
    assert {item['id'] for item in paid_result['items']}==expected['deposit']|expected['mid']|expected['full']
    assert paid_result['total']==4
    partial=http.get('/translation-customer-finance/page',params={'payment_status':'paid','exclude_full':True,'limit':100}).json()
    assert {item['id'] for item in partial['items']}==expected['deposit']|expected['mid']
    assert partial['total']==2
    invalid=http.get('/translation-customer-finance/page',params={'payment_status':'unknown'})
    assert invalid.status_code==422

def test_payment_filter_combines_customer_month_and_pagination(context):
    http,db,clients,_,actor=context;http.app.include_router(finance.router)
    first=project(db,clients[0],'A','2026-10',fixed=True)
    second=project(db,clients[0],'B','2026-10',fixed=True)
    other_month=project(db,clients[0],'C','2026-11',fixed=True)
    other_client=project(db,clients[1],'D','2026-10',fixed=True)
    for row in (first,second,other_month,other_client):paid(db,actor,row,[{'stage_type':'deposit','actual_amount':20}])
    params={'payment_status':'deposit','billing_month':'2026-10','client':clients[0].client_short_name,'limit':1,'include_payment_status':True}
    one=http.get('/translation-customer-finance/page',params=params).json()
    two=http.get('/translation-customer-finance/page',params={**params,'skip':1}).json()
    assert one['total']==two['total']==2
    assert {one['items'][0]['id'],two['items'][0]['id']}=={str(first.id),str(second.id)}
    single=http.get('/translation-customer-finance/page',params={'payment_project_id':str(first.id),'include_payment_status':True}).json()
    assert single['total']==1 and single['items'][0]['id']==str(first.id)


def test_amount_mismatch_uses_current_totals_before_pagination(context):
    http,db,clients,_,actor=context;http.app.include_router(finance.router)
    matched=project(db,clients[0],'MATCHED',fixed=True)
    changed=project(db,clients[0],'CHANGED',fixed=True)
    partial=project(db,clients[0],'PARTIAL',fixed=True)
    unpaid=project(db,clients[0],'UNPAID',fixed=True)
    other=project(db,clients[1],'OTHER',fixed=True)
    final=project(db,clients[0],'FINAL-MISMATCH',fixed=True)
    for row in (matched,changed,other):paid(db,actor,row,[],option='full')
    paid(db,actor,partial,[{'stage_type':'deposit','actual_amount':100}])
    paid(db,actor,final,[{'stage_type':'deposit','actual_amount':100},{'stage_type':'final','actual_amount':400}])
    # 保存时匹配的全款，在收费调整后应实时列入，而非依赖旧核对状态。
    changed.customer_charge_items[0].total_excl_tax=600
    final.customer_charge_items[0].total_excl_tax=600
    db.commit()
    params={'payment_amount_mismatch':True,'include_payment_status':True,
            'client':clients[0].client_short_name,'limit':1}
    expected={str(row.id) for row in (changed,final)}
    pages=[http.get('/translation-customer-finance/page',params={**params,'skip':offset}) for offset in range(2)]
    assert all(response.status_code==200 for response in pages)
    assert all(response.json()['total']==2 for response in pages)
    assert {response.json()['items'][0]['id'] for response in pages}==expected
    assert all(response.json()['items'][0]['payment_amount_mismatch'] for response in pages)
    assert all(response.json()['items'][0]['payment_status']=='full' for response in pages)
    assert all(response.json()['payment_amount_mismatch_filter_applied'] for response in pages)
    full=http.get('/translation-customer-finance/page',params={**params,'payment_status':'full','limit':100}).json()
    assert full['total']==2 and {item['id'] for item in full['items']}==expected
    for status in ('unpaid','deposit','mid'):
        result=http.get('/translation-customer-finance/page',params={**params,'payment_status':status,'billing_month':'2020-01','client':'不存在的客户','limit':100}).json()
        assert result['total']==2 and {item['id'] for item in result['items']}==expected
    reset=http.get('/translation-customer-finance/page',params={**params,'payment_amount_mismatch':False,'limit':100}).json()
    assert reset['total']==5


def test_amount_mismatch_currency_missing_zero_and_reference():
    from translation_payment_filters import payment_amount_mismatches
    node={'payment_actual_total':'0.00','payment_currency':'CNY','billing_totals':{'CNY':'0'}}
    assert not payment_amount_mismatches(node,{})
    assert payment_amount_mismatches({**node,'payment_actual_total':None},{})
    assert payment_amount_mismatches({**node,'billing_totals':{}},{})
    assert payment_amount_mismatches({**node,'billing_totals':{'USD':'0'}},{})
    assert payment_amount_mismatches({**node,'billing_totals':{'CNY':'0','USD':'10'}},{})
    node.update(payment_actual_total='530.00',billing_totals={'CNY':'500'},totals_incl_tax={'CNY':'530'})
    assert payment_amount_mismatches(node,{})
    assert not payment_amount_mismatches(node,{'full_payment_total_key':'incl:CNY'})
    assert payment_amount_mismatches(node,{'full_payment_total_key':'incl:USD'})


def test_finance_header_filters_combine_before_pagination(context):
    http,db,clients,_,actor=context;http.app.include_router(finance.router)
    first=project(db,clients[0],'HEADER-A',fixed=True)
    second=project(db,clients[0],'HEADER-B',fixed=True)
    excluded=project(db,clients[0],'HEADER-C',fixed=True)
    metric=project(db,clients[0],'HEADER-METRIC',fixed=False)
    for row in (first,second,excluded,metric):
        row.project_status='confirmed'
        from translation_document_requirements import save as save_documents
        save_documents(db,row,statement_required=row is not excluded,actor_id=actor.id)
    db.commit()
    for row in (first,second,excluded):paid(db,actor,row,[],option='full')
    params={'pricing_mode':'fixed','payment_status':'full','statement_required':True,
            'project_statuses':['confirmed'],'include_payment_status':True,'limit':1}
    pages=[http.get('/translation-customer-finance/page',params={**params,'skip':skip}) for skip in (0,1)]
    assert all(response.status_code==200 for response in pages)
    assert all(response.json()['total']==2 for response in pages)
    assert {response.json()['items'][0]['id'] for response in pages}=={str(first.id),str(second.id)}
    assert all(response.json()['items'][0]['payment_status']=='full' for response in pages)
    no_statement=http.get('/translation-customer-finance/page',params={**params,'statement_required':False}).json()
    assert no_statement['total']==1 and no_statement['items'][0]['id']==str(excluded.id)
    workload=http.get('/translation-customer-finance/page',params={'pricing_mode':'metric','include_payment_status':True}).json()
    assert workload['total']==1 and workload['items'][0]['id']==str(metric.id)
    assert workload['items'][0]['payment_status']=='unpaid'
    assert http.get('/translation-customer-finance/page',params={'pricing_mode':'invalid'}).status_code==422
