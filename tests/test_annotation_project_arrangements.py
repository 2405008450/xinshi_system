from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import annotation_ops_service
from annotation_ops_models import (
    AnnotationArrangementTaskType,
    AnnotationProjectArrangementTask,
    AnnotationProjectStatusHistory,
)
from annotation_ops_schemas import ArrangementBatchWrite, ArrangementTaskTypeWrite
from annotation_ops_service import update_progress_history


def test_arrangement_models_keep_project_fields_live_through_foreign_key():
    task_columns = AnnotationProjectArrangementTask.__table__.c
    assert "project_name" not in task_columns
    assert "client_name" not in task_columns
    assert "project_status" not in task_columns
    assert {
        foreign_key.target_fullname
        for foreign_key in task_columns.project_id.foreign_keys
    } == {"annotation_project.id"}
    assert next(iter(task_columns.project_id.foreign_keys)).ondelete == "CASCADE"


def test_arrangement_task_type_name_is_normalized_and_batch_defaults_are_empty():
    payload = ArrangementTaskTypeWrite(name="  数据   清洗  ")
    batch = ArrangementBatchWrite()

    assert payload.name == "数据 清洗"
    assert batch.items == []
    assert batch.deleted_items == []
    assert "normalized_name" in AnnotationArrangementTaskType.__table__.c


def test_progress_history_has_explicit_kind_and_edit_metadata():
    columns = AnnotationProjectStatusHistory.__table__.c
    assert columns.entry_kind.server_default.arg.text == "'status'"
    assert "updated_at" in columns
    assert "updated_by" in columns


class ProgressDb:
    def __init__(self, row):
        self.row = row
        self.committed = False

    def get(self, _model, _row_id):
        return self.row

    def commit(self):
        self.committed = True


def test_only_progress_history_can_be_edited(monkeypatch):
    project_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        from_status="trial_in_progress",
        to_status="trial_passed",
        entry_kind="status",
        effective_on=datetime(2026, 9, 18, 9, 0),
        change_note="状态变化",
        updated_at=datetime(2026, 9, 18, 9, 0),
        updated_by=None,
    )
    payload = SimpleNamespace(
        effective_on=datetime(2026, 9, 18, 10, 0),
        change_note="不允许修改",
        expected_updated_at=row.updated_at,
    )

    with pytest.raises(ValueError, match="状态流转记录不可"):
        update_progress_history(ProgressDb(row), row.id, payload, uuid4())

    row.entry_kind = "progress"
    monkeypatch.setattr(annotation_ops_service, "list_status_history", lambda _db, value: [value])
    db = ProgressDb(row)
    result = update_progress_history(db, row.id, payload, uuid4())

    assert result == [project_id]
    assert row.change_note == "不允许修改"
    assert row.effective_on == payload.effective_on
    assert db.committed is True
