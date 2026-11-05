from decimal import Decimal
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context,item,write
import translation_customer_finance as finance
import translation_finance_audit as audit
import customer_translation_rates as rates


def test_price_adjustment_and_inherited_changes_are_audited(environment):
    db,(owner,_,_)=environment;client,root,child,third=context(db,owner)
    write(db,owner,root,root,[item()],billing_month='2026-11')
    first=audit.history(db,root.id)
    assert first['total']==3
    assert {row['order_no'] for row in first['items']}=={root.order_no,child.sub_order_no,third.sub_order_no}
    assert first['items'][0]['created_at'].endswith('+08:00')
    write(db,owner,root,third,[item(amount='.5')],adjusted_total='8.88',explanation='客户确认调价')
    changes=audit.history(db,root.id,third.id)
    record=changes['items'][0]
    assert record['actor_name']==owner.full_name
    assert record['before']['adjusted_total'] is None
    assert Decimal(record['after']['adjusted_total'])==Decimal('8.88')
    assert Decimal(record['before']['prices'][0]['amount'])==Decimal('.1')
    assert Decimal(record['after']['prices'][0]['amount'])==Decimal('.5')
    assert record['after']['explanation']=='客户确认调价'
    assert first['items'][0]['after']['adjusted_total'] is None


def test_adjustment_clear_and_history_pagination(environment):
    db,(owner,_,_)=environment;_,root,_,third=context(db,owner)
    for index in range(12):write(db,owner,root,third,[item(amount='.2')],adjusted_total=str(index))
    assert audit.history(db,root.id,third.id,1)['total']==12
    assert len(audit.history(db,root.id,third.id,1)['items'])==10
    assert len(audit.history(db,root.id,third.id,2)['items'])==2
    write(db,owner,root,third,[item(amount='.2')],adjusted_total=None)
    assert audit.history(db,root.id,third.id)['items'][0]['after']['adjusted_total'] is None


def test_audit_failure_rolls_back_prices_and_customer_reference(environment,monkeypatch):
    db,(owner,_,_)=environment;client,root,_,leaf=context(db,owner)
    monkeypatch.setattr(finance,'user_has_permission',lambda *a:True)
    original=finance.read(db,root.id)
    def fail(*a):raise HTTPException(503,'隔离测试记录保存失败')
    monkeypatch.setattr(audit,'append',fail)
    payload=finance.PriceWrite(version=original['version'],order_id=leaf.id,prices=[item()],update_library=True,library_version=original['reference_prices']['version'])
    with pytest.raises(HTTPException):finance.update(root.id,payload,db,owner)
    assert not rates.library(db,client.id)['items']
    assert not finance.read(db,root.id)['item']['children'][0]['children'][0]['prices']
    assert db.query(audit.TranslationFinanceEvent).count()==0
    assert db.query(rates.CustomerTranslationRateHistory).count()==0


def test_repeatable_create_only_audit_migration(environment):
    from tools.apply_translation_finance_audit_migration import apply_migration
    db,_=environment
    audit.TranslationFinanceEventItem.__table__.drop(db.connection());audit.TranslationFinanceEvent.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert audit.ready(db)
