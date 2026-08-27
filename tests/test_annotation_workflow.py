from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from annotation_ops_schemas import AnnotationWorkflowWrite, AssigneeRateWrite


def test_workflow_accepts_independent_quality_inspector_assignment():
    payload = AnnotationWorkflowWrite(
        person_id=uuid4(),
        assignment_role="quality_inspector",
        audio_duration_value=Decimal("120.5"),
        audio_duration_unit="minute",
        amount=Decimal("0.10"),
        unit="item",
    )

    assert payload.assignment_role == "quality_inspector"
    assert payload.amount == Decimal("0.10")


def test_workflow_rejects_amount_without_unit():
    with pytest.raises(ValidationError, match="人员价格和单位必须同时填写"):
        AnnotationWorkflowWrite(person_id=uuid4(), amount=Decimal("1"))


def test_rate_belongs_to_one_assignment_role():
    payload = AssigneeRateWrite(
        amount=Decimal("0.08"),
        unit="second",
        currency="CNY",
    )

    assert payload.amount == Decimal("0.08")
    assert payload.unit == "second"
