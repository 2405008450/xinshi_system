"""口译客户/子客户设置、分期单据与笔译数据隔离；只使用内存数据库。"""
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from models import Client,SubClient
from interpretation_models import InterpretationProject
import interpretation_customer_finance as finance
import interpretation_settlement_settings as service


def seed(environment,monkeypatch):
    db,(actor,*_)=environment
    monkeypatch.setattr(finance,'user_has_permission',lambda *_:True)
    client=Client(id=uuid4(),client_code='CL-ORAL-SETTINGS',client_name='测试客户',client_short_name='客户')
    db.add(client);db.flush()
    children=[SubClient(id=uuid4(),parent_client_id=client.id,sub_client_code=f'SUB-{n}',client_name=f'分支{n}',client_short_name=f'分支{n}') for n in range(2)]
    db.add_all(children);db.flush()
    projects=[]
    for index,(child,period,mode) in enumerate([(children[0],1,'sub_client'),(children[0],1,'sub_client'),(children[0],2,'sub_client'),(children[1],1,'sub_client'),(children[0],1,'special')]):
        project=InterpretationProject(id=uuid4(),order_no=f'IP-261127-{index:03}',project_name=f'隔离项目{index}',client_id=client.id,sub_client_id=child.id)
        db.add(project);db.flush()
        finance.save(db,actor,'project',project.id,finance.FinanceWrite(revision=0,
            settlement={'payment_method':mode,'pricing_mode':'fixed','tax_basis':'incl_tax','billing_month':'2026-11','period_number':period,'invoice_required':True},
            fixed_totals=[{'amount':100,'tax_prices':{'total_incl_tax':100}}]))
        projects.append(project)
    return db,actor,client,children,projects


def test_sub_client_bidirectional_sync_preserves_special_and_translation(environment,monkeypatch):
    db,actor,client,children,projects=seed(environment,monkeypatch)
    from sub_client_finance import SubClientFinancePreference
    db.add(SubClientFinancePreference(sub_client_id=children[0].id,quotation_required=False,revision=5));db.commit()
    old=service.read('sub-client',children[0].id,db,actor)
    service.write('sub-client',children[0].id,service.SettingsWrite(revision=old['revision'],quotation_required=True,
        document_notes={'quotation':'口译报价说明'},statement_subject_key='shenzhen'),db,actor)
    for index in [0,1,2]:
        setting=finance.context(db,'project',projects[index].id)['payload']['settlement']
        assert setting['quotation_required'] is True and setting['document_notes']['quotation']=='口译报价说明'
    assert not finance.context(db,'project',projects[3].id)['payload']['settlement']['quotation_required']
    assert not finance.context(db,'project',projects[4].id)['payload']['settlement']['quotation_required']
    first=finance.context(db,'project',projects[0].id)
    payload=deepcopy(first['payload']);payload['revision']=first['revision'];payload['settlement']['quotation_required']=False
    finance.save(db,actor,'project',projects[0].id,finance.FinanceWrite.model_validate(payload))
    assert service.read('sub-client',children[0].id,db,actor)['quotation_required'] is False
    assert not finance.context(db,'project',projects[1].id)['payload']['settlement']['quotation_required']
    assert db.get(SubClientFinancePreference,children[0].id).revision==5
    with pytest.raises(HTTPException) as stale:
        service.write('sub-client',children[0].id,service.SettingsWrite(revision=old['revision'],quotation_required=True),db,actor)
    assert stale.value.status_code==409


def test_period_party_statement_and_invoice_share_scope(environment,monkeypatch):
    db,actor,client,children,projects=seed(environment,monkeypatch)
    import interpretation_statements as statements
    invoice=finance.get_invoice(projects[0].id,db,actor)
    assert {row['id'] for row in invoice['items']}=={str(p.id) for p in projects[:2]}
    board=statements.build(db,projects[0].id,'2026-11','settlement')
    assert board['totals']=={'CNY':'200.00'}
    assert board['client_name']=='分支0'
    service.write_party(children[0].id,service.PeriodPartyWrite(month='2026-11',period=1,party='client',expected_party='sub_client'),db,actor)
    assert statements.build(db,projects[0].id,'2026-11','settlement')['client_name']=='测试客户'
    assert finance.get_invoice(projects[0].id,db,actor)['items'][0]['sub_client_id'] is None
    current=service.read('client',client.id,db,actor)
    service.write('client',client.id,service.SettingsWrite(revision=current['revision'],collection_terms='月结30天'),db,actor)
    assert finance.context(db,'project',projects[0].id)['collection_terms']=='月结30天'


def test_billing_period_change_and_permissions(environment,monkeypatch):
    db,actor,client,children,projects=seed(environment,monkeypatch)
    options=service.billing_period(projects[2].id,'2026-11',db,actor)
    assert {row['number'] for row in options['boards']}=={1,2}
    result=service.save_billing_period(projects[2].id,service.BillingWrite(month='2026-11',revision=options['revision'],board_id='2026-11:1'),db,actor)
    assert result['payload']['settlement']['period_number']==1
    assert len(service.get_period_projects(projects[0].id,db,actor)['items'])==4
    with pytest.raises(HTTPException) as stale:
        service.save_billing_period(projects[2].id,service.BillingWrite(month='2026-11',revision=options['revision']),db,actor)
    assert stale.value.status_code==409
    monkeypatch.setattr(finance,'user_has_permission',lambda *_:False)
    with pytest.raises(HTTPException) as denied:service.read('client',client.id,db,actor)
    assert denied.value.status_code==403
