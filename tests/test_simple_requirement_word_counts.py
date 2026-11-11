"""简单需求统计累加：隔离 SQLite，覆盖重试幂等、逐级累计及失败回滚。"""
from uuid import uuid4
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,inspect,text
from tests.test_translation_simple_requirements import context,payload
from tests.test_chat_participant_access import environment
import translation_simple_requirements as service
from translation_simple_requirement_counts import SimpleRequirementWordCount
from word_count_models import WordCountMetric
from word_count_service import get_word_count_matrix,patch_word_count_matrix
from word_count_schemas import WordCountMatrixPatch
from models import TranslationSubOrder,AppNotification


def test_add_to_existing_counts_once_retry_and_history(context):
 db,actor,member,_,root,_=context
 db.add(WordCountMetric(id=uuid4(),project_id=root.id,dimension='company',metric_type='words',count_value=100));db.commit()
 request=payload(root,member,word_count_matrix={'company':{'words':23},'customer':{'words':20}})
 result=service.create_requirement(db,root.id,request,actor)
 assert result['word_count_added'] and result['word_count_matrix']['company']['words']==123
 assert result['item']['word_count_matrix']['company']['words']==23
 assert get_word_count_matrix(db,'project',root.id)['customer']['words']==20
 assert service.create_requirement(db,root.id,request,actor)['word_count_matrix']['company']['words']==123
 assert db.query(SimpleRequirementWordCount).count()==1 and db.query(AppNotification).count()==1
 with pytest.raises(HTTPException):service.create_requirement(db,root.id,request.model_copy(update={'word_count_matrix':request.word_count_matrix.model_copy(update={'company':request.word_count_matrix.company.model_copy(update={'words':24})})}),actor)
 db.rollback()
 second=service.create_requirement(db,root.id,payload(root,member,word_count_matrix={'company':{'words':7}}),actor)
 assert second['word_count_matrix']['company']['words']==130
 assert service.create_requirement(db,root.id,request,actor)['word_count_matrix']['company']['words']==130
 assert db.query(SimpleRequirementWordCount).count()==2


def test_parent_counts_include_direct_simple_requirements_without_overwriting_children(context):
 db,actor,member,_,root,_=context
 db.add(WordCountMetric(id=uuid4(),project_id=root.id,dimension='company',metric_type='words',count_value=9000))
 children=[]
 for index,count in enumerate([10,20],1):
  child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+f'.{index:03}',sub_project_name=f'{index}.pdf');db.add(child);children.append(child)
  db.add(WordCountMetric(id=uuid4(),sub_order_id=child.id,dimension='company',metric_type='words',count_value=count))
 db.commit()
 result=service.create_requirement(db,root.id,payload(root,member,word_count_matrix={'company':{'words':5}}),actor)
 assert result['word_count_matrix']['company']['words']==9005
 import crud
 crud._attach_word_count_matrices(db,projects=[root]);assert root.word_count_matrix['company']['words']==9005
 assert get_word_count_matrix(db,'project',root.id)['company']['words']==9005
 patch_word_count_matrix(db,'suborder',children[0].id,WordCountMatrixPatch(changes=[{'scope':'entity','dimension':'company','metric_type':'words','value':100}]),updated_by=actor.id)
 assert get_word_count_matrix(db,'project',root.id)['company']['words']==9005


def test_failure_rolls_back_statistics_requirement_status_and_notifications(context,monkeypatch):
 db,actor,member,_,root,_=context
 original_status=root.project_status
 monkeypatch.setattr(service,'notification',lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError('模拟通知写入失败')))
 with pytest.raises(RuntimeError):service.create_requirement(db,root.id,payload(root,member,word_count_matrix={'company':{'words':10}}),actor)
 db.rollback()
 assert root.project_status==original_status
 assert db.query(SimpleRequirementWordCount).count()==0 and db.query(service.TranslationSimpleRequirement).count()==0
 assert get_word_count_matrix(db,'project',root.id)['company']['words'] is None


def test_mismatched_leaf_units_rejected_zero_preserved_and_migration_is_create_only(context):
 db,actor,member,_,root,_=context
 db.add(WordCountMetric(id=uuid4(),project_id=root.id,dimension='company',metric_type='pages',count_value=3));db.commit()
 with pytest.raises(HTTPException,match='') as error:service.create_requirement(db,root.id,payload(root,member,word_count_matrix={'company':{'words':10}}),actor)
 assert error.value.status_code==422;db.rollback()
 result=service.create_requirement(db,root.id,payload(root,member,word_count_matrix={'company':{'pages':0}}),actor)
 assert result['word_count_added'] and result['word_count_matrix']['company']['pages']==3
 from tools.apply_simple_requirement_word_count_migration import apply_migration
 engine=create_engine('sqlite://')
 with engine.begin() as conn:
  conn.execute(text('CREATE TABLE translation_simple_requirement(id CHAR(32) PRIMARY KEY)'));conn.execute(text('CREATE TABLE translation_project(id CHAR(32) PRIMARY KEY)'))
  before=set(inspect(conn).get_table_names());apply_migration(conn);apply_migration(conn)
  assert set(inspect(conn).get_table_names())-before=={'translation_simple_requirement_word_count'}
 engine.dispose()


def test_preserving_original_file_does_not_copy_simple_requirement_twice(context):
 db,actor,member,_,root,_=context
 from sqlalchemy import event
 def assign_ids(session,*_):
  for row in session.new:
   if hasattr(row,'id') and row.id is None:row.id=uuid4()
 event.listen(db,'before_flush',assign_ids)
 db.add(WordCountMetric(id=uuid4(),project_id=root.id,dimension='company',metric_type='words',count_value=100));db.commit()
 service.create_requirement(db,root.id,payload(root,member,word_count_matrix={'company':{'words':20}}),actor)
 from schemas import TranslationSubOrderCreate
 import crud
 crud.create_sub_order(db,TranslationSubOrderCreate(parent_project_id=root.id,sub_project_name='新文件.pdf',preserve_original_file=True,created_by=actor.id,word_count_matrix={'company':{'words':10}}))
 assert get_word_count_matrix(db,'project',root.id)['company']['words']==120
