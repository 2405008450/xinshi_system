"""稿件查询性能与分页回归；只使用内存 SQLite。"""
from datetime import datetime, timedelta
from uuid import uuid4
import pytest

from sqlalchemy import event

from tests.test_chat_participant_access import environment
from tests.test_arrangement_order_targets import orders
from models import TranslationSubOrder
from manuscript_models import ManuscriptDispatch
from word_count_models import WordCountMetric
import preliminary_word_count as preliminary
import manuscript_service as service
import word_count_service as counts


def test_batch_matrices_keep_recursive_values_with_constant_queries(environment):
    db, (owner, _, _) = environment
    root, child, leaf, foreign = orders(db, owner)
    siblings = [TranslationSubOrder(id=uuid4(), parent_project_id=root.id,
        sub_order_no=f'{root.order_no}.{i:03}', sub_project_name=f'稿件{i}') for i in range(2, 102)]
    db.add_all(siblings)
    for row, value in [(root, 9999), (child, 8888), (leaf, 0), *[(r, 1) for r in siblings]]:
        db.add(WordCountMetric(id=uuid4(), project_id=root.id if row is root else None,
            sub_order_id=None if row is root else row.id, dimension='company', metric_type='words', count_value=value))
    db.add(preliminary.PreliminaryWordCountMetric(id=uuid4(), sub_order_id=leaf.id,
        metric_type='words', count_value=15))
    db.commit()
    statements = []
    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)
    event.listen(db.get_bind(), 'before_cursor_execute', record)
    try:
        legacy = {row.id: counts.entity_matrix_values(db, 'suborder', row.id) for row in [child, leaf, *siblings]}
        old_count = len(statements)
        statements.clear()
        counts.attach_entity_matrices(db, [root] * 102)
        new_count = len(statements)
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', record)
    assert old_count >= 400
    assert new_count <= 4
    assert root.word_count_matrix['company']['words'] == 100
    assert child.word_count_matrix['company']['words'] == 0
    assert root.word_count_matrix['preliminary']['words'] == 15
    assert root.word_count_matrix['customer']['words'] is None
    assert {row.id: row.word_count_matrix for row in [child, leaf, *siblings]} == legacy
    assert foreign.id not in legacy
    print(f'word_count_sql: {old_count} -> {new_count}')


def seed_dispatches(db, owner):
    root, child, leaf, foreign = orders(db, owner)
    rows = []
    for index in range(27):
        row = ManuscriptDispatch(id=uuid4(), entity_type='project', translation_project_id=root.id,
            order_no_snapshot=root.order_no, project_name_snapshot=f'安排{index:02}',
            status='draft' if index == 0 else 'cancelled' if index == 1 else 'sent',
            created_by=owner.id, created_at=datetime(2026, 11, 4, 12) + timedelta(minutes=index),
            updated_at=datetime(2026, 11, 4, 12, microsecond=123456))
        db.add(row); rows.append(row)
    hidden = ManuscriptDispatch(id=uuid4(), entity_type='suborder', translation_project_id=root.id,
        sub_order_id=leaf.id, order_no_snapshot=leaf.sub_order_no, project_name_snapshot='待确认不应出现',
        status='draft', created_at=datetime(2026, 11, 4, 13), updated_at=datetime(2026, 11, 4, 13))
    db.add(hidden); db.commit()
    return root, rows, hidden


def test_page_total_filters_stability_and_off_page_workbench(environment):
    db, (owner, _, _) = environment
    root, rows, hidden = seed_dispatches(db, owner)
    first = service.get_dispatch_page(db, current_user=owner, project_id=root.id,
        selected_dispatch_id=rows[4].id)
    second = service.get_dispatch_page(db, current_user=owner, skip=10)
    assert first['total'] == second['total'] == 27
    assert len(first['items']) == len(second['items']) == 10
    assert not ({r.id for r in first['items']} & {r.id for r in second['items']})
    assert {r.id for r in first['workbench_items']} == {rows[0].id, rows[1].id, rows[4].id, rows[26].id}
    assert hidden.id not in {r.id for r in first['items']}
    assert first['items'][0].id == rows[26].id
    assert {item['value'] for item in first['creator_options']} == {owner.id}
    from manuscript_schemas import ManuscriptDispatchPage
    serialized = ManuscriptDispatchPage.model_validate(first).model_dump(mode='json')
    assert serialized['items'][0]['updated_at'].endswith('.123456+08:00')
    from concurrency import assert_fresh, StaleUpdateError
    assert_fresh(rows[26], serialized['items'][0]['updated_at'])
    with pytest.raises(StaleUpdateError):
        assert_fresh(rows[26], '2026-11-04T11:59:59.123456+08:00')
    filtered = service.get_dispatch_page(db, current_user=owner, field_filters={
        'status': {'value': ['sent']}, 'project_name': {'value': '安排2'},
    })
    assert filtered['total'] == 7 and len(filtered['items']) == 7
    assert all(r.status == 'sent' and '安排2' in r.project_name_snapshot for r in filtered['items'])
    empty = service.get_dispatch_page(db, current_user=owner, keyword='不存在')
    assert empty['total'] == 0 and empty['skip'] == 0 and empty['items'] == []


def test_page_clamps_after_records_removed_and_workbench_is_entity_scoped(environment):
    db, (owner, _, _) = environment
    root, rows, hidden = seed_dispatches(db, owner)
    page = service.get_dispatch_page(db, current_user=owner, skip=900)
    assert page['skip'] == 20 and len(page['items']) == 7
    for row in rows[20:]:
        db.delete(row)
    db.commit()
    page = service.get_dispatch_page(db, current_user=owner, skip=20,
        project_id=root.id, sub_order_id=hidden.sub_order_id, selected_dispatch_id=rows[0].id)
    assert page['skip'] == 10 and len(page['items']) == 10
    assert page['workbench_items'] == []
