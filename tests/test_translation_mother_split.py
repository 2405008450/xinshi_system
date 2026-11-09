from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case
from schemas import TranslationProjectCreate,TranslationProjectUpdate,TranslationSubOrderCreate,TranslationSubOrderBulkCreate


def root(case,name='原文件.docx'):
    db,user,crud=case
    return crud.create_translation_project(db,TranslationProjectCreate(project_name=name,created_by=user.id,service_content='翻译',customer_requirement_professional='原要求',remarks='原说明',language_pair='中文→英语',priority='高',word_count_matrix={'company':{'words':100}},project_status='confirmed'),order_no='TP-261108-990',folder_root='.' not in name)


def test_small_creation_preserves_original_and_independent_parent_statistics(case):
    from translation_mother_split import TranslationMotherSplit
    db,user,crud=case;parent=root(case)
    added=crud.create_sub_order(db,TranslationSubOrderCreate(parent_project_id=parent.id,sub_project_name='新增.pdf',word_count_matrix={'company':{'words':20}},created_by=user.id,preserve_original_file=True))
    assert added.sub_order_no==parent.order_no+'.002' and added.word_count_matrix['company']['words']==20
    parent=crud.get_translation_project(db,parent.id)
    first=next(row for row in parent.sub_orders if row.sub_order_no.endswith('.001'))
    assert first.sub_project_name=='原文件.docx' and first.word_count_matrix['company']['words']==100
    assert first.service_content=='翻译' and first.customer_requirement_professional=='原要求' and first.remarks=='原说明'
    assert parent.project_name=='原文件' and parent.source_file_name=='原文件'
    assert parent.word_count_matrix['company']['words']==100 and parent.mother_split_review['required']
    saved=db.get(TranslationMotherSplit,parent.id)
    assert saved.original_information['word_count_matrix']['company']['words']==100
    assert 'client_id' not in saved.original_information
    crud.update_translation_project(db,parent.id,TranslationProjectUpdate(project_name='修改后的汇总项目',source_file_name='修改后的汇总项目',customer_requirement_professional='新的母要求',mother_split_reviewed=True),actor_user_id=user.id)
    first=crud.get_sub_order(db,first.id)
    assert first.customer_requirement_professional=='原要求'
    assert not crud.get_translation_project(db,parent.id).mother_split_review['required']
    third=crud.create_sub_order(db,TranslationSubOrderCreate(parent_project_id=parent.id,sub_project_name='第三个.txt',created_by=user.id,preserve_original_file=True))
    assert third.sub_order_no.endswith('.003')


def test_bulk_creation_offsets_all_new_files(case):
    db,user,crud=case;parent=root(case)
    children,_=crud.create_sub_orders_bulk(db,TranslationSubOrderBulkCreate(parent_project_id=parent.id,sub_project_names=['第二个.pdf','第三个.txt'],preserve_original_file=True),user.id)
    assert [row.sub_order_no.rsplit('.',1)[1] for row in children]==['002','003']


def test_no_extension_and_already_hierarchical_mother_do_not_convert(case):
    from translation_mother_split import TranslationMotherSplit
    db,user,crud=case;parent=root(case,'汇总项目')
    child=crud.create_sub_order(db,TranslationSubOrderCreate(parent_project_id=parent.id,sub_project_name='a.pdf',created_by=user.id,preserve_original_file=True))
    assert child.sub_order_no.endswith('.001') and db.get(TranslationMotherSplit,parent.id) is None


def test_failure_rolls_back_original_and_new_child_together(case):
    from models import TranslationSubOrder
    from translation_mother_split import TranslationMotherSplit
    db,user,crud=case;parent=root(case)
    with pytest.raises(Exception):
        crud.create_sub_order(db,TranslationSubOrderCreate(parent_project_id=parent.id,sub_project_name='b.pdf',translator_id=uuid4(),created_by=user.id,preserve_original_file=True))
    db.rollback()
    assert db.query(TranslationSubOrder).count()==0 and db.query(TranslationMotherSplit).count()==0
    assert crud.get_translation_project(db,parent.id).source_file_name=='原文件.docx'


def test_migration_only_creates_new_table_and_is_repeatable():
    from sqlalchemy import create_engine,inspect,text
    from tools.apply_translation_mother_split_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        for table in ('translation_project','translation_sub_order','app_user'):
            connection.execute(text(f'CREATE TABLE {table} (id CHAR(32) PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())=={'translation_project','translation_sub_order','app_user','translation_mother_split'}
