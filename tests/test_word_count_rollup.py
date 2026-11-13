"""母子订单独立填报，覆盖列表、弹窗、修改和删除的互不影响。"""
from uuid import uuid4

from tests.test_chat_participant_access import environment
from tests.test_arrangement_order_targets import orders
from models import TranslationSubOrder
from word_count_models import WordCountMetric
from word_count_schemas import WordCountMatrixPatch
from word_count_service import get_word_count_matrix, patch_word_count_matrix


def test_word_count_edits_are_visible_in_finance_and_audited(environment):
    import translation_customer_finance as finance
    from translation_finance_audit import history

    db, (actor, _, _) = environment
    root, _, leaf, _ = orders(db, actor)

    def patch(value):
        return patch_word_count_matrix(db, 'suborder', leaf.id, WordCountMatrixPatch(changes=[
            {'scope':'entity','dimension':'customer','metric_type':'words','value':value},
        ]), updated_by=actor.id)

    patch(120)
    patch(0)
    patch(0)
    assert get_word_count_matrix(db, 'suborder', leaf.id)['customer']['words'] == 0
    root_node = finance.read(db, root.id)['item']
    assert root_node['word_count_matrix']['customer']['words'] is None
    assert get_word_count_matrix(db, 'suborder', leaf.id)['customer']['words'] == 0
    records = history(db, root.id, leaf.id)
    assert records['total'] == 2
    latest = records['items'][0]
    assert latest['actor_name'] == actor.full_name
    assert latest['before']['word_count_cells'][0]['value'] == 120
    assert latest['after']['word_count_cells'][0]['value'] == 0
import crud


def test_independent_counts_are_consistent_across_popup_list_and_updates(environment):
    db, (user, _, _) = environment
    root, child, third, _ = orders(db, user)
    sibling = TranslationSubOrder(id=uuid4(), parent_project_id=root.id,
        sub_order_no=root.order_no+'.002', sub_project_name='第二份.docx')
    nested = TranslationSubOrder(id=uuid4(), parent_project_id=root.id,
        sub_order_no=child.sub_order_no+'.002', sub_project_name='第二部分.docx')
    db.add_all([sibling, nested])
    for owner, value in [(root, 9000), (child, 8000), (third, 10), (nested, 20), (sibling, 7)]:
        for dimension in ['company', 'customer', 'translator_estimate']:
            db.add(WordCountMetric(id=uuid4(), project_id=root.id if owner is root else None,
                sub_order_id=None if owner is root else owner.id, dimension=dimension,
                metric_type='words', count_value=value))
    db.add(WordCountMetric(id=uuid4(), sub_order_id=third.id, dimension='customer', metric_type='pages', count_value=0))
    db.commit()
    for kind, owner, expected in [('project', root, 9000), ('suborder', child, 8000), ('suborder', third, 10)]:
        matrix = get_word_count_matrix(db, kind, owner.id)
        for dimension in ['company', 'customer', 'translator_estimate']:
            assert matrix[dimension]['words'] == expected
        assert matrix['customer']['documents'] is None
    assert get_word_count_matrix(db, 'project', root.id)['customer']['pages'] is None
    crud._attach_word_count_matrices(db, projects=[root])
    assert root.word_count_matrix['company']['words'] == 9000
    assert child.word_count_matrix['company']['words'] == 8000
    assert child.word_count_matrix_source == 'suborder'
    crud._attach_word_count_matrices(db, sub_orders=[child])
    assert child.word_count_matrix['company']['words'] == 8000
    patch_word_count_matrix(db, 'suborder', third.id, WordCountMatrixPatch(changes=[
        dict(scope='entity', dimension='customer', metric_type='words', value=100),
        dict(scope='entity', dimension='customer', metric_type='pages', value=None),
        dict(scope='entity', dimension='preliminary', metric_type='words', value=999),
    ]), updated_by=user.id)
    matrix = get_word_count_matrix(db, 'project', root.id)
    assert matrix['customer']['words'] == 9000
    assert matrix['company']['words'] == 9000
    assert matrix['preliminary']['words'] is None
    assert get_word_count_matrix(db, 'suborder', third.id)['customer']['words'] == 100
    assert get_word_count_matrix(db, 'suborder', child.id)['customer']['words'] == 8000
    db.delete(nested); db.commit(); db.expire_all()
    assert get_word_count_matrix(db, 'project', root.id)['customer']['words'] == 9000


def test_leaf_without_children_keeps_own_counts(environment):
    db, (user, _, _) = environment
    root, child, third, _ = orders(db, user)
    db.add(WordCountMetric(id=uuid4(), sub_order_id=third.id, dimension='company', metric_type='words', count_value=0))
    db.commit()
    matrix = get_word_count_matrix(db, 'suborder', third.id)
    assert matrix['source'] == 'suborder' and matrix['company']['words'] == 0
    assert get_word_count_matrix(db, 'project', root.id)['company']['words'] is None
    assert get_word_count_matrix(db, 'suborder', child.id)['company']['words'] is None
