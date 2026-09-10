from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from manuscript_schemas import (
    ManuscriptArrangementCreate,
    ManuscriptAssignmentInput,
    ManuscriptDispatchCreate,
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
            ),
            ManuscriptMilestoneInput(
                milestone_type="final",
                name="译员交稿_全稿预定时间",
                sequence_no=2,
                planned_at=datetime(2026, 9, 2, 18, 0),
            ),
        ],
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"planned": {}}, "至少需要填写一个计量数值"),
        ({"milestones": []}, "全稿预定时间"),
        ({"settlement_method": "  "}, "译员结账方式"),
    ],
)
def test_assignment_required_fields(changes, message):
    values = _valid_values()
    values.update(changes)

    with pytest.raises(ValidationError) as exc_info:
        ManuscriptAssignmentInput(**values)

    assert message in str(exc_info.value)


def test_assignment_requires_final_manuscript_planned_time():
    values = _valid_values()
    values["milestones"] = values["milestones"][:1]

    with pytest.raises(ValidationError) as exc_info:
        ManuscriptAssignmentInput(**values)

    assert "全稿预定时间" in str(exc_info.value)


def test_phase_milestones_are_optional_when_final_time_is_filled():
    values = _valid_values()
    values["milestones"] = values["milestones"][1:]

    assignment = ManuscriptAssignmentInput(**values)

    assert len(assignment.milestones) == 1
    assert assignment.milestones[0].milestone_type == "final"


def test_zero_is_a_filled_word_count_and_unit_price():
    values = _valid_values()
    values["planned"] = {"words": 0}
    values["translator_unit_price"] = 0

    assignment = ManuscriptAssignmentInput(**values)

    assert assignment.planned.words == 0
    assert assignment.translator_unit_price == 0


def test_assignment_allows_empty_unit_price():
    values = _valid_values()
    values["translator_unit_price"] = None

    assignment = ManuscriptAssignmentInput(**values)

    assert assignment.translator_unit_price is None


def test_translator_pricing_method_accepts_free_text():
    assignment = ManuscriptAssignmentInput(**_valid_values())

    assert assignment.translator_pricing_method == "按页数"


def test_assignment_defaults_settlement_method_to_next_month():
    values = _valid_values()
    values.pop("settlement_method")

    assignment = ManuscriptAssignmentInput(**values)

    assert assignment.settlement_method == "次月结"


def test_legacy_create_endpoint_payload_uses_the_same_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        ManuscriptArrangementCreate(
            entity_type="project",
            translation_project_id=uuid4(),
            translator_id=uuid4(),
        )

    assert "至少需要填写一个计量数值" in str(exc_info.value)


def test_sub_order_dispatch_supports_legacy_directory_and_selected_files():
    values = _valid_values()
    assignment = ManuscriptAssignmentInput(**values)
    legacy_payload = ManuscriptDispatchCreate(
        entity_type="suborder",
        translation_project_id=uuid4(),
        sub_order_id=uuid4(),
        arrangements=[assignment],
    )
    assert legacy_payload.arrangements[0].file_selection_mode == "legacy_all"
    assert legacy_payload.arrangements[0].selected_files == []

    values.update({
        "file_selection_mode": "selected",
        "selected_files": [{"relative_path": "合同/正文.docx"}],
    })
    payload = ManuscriptDispatchCreate(
        entity_type="suborder",
        translation_project_id=uuid4(),
        sub_order_id=uuid4(),
        arrangements=[ManuscriptAssignmentInput(**values)],
    )
    assert payload.arrangements[0].selected_files[0].relative_path == "合同/正文.docx"


def test_selected_file_mode_still_requires_a_file():
    values = _valid_values()
    values["file_selection_mode"] = "selected"
    with pytest.raises(ValidationError, match="请选择至少一个派稿文件"):
        ManuscriptAssignmentInput(**values)
