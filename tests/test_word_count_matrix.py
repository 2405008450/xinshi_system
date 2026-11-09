from uuid import uuid4

import pytest
from pydantic import ValidationError

from manuscript_service import _word_count_summary
import word_count_service
from tests.test_chat_participant_access import environment
from tests.test_arrangement_order_targets import orders
from word_count_schemas import WordCountCellChange, WordCountMatrixPatch, WordCountValues


def test_word_count_values_accept_all_workload_units_and_reject_negative():
    values = WordCountValues(words=0, foreign_words=12, documents=3, pages=25)
    assert values.words == 0
    assert values.foreign_words == 12
    assert values.documents == 3
    assert values.pages == 25

    with pytest.raises(ValidationError):
        WordCountValues(words=-1)
    with pytest.raises(ValidationError):
        WordCountValues(pages=-1)


def test_entity_change_rejects_translator_dimension():
    with pytest.raises(ValidationError):
        WordCountCellChange(
            scope="entity",
            dimension="planned",
            metric_type="words",
            value=100,
        )

    change = WordCountCellChange(
        scope="entity",
        dimension="company",
        metric_type="documents",
        value=4,
    )
    assert change.metric_type == "documents"


def test_translator_change_requires_arrangement_and_allows_delete():
    with pytest.raises(ValidationError):
        WordCountCellChange(
            scope="translator",
            dimension="actual",
            metric_type="words",
            value=100,
        )

    change = WordCountCellChange(
        scope="translator",
        arrangement_id=uuid4(),
        dimension="actual",
        metric_type="characters_no_spaces",
        value=None,
    )
    assert change.value is None


def test_summary_uses_fixed_metric_order_and_reports_more_values():
    summary = _word_count_summary(
        WordCountValues(words=0, characters_no_spaces=200, foreign_words=30)
    )
    assert summary == "字数 0（另有 2 项）"


def test_summary_supports_document_and_page_counts():
    summary = _word_count_summary(WordCountValues(documents=2, pages=18))
    assert summary == "份数 2（另有 1 项）"


def test_parent_statistics_can_be_written_through_patch_and_full_form(environment, monkeypatch):
    """有下级的母订单和中间订单都必须支持两种保存入口。"""
    from word_count_models import WordCountMetric
    from word_count_schemas import WordCountCreateMatrix

    db, (actor, _, _) = environment
    # 内存测试库没有 PostgreSQL 的 UUID 默认值。
    original_apply = word_count_service._apply_cell
    def apply_with_id(*args, **kwargs):
        original_apply(*args, **kwargs)
        for row in db.new:
            if isinstance(row, WordCountMetric) and row.id is None:
                row.id = uuid4()
    monkeypatch.setattr(word_count_service, '_apply_cell', apply_with_id)
    root, middle, _, _ = orders(db, actor)
    for kind, owner, owner_field in [
        ('project', root, 'project_id'),
        ('suborder', middle, 'sub_order_id'),
    ]:
        saved = word_count_service.patch_word_count_matrix(
            db, kind, owner.id,
            WordCountMatrixPatch(changes=[dict(scope='entity', dimension='company', metric_type='pages', value=12)]),
            updated_by=actor.id,
        )
        assert saved['company']['pages'] == 12
        assert saved['source'] == kind
        assert saved['sub_order_count'] > 0
        query = db.query(WordCountMetric).filter_by(**{owner_field: owner.id}, dimension='company')
        assert query.one().count_value == 12
        word_count_service.replace_entity_matrix(
            db, kind, owner.id, WordCountCreateMatrix(company={'words': 345}), updated_by=actor.id,
        )
        db.commit()
        assert query.one().metric_type == 'words'
        assert query.one().count_value == 345
        assert word_count_service.get_word_count_matrix(db, kind, owner.id)['company']['words'] == 345
