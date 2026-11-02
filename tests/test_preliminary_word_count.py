from decimal import Decimal
import pytest
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context,item,write
from word_count_schemas import WordCountMatrixPatch,WordCountCreateMatrix
from word_count_service import patch_word_count_matrix,replace_entity_matrix,get_word_count_matrix
from preliminary_word_count import PreliminaryWordCountMetric,ready
import translation_customer_finance as finance


def test_save_reload_and_fee_exclusion(environment):
    db,(owner,_,_)=environment;_,root,_,third=context(db,owner)
    result=patch_word_count_matrix(db,'suborder',third.id,WordCountMatrixPatch(changes=[
        dict(scope='entity',dimension='preliminary',metric_type='foreign_words',value=9999),
    ]),updated_by=owner.id)
    assert result['preliminary']['foreign_words']==9999
    assert result['customer']['foreign_words']==10
    data=write(db,owner,root,third,[item(amount='.2')])
    assert data['item']['totals']=={'CNY':'2.00'}
    assert data['item']['children'][0]['children'][0]['word_count_matrix']['preliminary']['foreign_words']==9999
    replace_entity_matrix(db,'suborder',third.id,WordCountCreateMatrix(preliminary={'words':0}),updated_by=owner.id);db.commit()
    saved=get_word_count_matrix(db,'suborder',third.id)
    assert saved['preliminary']['words']==0 and saved['preliminary']['foreign_words'] is None
    assert not saved['customer']['foreign_words']
    assert db.query(PreliminaryWordCountMetric).filter_by(sub_order_id=third.id).count()==1


def test_preliminary_migration_is_create_only_and_repeatable(environment):
    from tools.apply_preliminary_word_count_migration import apply_migration
    db,_=environment
    PreliminaryWordCountMetric.__table__.drop(db.connection());db.info.pop('preliminary_word_count_ready',None)
    apply_migration(db.connection());apply_migration(db.connection());assert ready(db)
