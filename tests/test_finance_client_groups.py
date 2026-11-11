from uuid import uuid4
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from models import Client,TranslationSubOrder
import translation_customer_finance as finance

def test_client_order_count_uses_filtered_roots_and_paginates_whole_clients(context):
    http,db,clients,_,_=context;http.app.include_router(finance.router)
    third=Client(id=uuid4(),client_code='CL-3',client_name='第三客户',client_short_name='客户3');db.add(third);db.commit()
    a=[project(db,clients[0],f'A{i}') for i in range(3)]
    b=project(db,clients[1],'B1')
    c=[project(db,third,f'C{i}') for i in range(2)]
    db.add(TranslationSubOrder(id=uuid4(),parent_project_id=b.id,sub_order_no=b.order_no+'.001',sub_project_name='子订单不计客户订单数'))
    a[0].project_status='confirmed';a[1].project_status='confirmed';a[2].project_status='cancelled';db.commit()
    single=http.get('/translation-customer-finance/page',params={'client_order_count':'single'}).json()
    assert single['total']==1 and single['items'][0]['id']==str(b.id)
    params={'client_order_count':'multiple','limit':1}
    first=http.get('/translation-customer-finance/page',params=params).json()
    second=http.get('/translation-customer-finance/page',params={**params,'skip':1}).json()
    assert first['total']==second['total']==2 and first['order_total']==5
    assert len(first['client_groups'])==len(second['client_groups'])==1
    assert len(first['items'])==3 and len(second['items'])==2
    assert len({node['client_id'] for node in first['items']})==1
    assert sum(row['project_count'] for row in first['client_subtotals'])==5
    assert first['client_subtotals']==second['client_subtotals']
    filtered=http.get('/translation-customer-finance/page',params={'client_order_count':'multiple','project_statuses':'confirmed'}).json()
    assert filtered['total']==1 and filtered['order_total']==2
    assert {row['id'] for row in filtered['items']}=={str(a[0].id),str(a[1].id)}
    keyword=http.get('/translation-customer-finance/page',params={'client_order_count':'single','keyword':a[0].order_no}).json()
    assert keyword['total']==1 and keyword['items'][0]['id']==str(a[0].id)

    flat=http.get('/translation-customer-finance/page',params={'client_order_count':'multiple','group_clients':False,'limit':1}).json()
    assert flat['total']==5 and len(flat['items'])==1
    standalone=http.get('/translation-customer-finance/page',params={'paginate_children':True,'keyword':a[0].order_no}).json()
    assert standalone['total']==1 and standalone['items'][0]['page_index']==1
