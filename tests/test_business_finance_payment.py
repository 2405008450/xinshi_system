from copy import deepcopy
from decimal import Decimal
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_business_finance_workspace import seed
import business_finance as business
from business_finance_payment import registration, apply_registration


def test_legacy_receipts_keep_dates_notes_and_currencies():
    payload={'settlement':{'payment_status':'partial','payment_note':'原说明','payments':[
        {'amount':'30.00','currency':'CNY','received_on':'2026-11-24','note':'原截图备注','stage_type':'deposit'},
        {'amount':'20.00','currency':'USD','received_on':None,'note':'美元款','stage_type':'mid'}]}}
    payload['payment_registration']=registration(payload)
    apply_registration(payload,{'CNY':'100','USD':'20'})
    assert payload['settlement']['payments'][0]['received_on']=='2026-11-24'
    assert payload['settlement']['payments'][0]['note']=='原截图备注'
    assert payload['settlement']['payments'][1]['currency']=='USD'
    assert payload['payment_registration']['confirmation']['proofs']=='原说明'


def test_existing_full_payment_keeps_received_date():
    payload={'settlement':{'payment_status':'full','payments':[
        {'amount':'50','currency':'CNY','received_on':'2026-11-20','note':'凭证','stage_type':'full'}]}}
    payload['payment_registration']=registration(payload)
    apply_registration(payload,{'CNY':'50'})
    assert payload['settlement']['payments'][0]['received_on']=='2026-11-20'
    assert payload['payment_registration']['confirmation']['proofs']=='凭证'


def test_business_save_roundtrip_history_clear_and_stale(environment,monkeypatch):
    db,(actor,*_)=environment
    monkeypatch.setattr('permission_service.user_has_permission',lambda *_:True)
    _,project,_=seed(db)
    initial=business.read('annotation',project.id,db,actor)['payload']
    initial['rates'][0]['quantity']='800' # 应收100元。
    initial['payment_registration']={'confirmation':{'is_paid':True,'payment_option':'deposit','proofs':'共用凭证'},'payments':[
        {'stage_type':'deposit','actual_amount':'30','planned_amount':'40','currency':'CNY','payment_time':'2026-11-24T15:12:00+08:00','payment_method':'广州公司公账','proofs':'首款截图'},
        {'stage_type':'final','actual_amount':'70','currency':'CNY','proofs':'尾款截图'}]}
    saved=business.put('annotation',project.id,business.Write.model_validate(initial),db,actor)
    assert saved['received_totals']=={'CNY':'100.00'}
    assert saved['payload']['payment_registration']['confirmation']['full_payment_source']=='details'
    assert saved['payload']['payment_registration']['confirmation']['full_match_status']=='matched'
    assert Decimal(saved['payload']['payment_registration']['payments'][0]['planned_amount'])==Decimal('40.00')
    assert saved['payload']['payment_registration']['payments'][0]['payment_time'].endswith('+08:00')
    history=business.payment_history('annotation',project.id,1,db,actor)
    assert history['total']==1 and history['items'][0]['after']['payment_details'][1]['proofs']=='尾款截图'
    with pytest.raises(HTTPException) as stale:
        business.put('annotation',project.id,business.Write.model_validate(initial),db,actor)
    assert stale.value.status_code==409
    updated=deepcopy(saved['payload'])
    updated.pop('invoice',None)
    updated['payment_registration']={'confirmation':{'is_paid':False},'payments':[]}
    cleared=business.put('annotation',project.id,business.Write.model_validate(updated),db,actor)
    assert cleared['received_totals']=={}
    history=business.payment_history('annotation',project.id,1,db,actor)
    assert history['total']==2
    assert history['items'][0]['before']['payment_details'][0]['proofs']=='首款截图'


def test_full_amount_mismatch_rejected_without_reason():
    payload={'settlement':{},'payment_registration':{'confirmation':{'is_paid':True,'payment_option':'full','full_payment_amount':'90'},'payments':[]}}
    with pytest.raises(HTTPException):apply_registration(payload,{'CNY':'100'})
    payload['payment_registration']['confirmation']['mismatch_reason']='客户扣款'
    apply_registration(payload,{'CNY':'100'})
    assert payload['settlement']['payments'][0]['amount']=='90'


def test_old_client_does_not_overwrite_new_payment_fields(environment,monkeypatch):
    db,(actor,*_)=environment
    monkeypatch.setattr('permission_service.user_has_permission',lambda *_:True)
    _,project,_=seed(db)
    payload=business.read('annotation',project.id,db,actor)['payload']
    payload['rates'][0]['quantity']='800'
    payload['payment_registration']={'confirmation':{'is_paid':True,'payment_option':'full','full_payment_amount':'100'},'payments':[]}
    saved=business.put('annotation',project.id,business.Write.model_validate(payload),db,actor)
    legacy=deepcopy(saved['payload']);legacy.pop('payment_registration');legacy.pop('invoice',None)
    legacy['settlement']['payments']=[];legacy['settlement']['payment_status']='unrecorded'
    preserved=business.put('annotation',project.id,business.Write.model_validate(legacy),db,actor)
    assert preserved['received_totals']=={'CNY':'100.00'}
    assert preserved['payload']['payment_registration']['confirmation']['payment_option']=='full'
