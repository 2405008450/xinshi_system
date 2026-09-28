from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import annotation_ops_service as service
from annotation_ops_schemas import TrialWrite


def test_changing_round_allocates_sequence_in_destination_round(monkeypatch):
    project_id, person_id, trial_id = uuid4(), uuid4(), uuid4()
    row = SimpleNamespace(project_id=project_id, round_no=1, sequence_no=1, custom_values={})
    db = MagicMock()
    db.get.return_value = row
    db.query.return_value.filter.return_value.first.return_value = None
    monkeypatch.setattr(service, "_validate_trial_member", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "validate_custom_values", lambda *args, **kwargs: {})
    monkeypatch.setattr(service, "_next_sequence", lambda *args: 7)
    monkeypatch.setattr(service, "_trial_dict", lambda db, record: record)
    service.save_trial(db, TrialWrite(project_id=project_id, person_id=person_id, round_no=2, sequence_no=1), None, trial_id)
    assert row.sequence_no == 7
    assert row.round_no == 2
    db.commit.assert_called_once()
    db.query.return_value.filter.return_value.with_for_update.assert_called_once()
