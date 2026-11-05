from uuid import uuid4
from tests.test_chat_participant_access import environment
from models import TranslationProject
import translation_customer_finance as finance


def test_month_follows_order_number_even_without_prices(environment):
    db,(user,_,_)=environment
    numbers=['TP-261029-010','TP-261001-001','TP-261101-001','TP-20261029-001','TP-2610BAD-001']
    db.add_all([TranslationProject(id=uuid4(),order_no=number,project_name='测试.docx') for number in numbers]);db.commit()
    data=finance.page(skip=0,limit=10,billing_month='2026-10',db=db,user=user,only_mine=False,manager_ids=None)
    assert {row['order_no'] for row in data['items']}==set(numbers[index] for index in (0,1,3))
    assert data['total']==3 and sum(row['project_count'] for row in data['client_subtotals'])==3
    assert finance.order_billing_month('TP-261029-010.001.001')=='2026-10'


def test_display_ignores_stale_fee_month_and_reads_do_not_write(environment):
    from tests.test_customer_translation_rates import context
    from models import TranslationSubOrderChargeItem
    db,(actor,*_)=environment;_,root,child,leaf=context(db,actor)
    old=root.order_no;root.order_no='TP-261025-003'
    for node in (child,leaf):node.sub_order_no=node.sub_order_no.replace(old,root.order_no)
    charge=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=root.id,sequence_no=1,item_name='翻译费',pricing_mode='metric',metric_type='words',currency='CNY',unit_size=1,unit_price_excl_tax=.2,billing_month='2026-11')
    root.customer_charge_items.append(charge);db.commit()
    result=finance.read(db,root.id)['item']
    assert result['billing_month']=='2026-10' and result['recorded_billing_month']=='2026-11'
    assert result['children'][0]['billing_month']==result['children'][0]['children'][0]['billing_month']=='2026-10'
    assert charge.billing_month=='2026-11'
    charge.billing_month=None;db.commit()
    assert finance.read(db,root.id)['item']['billing_month']=='2026-10'


def test_save_and_sync_use_generated_month_instead_of_current_month(environment):
    from tests.test_customer_translation_rates import context,item,write
    import translation_month_price_sync as sync
    db,(actor,*_)=environment;_,root,child,leaf=context(db,actor)
    old=root.order_no;root.order_no='TP-20261025-003'
    for node in (child,leaf):node.sub_order_no=node.sub_order_no.replace(old,root.order_no)
    db.commit()
    result=write(db,actor,root,root,[item(metric='customer_auto:foreign_words')],billing_month='2026-11')
    assert result['item']['billing_month']=='2026-10'
    assert finance.primary(root).billing_month=='2026-10'
    finance.primary(root).billing_month='2026-11';db.commit()
    scope=sync.SyncScope(order_id=root.id,version=finance.read(db,root.id)['version'],billing_month='2026-10')
    assert sync.plan(db,root.id,scope)[0]['billing_month']=='2026-10'
