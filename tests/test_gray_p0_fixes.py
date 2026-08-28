import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from consultation_intake import validated_intake
from schemas import TranslationProjectUpdate, TranslationSubOrderUpdate, normalize_progress_percent


def test_interpretation_intake_with_datetime_is_json_serializable():
    data = validated_intake("interpretation", {
        "time_ranges": [{
            "scheduled_start": "2026-08-28T09:00:00",
            "scheduled_end": "2026-08-28T12:00:00",
        }],
    })
    json.dumps(data)
    assert isinstance(data["time_ranges"][0]["scheduled_start"], str)


def test_annotation_intake_default_date_and_language_uuid_are_json_serializable():
    language_id = uuid4()
    data = validated_intake("annotation", {
        "language_items": [{"source_language_id": str(language_id)}],
    })
    json.dumps(data)
    assert isinstance(data["status_effective_on"], str)
    assert data["language_items"][0]["source_language_id"] == str(language_id)


def test_recruitment_intake_dates_are_json_serializable():
    data = validated_intake("recruitment", {
        "employment_start": "2026-10-01",
        "employment_end": "2027-03-31",
    })
    json.dumps(data)
    assert data["employment_start"] == "2026-10-01"
    assert data["employment_end"] == "2027-03-31"


def test_progress_percent_accepts_boundary_and_rejects_invalid():
    assert normalize_progress_percent("0%") == "0%"
    assert normalize_progress_percent("100%") == "100%"
    assert normalize_progress_percent("80") == "80%"
    assert TranslationProjectUpdate(translator_delivery_progress="70%").translator_delivery_progress == "70%"
    with pytest.raises(ValidationError):
        TranslationProjectUpdate(translator_delivery_progress="999%")
    with pytest.raises(ValidationError):
        TranslationSubOrderUpdate(review_progress="not-a-percent")


def test_stale_update_detects_version_mismatch():
    from types import SimpleNamespace
    from datetime import datetime

    from concurrency import StaleUpdateError, assert_fresh

    row = SimpleNamespace(updated_at=datetime(2026, 8, 27, 20, 31, 5, 994669))
    assert_fresh(row, None)
    assert_fresh(row, "2026-08-27T20:31:05.994669")
    with pytest.raises(StaleUpdateError):
        assert_fresh(row, "2026-08-27T21:00:00")


def test_manuscript_dispatch_update_accepts_expected_updated_at():
    from datetime import datetime
    from manuscript_schemas import ManuscriptDispatchUpdate

    payload = ManuscriptDispatchUpdate(
        entity_type="project",
        translation_project_id=uuid4(),
        expected_updated_at=datetime(2026, 8, 27, 20, 31, 5),
        arrangements=[{"translator_id": uuid4()}],
    )
    assert payload.expected_updated_at == datetime(2026, 8, 27, 20, 31, 5)
