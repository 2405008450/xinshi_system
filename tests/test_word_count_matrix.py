from uuid import uuid4
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from manuscript_service import _word_count_summary
import word_count_service
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


def test_project_matrix_keeps_its_own_values_when_suborders_exist(monkeypatch):
    project_id = uuid4()
    project_metric = SimpleNamespace(
        dimension="company",
        metric_type="words",
        count_value=9000,
    )

    class MetricQuery:
        def all(self):
            return [project_metric]

    class SubOrderCountQuery:
        def filter(self, *_conditions):
            return self

        def count(self):
            return 2

    class FakeDb:
        def query(self, *_entities):
            return SubOrderCountQuery()

    monkeypatch.setattr(word_count_service, "_load_entity", lambda *_args: SimpleNamespace(id=project_id))
    monkeypatch.setattr(word_count_service, "_entity_metric_query", lambda *_args: MetricQuery())
    monkeypatch.setattr(word_count_service, "_arrangements_for_entity", lambda *_args: [])

    matrix = word_count_service.get_word_count_matrix(FakeDb(), "project", project_id)

    assert matrix["source"] == "project"
    assert matrix["sub_order_count"] == 2
    assert matrix["company"]["words"] == 9000


def test_project_matrix_can_be_patched_when_suborders_exist(monkeypatch):
    project_id = uuid4()
    applied = []

    class FakeDb:
        committed = False
        rolled_back = False

        def query(self, *_entities):
            raise AssertionError("保存母订单字数时不应再查询子订单并阻止提交")

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    db = FakeDb()
    monkeypatch.setattr(word_count_service, "_load_entity", lambda *_args: SimpleNamespace(id=project_id))
    monkeypatch.setattr(word_count_service, "_arrangements_for_entity", lambda *_args: [])
    monkeypatch.setattr(word_count_service, "_apply_cell", lambda *_args, **kwargs: applied.append(kwargs))
    monkeypatch.setattr(word_count_service, "get_word_count_matrix", lambda *_args: {"source": "project"})

    result = word_count_service.patch_word_count_matrix(
        db,
        "project",
        project_id,
        WordCountMatrixPatch(changes=[{
            "scope": "entity",
            "dimension": "company",
            "metric_type": "pages",
            "value": 12,
        }]),
        updated_by=None,
    )

    assert result == {"source": "project"}
    assert db.committed is True
    assert db.rolled_back is False
    assert applied[0]["owner_filters"]["project_id"] == project_id
    assert applied[0]["metric_type"] == "pages"
    assert applied[0]["value"] == 12
