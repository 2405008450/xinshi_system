import inspect
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from annotation_ops_service import _escape_like_keyword, search_status_history
from routers.annotation_ops import project_router, status_history_search


def _sql(expression):
    return str(expression.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )).lower()


class RecordingQuery:
    def __init__(self, rows):
        self.rows = rows
        self.conditions = []
        self.ordering = []

    def join(self, *_args):
        return self

    def outerjoin(self, *_args):
        return self

    def filter(self, *conditions):
        self.conditions.extend(conditions)
        return self

    def order_by(self, *ordering):
        self.ordering = list(ordering)
        return self

    def offset(self, _value):
        return self

    def limit(self, _value):
        return self

    def all(self):
        return self.rows


class RecordingDb:
    def __init__(self, rows):
        self.query_instance = RecordingQuery(rows)

    def query(self, *_columns):
        return self.query_instance


def history_row(*, from_status, to_status, note, total=2):
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        from_status=from_status,
        to_status=to_status,
        effective_on=datetime(2026, 9, 7, 10, 30),
        changed_at=datetime(2026, 9, 7, 11, 15),
        changed_by=uuid4(),
        changed_by_name="项目经理",
        change_note=note,
        project_order_no="AP-260907-001",
        project_name="语音标注项目",
        project_current_status="project_in_progress",
        page_total=total,
    )


def test_progress_search_escapes_like_wildcards_as_literal_text():
    assert _escape_like_keyword(r"完成_50%\待确认") == r"完成\_50\%\\待确认"


def test_progress_search_filters_body_and_node_date_and_maps_record_types():
    db = RecordingDb([
        history_row(from_status="trial_in_progress", to_status="trial_in_progress", note="完成 50%"),
        history_row(from_status="trial_in_progress", to_status="trial_passed", note="客户确认通过"),
    ])

    result = search_status_history(
        db,
        keyword="50%",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 7),
        skip=0,
        limit=20,
    )

    condition_sql = " ".join(_sql(item) for item in db.query_instance.conditions)
    ordering_sql = " ".join(_sql(item) for item in db.query_instance.ordering)
    assert "effective_on >= '2026-09-01 00:00:00'" in condition_sql
    assert "effective_on < '2026-09-08 00:00:00'" in condition_sql
    assert "change_note" in condition_sql and "ilike" in condition_sql
    assert r"50\\%" in condition_sql
    assert "effective_on desc" in ordering_sql
    assert "changed_at desc" in ordering_sql
    assert result["total"] == 2
    assert [item["record_type"] for item in result["items"]] == ["progress", "status_change"]


@pytest.mark.parametrize(
    ("keyword", "date_from", "date_to", "message"),
    [
        ("   ", date(2026, 9, 1), date(2026, 9, 7), "请输入进度关键词"),
        ("进度", date(2026, 9, 8), date(2026, 9, 7), "开始日期不能晚于结束日期"),
        ("进度", date(2025, 9, 6), date(2026, 9, 7), "不能超过 366 天"),
    ],
)
def test_progress_search_route_rejects_invalid_scope(keyword, date_from, date_to, message):
    with pytest.raises(HTTPException, match=message) as exc_info:
        status_history_search(
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
            skip=0,
            limit=20,
            db=object(),
        )
    assert exc_info.value.status_code == 422


def test_progress_search_route_accepts_exactly_366_days(monkeypatch):
    captured = {}

    def fake_search(_db, **kwargs):
        captured.update(kwargs)
        return {"items": [], "total": 0}

    monkeypatch.setattr("routers.annotation_ops.search_status_history", fake_search)
    result = status_history_search(
        keyword="  客户确认  ",
        date_from=date(2025, 9, 8),
        date_to=date(2026, 9, 7),
        skip=0,
        limit=20,
        db=object(),
    )

    assert result == {"items": [], "total": 0}
    assert captured["keyword"] == "客户确认"


def test_progress_search_route_uses_existing_project_module_permission():
    route = next(
        item for item in project_router.routes
        if getattr(item, "path", None) == "/status-history/search"
    )
    permission_settings = [
        inspect.getclosurevars(dependency.call).nonlocals
        for dependency in route.dependant.dependencies
        if inspect.isfunction(dependency.call)
    ]
    assert any(
        settings.get("read_permission") == "projects:read"
        and settings.get("write_permission") == "projects:write"
        for settings in permission_settings
    )
