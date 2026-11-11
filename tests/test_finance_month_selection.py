"""多月份查询在分页前过滤，空选不限月份；只使用隔离数据库。"""
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context, project
import translation_customer_finance as finance


def test_multiple_months_all_tabs_and_pagination(context):
    http,db,clients,_,_=context
    http.app.include_router(finance.router)
    rows=[project(db,clients[0],str(index),month,fixed=True) for index,month in enumerate(['2026-07','2026-08','2026-09'])]
    for row,month in zip(rows,['2607','2608','2609']):
        row.order_no=f'TP-{month}10-001'
    db.commit()
    for tab in ({'include_invoice_status':True},{'include_payment_status':True},{'include_payment_status':True,'exclude_full':True}):
        query={**tab,'billing_months':['2026-07','2026-09'],'limit':1}
        first=http.get('/translation-customer-finance/page',params=query)
        assert first.status_code==200,first.text
        second=http.get('/translation-customer-finance/page',params={**query,'skip':1}).json()
        assert first.json()['total']==second['total']==2
        assert {first.json()['items'][0]['id'],second['items'][0]['id']}=={str(rows[0].id),str(rows[2].id)}
        all_time=http.get('/translation-customer-finance/page',params=tab).json()
        assert all_time['total']==3
    legacy=http.get('/translation-customer-finance/page',params={'billing_month':'2026-08'}).json()
    assert legacy['total']==1 and legacy['items'][0]['id']==str(rows[1].id)
    assert http.get('/translation-customer-finance/page',params={'billing_months':['2026-13']}).status_code==422
