from uuid import uuid4
from decimal import Decimal
import pytest
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context,item,write
from word_count_models import WordCountMetric
import translation_quantity_basis as basis
import translation_customer_finance as finance


def test_customer_unique_zero_and_ambiguous_values():
    assert basis.resolve({'customer':{'pages':0}},'customer_auto')[:3]==(0,'customer','pages')
    assert basis.resolve({'customer':{'foreign_words':120}},'customer_auto')[:3]==(120,'customer','foreign_words')
    assert basis.resolve({'customer':{'words':10,'characters_no_spaces':30}},'customer_auto')[0] is None
    assert basis.resolve({'customer':{'words':10,'characters_no_spaces':30}},'customer_auto:words')[0]==10
    assert basis.resolve({'customer':{'pages':5}},'customer_auto:words')==(None,'customer','words','未登记对应数量')
    assert basis.resolve({'customer':{}},'customer_auto')[0] is None


@pytest.mark.parametrize('metric',basis.METRICS)
def test_company_dimensions_are_independent(metric):
    assert basis.resolve({'customer':{metric:999},'company':{metric:25}},'company_'+metric)[:3]==(25,'company',metric)


@pytest.mark.parametrize('metric',['words','documents','pages'])
def test_company_price_persistence_and_other_project_views(environment,metric):
    db,(owner,_,_)=environment;_,root,_,third=context(db,owner)
    db.add(WordCountMetric(id=uuid4(),sub_order_id=third.id,dimension='company',metric_type=metric,count_value=15));db.commit()
    result=write(db,owner,root,third,[item(metric='company_'+metric,amount='.2')])
    leaf=result['item']['children'][0]['children'][0]
    assert leaf['prices'][0]['metric']=='company_'+metric
    assert leaf['prices'][0]['quantity']==15
    assert result['item']['totals']=={'CNY':'3.00'}
    loaded=finance.crud.get_translation_project(db,root.id)
    charge=finance.primary(next(child for child in loaded.sub_orders if child.id==third.id))
    assert charge.metric_type==metric and charge.calculated_amount==Decimal('3.00')
    assert db.get(basis.TranslationChargeQuantityBasis,charge.id).mode=='company_'+metric


def test_customer_auto_tracks_the_current_unique_column(environment):
    db,(owner,_,_)=environment;_,root,_,third=context(db,owner)
    db.query(WordCountMetric).filter_by(sub_order_id=third.id,dimension='customer').delete()
    row=WordCountMetric(id=uuid4(),sub_order_id=third.id,dimension='customer',metric_type='pages',count_value=5);db.add(row);db.commit()
    result=write(db,owner,root,third,[item(metric='customer_auto',amount='2')])
    assert result['item']['totals']=={'CNY':'10.00'}
    row.metric_type='documents';row.count_value=3;db.commit()
    assert finance.read(db,root.id)['item']['totals']=={'CNY':'6.00'}


def test_explicit_basis_can_be_saved_without_quantity_and_keeps_unit_size(environment):
    db,(owner,_,_)=environment;_,root,_,third=context(db,owner)
    db.query(WordCountMetric).filter_by(sub_order_id=third.id,dimension='customer').delete()
    db.add(WordCountMetric(id=uuid4(),sub_order_id=third.id,dimension='customer',metric_type='pages',count_value=5))
    db.commit()
    result=write(db,owner,root,third,[item(metric='customer_auto:words',amount='200',unit_size='1000')])
    leaf=result['item']['children'][0]['children'][0]
    assert leaf['prices'][0]['quantity'] is None
    assert Decimal(leaf['prices'][0]['unit_size'])==1000
    db.add(WordCountMetric(id=uuid4(),sub_order_id=third.id,dimension='customer',metric_type='words',count_value=1000))
    db.commit()
    result=finance.read(db,root.id)
    assert result['item']['totals']=={'CNY':'200.00'}


def test_create_only_repeatable_basis_migration(environment):
    from tools.apply_translation_quantity_basis_migration import apply_migration
    db,_=environment
    basis.TranslationChargeQuantityBasis.__table__.drop(db.connection());db.info.pop('translation_quantity_basis_ready',None)
    apply_migration(db.connection());apply_migration(db.connection());assert basis.ready(db)
