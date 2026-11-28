from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from interpretation_customer_finance import calculate,FinanceWrite
from interpretation_status_notice import automatic_reason
from interpretation_candidate_status import apply


def rates():
 return [dict(direction='中文 ↔ 英语',amount=1000,currency='CNY',unit='天',quantity=1,tax_prices={'unit_price_excl_tax':1000,'unit_price_incl_tax':1100}),dict(direction='中文 ↔ 英语',amount=600,currency='CNY',unit='半天',quantity=1,tax_prices={'unit_price_excl_tax':600,'unit_price_incl_tax':660})]

@pytest.mark.parametrize('overtime,excl,incl',[(None,'1600.00','1760.00'),({'amount':0,'pricing_mode':'multiplier','base_rate_index':0,'multiplier':'1.5','quantity':2},'4600.00','5060.00'),({'amount':0,'pricing_mode':'rates','rates':[{'direction':'中文 ↔ 英语','amount':200,'unit':'小时','quantity':2,'tax_prices':{'unit_price_excl_tax':200,'unit_price_incl_tax':220}}]},'2000.00','2200.00')])
def test_combination_and_overtime_share_authoritative_totals(overtime,excl,incl):
 data=FinanceWrite(revision=0,rates=rates(),has_overtime=overtime is not None,overtime=overtime)
 values=calculate(data.model_dump(mode='json'))
 assert values['totals_excl_tax']=={'CNY':excl};assert values['totals_incl_tax']=={'CNY':incl}

def test_statement_includes_combination_overtime_once():
 from interpretation_statements import project_rows
 from datetime import datetime
 payload=FinanceWrite(revision=0,rates=rates(),has_overtime=True,overtime={'amount':0,'pricing_mode':'multiplier','base_rate_index':0,'multiplier':1.5,'quantity':2}).model_dump(mode='json')
 project=SimpleNamespace(id=uuid4(),order_no='IP-261128-001',project_name='加班对账',customer_order_no='',customer_confirmation_time=None,customer_consultation_time=None,created_at=datetime(2026,11,28))
 rows=project_rows(project,payload,'excl_tax')
 assert sum(Decimal(row['subtotal']) for row in rows)==Decimal('4600.00')
 assert len([row for row in rows if row['basis'].startswith('加班费')])==1

def test_group_discount_then_combined_adjustment_reaches_statement():
 from interpretation_statements import project_rows
 from datetime import datetime
 rows=rates()+[dict(direction='中文 ↔ 日语',amount=500,currency='CNY',unit='小时',quantity=1,tax_prices={'unit_price_excl_tax':500})]
 rows[0]['group_adjustments']=[{'currency':'CNY','excl_discount':90}]
 rows[0]['combined_adjustments']=[{'currency':'CNY','excl_amount':1800}]
 payload=FinanceWrite(revision=0,rates=rows,settlement={'tax_basis':'excl_tax'}).model_dump(mode='json')
 assert calculate(payload)['totals_excl_tax']=={'CNY':'1800.00'}
 project=SimpleNamespace(id=uuid4(),order_no='IP-261128-001',project_name='组合折扣',customer_order_no='',client_full_name='',client_short_name='')
 assert sum(Decimal(row['subtotal']) for row in project_rows(project,payload,'excl_tax'))==Decimal('1800')
 from interpretation_customer_finance import quotation_context
 assert quotation_context(project,None,payload)['document']['items'][0]['unit_price']=='1800.00'
 payload['rates'][0]['combined_adjustments']=[]
 assert calculate(payload)['totals_excl_tax']=={'CNY':'1940.00'}

@pytest.mark.parametrize('before,current,status,text',[(('甲',),(),'client_cancelled','客户取消人选：甲'),(('甲',),('甲','乙'),'client_added','客户增加人选：乙'),(('甲','乙'),('甲',),'client_reduced','客户减少人数：乙'),(('甲','乙'),('甲','丙'),'client_mixed','客户增减人选：增加：丙；减少：乙')])
def test_client_selection_counts_and_names(before,current,status,text,monkeypatch):
 import interpretation_candidate_status as logic
 people={name:uuid4() for name in {'甲','乙','丙'}}
 assignments=[SimpleNamespace(translator_id=people[name],translator_name=name,client_selected=name in current) for name in people]
 project=SimpleNamespace(project_status='client_selected',interpreter_assignments=assignments,assigned_interpreter_count=3)
 monkeypatch.setattr(logic,'selected_ids',lambda *_:{people[name] for name in current})
 logic.apply(None,project,{people[name] for name in before},[str(people[name]) for name in people])
 assert project.project_status==status
 assert automatic_reason(project,None,list(people),list(before))==text


def test_dual_payment_proofs_persist_and_appear_in_history(environment):
 from tests.test_translation_payments import project
 from routers.translation_payments import write
 import translation_payment_service as payments
 db,(actor,*_)=environment;row=project(db,actor)
 current=payments.read(db,row)
 result=write(row.id,payments.PaymentWrite(version=current['version'],confirmation={'is_paid':True,'payment_option':'deposit','proofs':'客户支付凭证','receipt_proofs':'信实收款凭证'},payments=[{'stage_type':'deposit','actual_amount':10,'receipt_proofs':'本次到账备注','proofs':'本次支付备注'}]),db,actor)
 assert result['confirmation']['receipt_proofs']=='信实收款凭证'
 assert result['payments'][0]['receipt_proofs']=='本次到账备注'
 assert result['payments'][0]['proofs']=='本次支付备注'
 db.expire_all();loaded=payments.read(db,row)
 assert loaded['confirmation']['receipt_proofs']=='信实收款凭证' and loaded['payments'][0]['receipt_proofs']=='本次到账备注'


def test_project_talent_profile_never_exposes_contacts(environment):
 from resource_models import ResourcePerson
 from routers.talent_options import read_project_talent_profile
 db,_=environment;person=ResourcePerson(id=uuid4(),resource_code='RC-PRIVATE',full_name='资料测试',status='standby',primary_phone='13800000000',wechat='secret-wechat')
 db.add(person);db.commit();profile=read_project_talent_profile(person.id,db)
 assert profile['full_name']=='资料测试' and not {'primary_phone','primary_email','wechat','contact_info'}&profile.keys()
