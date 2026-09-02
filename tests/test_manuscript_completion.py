from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import manuscript_service
from manuscript_schemas import ManuscriptCompletionUpdate


class DbStub:
    def __init__(self):
        self.commit_count = 0

    def commit(self):
        self.commit_count += 1


def _arrangement(status="sent", completion_remarks=None):
    return SimpleNamespace(
        id=uuid4(),
        entity_type="project",
        translation_project_id=uuid4(),
        sub_order_id=None,
        status=status,
        completion_remarks=completion_remarks,
        updated_at=None,
    )


def _prepare(monkeypatch, arrangement):
    monkeypatch.setattr(
        manuscript_service,
        "get_arrangement",
        lambda _db, _arrangement_id: arrangement,
    )
    monkeypatch.setattr(
        manuscript_service,
        "_load_entity",
        lambda *_args, **_kwargs: (SimpleNamespace(), None),
    )
    monkeypatch.setattr(
        manuscript_service,
        "_ensure_can_manage_manuscript",
        lambda *_args, **_kwargs: None,
    )


def test_completion_remarks_accepts_255_characters_and_rejects_more():
    ManuscriptCompletionUpdate(completion_remarks="完" * 255)

    with pytest.raises(ValidationError):
        ManuscriptCompletionUpdate(completion_remarks="完" * 256)


def test_update_completion_trims_and_saves(monkeypatch):
    arrangement = _arrangement()
    db = DbStub()
    _prepare(monkeypatch, arrangement)

    result = manuscript_service.update_completion(
        db,
        arrangement.id,
        ManuscriptCompletionUpdate(completion_remarks="  实际耗时 3 小时，质量良好  "),
        SimpleNamespace(),
    )

    assert result is arrangement
    assert arrangement.completion_remarks == "实际耗时 3 小时，质量良好"
    assert db.commit_count == 1


def test_update_completion_clears_blank_value(monkeypatch):
    arrangement = _arrangement(completion_remarks="旧内容")
    db = DbStub()
    _prepare(monkeypatch, arrangement)

    manuscript_service.update_completion(
        db,
        arrangement.id,
        ManuscriptCompletionUpdate(completion_remarks="   "),
        SimpleNamespace(),
    )

    assert arrangement.completion_remarks is None


def test_update_completion_rejects_cancelled_arrangement(monkeypatch):
    arrangement = _arrangement(status="cancelled")
    db = DbStub()
    _prepare(monkeypatch, arrangement)

    with pytest.raises(ValueError, match="已取消"):
        manuscript_service.update_completion(
            db,
            arrangement.id,
            ManuscriptCompletionUpdate(completion_remarks="已完成"),
            SimpleNamespace(),
        )

    assert db.commit_count == 0
