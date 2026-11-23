from copy import deepcopy
from decimal import Decimal
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
import business_finance as business
import business_finance_source as sources
import interpretation_customer_finance as oral
import interpretation_statement_workspace as workspace
from interpretation_finance_schemas import FinanceWrite
from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from recruitment_models import RecruitmentProject
from models import Client
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context


def test_discount_manual_zero_and_fixed_amounts_are_consistent():
    payload=FinanceWrite(revision=0,rates=[{'direction':'中英','amount':'10.005','quantity':2,'tax_prices':{'unit_price_incl_tax':'10.005'}}],settlement={'tax_basis':'incl_tax'},settlement_adjustments=[{'currency':'CNY','incl_discount':90,'legacy_amount':0}]).model_dump(mode='json')
    result=oral.calculate(payload)
    assert result['totals_incl_tax']=={'CNY':'18.01'}
    assert result['adjusted_totals']=={'CNY':'0.00'}
    payload['settlement_adjustments'][0]['incl_amount']='7.21'
    assert oral.calculate(payload)['totals_incl_tax']=={'CNY':'7.21'}
    payload['settlement']['pricing_mode']='fixed';payload['fixed_totals']=[{'currency':'CNY','amount':'100','tax_prices':{'total_incl_tax':'106'}}]
    assert oral.calculate(payload)['totals_incl_tax']=={'CNY':'7.21'}


def seed(db):
    client=Client(id=uuid4(),client_code='CL-BUSINESS',client_name='财务测试客户')
    db.add(client);db.flush()
    annotation=AnnotationProject(id=uuid4(),order_no='AP-261101-901',project_name='标注验收',client_id=client.id,project_types=['text'])
    annotation.price_items=[AnnotationProjectPriceItem(id=uuid4(),sequence_no=1,project_type='text',amount=Decimal('0.125'),currency='CNY',unit='条')]
    recruitment=RecruitmentProject(id=uuid4(),order_no='RP-261101-901',project_name='招聘验收',position_title='工程师',client_id=client.id,service_fee_type='annual_salary_rate',service_fee_rate=Decimal('20'),service_fee_currency='CNY')
    db.add_all([annotation,recruitment]);db.commit()
    return client,annotation,recruitment


def test_financial_acceptance_does_not_rewrite_source_prices(environment,monkeypatch):
    db,(actor,*_)=environment
    monkeypatch.setattr('permission_service.user_has_permission',lambda *_:True)
    client,annotation,recruitment=seed(db)
    initial=business.read('annotation',annotation.id,db,actor)
    assert initial['billing_totals']=={}
    assert initial['payload']['rates'][0]['quantity'] is None
    values=business.Write.model_validate({**initial['payload'],'rates':[{'direction':'标注','amount':'0.2','currency':'CNY','unit':'条','quantity':'3'}],'settlement':{'tax_basis':'incl_tax','payment_method':'monthly'}})
    saved=business.put('annotation',annotation.id,values,db,actor)
    assert saved['billing_totals']=={'CNY':'0.60'}
    assert annotation.price_items[0].amount==Decimal('.125')
    assert business.record(db,'annotation',annotation.id).revision==1
    with pytest.raises(HTTPException) as conflict:business.put('annotation',annotation.id,values,db,actor)
    assert conflict.value.status_code==409
    row=business.record(db,'recruitment',recruitment.id)
    payload=row.payload;payload['salary_basis']='300000';payload['rates'][0]['quantity']='2'
    result=business.context(db,'recruitment',recruitment,payload)
    assert result['billing_totals']=={'CNY':'120000.00'}
    assert recruitment.service_fee_amount is None


def test_saved_board_duplicate_rules_and_reversible_removal(environment,monkeypatch):
    db,(actor,*_)=environment
    monkeypatch.setattr(oral,'user_has_permission',lambda *_:True)
    _,annotation,_=seed(db)
    payload=business.record(db,'annotation',annotation.id).payload
    payload['rates'][0]['quantity']='10';payload['settlement']['payment_method']='monthly'
    business.append(db,'annotation',annotation,payload,actor);db.commit()
    token=sources.MODULE.set('annotation')
    try:
        result=workspace.write(annotation.id,workspace.Write(revision=0,mode='monthly',action='generate',months=['2026-11']),db,actor)
        first=result['documents'][0]
        assert first['statement']['totals']=={'CNY':'1.25'}
        result=workspace.write(annotation.id,workspace.Write(revision=1,mode='monthly',action='new_board',board_id=first['id']),db,actor)
        assert [row['period_number'] for row in result['documents']]==[1,2]
        second=result['documents'][1]
        with pytest.raises(HTTPException) as conflict:
            workspace.write(annotation.id,workspace.Write(revision=2,mode='monthly',action='add_projects',board_id=second['id'],months=['2026-11']),db,actor)
        assert conflict.value.status_code==409
        db.rollback()
        removed=workspace.write(annotation.id,workspace.Write(revision=2,mode='monthly',action='remove_projects',board_id=first['id'],project_ids=[annotation.id]),db,actor)
        board=removed['documents'][0]
        assert board['statement']['rows']==[]
        restored=workspace.write(annotation.id,workspace.Write(revision=3,mode='monthly',action='restore_project',board_id=first['id'],data={'removed_id':board['removed_projects'][0]['id']}),db,actor)
        assert restored['documents'][0]['statement']['totals']=={'CNY':'1.25'}
        assert restored['documents'][0]['statement']['rows'][0]['root_id']==str(annotation.id)
        assert annotation.price_items[0].amount==Decimal('.125')
    finally:sources.MODULE.reset(token)


def test_generic_invoice_requests_keep_snapshot_and_recipient_access(environment,monkeypatch):
    import interpretation_invoice_requests as requests
    db,(actor,other,*_)=environment
    monkeypatch.setattr(oral,'user_has_permission',lambda *_:True)
    monkeypatch.setattr(requests,'profile',lambda *_:{'party':{'title':'开票测试客户'},'parties':[{'title':'开票测试客户'}],'subject_key':'guangzhou','invoice_type':'electronic_normal'})
    monkeypatch.setattr(requests,'subject',lambda db,key:{'key':key,'name':'测试开票主体','party':{'title':'测试开票主体'}})
    monkeypatch.setattr(requests,'batch_settings',lambda db:{'revision':2,'users':[{'id':str(other.id),'name':'开票人'}],'user_ids':[str(other.id)]})
    monkeypatch.setattr(requests,'commit_notices',lambda db,notices:db.commit())
    client,annotation,_=seed(db)
    payload=business.record(db,'annotation',annotation.id).payload
    payload['rates'][0]['quantity']='10';payload['settlement'].update(tax_basis='incl_tax',invoice_required=True)
    business.append(db,'annotation',annotation,payload,actor);db.commit()
    token=sources.MODULE.set('annotation')
    try:
        data=requests.Send(subject_key='guangzhou',settings_revision=2,expected_user_ids=[other.id],project_revisions={str(annotation.id):1},idempotency_key=uuid4())
        sent=requests.send(annotation.id,data,db,actor)
        assert sent['module']=='annotation'
        assert sent['snapshot']['projects'][0]['totals']=={'CNY':'1.25'}
        assert requests.send(annotation.id,data,db,actor)['id']==sent['id']
        assert business.record(db,'annotation',annotation.id).revision==1
        receiver=requests.read(UUID(sent['id']),db,other)
        assert receiver['is_recipient'] and not receiver['is_sender']
        updated=requests.update(UUID(sent['id']),requests.Action(revision=1,action='receive'),db,other)
        assert str(other.id) in updated['request_receipts']
        with pytest.raises(HTTPException):requests.update(UUID(sent['id']),requests.Action(revision=2,action='complete'),db,actor)
    finally:sources.MODULE.reset(token)


def test_interpretation_ledger_uses_manager_history_and_client_fallback(environment,monkeypatch):
    from interpretation_models import InterpretationProject
    db,(actor,*_)=environment
    monkeypatch.setattr(oral,'user_has_permission',lambda *_:True)
    client=Client(id=uuid4(),client_code='CL-ORAL-LEDGER',client_name='口译查账客户',client_manager=actor.full_name or actor.username)
    project=InterpretationProject(id=uuid4(),order_no='IP-261123-908',project_name='口译查账项目',client_id=client.id)
    db.add_all([client,project]);db.commit()
    data=business.ledger('interpretation',client_id=client.id,only_mine=True,client_manager='',db=db,user=actor)
    assert [item['id'] for item in data['items']]==[str(project.id)]
