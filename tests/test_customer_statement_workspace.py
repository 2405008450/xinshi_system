"""对账单编排：仅在隔离内存数据库验证，不连接业务库。"""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import inspect
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
import customer_statement_workspace as service
from tools.apply_customer_statement_workspace_migration import apply_migration,TABLES


@pytest.fixture
def setup(context):
    http,db,clients,granted,user=context
    granted.add('projects:write');http.app.include_router(service.router)
    first=project(db,clients[0],'001','2026-10');second=project(db,clients[0],'002','2026-11',fixed=True)
    return http,db,clients,granted,user,first,second


def imported(setup,months=None):
    http,_,_,_,_,first,_=setup
    response=http.post('/translation-statement-workspaces/import',json={'project_id':str(first.id),'months':months or ['2026-10','2026-11'],'revision':0,'confirmed':True})
    assert response.status_code==200,response.text
    return response.json()


def change(setup,state,action,data,mode='children',expected=200):
    http=setup[0]
    response=http.post(f"/translation-statement-workspaces/{state['client_id']}/actions",params={'mode':mode},json={'revision':state['revision'],'action':action,'data':data,'confirmed':True})
    assert response.status_code==expected,response.text
    return response.json()


def test_generation_versions_keep_order_combinations_and_amount_snapshots(setup):
    http,db,clients,_,_,first,second=setup
    path=f'/translation-statement-workspaces/{clients[0].id}'
    body={'client_id':str(clients[0].id),'months':['2026-10'],
          'order_ids':[str(first.id)],'confirmed':True,'revision':0}
    assert http.post(f'{path}/generation-status',json=body).json()=={'exists':False}
    original=http.post('/translation-statement-workspaces/import',json=body)
    assert original.status_code==200,original.text
    assert http.post(f'{path}/generation-status',json=body).json()=={'exists':True}
    before=original.json()['documents'][0]['statement']['totals']
    first.customer_charge_items[0].unit_price_excl_tax=200
    db.commit()
    repeated=http.post('/translation-statement-workspaces/import',json={**body,'revision':1})
    assert repeated.status_code==200,repeated.text
    assert repeated.json()['generation_saved']
    assert repeated.json()['documents'][0]['statement']['totals']==before

    other={**body,'months':['2026-11'],'order_ids':[str(second.id)],'revision':2}
    assert http.post(f'{path}/generation-status',json=other).json()=={'exists':False}
    result=http.post('/translation-statement-workspaces/import',json=other)
    assert result.status_code==200,result.text

    versions=http.get(f'{path}/generation-versions').json()
    assert [row['revision'] for row in versions['items']]==[3,2,1]
    latest,revised,initial=versions['items']
    assert latest['orders']==[second.order_no]
    assert revised['orders']==initial['orders']==[first.order_no]
    snapshot=lambda row:http.get(f"{path}/generation-versions/{row['id']}").json()['documents'][0]['statement']
    assert snapshot(initial)['totals']==before
    assert snapshot(revised)['totals']=={'CNY':'246.80'}
    assert snapshot(revised)['statement_number']==snapshot(initial)['statement_number']


def test_multimonth_import_move_uniqueness_and_original_project_untouched(setup):
    http,db,clients,_,_,first,second=setup
    state=imported(setup);assert len(state['payload']['tasks'])==2
    board1=state['documents'][0]['id']
    assert state['documents'][0]['statement']['totals']=={'CNY':'623.40'}
    state=change(setup,state,'create_board',{'name':'第二份'})
    board2=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(first.id)],'board_id':board2,'month':'2026-12'})
    assert [len(board['statement']['rows']) for board in state['documents']]==[1,1]
    assert state['documents'][1]['statement']['month']=='2026-12'
    assert first.customer_charge_items[0].billing_month=='2026-10'
    body={'project_id':str(first.id),'months':['2026-10','2026-11'],'revision':state['revision'],'confirmed':True,'board_id':board1}
    duplicate=http.post('/translation-statement-workspaces/import',json=body).json()
    assert duplicate['imported']==0 and duplicate['existing']==2
    assert duplicate['payload']['tasks'][str(first.id)]['board_id']==board2
    state=change(setup,duplicate,'restore_task',{'task_ids':[str(first.id)]})
    assert state['payload']['tasks'][str(first.id)]['month']=='2026-10'
    assert state['payload']['tasks'][str(first.id)]['board_id']==board1


def test_statement_windows_separate_project_lists_and_existing_bill_rows(setup):
    from translation_customer_finance import router
    from translation_document_requirements import save

    http,db,clients,_,user,_,ordinary=setup
    http.app.include_router(router)
    special=project(db,clients[0],'003',fixed=True)
    special_only=project(db,clients[1],'004',fixed=True)
    save(db,ordinary,payment_method='individual',actor_id=user.id)
    save(db,special,payment_method='special',statement_required=True,actor_id=user.id)
    save(db,special_only,payment_method='special',statement_required=False,actor_id=user.id)
    db.commit()
    state=imported(setup,['2026-11'])
    assert len(state['payload']['tasks'])==2
    for scope, order in [('standard',ordinary),('special',special)]:
        params={'settlement_scope':scope,'billing_month':'2026-11'}
        page=http.get('/translation-customer-finance/page',params={**params,'client_ids':str(clients[0].id)}).json()
        assert [item['id'] for item in page['items']]==[str(order.id)]
        groups=http.get('/translation-customer-finance/statement-customer-groups',params={
            **params,'statement_required':scope=='special',
        }).json()
        expected={str(clients[0].id),str(clients[1].id)} if scope=='special' else {str(clients[0].id)}
        assert {item['id'] for item in groups['items']}==expected
        workspace=http.get(f"/translation-statement-workspaces/{clients[0].id}",params={'settlement_scope':scope}).json()
        assert set(workspace['payload']['tasks'])=={str(order.id)}
        assert [row['root_id'] for row in workspace['documents'][0]['statement']['rows']]==[str(order.id)]
    groups=http.get('/translation-customer-finance/statement-customer-groups',params={
        'settlement_scope':'special','billing_month':'2026-11','statement_required':False,
    }).json()
    assert groups['items']==[]
    response=http.post('/translation-statement-workspaces/import',json={
        'project_id':str(special_only.id),'months':['2026-11'],'revision':0,'confirmed':True,
        'settlement_scope':'special',
    })
    assert response.status_code==200,response.text
    assert response.json()['documents'][0]['statement']['title']=='特殊结算单'


def test_special_settlement_settings_are_independent_and_can_override_each_child(setup):
    from models import TranslationSubOrder,TranslationSubOrderChargeItem
    import translation_customer_finance as finance

    http,db,clients,_,user,_,root=setup
    http.app.include_router(finance.router)
    root.customer_charge_items.clear()
    children=[]
    for suffix in ('.001','.002'):
        child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+suffix,
                                  sub_project_name='子订单'+suffix,language_pair=root.language_pair)
        db.add(child)
        children.append(child)
    db.commit()
    with pytest.raises(service.HTTPException,match='填写单价'):
        finance.save(db,user,root.id,finance.PriceWrite(version=finance.read(db,root.id)['version'],
                     order_id=root.id,documents_only=True,payment_method='special'))
    for child in children:
        child.customer_charge_items.append(TranslationSubOrderChargeItem(
            id=uuid4(),sequence_no=1,item_name='翻译费',pricing_mode='metric',currency='CNY',
            metric_type='words',unit_size=1,unit_price_excl_tax=2,unit_price_incl_tax=3,
            total_excl_tax=20,total_incl_tax=30,billing_month='2026-11',
        ))
    db.commit()
    finance.save(db,user,root.id,finance.PriceWrite(version=finance.read(db,root.id)['version'],
                 order_id=root.id,documents_only=True,payment_method='special'))
    original=finance.read(db,root.id)
    url=f'/translation-customer-finance/project/{root.id}/special-settlement'
    for child,tax,required,whole in [(children[0],'incl_tax',True,True),(children[1],'excl_tax',False,False)]:
        response=http.put(url,json={'order_id':str(child.id),'apply_to_order':whole,
                                    'tax_mode':tax,'statement_required':required})
        assert response.status_code==200,response.text
    assert finance.read(db,root.id)==original
    response=http.get('/translation-customer-finance/page',params={
        'client_ids':str(clients[0].id),'settlement_scope':'special','billing_month':'2026-11',
    })
    assert response.status_code==200,response.text
    changed=response.json()
    assert [(row['special_tax_mode'],row['statement_required'],row['invoice_required'])
            for row in changed['items'][0]['children']]==[('incl_tax',True,True),('excl_tax',False,False)]
    assert changed['client_subtotals'][0]['totals_excl_tax']=={'CNY':'40.00'}
    assert changed['client_subtotals'][0]['totals_incl_tax']=={'CNY':'60.00'}
    response=http.post('/translation-statement-workspaces/import',json={
        'project_id':str(root.id),'months':['2026-11'],'revision':0,'confirmed':True,'settlement_scope':'special',
    })
    assert response.status_code==200,response.text
    rows=response.json()['documents'][0]['statement']['rows']
    assert [(row['unit_label'],row['subtotal']) for row in rows]==[('含税','30.00'),('不含税','20.00')]
    response=http.put(url,json={'order_id':str(children[0].id),'invoice_status':'issued','invoice_sent':True})
    assert response.status_code==200,response.text
    tracking={'settlement_scope':'special','special_invoice_tracking':True,'invoice_status':'issued'}
    response=http.get('/translation-customer-finance/page',params=tracking)
    assert response.status_code==200,response.text
    invoice,=response.json()['items']
    assert invoice['id']==str(children[0].id) and invoice['special_invoice_sent']
    assert invoice['special_invoice_required'] and invoice['invoice_status']=='unissued'
    standard=http.get('/translation-customer-finance/page',params={
        'settlement_scope':'standard','include_invoice_status':True,
    }).json()
    assert str(root.id) not in {row['id'] for row in standard['items']}
    before_payment=finance.read(db,root.id)
    payment_path=f'/translation-statement-workspaces/{clients[0].id}/special-payment/2026-11'
    deposit={'revision':0,'confirmation':{'is_paid':True,'payment_option':'deposit'},
             'payments':[{'stage_type':'deposit','actual_amount':'20.00'}]}
    response=http.put(payment_path,json=deposit)
    assert response.status_code==200,response.text
    assert response.json()['payments'][0]['actual_amount']=='20.00'
    assert http.put(payment_path,json=deposit).status_code==409
    response=http.put(payment_path,json={'revision':1,'confirmation':{
        'is_paid':True,'payment_option':'full','full_payment_amount':'60.00',
    },'payments':[]})
    assert response.status_code==200,response.text
    assert http.get(payment_path).json()['confirmation']['full_payment_amount']=='60.00'
    assert http.get(payment_path,params={'period_number':2}).json()['revision']==0
    assert finance.read(db,root.id)==before_payment


def test_add_periods_preserves_original_tasks_and_imports_into_selected_period(setup):
    http,_,_,_,_,_,second=setup
    original=imported(setup,['2026-11'])
    first_id=original['documents'][0]['id']
    tasks=original['payload']['tasks']
    second_period=change(setup,original,'add_billing_period',{'month':'2026-11'})
    change(setup,original,'add_billing_period',{'month':'2026-11'},expected=409)
    state=change(setup,second_period,'add_billing_period',{'month':'2026-11'})
    assert state['payload']['tasks']==tasks
    assert [board['statement']['month'] for board in state['documents']]==[
        '2026年11月份第1期','2026年11月份第2期','2026年11月份第3期']
    assert [board['period_number'] for board in state['documents']]==[1,2,3]
    assert state['documents'][0]['id']==first_id
    third_id=state['documents'][2]['id']
    body={'project_id':str(second.id),'months':['2026-11'],'revision':state['revision'],'confirmed':True}
    assert http.post('/translation-statement-workspaces/import',json=body).status_code==422
    new_order=project(setup[1],setup[2][0],'003','2026-11',fixed=True)
    response=http.post('/translation-statement-workspaces/import',json={**body,'board_id':third_id})
    assert response.status_code==200,response.text
    saved=response.json()
    assert saved['payload']['tasks'][str(second.id)]['board_id']==first_id
    assert saved['payload']['tasks'][str(new_order.id)]['board_id']==third_id
    assert saved['payload']['tasks'][str(new_order.id)]['month']=='2026-11'


def test_statement_number_retains_parent_base_across_split_and_new_child(setup):
    state=imported(setup,['2026-11'])
    main=state['documents'][0]
    number=main['statement']['statement_number']
    assert number.startswith('TB-') and '.' not in number
    state=change(setup,state,'split_board',{'task_ids':list(state['payload']['tasks']),'name':'分拆'})
    assert state['documents'][1]['statement']['statement_number']==number+'.01'
    child=state['documents'][1]
    state=change(setup,state,'create_board',{'board_id':main['id'],'name':'新增'})
    assert state['documents'][2]['statement']['statement_number']==number+'.02'
    state=change(setup,state,'rename_board',{'board_id':child['id'],'name':'改名'})
    assert state['documents'][1]['statement']['statement_number']==number+'.01'
    response=setup[0].get(f"/translation-statement-workspaces/{state['client_id']}/excel",
                          params={'revision':state['revision'],'board_ids':child['id']})
    assert response.status_code==200
    sheet=load_workbook(BytesIO(response.content)).active
    assert sheet['A4'].value==f'对账单编号：{number}.01'


def test_billing_period_has_its_own_number_and_repairs_legacy_family_on_save(setup):
    from translation_statement_number import TranslationStatementNumber

    _,db,*_=setup
    state=imported(setup,['2026-11'])
    first=state['documents'][0]
    state=change(setup,state,'add_billing_period',{'month':'2026-11'})
    second=state['documents'][1]
    first_number=first['statement']['statement_number']
    second_number=second['statement']['statement_number']
    assert second_number!=first_number and '.' not in second_number
    state=change(setup,state,'create_board',{'board_id':second['id'],'name':'第二期子单'})
    child=state['documents'][2]
    assert child['statement']['statement_number']==second_number+'.01'

    first_entry=db.get(TranslationStatementNumber,first['id'])
    for index, board in enumerate((second,child), 1):
        entry=db.get(TranslationStatementNumber,board['id'])
        entry.number=f'{first_number}.{index:02d}'
        entry.date_code,entry.sequence,entry.child_sequence=first_entry.date_code,first_entry.sequence,index
    db.commit()

    state=change(setup,state,'create_board',{'board_id':second['id'],'name':'第二期另一张子单'})
    numbers=[board['statement']['statement_number'] for board in state['documents']]
    assert numbers[0]==first_number
    assert numbers[1]!=first_number and '.' not in numbers[1]
    assert numbers[2:]==[numbers[1]+'.01',numbers[1]+'.02']
    state=change(setup,state,'rename_board',{'board_id':second['id'],'name':'第二期'})
    assert [board['statement']['statement_number'] for board in state['documents']]==numbers


def test_new_unpaid_orders_roll_to_next_period_and_keep_group_when_paid(setup):
    from tests.test_translation_payment_filters import paid
    import translation_customer_finance as finance

    http,db,clients,_,actor,_,existing=setup
    http.app.include_router(finance.router)
    paid(db,actor,existing,[{'stage_type':'deposit','actual_amount':20}])
    first=project(db,clients[0],'NEW-A',fixed=True)
    second=project(db,clients[0],'NEW-B',fixed=True)
    assignment=service.place_unpaid_orders_after_paid_period(db,[first],actor)
    assert assignment['number']==2
    board=db.get(service.statement_number.TranslationStatementNumber,assignment['board_id'])
    assert '.' not in board.number
    assert service.place_unpaid_orders_after_paid_period(db,[second],actor)==assignment
    db.commit()
    for order in (first,second):
        item=finance.read(db,order.id)['item']
        assert item['payment_method']=='monthly' and item['settlement_period_number']==2
    paid(db,actor,first,[{'stage_type':'deposit','actual_amount':20}])
    assert finance.read(db,second.id)['item']['payment_method']=='monthly'
    third=project(db,clients[0],'NEW-C',fixed=True)
    assert service.place_unpaid_orders_after_paid_period(db,[third],actor)['number']==3
    db.commit()
    assert finance.read(db,third.id)['item']['payment_method']=='individual'
    summary=finance.payment_summary(db,first,'monthly',include_orders=True)
    assert {row['id'] for row in summary['orders']}=={str(first.id),str(second.id)}


def test_price_window_assigns_new_order_and_moves_existing_statement_task(setup):
    from translation_customer_finance import router

    http, _, (client, _), _, _, first, second = setup
    http.app.include_router(router)
    original = imported(setup, ['2026-11'])
    first_board = original['documents'][0]['id']

    def assign(order, revision, **fields):
        url = f'/translation-statement-workspaces/project/{order.id}/billing-period'
        version = http.get(f'/translation-customer-finance/project/{order.id}').json()['version']
        response = http.put(url, json={'month':'2026-11','revision':revision,'version':version,**fields})
        assert response.status_code == 200, response.text
        return response.json()['item']['billing_period']

    period = assign(first, original['revision'], create_period=True)
    assert period['number'] == 2
    for order, number in [(first, 2), (second, 1)]:
        endpoint = f'/translation-customer-finance/project/{order.id}'
        item = http.get(endpoint).json()['item']
        assert item['settlement_period_number'] == number
        summary = http.get(f'{endpoint}/payment-summary', params={'method':'monthly'}).json()
        assert [entry['id'] for entry in summary['orders']] == [str(order.id)]
    result = http.get('/translation-customer-finance/page', params={'billing_month':'2026-11'}).json()
    assert {item['id'] for item in result['items']} == {str(first.id), str(second.id)}
    options = http.get('/translation-statement-workspaces/period-options/2026-11',
                       params={'client_id':str(client.id),'settlement_scope':'standard'})
    assert options.status_code == 200 and options.json() == [1, 2]
    result = http.get('/translation-customer-finance/page', params={
        'billing_month':'2026-11','period_number':2,'settlement_scope':'standard',
    }).json()
    assert [item['id'] for item in result['items']] == [str(first.id)]
    response = http.post('/translation-statement-workspaces/import', json={
        'project_id':str(first.id),'months':['2026-11'],'revision':original['revision']+1,'confirmed':True,
        'period_number':2,'settlement_scope':'standard',
    })
    assert response.status_code == 200, response.text
    state = response.json()
    assert state['payload']['tasks'][str(first.id)]['board_id'] == period['board_id']
    preview = http.post('/translation-customer-finance/statement-preview', json={
        'client_id':str(client.id),'month':'2026-11','order_ids':[str(first.id),str(second.id)],
        'period_number':2,'settlement_scope':'standard',
    })
    assert preview.status_code==200,preview.text
    target=next(board for board in state['documents'] if board['id']==period['board_id'])
    assert preview.json()['statement_number']==target['statement']['statement_number']
    assert state['payload']['tasks'][str(second.id)]['board_id'] == first_board
    assign(second, state['revision'], board_id=period['board_id'])
    latest = http.get(f"/translation-statement-workspaces/{state['client_id']}").json()
    assert latest['payload']['tasks'][str(second.id)]['board_id'] == period['board_id']
    merged = http.get(f'/translation-customer-finance/project/{first.id}/payment-summary',
                      params={'method':'monthly'}).json()
    assert {entry['id'] for entry in merged['orders']} == {str(first.id), str(second.id)}


def test_statement_company_uses_subject_account_and_prefills_new_invoice(setup,monkeypatch):
    from invoice_workflow import batch_projects
    from invoice_parties import SUBJECTS
    import translation_customer_finance as finance

    http,db,_,_,user,_,order=setup
    monkeypatch.setenv('APP_ENV','production')
    settings_url='/customer-statement-settings'
    for key in ('guangzhou','shenzhen'):
        response=http.put(settings_url,params={'subject_key':key},json={
            'company':SUBJECTS[key][1],'revision':0,'bank_name':f'{key} bank',
            'account_name':SUBJECTS[key][1],'account_number':f'{key}-account',
        })
        assert response.status_code==200,response.text
    current=finance.read(db,order.id)
    finance.save(db,user,order.id,finance.PriceWrite(
        version=current['version'],order_id=order.id,pricing_mode='fixed',
        adjusted_total=500,adjusted_total_incl_tax=530,billing_tax_mode='incl_tax',payment_method='individual',
    ))
    state=imported(setup,['2026-11'])
    board=state['documents'][0]
    assert board['statement']['settings']['account_number']=='guangzhou-account'
    data={'board_id':board['id'],'subject_key':'shenzhen'}
    change(setup,state,'change_company_subject',{**data,'subject_key':'shanghai'},expected=422)
    state=change(setup,state,'change_company_subject',data)
    statement=state['documents'][0]['statement']
    assert statement['company']==SUBJECTS['shenzhen'][1]
    assert statement['settings']['account_number']=='shenzhen-account'
    assert batch_projects(db,[order.id])[0]['default_subject']=='shenzhen'
    response=http.get(f"/translation-statement-workspaces/{state['client_id']}/excel",
                      params={'revision':state['revision'],'board_ids':board['id']})
    assert response.status_code==200,response.text[:300]
    workbook=load_workbook(BytesIO(response.content))
    values={str(value) for row in workbook.active.values for value in row if value is not None}
    assert SUBJECTS['shenzhen'][1] in values and any('shenzhen-account' in value for value in values)


def test_local_workspace_excludes_private_fields_from_documents_and_history(setup,monkeypatch):
    http=setup[0]
    monkeypatch.setenv('APP_ENV','production')
    state=imported(setup)
    board=state['documents'][0]
    state=change(setup,state,'edit_board',{'board_id':board['id'],'fields':{'account_number':'TEST-OA-ACCOUNT'}})
    assert state['documents'][0]['statement']['settings']['account_number']=='TEST-OA-ACCOUNT'
    path=f"/translation-statement-workspaces/{state['client_id']}"

    monkeypatch.setenv('APP_ENV','development')
    local=http.get(path)
    assert local.status_code==200 and 'TEST-OA-ACCOUNT' not in local.text
    assert local.json()['documents'][0]['statement']['stamp_image'] is None
    log=http.get(f'{path}/history')
    assert 'TEST-OA-ACCOUNT' not in log.text
    record_id=log.json()['items'][0]['id']
    assert 'TEST-OA-ACCOUNT' not in http.get(f'{path}/history/{record_id}').text
    change(setup,state,'edit_board',{'board_id':board['id'],'fields':{'account_number':'TEST-LOCAL-ACCOUNT'}},expected=403)
    change(setup,state,'restore_history',{'history_id':record_id})

    monkeypatch.setenv('APP_ENV','production')
    assert http.get(path).json()['documents'][0]['statement']['settings']['account_number']=='TEST-OA-ACCOUNT'


def test_edits_confirmation_audit_restore_and_immutable_identity(setup):
    http,db,_,_,user,first,_=setup
    state=imported(setup);board=state['documents'][0];line=board['statement']['rows'][0]
    target={'board_id':board['id'],'row_id':line['_row_id'],'fields':{'project_name':'对账单专用名称','subtotal':'25.50','remarks':'约定调整'}}
    no_confirm=http.post(f"/translation-statement-workspaces/{state['client_id']}/actions",json={'revision':state['revision'],'action':'edit_row','data':target})
    assert no_confirm.status_code==422
    state=change(setup,state,'edit_row',target)
    changed=state['documents'][0]['statement']['rows'][0]
    assert changed['project_name']=='对账单专用名称' and changed['order_no']==line['order_no']
    assert first.project_name=='测试项目.docx'
    assert Decimal(first.customer_charge_items[0].unit_price_excl_tax)==100
    assert state['documents'][0]['statement']['totals']=={'CNY':'525.50'}
    change(setup,state,'edit_row',{**target,'fields':{'order_no':'OTHER'}},expected=422)
    change(setup,state,'edit_row',{**target,'fields':{'subtotal':'NaN'}},expected=422)
    stale={**state,'revision':1};change(setup,stale,'edit_row',target,expected=409)
    history=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()
    assert history['items'][0]['actor_name']==user.full_name
    assert history['items'][0]['created_at'].endswith('+08:00')
    assert history['items'][0]['changes']['fields']['project_name']['before']=='测试项目.docx'
    state=change(setup,state,'restore_history',{'history_id':history['items'][0]['id']})
    assert state['documents'][0]['statement']['rows'][0]['project_name']=='测试项目.docx'
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['total']==3


def test_header_layout_excel_multisheet_and_formula_escape(setup,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    http,db,_,_,_,first,_=setup
    state=imported(setup);first_board=state['documents'][0]['id']
    state=change(setup,state,'edit_board',{'board_id':first_board,'fields':{'company':'=1+1','title':'合并月结对账单','bank_name':'编排开户行','billing_label':'十月至十一月'}})
    state=change(setup,state,'position_board',{'board_id':first_board,'x':150,'y':35})
    assert state['documents'][0]['x']==150
    state=change(setup,state,'create_board',{'name':'另一份'})
    second_board=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(first.id)],'board_id':second_board,'month':'2026-12'})
    response=http.get(f"/translation-statement-workspaces/{state['client_id']}/excel",params=[('revision',state['revision']),('board_ids',first_board),('board_ids',second_board)])
    assert response.status_code==200,response.text
    workbook=load_workbook(BytesIO(response.content));assert len(workbook.worksheets)==2
    sheet=workbook.worksheets[0]
    assert sheet['A1'].data_type!='f'
    assert sheet['A2'].value=='合并月结对账单'
    assert sheet['A5'].value=='来稿日期'
    assert sheet['B5'].value=='项目名称'
    assert sheet['B6'].value==state['documents'][0]['statement']['rows'][0]['project_name']
    assert not any(cell.value in ('订单号','账单月份') for cell in sheet[5])
    assert any(cell.value=='开户行：编排开户行' for row in sheet for cell in row)
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/excel",params={'revision':1,'board_ids':first_board}).status_code==409


def test_no_cross_customer_restore_and_permissions(setup):
    http,_,clients,granted,_,first,_=setup
    state=imported(setup)
    other=project(setup[1],clients[1],'003')
    new=http.post('/translation-statement-workspaces/import',json={'project_id':str(other.id),'months':['2026-11'],'revision':0,'confirmed':True}).json()
    history=http.get(f"/translation-statement-workspaces/{new['client_id']}/history").json()
    change(setup,state,'restore_history',{'history_id':history['items'][0]['id']},expected=422)
    change(setup,state,'move_tasks',{'task_ids':[str(other.id)],'board_id':state['documents'][0]['id'],'month':'2026-12'},expected=422)
    granted.remove('projects:write')
    change(setup,state,'create_board',{'name':'越权'},expected=403)
    granted.remove('projects:read')
    assert http.get(f'/translation-statement-workspaces/project/{first.id}').status_code==403


def test_create_only_migration_repeatable(setup):
    _,db,*_=setup
    for name in reversed(TABLES):service.Base.metadata.tables[name].drop(db.connection())
    before=set(inspect(db.connection()).get_table_names())
    existing=[item['name'] for item in inspect(db.connection()).get_columns('translation_sub_order_charge_item')]
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())-before==set(TABLES)
    assert existing==[item['name'] for item in inspect(db.connection()).get_columns('translation_sub_order_charge_item')]


def test_delete_selected_boards_releases_tasks_for_regeneration_and_keeps_history(setup):
    http,db,_,_,user,first,second=setup
    state=imported(setup);original=state['documents'][0]['id']
    state=change(setup,state,'create_board',{'name':'保留的一份'})
    keep=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(second.id)],'board_id':keep,'month':'2026-11'})
    state=change(setup,state,'edit_row',{'board_id':original,'row_id':state['documents'][0]['statement']['rows'][0]['_row_id'],'fields':{'project_name':'删除前自定义名称'}})
    stale=deepcopy(state)
    state=change(setup,state,'delete_boards',{'board_ids':[original]})
    assert [board['id'] for board in state['documents']]==[keep]
    assert str(first.id) not in state['payload']['tasks'] and str(second.id) in state['payload']['tasks']
    assert first.project_name=='测试项目.docx'
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    assert log['action']=='删除对账单' and log['actor_name']==user.full_name and log['restorable']
    assert log['changes']['deleted_boards'][0]['name']
    stored=db.get(service.StatementWorkspaceHistory, __import__('uuid').UUID(log['id']))
    assert stored.before['tasks'][str(first.id)]['rows'][0]['project_name']=='删除前自定义名称'
    change(setup,stale,'delete_boards',{'board_ids':[keep]},expected=409)
    restored=change(setup,state,'restore_history',{'history_id':log['id']})
    assert restored['documents'][0]['statement']['rows'][0]['project_name']=='删除前自定义名称'
    state=change(setup,restored,'delete_boards',{'board_ids':[original]})
    response=http.post('/translation-statement-workspaces/import',json={'project_id':str(first.id),'months':['2026-10','2026-11'],'revision':state['revision'],'board_id':keep,'confirmed':True})
    assert response.status_code==200,response.text
    regenerated=response.json();assert regenerated['imported']==1 and regenerated['existing']==1
    assert len(regenerated['payload']['tasks'])==2
    assert regenerated['payload']['tasks'][str(first.id)]['rows'][0]['project_name']=='测试项目.docx'
    assert any(row['action']=='删除对账单' for row in http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'])


def test_delete_all_batch_validation_restore_and_regenerate(setup):
    http,_,clients,granted,_,first,_=setup
    state=imported(setup);state=change(setup,state,'create_board',{'name':'空对账单'})
    ids=[board['id'] for board in state['documents']]
    for data in [{'board_ids':ids},{'board_ids':[]},{'board_ids':[ids[0],ids[0]],'confirmation':'删除'},{'board_ids':[ids[0],str(uuid4())],'confirmation':'删除'}]:
        response=http.post(f"/translation-statement-workspaces/{state['client_id']}/actions",json={'revision':state['revision'],'action':'delete_boards','data':data,'confirmed':True})
        assert response.status_code in (404,422)
    unchanged=http.get(f"/translation-statement-workspaces/{state['client_id']}").json();assert unchanged['revision']==state['revision']
    deleted=change(setup,state,'delete_boards',{'board_ids':ids,'confirmation':'删除'})
    assert deleted['documents']==[] and deleted['payload']['tasks']=={} and deleted['payload']['roots']=={}
    change(setup,deleted,'create_board',{'name':'应提示先生成'},expected=422)
    response=http.post('/translation-statement-workspaces/import',json={'project_id':str(first.id),'months':['2026-10','2026-11'],'revision':deleted['revision'],'confirmed':True})
    assert response.status_code==200,response.text
    regenerated=response.json();assert len(regenerated['documents'])==1 and regenerated['imported']==2
    assert regenerated['documents'][0]['id'] not in ids
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    # 重新生成也可恢复到生成前的空工作区。
    assert log['restorable']
    empty=change(setup,regenerated,'restore_history',{'history_id':log['id']})
    assert not empty['documents']
    granted.remove('projects:write')
    change(setup,empty,'delete_boards',{'board_ids':ids,'confirmation':'删除'},expected=403)


def test_inline_document_edit_audits_every_field_and_moves_month_without_changing_project(setup,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    http,db,_,_,user,first,_=setup
    state=imported(setup);board=state['documents'][0];line=board['statement']['rows'][0]
    state=change(setup,state,'edit_document',{'board_id':board['id'],'fields':{'company':'对账单抬头','title':'核对清单','bank_name':'对账单专用银行'},'rows':[{'row_id':line['_row_id'],'fields':{'project_name':'对账专用名称','subtotal':'42.50','remarks':'协商调整','billing_month':'2026-12'}}]})
    changed=state['documents'][0]['statement'];row=next(item for item in changed['rows'] if item['_row_id']==line['_row_id'])
    assert changed['company']=='对账单抬头' and changed['title']=='核对清单' and changed['settings']['bank_name']=='对账单专用银行'
    assert row['project_name']=='对账专用名称' and row['subtotal']=='42.50' and row['billing_month']=='2026-12'
    assert first.project_name=='测试项目.docx' and first.customer_charge_items[0].billing_month=='2026-10'
    assert first.customer_charge_items[0].unit_price_excl_tax==100
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    assert log['action']=='直接编辑对账单' and log['actor_name']==user.full_name and log['created_at'].endswith('+08:00')
    assert log['changes']['fields']['company']['after']=='对账单抬头'
    assert log['changes']['rows'][0]['fields']['project_name']=={'before':line['project_name'],'after':'对账专用名称'}
    assert log['changes']['rows'][0]['fields']['billing_month']['after']=='2026-12'
    restored=change(setup,state,'restore_history',{'history_id':log['id']})
    assert restored['documents'][0]['statement']['rows'][0]['project_name']==line['project_name']
    assert restored['documents'][0]['statement']['company']==board['statement']['company']


def test_inline_invalid_changes_are_atomic_and_identity_locked(setup):
    http,_,_,_,_,_,_=setup;state=imported(setup);board=state['documents'][0];line=board['statement']['rows'][0]
    for fields in [{'order_no':'FAKE'},{'billing_month':'2026-13'},{'subtotal':'NaN'},{'currency':'bad-code'}]:
        change(setup,state,'edit_document',{'board_id':board['id'],'fields':{'company':'不可部分保存'},'rows':[{'row_id':line['_row_id'],'fields':fields}]},expected=422)
    current=http.get(f"/translation-statement-workspaces/{state['client_id']}").json()
    assert current['revision']==state['revision'] and current['documents'][0]['statement']['company']==board['statement']['company']
    change(setup,state,'edit_document',{'board_id':board['id'],'rows':[{'row_id':'missing','fields':{'remarks':'wrong'}}]},expected=409)
    state=change(setup,state,'edit_document',{'board_id':board['id'],'rows':[{'row_id':line['_row_id'],'fields':{'remarks':'修改一次'}}]})
    change(setup,{**state,'revision':state['revision']-1},'edit_document',{'board_id':board['id'],'rows':[{'row_id':line['_row_id'],'fields':{'remarks':'旧窗口覆盖'}}]},expected=409)


def test_membership_tracks_board_months_delete_restore_and_customer_snapshot(setup):
    import crud
    from translation_statement_status import attach
    http,db,clients,_,_,first,second=setup
    attach(db,[first,second]);assert first.statement_status==[]
    state=imported(setup);board=state['documents'][0]['id']
    root=crud.get_translation_project(db,first.id)
    assert root.statement_status==[{'client_id':str(clients[0].id),'board_id':board,'board_name':'2026-10、2026-11 对账单','months':['2026-10']}]
    state=change(setup,state,'create_board',{'name':'另一个月'})
    other=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(first.id)],'board_id':other,'month':'2027-01'})
    assert crud.get_translation_project(db,first.id).statement_status[0]['months']==['2027-01']
    assert crud.get_translation_project(db,first.id).statement_status[0]['board_id']==other
    # 项目客户改动不应掩盖已独立保存的旧客户对账单归属。
    first.client_id=clients[1].id;db.commit()
    assert crud.get_translation_project(db,first.id).statement_status[0]['client_id']==str(clients[0].id)
    state=change(setup,state,'delete_boards',{'board_ids':[other]})
    assert crud.get_translation_project(db,first.id).statement_status==[]
    assert crud.get_translation_project(db,second.id).statement_status
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    state=change(setup,state,'restore_history',{'history_id':log['id']})
    assert crud.get_translation_project(db,first.id).statement_status[0]['months']==['2027-01']


def test_issue_date_is_frozen_and_month_moves_to_title(setup,monkeypatch):
    from datetime import datetime,timezone,timedelta
    import customer_statement_workspace as service
    import customer_statements as statements
    http,db,clients,*_=setup
    first=datetime(2026,11,5,18,tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(service,'business_now',lambda:first)
    state=imported(setup,['2026-10'])
    board=state['documents'][0]
    assert board['fields']['issue_date']=='2026-11-05'
    monkeypatch.setattr(service,'business_now',lambda:datetime(2026,11,8,18,tzinfo=first.tzinfo))
    fresh=http.get(f"/translation-statement-workspaces/{clients[0].id}").json()
    paper=fresh['documents'][0]['statement']
    assert paper['issue_date']=='2026-11-05'
    assert statements.statement_title(paper)=='对账单'
    # 旧版本从首次生成记录推算日期，不能把再次查看的日期当作出账日。
    row=db.get(service.StatementWorkspace,clients[0].id)
    import copy
    original=copy.deepcopy(row.payload)
    row.payload=copy.deepcopy(original)
    for saved in row.payload['boards']:saved['fields'].pop('issue_date',None)
    assert service.serialize(row,db=db)['documents'][0]['statement']['issue_date']=='2026-11-05'
    row.payload=original


def test_pdf_download_checks_revision_and_board_scope(setup):
    http,db,clients,_,_,_,_=setup
    state=imported(setup);board=state['documents'][0]
    params={'revision':state['revision'],'board_ids':[board['id']]}
    response=http.get(f"/translation-statement-workspaces/{state['client_id']}/pdf",params=params)
    assert response.status_code==200,response.text
    assert response.headers['content-type']=='application/pdf'
    assert response.content.startswith(b'%PDF-') and len(response.content)>1000
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/pdf",params={**params,'revision':0}).status_code==409
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/pdf",params={**params,'board_ids':['unknown']}).status_code==404
