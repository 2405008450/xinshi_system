from datetime import date, datetime, timedelta
import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import resource_request_service
from concurrency import StaleUpdateError
from resource_request_schemas import ResourceRequestDailyNoteWrite
from resource_request_service import save_resource_request_daily_note
from routers.resource_requests import router as resource_requests_router


def document(text="今日优先开拓日语标注资源"):
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
    def options(self, *_args): return self
    def first(self): return self.row


class FakeDb:
    def __init__(self, row):
        self.row = row
        self.commits = 0

    def query(self, *_args): return FakeQuery(self.row)
    def commit(self): self.commits += 1


def daily_note_row(updated_at=None):
    return SimpleNamespace(
        id=uuid4(),
        note_date=date(2026, 9, 18),
        content_json=document("原说明"),
        updated_by=None,
        created_at=datetime(2026, 9, 18, 9, 0),
        updated_at=updated_at or datetime(2026, 9, 18, 9, 0),
        editor=SimpleNamespace(full_name="测试用户", username="tester"),
    )


def test_daily_note_schema_reuses_safe_rich_text_contract():
    payload = ResourceRequestDailyNoteWrite(content_json=document())
    assert payload.content_json["content"][0]["content"][0]["text"] == "今日优先开拓日语标注资源"

    with pytest.raises(ValidationError, match="不能为空"):
        ResourceRequestDailyNoteWrite(content_json={"type": "doc", "content": [{"type": "paragraph"}]})
    with pytest.raises(ValidationError):
        ResourceRequestDailyNoteWrite(content_json={
            "type": "doc",
            "content": [{"type": "image", "attrs": {"src": "javascript:alert(1)"}}],
        })


def test_daily_note_update_records_editor_and_uses_optimistic_lock(monkeypatch):
    current = datetime(2026, 9, 18, 10, 0)
    row = daily_note_row(current)
    db = FakeDb(row)
    user_id = uuid4()
    monkeypatch.setattr(
        resource_request_service,
        "get_resource_request_daily_note",
        lambda _db, _note_date: {
            "note_date": row.note_date,
            "content_json": row.content_json,
        },
    )

    result = save_resource_request_daily_note(
        db,
        row.note_date,
        ResourceRequestDailyNoteWrite(
            content_json=document("更新后的说明"),
            expected_updated_at=current,
        ),
        user_id,
    )

    assert db.commits == 1
    assert row.updated_by == user_id
    assert row.content_json == document("更新后的说明")
    assert result["note_date"] == row.note_date

    stale_db = FakeDb(daily_note_row(current))
    with pytest.raises(StaleUpdateError):
        save_resource_request_daily_note(
            stale_db,
            date(2026, 9, 18),
            ResourceRequestDailyNoteWrite(
                content_json=document("过期修改"),
                expected_updated_at=current - timedelta(minutes=1),
            ),
            user_id,
        )
    assert stale_db.commits == 0


def test_daily_note_routes_apply_read_and_write_permissions():
    read_route = next(
        route for route in resource_requests_router.routes
        if route.path == "/resource-requests/daily-notes" and "GET" in route.methods
    )
    write_route = next(
        route for route in resource_requests_router.routes
        if route.path == "/resource-requests/daily-notes/{note_date}" and "PUT" in route.methods
    )
    read_dependencies = [
        inspect.getclosurevars(item.call).nonlocals
        for item in read_route.dependant.dependencies
    ]
    write_dependencies = [
        inspect.getclosurevars(item.call).nonlocals
        for item in write_route.dependant.dependencies
    ]
    assert any(item.get("read_permission") == "projects:read" for item in read_dependencies)
    assert any(item.get("permission_codes") == ("projects:write",) for item in write_dependencies)


def test_daily_note_migration_enforces_one_note_per_date():
    migration = Path(
        "data/migrations/20261001_resource_request_daily_notes.sql"
    ).read_text(encoding="utf-8")
    assert "note_date DATE NOT NULL" in migration
    assert "UNIQUE (note_date)" in migration
    assert "note_date DESC" in migration
