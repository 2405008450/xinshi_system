from uuid import uuid4
from decimal import Decimal
import pytest
from fastapi import HTTPException
from models import TranslationProject,TranslationSubOrder,Client
from word_count_models import WordCountMetric
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context,item,write
import translation_customer_finance as finance
import translation_month_price_sync as sync
import translation_finance_audit as audit


def setup(db,owner):
    client,source,_,_=context(db,owner)
    write(db,owner,source,source,[item(amount='.2',metric='customer_auto:foreign_words')],billing_month='2026-11')
    target=TranslationProject(id=uuid4(),order_no='TP-MATCH-001',project_name='目标.docx',client_id=client.id,language_pair='英语→简中')
    db.add(target);db.flush()
    child=TranslationSubOrder(id=uuid4(),parent_project_id=target.id,sub_order_no=target.order_no+'.001',sub_project_name='目标子订单.docx',language_pair='英语→简中')
    third=TranslationSubOrder(id=uuid4(),parent_project_id=target.id,sub_order_no=target.order_no+'.001.001',sub_project_name='目标三级.docx',language_pair='英语→简中')
    other_month=TranslationSubOrder(id=uuid4(),parent_project_id=target.id,sub_order_no=target.order_no+'.002',sub_project_name='上月.docx',language_pair='英语→简中')
    db.add_all([child,third,other_month]);db.flush()
    for row in (target,child,third,other_month):db.add(WordCountMetric(id=uuid4(),project_id=row.id if row is target else None,sub_order_id=None if row is target else row.id,dimension='customer',metric_type='foreign_words',count_value=10))
    db.commit()
    write(db,owner,target,target,[item(amount='.5',metric='customer_auto')],billing_month='2026-11')
    write(db,owner,target,child,[item(amount='.7',metric='customer_auto')],billing_month='2026-11',adjusted_total='3.33',explanation='保留调价')
    write(db,owner,target,other_month,[item(amount='.9',metric='customer_auto')],billing_month='2026-10')
    return source,target,child,third,other_month


def test_preview_then_sync_all_order_levels_preserves_other_month_and_adjustment(environment):
    db,(owner,_,_)=environment;source,target,child,third,other_month=setup(db,owner)
    scope=sync.SyncScope(order_id=source.id,version=finance.read(db,source.id)['version'],billing_month='2026-11')
    preview,_=sync.plan(db,source.id,scope)
    target_ids={row['order_id'] for row in preview['targets']}
    assert {str(target.id),str(child.id),str(third.id)}.issubset(target_ids)
    assert str(other_month.id) not in target_ids
    assert finance.primary(child).unit_price_excl_tax==Decimal('.7')
    scope.token=preview['token'];result=sync.apply(db,owner,source.id,scope)
    assert result['updated_orders']==len(preview['targets'])
    finance.read(db,target.id)
    assert finance.primary(child).unit_price_excl_tax==Decimal('.2')
    assert finance.primary(third).unit_price_excl_tax==Decimal('.2')
    assert finance.primary(other_month).unit_price_excl_tax==Decimal('.9')
    assert finance.primary(child).total_excl_tax==Decimal('3.33') and finance.primary(child).remarks=='保留调价'
    assert audit.history(db,target.id,child.id)['items'][0]['after']['prices'][0]['amount']=='0.2'


def test_other_customer_direction_and_stale_preview_are_not_overwritten(environment):
    db,(owner,_,_)=environment;source,target,child,_,_=setup(db,owner)
    customer=Client(id=uuid4(),client_name='其他',client_short_name='其他');db.add(customer);db.flush()
    foreign=TranslationProject(id=uuid4(),order_no='TP-OTHER',project_name='其他.docx',client_id=customer.id,language_pair='英语→简中')
    direction=TranslationProject(id=uuid4(),order_no='TP-DIRECTION',project_name='反向.docx',client_id=source.client_id,language_pair='简中→英语')
    db.add_all([foreign,direction]);db.commit()
    write(db,owner,foreign,foreign,[item(amount='.8')],billing_month='2026-11')
    write(db,owner,direction,direction,[item('简中→英语',amount='.8')],billing_month='2026-11')
    scope=sync.SyncScope(order_id=source.id,version=finance.read(db,source.id)['version'],billing_month='2026-11')
    preview,_=sync.plan(db,source.id,scope)
    assert not {str(foreign.id),str(direction.id)}&{row['order_id'] for row in preview['targets']}
    write(db,owner,target,child,[item(amount='.6')],billing_month='2026-11')
    scope.token=preview['token']
    with pytest.raises(HTTPException) as stale:sync.execute(source.id,scope,db,owner)
    assert stale.value.status_code==409
    assert finance.primary(child).unit_price_excl_tax==Decimal('.6')


def test_mid_batch_conflict_rolls_back_prices_and_audit(environment):
    db,(owner,_,_)=environment;source,target,child,_,_=setup(db,owner)
    finance.primary(child).currency='USD';db.commit()
    before=db.query(audit.TranslationFinanceEvent).count()
    scope=sync.SyncScope(order_id=source.id,version=finance.read(db,source.id)['version'],billing_month='2026-11')
    scope.token=sync.plan(db,source.id,scope)[0]['token']
    with pytest.raises(HTTPException) as conflict:sync.execute(source.id,scope,db,owner)
    assert conflict.value.status_code==409
    finance.read(db,target.id)
    assert finance.primary(target).unit_price_excl_tax==Decimal('.5')
    assert finance.primary(child).currency=='USD' and finance.primary(child).unit_price_excl_tax==Decimal('.7')
    assert db.query(audit.TranslationFinanceEvent).count()==before
