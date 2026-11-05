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
    assert db.query(FinancePayment).one().confirmed_by is None
    with pytest.raises(HTTPException) as error:write(other.id,service.PaymentWrite(version=read(other.id,db,actor)['version'],payments=result['payments']),db,actor)
    assert error.value.status_code==422
    db.rollback()
    result=write(row.id,service.PaymentWrite(version=read(row.id,db,actor)['version'],payments=[]),db,actor)
    assert not result['payments'] and db.query(FinanceRecord).filter_by(project_id=row.id).count()==1
