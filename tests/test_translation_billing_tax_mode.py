from decimal import Decimal
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
import translation_customer_finance as finance
import translation_billing_tax_mode as billing
import customer_statements as statements


def test_both_prices_choose_included_and_new_statement_uses_selection(context):
    _,db,clients,_,actor=context
    root=project(db,clients[0])
    original=statements.build_statement(db,root.id,None,'2026-11','project')
    data=finance.read(db,root.id)
    saved=finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=data['version'],order_id=root.id,billing_tax_mode='incl_tax'))
    assert saved['item']['billing_totals']=={'CNY':'130.80'}
    assert saved['item']['totals_excl_tax']=={'CNY':'123.40'}
    result=statements.build_statement(db,root.id,None,'2026-11','project')
    assert result['totals']=={'CNY':'130.80'} and result['rows'][0]['unit_label']=='含税'
    assert original['totals']=={'CNY':'123.40'}
    event=finance.audit.history(db,root.id)['items'][0]
    assert event['after']['billing_tax_mode']=='incl_tax'
    assert event['before']['billing_tax_mode'] is None


def test_special_settlement_can_choose_the_only_available_price(context):
    _,db,clients,_,actor=context;root=project(db,clients[0])
    from translation_document_requirements import save
    save(db,root,payment_method='special',actor_id=actor.id)
    billing.save(db,actor,root,root,'excl_tax')
    root.customer_charge_items[0].unit_price_excl_tax=None
    root.customer_charge_items[0].unit_price=None
    db.commit()
    data=finance.read(db,root.id)['item']
    assert data['effective_billing_tax_mode']=='incl_tax'
    assert data['billing_totals']=={'CNY':'130.80'}
    assert statements.build_statement(db,root.id,None,'2026-11','project')['totals']=={'CNY':'130.80'}


def test_tax_included_only_unifies_nested_orders_and_monthly_peers(context):
    from uuid import uuid4
    from models import TranslationSubOrder
    from translation_document_requirements import save
    from word_count_models import WordCountMetric

    _,db,clients,_,actor=context
    root=project(db,clients[0])
    root.customer_charge_items[0].unit_price_excl_tax=None
    root.customer_charge_items[0].unit_price_incl_tax=100
    branch=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=f'{root.order_no}.001',
                               sub_project_name='文件夹',language_pair=root.language_pair)
    db.add(branch)
    leaf=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=f'{branch.sub_order_no}.001',
                             sub_project_name='文件',language_pair=root.language_pair)
    db.add(leaf)
    db.add(WordCountMetric(id=uuid4(),sub_order_id=leaf.id,dimension='customer',
                           metric_type='words',count_value=2000))
    billing.save(db,actor,root,root,'excl_tax')
    db.commit()

    individual=finance.read(db,root.id)['item']
    peer=project(db,clients[0],'002',fixed=True)
    peer.customer_charge_items[0].total_excl_tax=None
    both_prices=project(db,clients[0],'003',fixed=True)
    for order in (root,peer,both_prices):
        save(db,order,payment_method='monthly',actor_id=actor.id)
        billing.save(db,actor,order,order,'excl_tax')
    db.commit()

    def verify(node,amount):
        assert node['effective_billing_tax_mode']=='incl_tax'
        assert node['billing_totals']=={'CNY':amount}
        assert node['totals_excl_tax']=={}
        assert not node['billing_tax_pending']
        assert node['invoice_required'] and node['statement_required']

    verify(individual,'200.00')
    mother=finance.read(db,root.id)['item']
    for node in (mother,mother['children'][0],mother['children'][0]['children'][0]):
        verify(node,'200.00')
    verify(finance.read(db,peer.id)['item'],'530.00')
    both=finance.read(db,both_prices.id)['item']
    assert both['effective_billing_tax_mode']=='incl_tax'
    assert both['billing_totals']=={'CNY':'530.00'}
    assert both['totals_excl_tax']=={'CNY':'500.00'}


def test_child_tax_change_unifies_monthly_orders_and_both_document_requirements(context):
    from uuid import uuid4
    from models import TranslationSubOrder
    from translation_document_requirements import save
    from word_count_models import WordCountMetric

    http,db,clients,permissions,actor=context
    permissions.add('projects:write')
    http.app.include_router(finance.router)
    root=project(db,clients[0],'001')
    peer=project(db,clients[0],'002',fixed=True)
    special=project(db,clients[0],'003',fixed=True)
    child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=f'{root.order_no}.001',
                              sub_project_name='文件',language_pair=root.language_pair)
    db.add(child)
    save(db,root,payment_method='monthly',actor_id=actor.id)
    save(db,peer,payment_method='monthly',actor_id=actor.id)
    save(db,special,payment_method='special',invoice_required=True,statement_required=True,actor_id=actor.id)
    db.commit()
    url=f'/translation-customer-finance/project/{root.id}'
    current=http.get(url).json()
    payload={'version':current['version'],'order_id':str(child.id),'documents_only':True}
    for field in ('invoice_required','statement_required'):
        rejected=http.put(url,json={**payload,field:True})
        assert rejected.status_code==422
    response=http.put(url,json={**payload,'billing_tax_mode':'incl_tax'})
    assert response.status_code==200,response.text
    mother=response.json()['item']
    peer_item=finance.read(db,peer.id)['item']
    for order in (mother,mother['children'][0],peer_item):
        assert order['effective_billing_tax_mode']=='incl_tax'
        assert order['invoice_required'] and order['statement_required']
    special_item=finance.read(db,special.id)['item']
    assert special_item['effective_billing_tax_mode']=='excl_tax'
    assert special_item['invoice_required'] and special_item['statement_required']
    summary=http.get(f'{url}/payment-summary',params={'method':'monthly'}).json()
    assert {row['id'] for row in summary['orders']}=={str(root.id),str(peer.id)}
    assert summary['pending']
    filtered=http.get('/translation-customer-finance/page',params={'statement_required':True}).json()
    assert {row['id'] for row in filtered['items']}=={str(root.id),str(peer.id),str(special.id)}

    db.add(WordCountMetric(id=uuid4(),sub_order_id=child.id,dimension='customer',
                           metric_type='words',count_value=1000))
    db.commit()
    current=http.get(url).json()
    response=http.put(url,json={
        'version':current['version'],'order_id':str(root.id),'documents_only':True,
        'payment_method':'special','invoice_required':True,'statement_required':True,
    })
    assert response.status_code==200,response.text
    response=http.put(url,json={
        'version':response.json()['version'],'order_id':str(child.id),'documents_only':True,
        'invoice_required':False,'statement_required':False,
    })
    assert response.status_code==200,response.text
    mother=response.json()['item']
    assert mother['payment_method']=='special'
    assert mother['invoice_required'] is True
    assert mother['statement_required'] is True
    assert mother['children'][0]['invoice_required'] is False
    assert mother['children'][0]['statement_required'] is False


def test_fixed_zero_is_filled_and_migration_only_creates_new_table(context):
    _,db,clients,_,actor=context;root=project(db,clients[0],fixed=True)
    charge=root.customer_charge_items[0];charge.total_excl_tax=None;charge.total_incl_tax=Decimal(0);db.commit()
    data=finance.read(db,root.id)['item']
    assert data['effective_billing_tax_mode']=='incl_tax' and Decimal(data['billing_totals']['CNY'])==0
    from tools.apply_translation_billing_tax_mode_migration import apply_migration
    columns=[row['name'] for row in inspect(db.connection()).get_columns('translation_project')]
    apply_migration(db.connection());apply_migration(db.connection())
    assert columns==[row['name'] for row in inspect(db.connection()).get_columns('translation_project')]
