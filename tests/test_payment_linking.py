from decimal import Decimal
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_translation_payments import project
from routers.translation_payments import write
import translation_payment_service as payments
import translation_payment_confirmation as confirmations
import translation_customer_finance as finance
from models import FinancePayment


@pytest.fixture
def context(environment):
    db,(actor,*_)=environment
    row=project(db,actor)
    data=finance.read(db,row.id)
    finance.save(db,actor,row.id,finance.PriceWrite(version=data['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=100,adjusted_total_incl_tax=106))
    return db,actor,row


def save(context,rows,confirmation=None,version=None):
    db,actor,row=context
    return write(row.id,payments.PaymentWrite(version=version or payments.read(db,row)['version'],payments=rows,confirmation=confirmation),db,actor)


def test_actual_details_sync_confirmation_to_finance(context):
    db,_,row=context
    result=save(context,[{'stage_type':'deposit','planned_amount':40,'actual_amount':40,'payment_method':'广州公司公账'}])
    assert result['confirmation']['payment_option']=='deposit'
    assert result['confirmation']['payment_account']=='广州公司公账'
    assert finance.read(db,row.id)['item']['payment_confirmation']==result['confirmation']
    assert confirmations.history(db,row.id)['total']==1


def test_full_preserves_existing_details_and_stores_matched_total(context):
    db,actor,row=context
    before=save(context,[{'stage_type':'deposit','actual_amount':40}])
    detail=db.query(FinancePayment).one()
    detail.confirmed_by=actor.id;db.commit()
    current=payments.read(db,row)
    full=save(context,[],{**current['confirmation'],'is_paid':True,'payment_option':'full','full_payment_amount':100,'full_payment_total_key':'excl:CNY'})
    assert len(full['payments'])==1 and full['payments'][0]['actual_amount']=='40.00'
    assert db.query(FinancePayment).one().confirmed_by==actor.id
    assert full['confirmation']['full_match_status']=='matched'
    assert Decimal(full['confirmation']['full_reference_amount'])==100


def test_mismatch_requires_reason_and_keeps_label_and_history(context):
    db,_,row=context
    info={'is_paid':True,'payment_option':'full','full_payment_amount':90,'full_payment_total_key':'excl:CNY'}
    with pytest.raises(HTTPException) as failure:save(context,[],info)
    assert failure.value.status_code==422
    info['mismatch_reason']='客户确认优惠10元'
    result=save(context,[],info)
    assert result['confirmation']['full_match_status']=='mismatch'
    assert result['confirmation']['mismatch_reason']=='客户确认优惠10元'
    assert finance.read(db,row.id)['item']['payment_confirmation']['full_match_status']=='mismatch'
    history=confirmations.history(db,row.id)['items'][0]
    assert history['after']['full_match_status']=='mismatch'
    assert history['after']['full_reference_label']=='不含税总价'


def test_project_update_saves_confirmation_and_details_atomically(context):
    from schemas import TranslationProjectUpdate
    import crud
    db,actor,row=context
    initial=payments.read(db,row)
    crud.update_translation_project(db,row.id,TranslationProjectUpdate(payment_draft=[{'stage_type':'deposit','actual_amount':30}],payment_version=initial['version'],payment_confirmation={'revision':0,'is_paid':True,'payment_option':'deposit'}),actor.id)
    current=payments.read(db,row)
    assert current['confirmation']['revision']==1
    assert current['confirmation']['payment_option']=='deposit'
    assert Decimal(current['payments'][0]['actual_amount'])==30


def test_fee_change_rechecks_full_match_without_erasing_payment(context):
    db,actor,row=context
    save(context,[],{'is_paid':True,'payment_option':'full','full_payment_amount':100,'full_payment_total_key':'excl:CNY'})
    before=finance.read(db,row.id)
    changed=finance.save(db,actor,row.id,finance.PriceWrite(version=before['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=200))
    status=changed['item']['payment_confirmation']
    assert status['full_match_status']=='mismatch'
    assert Decimal(status['full_payment_amount'])==100
    assert Decimal(status['full_reference_amount'])==200
    assert '总价变更' in status['mismatch_reason']
    assert confirmations.history(db,row.id)['total']==2


def test_final_sums_actual_details_and_keeps_deposit_mode(context):
    db,_,row=context
    result=save(context,[{'stage_type':'deposit','actual_amount':30,'planned_amount':50},{'stage_type':'mid','actual_amount':20},{'stage_type':'final','actual_amount':50}])
    status=result['confirmation']
    assert status['payment_option']=='deposit'
    assert status['full_payment_source']=='details'
    assert Decimal(status['full_payment_amount'])==100
    assert status['full_match_status']=='matched'
    assert len(result['payments'])==3
    assert confirmations.history(db,row.id)['items'][0]['after']['full_payment_source']=='details'


def test_final_mismatch_requires_reason_and_ignores_forged_total(context):
    db,_,row=context
    rows=[{'stage_type':'deposit','actual_amount':30},{'stage_type':'final','actual_amount':60}]
    info={'is_paid':True,'payment_option':'deposit','full_payment_amount':100,'full_payment_total_key':'excl:CNY'}
    with pytest.raises(HTTPException) as failure:save(context,rows,info)
    assert failure.value.status_code==422
    result=save(context,rows,{**info,'mismatch_reason':'优惠10元'})
    assert Decimal(result['confirmation']['full_payment_amount'])==90
    assert result['confirmation']['full_match_status']=='mismatch'
    changed=save(context,[{'stage_type':'deposit','actual_amount':30}],result['confirmation'])
    assert changed['confirmation']['full_match_status']=='none'
    assert changed['confirmation']['full_payment_source'] is None


def test_final_requires_all_actual_amounts_and_fee_change_rechecks(context):
    db,actor,row=context
    with pytest.raises(HTTPException) as failure:save(context,[{'stage_type':'deposit','planned_amount':40},{'stage_type':'final','actual_amount':60}])
    assert failure.value.status_code==422
    save(context,[{'stage_type':'deposit','actual_amount':40},{'stage_type':'final','actual_amount':60}])
    before=finance.read(db,row.id)
    result=finance.save(db,actor,row.id,finance.PriceWrite(version=before['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=200))
    assert result['item']['payment_confirmation']['full_match_status']=='mismatch'
    assert result['item']['payment_confirmation']['full_payment_source']=='details'
