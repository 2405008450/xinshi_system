"""口译付款与笔译相同契约，仅在隔离 SQLite 验证，不处理真实款项。"""
from copy import deepcopy
from uuid import uuid4,UUID
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
import interpretation_customer_finance as finance
from interpretation_models import InterpretationProject
from interpretation_payment_registration import PaymentConfirm


def seed(environment,monkeypatch):
    db,(actor,other,_)=environment
    monkeypatch.setattr(finance,'user_has_permission',lambda *_:True)
    monkeypatch.setattr('hr_access.can_manage_hr',lambda _db,user:user.id==actor.id)
    project=InterpretationProject(id=uuid4(),order_no='IP-PAYMENT',project_name='隔离口译付款')
    db.add(project);db.commit()
    data=dict(revision=0,settlement={'pricing_mode':'fixed','tax_basis':'incl_tax'},
              fixed_totals=[{'amount':'100','tax_prices':{'total_incl_tax':'100'}}])
    return db,actor,other,project,data


def test_deposit_final_confirmation_history_and_legacy_preservation(environment,monkeypatch):
    db,actor,other,project,data=seed(environment,monkeypatch)
    data['payment_registration']={'confirmation':{'is_paid':True,'payment_option':'deposit'},'payments':[
        {'stage_type':'deposit','planned_amount':'40','actual_amount':'30','payment_time':'2026-11-26T12:00:00+08:00','proofs':'定金凭证'},
        {'stage_type':'final','actual_amount':'70','proofs':'尾款凭证'}]}
    saved=finance.save(db,actor,'project',project.id,finance.FinanceWrite(**data))
    assert saved['received_totals']=={'CNY':'100.00'}
    registration=saved['payload']['payment_registration']
    assert registration['confirmation']['full_match_status']=='matched'
    assert registration['payments'][0]['payment_time'].endswith('+08:00')
    payment_id=UUID(registration['payments'][0]['id'])
    with pytest.raises(HTTPException) as denied:
        finance.confirm_payment(project.id,PaymentConfirm(revision=1,payment_id=payment_id),db,other)
    assert denied.value.status_code==403
    confirmed=finance.confirm_payment(project.id,PaymentConfirm(revision=1,payment_id=payment_id),db,actor)
    assert confirmed['payload']['payment_registration']['payments'][0]['confirmed_by_name']==actor.full_name
    payload=deepcopy(confirmed['payload']);payload['revision']=confirmed['revision']
    # 输入契约丢弃客户端确认字段，服务端只保留未改动付款原有的确认信息。
    payload['payment_registration']['payments'][0]['confirmed_by_name']='伪造人员'
    same=finance.save(db,actor,'project',project.id,finance.FinanceWrite(**payload))
    assert same['payload']['payment_registration']['payments'][0]['confirmed_by_name']==actor.full_name
    legacy=deepcopy(same['payload']);legacy.pop('payment_registration');legacy['revision']=same['revision']
    legacy['settlement']['payments']=[];legacy['settlement']['payment_status']='unrecorded'
    preserved=finance.save(db,actor,'project',project.id,finance.FinanceWrite(**legacy))
    assert preserved['received_totals']=={'CNY':'100.00'}
    changed=deepcopy(preserved['payload']);changed['revision']=preserved['revision']
    changed['payment_registration']['payments'][0]['actual_amount']='31'
    changed['payment_registration']['payments'][1]['actual_amount']='69'
    updated=finance.save(db,actor,'project',project.id,finance.FinanceWrite(**changed))
    assert not updated['payload']['payment_registration']['payments'][0].get('confirmed_at')
    history=finance.payment_history(project.id,1,db,actor)
    assert history['total']>=3 and history['items'][0]['after']['payment_details'][0]['proofs']=='定金凭证'
    assert history['items'][0]['created_at'].endswith('+08:00')


def test_full_payment_clear_mismatch_and_stale(environment,monkeypatch):
    db,actor,other,project,data=seed(environment,monkeypatch)
    data['payment_registration']={'confirmation':{'is_paid':True,'payment_option':'full','full_payment_amount':'90'},'payments':[]}
    with pytest.raises(HTTPException) as invalid:
        finance.save(db,actor,'project',project.id,finance.FinanceWrite(**data))
    assert invalid.value.status_code==422
    data['payment_registration']['confirmation']['mismatch_reason']='客户扣款'
    saved=finance.save(db,actor,'project',project.id,finance.FinanceWrite(**data))
    assert saved['received_totals']=={'CNY':'90.00'}
    with pytest.raises(HTTPException) as stale:
        finance.save(db,actor,'project',project.id,finance.FinanceWrite(**data))
    assert stale.value.status_code==409
    confirmed=finance.confirm_payment(project.id,PaymentConfirm(revision=saved['revision']),db,actor)
    assert confirmed['payload']['payment_registration']['confirmation']['full_payment_confirmed_at'].endswith('+08:00')
    cleared=deepcopy(confirmed['payload']);cleared['revision']=confirmed['revision']
    cleared['payment_registration']={'confirmation':{'is_paid':False},'payments':[]}
    result=finance.save(db,actor,'project',project.id,finance.FinanceWrite(**cleared))
    assert result['received_totals']=={}
    history=finance.payment_history(project.id,1,db,actor)
    assert history['items'][0]['before']['proofs']==''
    from decimal import Decimal
    assert Decimal(history['items'][0]['before']['full_payment_amount'])==Decimal('90.00')
