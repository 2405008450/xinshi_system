from uuid import uuid4

import pytest
from pydantic import ValidationError

from manuscript_service import _word_count_summary
from word_count_schemas import WordCountCellChange, WordCountValues


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
