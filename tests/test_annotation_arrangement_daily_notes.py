from datetime import date, datetime, timedelta
import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import annotation_arrangement_note_service
from annotation_arrangement_note_service import save_arrangement_daily_note
from annotation_ops_schemas import ArrangementDailyNoteWrite
from concurrency import StaleUpdateError
from routers.annotation_ops import project_router


def document(text="今日优先完成项目分配"):
    return {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": text}],
        }],
    }


class FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *_args): return self
    def with_for_update(self): return self
    def first(self): return self.row


class FakeDb:
    def __init__(self, row):
        self.row = row
        self.commits = 0

    def query(self, *_args): return FakeQuery(self.row)
    def add(self, row): self.row = row
    def commit(self): self.commits += 1


def daily_note_row(updated_at=None):
    return SimpleNamespace(
        id=uuid4(),
        note_date=date(2026, 9, 20),
        content_json=document("原安排"),
        updated_by=None,
        created_at=datetime(2026, 9, 20, 9, 0),
        updated_at=updated_at or datetime(2026, 9, 20, 9, 0),
        editor=SimpleNamespace(full_name="测试用户", username="tester"),
    )


def test_arrangement_daily_note_reuses_safe_rich_text_contract():
    payload = ArrangementDailyNoteWrite(content_json=document())
    assert payload.content_json["content"][0]["content"][0]["text"] == "今日优先完成项目分配"

    with pytest.raises(ValidationError, match="不能为空"):
        ArrangementDailyNoteWrite(content_json={"type": "doc", "content": [{"type": "paragraph"}]})


def test_arrangement_daily_note_update_uses_optimistic_lock(monkeypatch):
    current = datetime(2026, 9, 20, 10, 0)
    row = daily_note_row(current)
    db = FakeDb(row)
    monkeypatch.setattr(
        annotation_arrangement_note_service,
        "get_arrangement_daily_note",
        lambda _db, _note_date: {"note_date": row.note_date, "content_json": row.content_json},
    )

    result = save_arrangement_daily_note(
        db,
        row.note_date,
        ArrangementDailyNoteWrite(content_json=document("更新后的安排"), expected_updated_at=current),
        uuid4(),
    )
    assert db.commits == 1
    assert row.content_json == document("更新后的安排")
    assert result["note_date"] == row.note_date

    with pytest.raises(StaleUpdateError):
        save_arrangement_daily_note(
            FakeDb(daily_note_row(current)),
            row.note_date,
            ArrangementDailyNoteWrite(
                content_json=document("过期修改"),
                expected_updated_at=current - timedelta(minutes=1),
            ),
            uuid4(),
        )


def test_arrangement_daily_note_routes_apply_read_and_write_permissions():
    read_route = next(
        route for route in project_router.routes
        if route.path == "/project-arrangements/daily-notes/{note_date}"
        and "GET" in route.methods
    )
    write_route = next(
        route for route in project_router.routes
        if route.path == "/project-arrangements/daily-notes/{note_date}"
        and "PUT" in route.methods
    )
    assert read_route
    write_dependencies = [
        inspect.getclosurevars(item.call).nonlocals
        for item in write_route.dependant.dependencies
    ]
    assert any(item.get("permission_codes") == ("projects:write",) for item in write_dependencies)


def test_arrangement_daily_note_migration_enforces_one_note_per_date():
    migration = Path(
        "data/migrations/20261003_annotation_arrangement_daily_notes.sql"
    ).read_text(encoding="utf-8")
    assert "note_date DATE NOT NULL" in migration
    assert "UNIQUE (note_date)" in migration
    assert "note_date DESC" in migration
