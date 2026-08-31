from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from manuscript_schemas import (
    ManuscriptArrangementCreate,
    ManuscriptAssignmentInput,
    ManuscriptMilestoneInput,
)


def _valid_values():
    return {
        "translator_id": uuid4(),
        "planned": {"words": 1000},
        "settlement_method": "月结",
        "translator_pricing_method": "按页数",
        "translator_unit_price": 0.12,
        "milestones": [
            ManuscriptMilestoneInput(
                milestone_type="phase",
                name="译员交稿_预定时间1",
                sequence_no=1,
                planned_at=datetime(2026, 9, 1, 18, 0),
            )
        ],
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"planned": {}}, "至少需要填写一个字数数值"),
        ({"milestones": []}, "译员交稿_预定时间1"),
        ({"settlement_method": "  "}, "译员结账方式"),
        ({"translator_unit_price": None}, "必须填写单价"),
    ],
)
def test_assignment_required_fields(changes, message):
    values = _valid_values()
    values.update(changes)

    with pytest.raises(ValidationError) as exc_info:
        ManuscriptAssignmentInput(**values)

    assert message in str(exc_info.value)


def test_zero_is_a_filled_word_count_and_unit_price():
    values = _valid_values()
    values["planned"] = {"words": 0}
    values["translator_unit_price"] = 0

    assignment = ManuscriptAssignmentInput(**values)

    assert assignment.planned.words == 0
    assert assignment.translator_unit_price == 0


def test_translator_pricing_method_accepts_free_text():
    assignment = ManuscriptAssignmentInput(**_valid_values())

    assert assignment.translator_pricing_method == "按页数"


def test_legacy_create_endpoint_payload_uses_the_same_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        ManuscriptArrangementCreate(
            entity_type="project",
            translation_project_id=uuid4(),
            translator_id=uuid4(),
        )

    assert "至少需要填写一个字数数值" in str(exc_info.value)
