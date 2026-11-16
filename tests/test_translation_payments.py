from datetime import datetime
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from models import TranslationProject, FinanceRecord, FinancePayment
from schemas import TranslationProjectUpdate
import crud
import translation_payment_service as service
from routers.translation_payments import read, write


def test_settlement_number_is_issued_only_after_saving_actual_amount(environment,monkeypatch):
    from datetime import timezone,timedelta
    import translation_settlement_number as numbers
    from routers.translation_payments import numbered_payment_history

    db,(actor,_,_)=environment
    row=project(db,actor)
    moment=datetime(2026,11,15,9,tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(service,'business_now',lambda:moment)
    data=write(row.id,service.PaymentWrite(version=read(row.id,db,actor)['version'],
        payments=[dict(stage_type='deposit',planned_amount=100)]),db,actor)
    assert not numbers.records(db,row.id)
    number_key=data['payments'][0]['id']
    data['payments'][0]['actual_amount']=40
    data=write(row.id,service.PaymentWrite(version=data['version'],payments=data['payments']),db,actor)
    entry=numbers.records(db,row.id)[number_key]
    assert entry.number=='TS-261115-001.01'
    moment+=timedelta(days=1)
    data['payments'][0]['actual_amount']=50
    write(row.id,service.PaymentWrite(version=data['version'],payments=data['payments']),db,actor)
    assert numbers.records(db,row.id)[number_key].number==entry.number
    history=numbered_payment_history(row.id,entry.number,db,actor)
    assert history['payments'][0]['before']['actual_amount']=='40.00'
    assert history['payments'][0]['after']['actual_amount']=='50.00'


def test_historical_full_number_uses_original_saved_amount_date(environment):
    from uuid import uuid4
    from translation_payment_confirmation import TranslationPaymentConfirmation,TranslationPaymentConfirmationHistory
    import translation_settlement_number as numbers

    db,(actor,_,_)=environment
    row=project(db,actor)
    db.add(TranslationPaymentConfirmation(project_id=row.id,revision=2,is_paid=True,
        payment_option='{"type":"full","full_payment":{"amount":"96.00"}}',proofs='',updated_at=datetime(2026,11,20,10)))
    db.add(TranslationPaymentConfirmationHistory(id=uuid4(),project_id=row.id,revision=1,actor_name='测试',
        before={},after={'is_paid':True,'payment_option':'full','full_payment_amount':'80.00'},created_at=datetime(2026,11,15,9)))
    db.flush()
    assert numbers.apply(db,row.id)==1
    assert numbers.apply(db,row.id)==0
    assert numbers.records(db,row.id)['full'].number=='TS-261115-001'


def project(db, actor, number='001'):
    row=TranslationProject(id=uuid4(),order_no='TP-261104-'+number,project_name='付款测试.docx',source_file_name='付款测试.docx',created_by=actor.id)
    db.add(row);db.commit();return row


def test_shared_existing_finance_preserves_other_fields_and_rejects_stale(environment):
    db,(actor,_,_)=environment;row=project(db,actor)
    original=read(row.id,db,actor)
    result=write(row.id,service.PaymentWrite(version=original['version'],payments=[dict(stage_type='deposit',planned_amount='100',actual_amount='40',payment_time='2026-11-04T02:00:00Z',payment_method='银行转账')]),db,actor)
    finance=db.query(FinanceRecord).filter_by(project_id=row.id).one()
    assert finance.payments[0].actual_amount==Decimal('40')
    assert finance.payments[0].payment_time==datetime(2026,11,4,10)
    assert result['payments'][0]['payment_time'].endswith('+08:00')
    finance.remarks='保留原财务说明';finance.total_incl_tax=Decimal('500');db.commit()
    payload=result['payments'];payload[0]['actual_amount']='100'
    saved=crud.update_translation_project(db,row.id,TranslationProjectUpdate(payment_draft=payload,payment_version=result['version']),actor.id)
    assert saved.id==row.id
    assert db.query(FinanceRecord).filter_by(project_id=row.id).count()==1
    assert finance.remarks=='保留原财务说明' and finance.total_incl_tax==Decimal('500')
    assert read(row.id,db,actor)['payments'][0]['actual_amount']=='100.00'
    assert read(row.id,db,actor)['payments'][0]['id']==result['payments'][0]['id']
    with pytest.raises(HTTPException) as error:write(row.id,service.PaymentWrite(version=result['version'],payments=[]),db,actor)
    assert error.value.status_code==409


def test_clearing_and_foreign_ids_and_confirmation(environment):
    db,(actor,_,_)=environment;row=project(db,actor);other=project(db,actor,'002')
    data=write(row.id,service.PaymentWrite(version=read(row.id,db,actor)['version'],payments=[dict(stage_type='final',planned_amount=10,actual_amount=10)],confirmation={'is_paid':True,'payment_option':'deposit','mismatch_reason':'项目尚未登记收费'}),db,actor)
    payment=db.query(FinancePayment).one();payment.confirmed_by=actor.id;payment.confirmed_at=datetime(2026,11,4,9);db.commit()
    current=read(row.id,db,actor);current['payments'][0]['actual_amount']='9'
    result=write(row.id,service.PaymentWrite(version=current['version'],payments=current['payments']),db,actor)
    confirmed=db.query(FinancePayment).one()
    assert confirmed.confirmed_by is None and confirmed.confirmed_at is None
    assert result['payments'][0]['confirmed_at'] is None
    with pytest.raises(HTTPException) as error:write(other.id,service.PaymentWrite(version=read(other.id,db,actor)['version'],payments=result['payments']),db,actor)
    assert error.value.status_code==422
    db.rollback()
    result=write(row.id,service.PaymentWrite(version=read(row.id,db,actor)['version'],payments=[]),db,actor)
    assert not result['payments'] and db.query(FinanceRecord).filter_by(project_id=row.id).count()==1
