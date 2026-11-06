from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context,item,write
from word_count_schemas import WordCountMatrixPatch,WordCountCreateMatrix
from word_count_service import patch_word_count_matrix,get_word_count_matrix,save_created_entity_matrix
from word_count_models import WordCountMetric
import translation_quantity_basis as basis
import translation_customer_finance as finance
import translation_duration_metrics as duration

def test_default_customer_priority_company_fallback_and_zero():
    assert basis.resolve({'customer':{'pages':0},'company':{'words':100}},'customer_auto')[:3]==(0,'customer','pages')
    assert basis.resolve({'company':{'hours':1.5}},'customer_auto')[:3]==(1.5,'company','hours')
    assert basis.resolve({'customer':{'pages':2},'company':{'minutes':30}},'company_minutes')[:3]==(30,'company','minutes')
    assert '均未填写' in basis.resolve({},'customer_auto')[3]

def test_duration_migration_repeatable_and_preserves_old_tables(environment):
    from tools.apply_translation_duration_migration import apply_migration
    db,_=environment
    duration.TranslationDurationMetric.__table__.drop(db.connection());db.info.pop('translation_duration_ready',None)
    before=set(inspect(db.connection()).get_table_names())
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())==before|{'translation_duration_metric'}
    assert duration.ready(db)

def test_duration_patch_single_row_finance_and_switching_units(environment):
    db,(actor,*_)=environment;_,root,_,leaf=context(db,actor)
    # 旧测试数据只清理隔离库中的本行，客户缺省时自动使用我司小时。
    db.query(WordCountMetric).filter_by(sub_order_id=leaf.id,dimension='customer').delete();db.commit()
    def patch(changes):return patch_word_count_matrix(db,'suborder',leaf.id,WordCountMatrixPatch(changes=changes),updated_by=actor.id)
    cell=lambda metric,value:dict(scope='entity',dimension='company',metric_type=metric,value=value)
    saved=patch([cell('hours',1.5)])
    assert saved['company']['hours']==1.5
    loaded=finance.read(db,root.id)
    selected=next(child for child in loaded['item']['children'][0]['children'] if child['id']==str(leaf.id))
    assert selected['word_count_matrix']['company']['hours']==1.5
    result=write(db,actor,root,leaf,[item(metric='customer_auto',amount=100)])
    assert result['item']['totals']=={'CNY':'150.00'}
    charge=finance.primary(leaf)
    assert charge.metric_type in basis.LEGACY_METRICS
    with pytest.raises(HTTPException):patch([cell('words',50)])
    db.rollback()
    saved=patch([cell('hours',None),cell('minutes',90)])
    assert saved['company']['hours'] is None and saved['company']['minutes']==90
    assert db.query(duration.TranslationDurationMetric).count()==1
    assert finance.read(db,root.id)['item']['totals']=={'CNY':'9000.00'}

def test_create_matrix_rejects_multiple_company_fields(environment):
    db,(actor,*_)=environment;_,root,_,leaf=context(db,actor)
    with pytest.raises(HTTPException):save_created_entity_matrix(db,'suborder',leaf.id,WordCountCreateMatrix(company={'words':0,'pages':1}),updated_by=actor.id)
