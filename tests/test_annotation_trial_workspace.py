from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from annotation_ops_schemas import TrialStrategyWrite, TrialWrite


def trial_payload(**overrides):
    payload = {
        "project_id": uuid4(),
        "person_id": uuid4(),
        "language_item_id": uuid4(),
        "activity_type": "collection",
        "duty_role": "quality_inspector",
        "candidate_stage": "confirmed",
        "willingness_level": "high",
    }
    payload.update(overrides)
    return payload


def test_trial_workspace_accepts_multi_role_and_structured_fields():
    started_at = datetime(2026, 9, 21, 9, 0)
    payload = TrialWrite(**trial_payload(
        quote_amount=Decimal("120.50"),
        quote_currency="CNY",
        billing_unit="work_hour",
        started_at=started_at,
        deadline_at=started_at + timedelta(hours=4),
        submitted_at=started_at + timedelta(hours=3),
        cooperation_level="high",
        punctuality_level="medium",
        overall_score=9,
    ))

    assert payload.activity_type == "collection"
    assert payload.duty_role == "quality_inspector"
    assert payload.candidate_stage == "confirmed"
    assert payload.quote_amount == Decimal("120.50")


def test_trial_workspace_requires_quote_pair_and_partial_result_note():
    with pytest.raises(ValidationError, match="报价金额和计费单位必须同时填写"):
        TrialWrite(**trial_payload(quote_amount=Decimal("10")))

    with pytest.raises(ValidationError, match="部分通过时请填写结果说明"):
        TrialWrite(**trial_payload(trial_result="partially_passed", result_note=""))


def test_trial_workspace_rejects_invalid_time_range():
    started_at = datetime(2026, 9, 21, 10, 0)
    with pytest.raises(ValidationError, match="截止时间不能早于开始时间"):
        TrialWrite(**trial_payload(
            started_at=started_at,
            deadline_at=started_at - timedelta(minutes=1),
        ))


def test_trial_strategy_uses_ten_percent_default():
    payload = TrialStrategyWrite(language_item_id=uuid4(), planned_headcount=3)
    assert payload.conversion_rate == Decimal("0.1")

