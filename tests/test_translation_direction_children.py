"""多方向自动拆单回归：仅内存 SQLite，不连接业务库。"""
from uuid import uuid4
import pytest
from sqlalchemy import event
from tests.test_chat_participant_access import environment

@pytest.fixture
def case(environment):
    import crud
    from interpretation_models import InterpretationLanguage
    db, users = environment
    def ids(session, *_):
        for row in session.new:
            if hasattr(row, 'id') and row.id is None:
                row.id = uuid4()
    event.listen(db, 'before_flush', ids)
    db.add_all([InterpretationLanguage(id=uuid4(), label=label) for label in ['中文', '英语', '法语', '日语']])
    db.commit()
    return db, users[0], crud

def create(case, **kw):
    from schemas import TranslationProjectCreate
    db, user, crud = case
    return crud.create_translation_project(db, TranslationProjectCreate(
        project_name='原文件.docx', language_pair='中文→英语；中文→法语', created_by=user.id, **kw,
    ), order_no='TP-261107-901')

def test_root_directions_create_once_and_added_direction_keeps_manual_values(case):
    from schemas import TranslationProjectUpdate
    db, user, crud = case
    root = create(case, project_status='confirmed', word_count_matrix={'company': {'words': 100}},network_file_path=r'D:\原文目录')
    assert root.auto_created_child_count == 2
    children = sorted(root.sub_orders, key=lambda row: row.sub_order_no)
    assert all(row.network_file_path=='同上一级订单' for row in children)
    assert [row.sub_order_no for row in children] == ['TP-261107-901.001', 'TP-261107-901.002']
    assert {row.language_pair for row in children} == {'中文→英语', '中文→法语'}
    assert {row.sub_project_name for row in children} == {'原文件.docx'}
    assert {row.status for row in children} == {'confirmed'}
    from word_count_service import get_word_count_matrix
    assert [get_word_count_matrix(db, 'suborder', row.id)['company']['words'] for row in children] == [100, 100]
    children[0].remarks = '人工备注保留'
    db.commit()
    again = crud.update_translation_project(db, root.id, TranslationProjectUpdate(language_pair=root.language_pair), actor_user_id=user.id)
    assert again.auto_created_child_count == 0
    updated = crud.update_translation_project(db, root.id, TranslationProjectUpdate(language_pair='中文→英语；中文→法语；中文→日语'), actor_user_id=user.id)
    assert updated.auto_created_child_count == 1
    assert len(updated.sub_orders) == 3
    assert db.get(type(children[0]), children[0].id).remarks == '人工备注保留'
    assert updated.word_count_matrix['company']['words'] == 100
    assert updated.word_count_matrix_source == 'project'
    from schemas import TranslationSubOrderUpdate
    from word_count_service import patch_word_count_matrix
    from word_count_schemas import WordCountMatrixPatch
    crud.update_sub_order(db,children[0].id,TranslationSubOrderUpdate(status='paused', word_count_matrix={'company':{'words':80}}))
    assert crud.get_sub_order(db, children[0].id).status == 'paused'
    assert crud.get_sub_order(db, children[1].id).status == 'confirmed'
    assert get_word_count_matrix(db,'project',root.id)['company']['words']==100
    patch_word_count_matrix(db,'project',root.id,WordCountMatrixPatch(changes=[{'scope':'entity','dimension':'company','metric_type':'words','value':120}]),updated_by=user.id)
    assert get_word_count_matrix(db,'project',root.id)['company']['words']==120
    assert get_word_count_matrix(db,'suborder',children[0].id)['company']['words']==80


def test_file_children_split_into_second_level_without_duplicate_root_siblings(case):
    db, user, crud = case
    root = create(case, initial_sub_order_names=['文件一.pdf', '文件二.xlsx'])
    children = root.sub_orders
    first = [row for row in children if row.sub_order_no.count('.') == 1]
    second = [row for row in children if row.sub_order_no.count('.') == 2]
    assert len(first) == 2 and len(second) == 4
    assert root.auto_created_child_count == 4
    for parent in first:
        nested = [row for row in second if row.sub_order_no.rsplit('.', 1)[0] == parent.sub_order_no]
        assert {row.language_pair for row in nested} == {'中文→英语', '中文→法语'}
        assert {row.sub_project_name for row in nested} == {parent.sub_project_name}
    from business_numbering import translation_suborder_parent
    for row in second:
        parent = next(p for p in first if row.sub_order_no.startswith(p.sub_order_no+'.'))
        assert translation_suborder_parent(db, row) == parent.id


def test_fourth_level_file_splits_into_shared_path_direction_children(case):
    from models import TranslationProject
    from schemas import TranslationSubOrderCreate, TranslationSubOrderUpdate
    db, user, crud = case
    root = TranslationProject(id=uuid4(), order_no='TP-261107-901', project_name='原文件.docx')
    db.add(root); db.commit()
    child = crud.create_sub_order(db, TranslationSubOrderCreate(parent_project_id=root.id, sub_project_name='原文件.docx', language_pair='中文→英语', created_by=user.id))
    assert child.auto_created_child_count == 0
    updated = crud.update_sub_order(db, child.id, TranslationSubOrderUpdate(language_pair='中文→英语；中文→法语'))
    assert updated.auto_created_child_count == 2
    grand = db.query(type(child)).filter(type(child).sub_order_no.startswith(child.sub_order_no+'.')).first()
    crud.update_sub_order(db, grand.id, TranslationSubOrderUpdate(language_pair='中文→英语；中文→法语'))
    third=db.query(type(child)).filter(type(child).sub_order_no.startswith(grand.sub_order_no+'.')).first()
    crud.update_sub_order(db, third.id, TranslationSubOrderUpdate(language_pair='中文→英语；中文→法语'))
    fourth=db.query(type(child)).filter(type(child).sub_order_no.startswith(third.sub_order_no+'.')).first()
    update = TranslationSubOrderUpdate(language_pair='中文→英语；中文→法语', network_file_path=r'D:\资料\原文件.docx')
    assert crud.update_sub_order(db, fourth.id, update).auto_created_child_count == 2
    assert crud.update_sub_order(db, fourth.id, update).auto_created_child_count == 0
    leaves = db.query(type(child)).filter(type(child).sub_order_no.startswith(fourth.sub_order_no+'.')).all()
    assert {row.language_pair for row in leaves} == {'中文→英语','中文→法语'}
    assert all(row.sub_project_name == fourth.sub_project_name and row.network_file_path == '同上一级订单' for row in leaves)
    with pytest.raises(ValueError, match='只能选择一个'):
        crud.update_sub_order(db, leaves[0].id, update)
    db.rollback()


def test_child_creation_failure_rolls_back_entire_project(case, monkeypatch):
    from models import TranslationProject, TranslationSubOrder
    db, user, crud = case
    original = crud._create_sub_order_in_transaction
    calls = []
    def fail(db, payload, **kw):
        calls.append(payload)
        if len(calls) == 2:
            raise ValueError('模拟第二个方向创建失败')
        return original(db, payload, **kw)
    monkeypatch.setattr(crud, '_create_sub_order_in_transaction', fail)
    with pytest.raises(ValueError, match='模拟'):
        create(case)
    db.rollback()
    assert db.query(TranslationProject).count() == 0
    assert db.query(TranslationSubOrder).count() == 0


def test_second_level_number_recycles_in_its_direct_parent_pool(case):
    from models import TranslationSubOrder
    from business_numbering import BusinessNumberDeletionHistory
    from translation_direction_service import next_number
    db, user, crud = case
    root = create(case, initial_sub_order_names=['文件.pdf'])
    first = next(row for row in root.sub_orders if row.sub_order_no.count('.') == 1)
    grand = next(row for row in root.sub_orders if row.sub_order_no.count('.') == 2)
    old_number = grand.sub_order_no
    db.info['number_actor'] = user.id
    db.delete(grand); db.commit()
    history = db.query(BusinessNumberDeletionHistory).filter_by(number=old_number).one()
    assert history.scope == f'translation_suborder:{first.id}'
    assert next_number(db, root, first) == old_number
    assert db.query(TranslationSubOrder).filter_by(sub_order_no=old_number).count() == 0


def test_second_level_matrix_uses_file_raw_values_and_does_not_multiply_on_repeat(case):
    from models import TranslationProject
    from schemas import TranslationSubOrderCreate, TranslationSubOrderUpdate
    db, user, crud = case
    root = TranslationProject(id=uuid4(), order_no='TP-261107-901', project_name='文件集合')
    db.add(root); db.commit()
    first = crud.create_sub_order(db, TranslationSubOrderCreate(parent_project_id=root.id,
        sub_project_name='文件.pdf', language_pair='中文→英语；中文→法语', created_by=user.id,
        status='paused', word_count_matrix={'customer': {'pages': 5}, 'company': {'words': 100}}))
    assert crud.get_translation_project(db, root.id).word_count_matrix['company']['words'] is None
    first_direction = next(row for row in root.sub_orders if row.sub_order_no.startswith(first.sub_order_no + '.'))
    crud.update_sub_order(db, first_direction.id, TranslationSubOrderUpdate(word_count_matrix={'company': {'words': 80}}))
    again = crud.update_sub_order(db, first.id, TranslationSubOrderUpdate(language_pair='中文→英语；中文→法语；中文→日语'))
    assert again.auto_created_child_count == 1
    matrix = crud.get_translation_project(db, root.id).word_count_matrix
    assert matrix['company']['words'] is None
    assert matrix['customer']['pages'] is None
    children = [row for row in root.sub_orders if row.sub_order_no.startswith(first.sub_order_no + '.')]
    assert sorted(row.word_count_matrix['company']['words'] for row in children) == [80, 100, 100]
    assert {row.status for row in children} == {'paused'}
