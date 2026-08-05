from uuid import uuid4

import pytest
from pydantic import ValidationError

from manuscript_service import _word_count_summary
from word_count_schemas import WordCountCellChange, WordCountValues


def test_word_count_values_accept_zero_and_reject_negative():
    values = WordCountValues(words=0, foreign_words=12)
    assert values.words == 0
    assert values.foreign_words == 12

    with pytest.raises(ValidationError):
        WordCountValues(words=-1)


def test_entity_change_rejects_translator_dimension():
    with pytest.raises(ValidationError):
        WordCountCellChange(
            scope="entity",
            dimension="planned",
            metric_type="words",
            value=100,
        )


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

