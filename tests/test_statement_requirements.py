"""按月确认对账单需求、按客户查看及客户导入：隔离数据库验证。"""
from uuid import uuid4
from datetime import timedelta
import pytest
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from models import Client,SubClient,TranslationProject
from translation_document_requirements import TranslationProjectDocuments
from translation_customer_type import ClientCustomerType
from customer_statement_workspace import router as workspace_router
import translation_customer_finance as finance
import crud


@pytest.fixture
def setup(context):
    http,db,clients,granted,user=context
    granted.add('projects:write');http.app.include_router(finance.router);http.app.include_router(workspace_router)
    october=project(db,clients[0],'001','2026-10');october.order_no='TP-261025-001'
    november=project(db,clients[0],'002','2026-11')
    personal=project(db,clients[1],'003','2026-11')
    db.add(ClientCustomerType(id=uuid4(),client_id=clients[1].id,customer_type='个人客户'));db.commit()
    return http,db,clients,granted,user,october,november,personal


def test_month_page_has_shared_statement_flag_and_total(setup):
    http,db,clients,_,user,october,november,personal=setup
    response=http.get('/translation-customer-finance/page',params={'billing_month':'2026-11','limit':1})
    assert response.status_code==200,response.text
    assert response.json()['total']==2
    rows=http.get('/translation-customer-finance/page',params={'billing_month':'2026-11'}).json()['items']
    assert {row['id']:row['statement_required'] for row in rows}=={str(november.id):True,str(personal.id):False}
    assert all(row['updated_at'].endswith('+08:00') for row in rows)
    previous=http.get('/translation-customer-finance/page',params={'billing_month':'2026-10','keyword':'001 测试项目'}).json()
    assert previous['total']==1 and previous['items'][0]['id']==str(october.id)


def test_full_payments_default_no_statement_and_deposit_still_requires_one(setup):
    import json
    from translation_payment_confirmation import TranslationPaymentConfirmation
    http,db,clients,_,_,october,november,personal=setup
    first=TranslationPaymentConfirmation(project_id=october.id,is_paid=True,payment_option='full',proofs='',revision=1)
    second=TranslationPaymentConfirmation(project_id=november.id,is_paid=True,payment_option='deposit',proofs='',revision=1)
    db.add_all([first,second]);db.commit()
    def flags():return {row['id']:row['statement_required'] for row in http.get('/translation-customer-finance/page').json()['items']}
    assert flags()=={str(october.id):False,str(november.id):True,str(personal.id):False}
    result=http.get('/translation-customer-finance/page',params={'statement_required':False}).json()
    assert {row['id'] for row in result['items']}=={str(october.id),str(personal.id)}
    second.payment_option=json.dumps({'type':'deposit','full_payment':{'source':'details','amount':'100.00','match_status':'matched'}});db.commit()
    assert flags()[str(november.id)] is False
    assert http.get('/translation-customer-finance/statement-customers').json()['total']==0
    second.payment_option=json.dumps({'type':'deposit','full_payment':{'source':'details','amount':'90.00','match_status':'mismatch'}});db.commit()
    assert flags()[str(november.id)] is True
    second.payment_option='full';db.add(TranslationProjectDocuments(project_id=november.id,statement_required=True));db.commit()
    assert flags()[str(november.id)] is True
    assert http.get('/translation-customer-finance/statement-customers').json()['total']==1


def test_quick_update_shared_model_conflicts_and_permission(setup):
    http,db,_,granted,user,_,november,_=setup
    row=http.get('/translation-customer-finance/page',params={'keyword':november.order_no}).json()['items'][0]
    body={'statement_required':False,'expected_statement_required':True,'expected_updated_at':row['updated_at']}
    endpoint=f'/translation-customer-finance/project/{november.id}/statement-required'
    response=http.put(endpoint,json=body);assert response.status_code==200,response.text
    assert response.json()['statement_required'] is False
    assert crud.get_translation_project(db,november.id).statement_required is False
    assert db.get(TranslationProjectDocuments,november.id).statement_required is False
    assert db.get(TranslationProjectDocuments,november.id).updated_by==user.id
    assert http.put(endpoint,json=body).status_code==409
    latest=response.json()
    retry=http.put(endpoint,json={'statement_required':True,'expected_statement_required':False,'expected_updated_at':latest['updated_at']})
    assert retry.status_code==200,retry.text
    granted.remove('projects:write')
    assert http.put(endpoint,json=body).status_code==403


def test_client_filter_defaults_override_multikeyword_and_client_import(setup):
    http,db,clients,_,_,october,november,personal=setup
    endpoint='/translation-customer-finance/statement-customers'
    result=http.get(endpoint).json()
    assert result['total']==1 and result['items'][0]['id']==str(clients[0].id)
    db.add_all([TranslationProjectDocuments(project_id=row.id,statement_required=False) for row in (october,november)])
    db.commit()
    assert http.get(endpoint).json()['total']==0
    assert http.get(endpoint,params={'required_only':False}).json()['total']==2
    response=http.put(f'/translation-customer-finance/project/{personal.id}/statement-required',json={'statement_required':True,'expected_statement_required':False})
    assert response.status_code==200,response.text
    result=http.get(endpoint,params={'keyword':'CL-1 对账客户'}).json()
    assert result['total']==1 and result['items'][0]['id']==str(clients[1].id)
    initial=http.get(f'/translation-statement-workspaces/{clients[1].id}').json()
    assert initial['revision']==0 and initial['documents']==[]
    imported=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[1].id),'months':['2026-11'],'scope':'customer','revision':0,'confirmed':True})
    assert imported.status_code==200,imported.text
    assert imported.json()['client_id']==str(clients[1].id)
    assert len(imported.json()['payload']['tasks'])==1
    skipped=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-10','2026-11'],'scope':'customer','required_only':True,'revision':0,'confirmed':True})
    assert skipped.status_code==200,skipped.text
    assert skipped.json()['imported']==0 and skipped.json()['excluded']==2
    assert not skipped.json()['payload']['tasks']


def test_subclient_parent_group_and_excluded_migrated_projects(setup):
    http,db,clients,_,_,october,november,personal=setup
    sub=SubClient(id=uuid4(),parent_client_id=clients[1].id,sub_client_code='SUB',client_name='分部',client_short_name='分部')
    db.add(sub);db.flush()
    personal.client_id=None;personal.sub_client_id=sub.id
    db.add(ClientCustomerType(id=uuid4(),sub_client_id=sub.id,customer_type='企业客户'));db.commit()
    candidates=http.get('/translation-customer-finance/statement-customers').json()
    assert {row['id'] for row in candidates['items']}=={str(client.id) for client in clients}
    listed=http.get('/translation-customer-finance/page',params={'keyword':personal.order_no}).json()['items'][0]
    assert listed['client_id']==str(clients[1].id) and listed['statement_required'] is True
    personal.annotation_migrated_at=personal.created_at;db.commit()
    assert http.put(f'/translation-customer-finance/project/{personal.id}/statement-required',json={'statement_required':False,'expected_statement_required':True}).status_code==404


def test_requirement_filters_sort_and_pagination(setup):
    http,db,clients,_,_,october,november,personal=setup
    clients[0].client_short_name='Alpha';clients[1].client_short_name='Zulu'
    november.project_status='confirmed';personal.project_status='cancelled';db.commit()
    endpoint='/translation-customer-finance/page'
    base={'billing_month':'2026-11'}
    for flag,expected in [(True,november),(False,personal)]:
        result=http.get(endpoint,params={**base,'statement_required':flag}).json()
        assert result['total']==1 and result['items'][0]['id']==str(expected.id)
    for sort,expected in [('client_short_name_asc',november),('client_short_name_desc',personal)]:
        result=http.get(endpoint,params={**base,'sort':sort,'limit':1}).json()
        assert result['total']==2 and result['items'][0]['id']==str(expected.id)
        other=http.get(endpoint,params={**base,'sort':sort,'limit':1,'skip':1}).json()
        assert other['total']==2 and other['items'][0]['id']!=str(expected.id)
    assert http.get(endpoint,params={**base,'client':'Alpha','project_status':'confirmed','statement_required':True}).json()['total']==1
    assert http.get(endpoint,params={**base,'client':'Alpha','statement_required':False}).json()['total']==0
    db.add(TranslationProjectDocuments(project_id=personal.id,statement_required=True));db.commit()
    assert http.get(endpoint,params={**base,'statement_required':True}).json()['total']==2
    assert http.get(endpoint,params={**base,'sort':'invalid'}).status_code==422


def test_finance_payment_method_is_shared_with_main_table(setup):
    http, _, _, _, _, _, project_row, _ = setup
    url = f'/translation-customer-finance/project/{project_row.id}'
    page_url = '/translation-customer-finance/page'
    current = http.get(url).json()
    assert current['item']['payment_method'] == 'statement'
    for method, required in [('monthly', False), ('statement', True), ('individual', False)]:
        response = http.put(url, json={
            'version': current['version'], 'order_id': str(project_row.id),
            'documents_only': True, 'payment_method': method,
        })
        assert response.status_code == 200, response.text
        current = response.json()
        assert current['item']['payment_method'] == method
        assert current['item']['statement_required'] is required
        row = http.get(page_url, params={'keyword': project_row.order_no}).json()['items'][0]
        assert row['payment_method'] == method
        assert row['statement_required'] is required


def test_finance_payment_defaults_use_customer_month_and_statement_priority(setup):
    http, db, clients, _, _, october, november, personal = setup
    peer = project(db, clients[0], '004', '2026-11')
    db.add_all([
        TranslationProjectDocuments(project_id=october.id, statement_required=False),
        TranslationProjectDocuments(project_id=november.id, statement_required=False),
    ])
    db.commit()
    expected = {str(october.id): 'individual', str(november.id): 'monthly',
                str(peer.id): 'statement', str(personal.id): 'individual'}
    for project_id, method in expected.items():
        item = http.get(f'/translation-customer-finance/project/{project_id}').json()['item']
        assert item['payment_method'] == method
    result = http.get('/translation-customer-finance/page', params={'keyword': november.order_no, 'limit': 1}).json()
    assert result['items'][0]['payment_method'] == 'monthly'
    url = f'/translation-customer-finance/project/{november.id}/statement-required'
    checked = http.put(url, json={'statement_required': True, 'expected_statement_required': False})
    assert checked.status_code == 200, checked.text
    assert checked.json()['payment_method'] == 'statement'
    unchecked = http.put(url, json={'statement_required': False, 'expected_statement_required': True})
    assert unchecked.status_code == 200, unchecked.text
    assert unchecked.json()['payment_method'] == 'monthly'


def test_finance_manager_sort_matches_project_display_before_pagination(setup):
    from project_client_manager import ProjectClientManagerChange

    http, db, clients, _, _, october, november, personal = setup
    clients[0].client_manager = 'Zulu'
    clients[1].client_manager = 'Mike'
    db.add(ProjectClientManagerChange(project_type='translation', project_id=november.id,
        revision=1, new_manager_name='Alpha', reason='调整客户经理'))
    db.add(ProjectClientManagerChange(project_type='translation', project_id=october.id,
        revision=1, reason='取消分配'))
    db.commit()

    for direction, expected in [
        ('asc', [(november, 'Alpha'), (personal, 'Mike'), (october, '')]),
        ('desc', [(personal, 'Mike'), (november, 'Alpha'), (october, '')]),
    ]:
        for skip, (project_row, manager_name) in enumerate(expected):
            response = http.get('/translation-customer-finance/page', params={
                'sort': f'client_manager_{direction}', 'limit': 1, 'skip': skip,
            })
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['total'] == 3
            assert result['items'][0]['id'] == str(project_row.id)
            assert result['items'][0]['client_manager'] == manager_name


def test_copy_same_client_and_bill_month_only(setup):
    http,db,clients,_,user,october,november,personal=setup
    other=project(db,clients[0],'004','2026-11')
    sub=SubClient(id=uuid4(),parent_client_id=clients[0].id,sub_client_code='COPY-SUB',client_name='分部',client_short_name='分部')
    db.add(sub);db.flush();other.client_id=None;other.sub_client_id=sub.id
    for row in (october,november,other):db.add(TranslationProjectDocuments(project_id=row.id,statement_required=False))
    db.commit()
    url=f'/translation-customer-finance/project/{november.id}/statement-required'
    response=http.put(url,json={'statement_required':True,'expected_statement_required':False,'copy_to_same_month':True,'billing_month':'2026-11'})
    assert response.status_code==200,response.text
    assert response.json()['affected_count']==2
    assert crud.get_translation_project(db,november.id).statement_required
    assert crud.get_translation_project(db,other.id).statement_required
    assert not crud.get_translation_project(db,october.id).statement_required
    assert not crud.get_translation_project(db,personal.id).statement_required
    # 子客户只关联母客户时也能按界面显示的客户简称查询、排序。
    name=clients[0].client_short_name
    result=http.get('/translation-customer-finance/page',params={'billing_month':'2026-11','client':name,'sort':'client_short_name_asc'}).json()
    assert result['total']==2
    invalid=http.put(url,json={'statement_required':True,'expected_statement_required':True,'copy_to_same_month':True,'billing_month':'2026-10'})
    assert invalid.status_code==422


def test_price_and_payment_can_sync_no_statement_and_update_customer_default(setup, monkeypatch):
    http, db, clients, granted, _, october, november, personal = setup
    import permission_service
    permission = lambda db, user_id, code: code in granted
    monkeypatch.setattr(finance, 'user_has_permission', permission)
    monkeypatch.setattr(permission_service, 'user_has_permission', permission)
    peer = project(db, clients[0], '005', '2026-11')
    db.add(TranslationProjectDocuments(project_id=october.id, statement_required=True))
    db.commit()

    context = http.get('/translation-customer-finance/statement-requirement-context', params={'project_id': str(november.id)}).json()
    assert context['statement_default'] == 'unknown'
    assert context['other_count'] == 1 and context['can_update_customer']
    endpoint = f'/translation-customer-finance/project/{november.id}'
    draft = http.get(endpoint).json()
    payload = dict(order_id=str(november.id), version=draft['version'], documents_only=True, statement_required=False,
                   statement_sync={'client_id': str(clients[0].id), 'billing_month': context['billing_month']},
                   statement_customer_sync={'client_id': str(clients[0].id), 'revision': context['preference_revision']})
    response = http.put(endpoint, json=payload)
    assert response.status_code == 200, response.text
    assert db.get(TranslationProjectDocuments, peer.id).statement_required is False
    assert db.get(TranslationProjectDocuments, october.id).statement_required is True
    assert db.get(TranslationProjectDocuments, personal.id) is None
    pref = http.get(f'/clients/{clients[0].id}/statement-preference').json()
    assert pref['statement_default'] == 'not_required'

    payload.update(version=response.json()['version'], statement_required=True)
    conflict = http.put(endpoint, json=payload)
    assert conflict.status_code == 409, conflict.text
    db.expire_all()
    assert db.get(TranslationProjectDocuments, peer.id).statement_required is False


def test_finance_page_exposes_real_statement_status(setup):
    http,db,clients,_,_,october,november,personal=setup
    state=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-11'],'scope':'customer','revision':0,'confirmed':True}).json()
    assert state['documents']
    page=http.get('/translation-customer-finance/page',params={'billing_month':'2026-11'}).json()
    by_id={row['id']:row for row in page['items']}
    status=by_id[str(november.id)]['statement_status']
    assert status and status[0]['months']==['2026-11'] and status[0]['board_id']==state['documents'][0]['id']
    assert by_id[str(personal.id)]['statement_status']==[]


def test_group_payment_summary_uses_monthly_projects_and_generated_statement(setup):
    http, db, clients, _, user, _, november, _ = setup
    monthly = project(db, clients[0], '004', '2026-11', fixed=True)
    peer = project(db, clients[0], '005', '2026-11', fixed=True)
    statement = project(db, clients[0], '006', '2026-11', fixed=True)
    db.add_all([
        TranslationProjectDocuments(project_id=monthly.id, statement_required=False),
        TranslationProjectDocuments(project_id=peer.id, statement_required=False),
    ])
    db.commit()
    url = f'/translation-customer-finance/project/{monthly.id}'
    response = http.get(f'{url}/payment-summary', params={'method': 'monthly'})
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary['totals_excl_tax'] == {'CNY': 1000}
    assert summary['totals_incl_tax'] == {'CNY': 1060}
    assert summary['billing_totals'] == {'CNY': 1000}
    assert len(summary['internal_notes']) == 2
    assert not summary['pending']
    assert {'key': 'monthly:CNY', 'label': '订单汇总总价', 'currency': 'CNY',
            'amount': '1000.00', 'taxMode': None} in finance.confirmations.project_totals(db, monthly.id)['items']
    confirmed = finance.confirmations.save(db, monthly.id, finance.confirmations.PaymentConfirmationWrite(
        revision=0, is_paid=True, payment_option='full', full_payment_amount=1000,
        full_payment_total_key='monthly:CNY',
    ), user.id)
    assert confirmed['full_match_status'] == 'matched'

    db.add(TranslationProjectDocuments(project_id=november.id, statement_required=False))
    db.commit()
    imported = http.post('/translation-statement-workspaces/import', json={
        'client_id': str(clients[0].id), 'months': ['2026-11'], 'scope': 'customer',
        'order_ids': [str(statement.id)], 'revision': 0, 'confirmed': True,
    })
    assert imported.status_code == 200, imported.text
    response = http.get(f'/translation-customer-finance/project/{statement.id}/payment-summary', params={'method': 'statement'})
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary['board_name']
    assert [item['id'] for item in summary['statement_projects']] == [str(statement.id)]
    assert summary['billing_totals'] == {'CNY': 500}
    assert not summary['pending']


def test_customer_month_view_exists_even_when_this_project_not_imported(setup):
    http,db,clients,_,user,october,november,personal=setup
    excluded=project(db,clients[0],'099','2026-11')
    db.add(TranslationProjectDocuments(project_id=excluded.id,statement_required=False));db.commit()
    imported=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-11'],'scope':'customer','required_only':True,'revision':0,'confirmed':True}).json()
    result=http.get('/translation-customer-finance/page',params={'billing_month':'2026-11'}).json()
    rows={row['id']:row for row in result['items']}
    assert not rows[str(excluded.id)]['statement_status']
    boards=rows[str(excluded.id)]['customer_statements']
    assert len(boards)==1 and boards[0]['months']==['2026-11']
    assert boards[0]['client_id']==str(clients[0].id)
    assert not rows[str(personal.id)]['customer_statements']
    assert not any('2026-10' in board['months'] for board in boards)
    board_id=imported['documents'][0]['id']
    deleted=http.post(f"/translation-statement-workspaces/{clients[0].id}/actions",json={'revision':imported['revision'],'action':'delete_boards','data':{'board_ids':[board_id]},'confirmed':True})
    assert deleted.status_code==200,deleted.text
    result=http.get('/translation-customer-finance/page',params={'billing_month':'2026-11'}).json()
    assert all(not row['customer_statements'] for row in result['items'])


def test_client_statement_default_only_changes_unset_projects_and_keeps_manual_values(setup):
    http,db,clients,_,user,october,november,personal=setup
    from translation_document_requirements import save as save_documents
    save_documents(db,october,statement_required=True,actor_id=user.id);db.commit()
    initial=http.get(f'/clients/{clients[0].id}/statement-preference').json()
    assert initial['statement_default']=='unknown'
    changed=http.put(f'/clients/{clients[0].id}/statement-preference',json={'revision':initial['revision'],'tax_included':False,'statement_default':'not_required'})
    assert changed.status_code==200,changed.text
    flags={row['id']:row['statement_required'] for row in http.get('/translation-customer-finance/page').json()['items']}
    assert flags[str(october.id)] is True and flags[str(november.id)] is False
    assert crud.get_translation_project(db,november.id).statement_required is False
    assert crud.get_translation_project(db,november.id).statement_required_explicit is False
    # 人工再调整后，即使客户默认再次改变也不覆盖该项目。
    save_documents(db,november,statement_required=False,actor_id=user.id);db.commit()
    changed=http.put(f'/clients/{clients[0].id}/statement-preference',json={'revision':changed.json()['revision'],'tax_included':False,'statement_default':'required'})
    assert changed.status_code==200,changed.text
    assert crud.get_translation_project(db,november.id).statement_required is False
    assert crud.get_translation_project(db,november.id).statement_required_explicit is True
    rows=http.get('/translation-customer-finance/page',params={'statement_required':False}).json()['items']
    assert str(november.id) in {row['id'] for row in rows}


def test_client_default_paid_full_and_unknown_fallback(setup):
    http,db,clients,_,_,october,november,personal=setup
    from translation_payment_confirmation import TranslationPaymentConfirmation
    first=http.put(f'/clients/{clients[1].id}/statement-preference',json={'revision':0,'tax_included':False,'statement_default':'required'})
    assert first.status_code==200,first.text
    assert crud.get_translation_project(db,personal.id).statement_required is True
    # 只修改税口径，不丢失已设置的默认需求。
    tax=http.put(f'/clients/{clients[1].id}/statement-preference',json={'revision':first.json()['revision'],'tax_included':True})
    assert tax.json()['statement_default']=='required'
    db.add(TranslationPaymentConfirmation(project_id=personal.id,is_paid=True,payment_option='full',proofs='',revision=1));db.commit()
    assert crud.get_translation_project(db,personal.id).statement_required is False
    unknown=http.put(f'/clients/{clients[1].id}/statement-preference',json={'revision':tax.json()['revision'],'tax_included':True,'statement_default':'unknown'})
    assert unknown.status_code==200,unknown.text
    assert crud.get_translation_project(db,personal.id).statement_required is False


def test_default_inherits_parent_client_for_subclient_project(setup):
    http,db,clients,_,_,october,november,personal=setup
    sub=SubClient(id=uuid4(),parent_client_id=clients[0].id,sub_client_code='SUB-DEFAULT',client_name='默认规则子客户',client_short_name='子客户')
    db.add(sub);db.commit();november.client_id=None;november.sub_client_id=sub.id;db.commit()
    changed=http.put(f'/clients/{clients[0].id}/statement-preference',json={'revision':0,'tax_included':False,'statement_default':'not_required'})
    assert changed.status_code==200,changed.text
    assert crud.get_translation_project(db,november.id).statement_required is False
    rows=http.get('/translation-customer-finance/page',params={'statement_required':False}).json()['items']
    assert str(november.id) in {row['id'] for row in rows}


def test_customer_default_migration_is_repeatable(environment):
    from customer_statement_defaults import CustomerStatementDefault
    from tools.apply_customer_statement_default_migration import apply_migration
    from sqlalchemy import inspect
    db,_=environment
    CustomerStatementDefault.__table__.drop(db.connection(),checkfirst=True)
    apply_migration(db.connection());apply_migration(db.connection())
    assert inspect(db.connection()).has_table('customer_statement_default')
