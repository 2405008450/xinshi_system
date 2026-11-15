from uuid import uuid4
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from models import Client,TranslationSubOrder
import translation_customer_finance as finance

def test_finance_page_keeps_legacy_proofreading_projects_visible(context):
    http, db, clients, _, _ = context
    http.app.include_router(finance.router)
    order = project(db, clients[0], 'P1')
    order.language_pair = '校对'
    db.commit()

    response = http.get('/translation-customer-finance/page', params={
        'paginate_children': True, 'count_parent_orders': True, 'include_payment_status': True,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['total'] == 1
    assert result['items'][0]['language_pair'] == '校对'


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


def test_display_offset_counts_parent_rows_repeated_across_order_pages():
    def order(order_id, *children):
        return {'id':order_id,'children':list(children)}

    roots=[order('parent',order('a',order('a1'),order('a2')),order('b')),order('standalone')]

    def row_ids(rows):
        return [order_id for row in rows for order_id in (row['id'], *row_ids(row['children']))]

    for skip, expected_offset, expected_rows in [
        (0, 0, ['parent','a','a1']),
        (2, 3, ['parent','a','a2','b']),
        (4, 7, ['standalone']),
    ]:
        rows,total,offset=finance.paginate_child_orders(roots,skip,2)
        assert total==5
        assert offset==expected_offset
        assert row_ids(rows)==expected_rows


def test_finance_page_switches_between_parent_and_all_order_counts(context):
    http, db, clients, _, _ = context
    http.app.include_router(finance.router)
    mother = project(db, clients[0], 'A1')
    for index in range(1, 12):
        db.add(TranslationSubOrder(
            id=uuid4(), parent_project_id=mother.id,
            sub_order_no=f'{mother.order_no}.{index:03d}', sub_project_name=f'子订单 {index}',
        ))
    db.commit()

    url = '/translation-customer-finance/page'
    params = {'keyword': mother.order_no}
    collapsed = http.get(url, params=params).json()
    assert collapsed['total'] == 1
    assert collapsed['items'][0]['id'] == str(mother.id)

    params.update(paginate_children=True, count_parent_orders=True)
    first = http.get(url, params=params).json()
    second = http.get(url, params={**params, 'skip': 10}).json()
    assert first['total'] == second['total'] == 12
    assert first['items'][0]['page_index'] == 1
    assert [row['page_index'] for row in first['items'][0]['children']] == list(range(2, 11))
    assert second['display_offset'] == 10
    assert second['items'][0]['page_index'] is None
    assert [row['page_index'] for row in second['items'][0]['children']] == [11, 12]


def test_finance_page_expands_only_selected_orders_and_counts_visible_rows(context):
    http, db, clients, _, _ = context
    http.app.include_router(finance.router)
    mothers = [project(db, clients[0], number) for number in ('A1', 'A2')]
    for mother in mothers:
        for index in range(1, 12):
            db.add(TranslationSubOrder(
                id=uuid4(), parent_project_id=mother.id,
                sub_order_no=f'{mother.order_no}.{index:03d}', sub_project_name=f'子订单 {index}',
            ))
    db.commit()

    url = '/translation-customer-finance/page'
    params = {'paginate_children': True, 'count_parent_orders': True, 'expand_all_orders': False}
    collapsed = http.get(url, params=params).json()
    assert collapsed['total'] == 2
    assert all(row['has_children'] and not row['children'] for row in collapsed['items'])
    assert [row['child_order_count'] for row in collapsed['items']] == [11, 11]
    selected_id, other_id = (row['id'] for row in collapsed['items'])

    params['order_expansion_ids'] = selected_id
    first = http.get(url, params=params).json()
    second = http.get(url, params={**params, 'skip': 10}).json()
    assert first['total'] == second['total'] == 13
    assert len(first['items']) == 1 and len(first['items'][0]['children']) == 9
    assert first['items'][0]['child_order_count'] == 11
    continued, untouched = second['items']
    assert continued['page_index'] is None
    assert [row['page_index'] for row in continued['children']] == [11, 12]
    assert untouched['id'] == other_id and untouched['has_children'] and not untouched['children']
