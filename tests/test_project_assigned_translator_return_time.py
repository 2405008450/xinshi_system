import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import crud
import pytest
from schemas import AssignedTranslatorCompletionUpdate


class QueryStub:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class DbStub:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return QueryStub(self.rows)


def test_translation_project_assignee_exposes_final_planned_time(monkeypatch):
    project_id = uuid4()
    return_time = datetime.datetime(2026, 9, 8, 18, 0)
    arrangement = SimpleNamespace(
        id=uuid4(),
        dispatch_id=uuid4(),
        translation_project_id=project_id,
        sub_order_id=None,
        translator_id=uuid4(),
        translator_name_snapshot="测试译员",
        cooperation_type_snapshot="freelance",
        status="ready",
        translation_scope="全文",
        planned_delivery_at=return_time,
        completion_remarks="实际耗时 3 小时，质量良好",
        translator_unit_price=Decimal("0.1234"),
        translator_total_price=Decimal("123.45"),
    )
    project = SimpleNamespace(id=project_id, sub_orders=[])
    monkeypatch.setattr(crud, "_attach_word_count_matrices", lambda *args, **kwargs: None)

    crud._attach_manuscript_assignees(DbStub([arrangement]), projects=[project])

    assert project.assigned_translators[0]["translator_return_time"] == return_time
    assert project.assigned_translators[0]["completion_remarks"] == "实际耗时 3 小时，质量良好"
    assert project.assigned_translators[0]["translator_unit_price"] == Decimal("0.1234")
    assert project.assigned_translators[0]["translator_total_price"] == Decimal("123.45")


def test_project_editor_syncs_completion_back_to_arrangement():
    project_id = uuid4()
    arrangement = SimpleNamespace(
        id=uuid4(),
        completion_remarks="旧内容",
        translator_unit_price=Decimal("0.1000"),
        translator_total_price=Decimal("100.00"),
        updated_at=None,
    )

    crud._sync_assigned_translator_completions(
        DbStub([arrangement]),
        [
            AssignedTranslatorCompletionUpdate(
                arrangement_id=arrangement.id,
                completion_remarks="  已完成并通过检查  ",
            )
        ],
        project_id=project_id,
        sub_order_id=None,
    )

    assert arrangement.completion_remarks == "已完成并通过检查"
    assert arrangement.translator_unit_price == Decimal("0.1000")
    assert arrangement.translator_total_price == Decimal("100.00")
    assert arrangement.updated_at is not None


def test_sub_order_editor_syncs_prices_and_allows_zero_or_clear():
    arrangement = SimpleNamespace(
        id=uuid4(),
        completion_remarks="旧内容",
        translator_unit_price=Decimal("0.5000"),
        translator_total_price=Decimal("88.00"),
        updated_at=None,
    )

    crud._sync_assigned_translator_completions(
        DbStub([arrangement]),
        [
            AssignedTranslatorCompletionUpdate(
                arrangement_id=arrangement.id,
                completion_remarks=None,
                translator_unit_price=0,
                translator_total_price=None,
            )
        ],
        project_id=uuid4(),
        sub_order_id=uuid4(),
    )

    assert arrangement.completion_remarks is None
    assert arrangement.translator_unit_price == 0
    assert arrangement.translator_total_price is None
    assert arrangement.updated_at is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("translator_unit_price", "-0.0001"),
        ("translator_unit_price", "1.23456"),
        ("translator_total_price", "-0.01"),
        ("translator_total_price", "1.234"),
    ],
)
def test_assigned_translator_price_validation(field, value):
    with pytest.raises(ValueError):
        AssignedTranslatorCompletionUpdate(
            arrangement_id=uuid4(),
            **{field: value},
        )


def test_project_editor_rejects_completion_for_unmatched_arrangement():
    update = AssignedTranslatorCompletionUpdate(
        arrangement_id=uuid4(),
        completion_remarks="已完成",
    )

    with pytest.raises(ValueError, match="不存在对应的有效译员安排"):
        crud._sync_assigned_translator_completions(
            DbStub([]),
            [update],
            project_id=uuid4(),
            sub_order_id=None,
        )
