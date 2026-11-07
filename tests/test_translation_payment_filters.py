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
