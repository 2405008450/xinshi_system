from datetime import datetime, timedelta
import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import annotation_notice_service
from annotation_notice_schemas import AnnotationNoticeSectionUpdate
from annotation_notice_service import ANNOTATION_NOTICE_SECTIONS, update_annotation_notice_section
from concurrency import StaleUpdateError
from routers.annotation_notices import router as annotation_notices_router


def document(*marks):
    return {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": "注意事项", "marks": list(marks)}],
        }],
    }


def test_fixed_notice_sections_have_expected_order_and_titles():
    assert [title for _key, title in ANNOTATION_NOTICE_SECTIONS] == [
        "A. 客户报价", "B. 标注员报价", "C. 试标/试采流程", "D. 音频标注流程",
        "E. 音频评测流程", "F. 文本评测流程", "G. 质检流程", "H. 测听流程",
        "I. 扣槽流程", "J. 泛化流程", "K. 翻译流程",
    ]


def test_notice_routes_require_project_permissions():
    read_route = next(item for item in annotation_notices_router.routes if item.path == "/annotation-notices")
    write_route = next(item for item in annotation_notices_router.routes if item.path == "/annotation-notices/{section_key}")
    read_dependencies = [inspect.getclosurevars(item.call).nonlocals for item in read_route.dependant.dependencies]
    write_dependencies = [inspect.getclosurevars(item.call).nonlocals for item in write_route.dependant.dependencies]

    assert any(item.get("read_permission") == "projects:read" for item in read_dependencies)
    assert any(item.get("write_permission") == "projects:write" for item in write_dependencies)
    assert any(item.get("permission_codes") == ("projects:write",) for item in write_dependencies)


def test_notice_routes_are_registered_on_application():
    from main import app

    def collect_paths(routes):
        for route in routes:
            if hasattr(route, "path"):
                yield route.path
            nested = getattr(route, "routes", None)
            if nested:
                yield from collect_paths(nested)
            nested_router = getattr(route, "router", None)
            if nested_router is not None:
                yield from collect_paths(getattr(nested_router, "routes", ()))
            candidates = getattr(route, "effective_candidates", None)
            if callable(candidates):
                yield from collect_paths(candidates())

    paths = set(collect_paths(app.routes))
    assert "/annotation-notices" in paths
    assert "/annotation-notices/{section_key}" in paths


def test_notice_schema_accepts_text_color_and_yellow_highlight():
    payload = AnnotationNoticeSectionUpdate(content_json=document(
        {"type": "bold"},
        {"type": "textColor", "attrs": {"color": "#b91c1c"}},
        {"type": "highlight", "attrs": {"color": "#fff59d"}},
    ))

    assert payload.content_json["content"][0]["content"][0]["text"] == "注意事项"


@pytest.mark.parametrize("mark", [
    {"type": "link", "attrs": {"href": "javascript:alert(1)"}},
    {"type": "textColor", "attrs": {"color": "red;position:fixed"}},
    {"type": "highlight", "attrs": {"color": "#ff0000"}},
])
def test_notice_schema_rejects_unsupported_or_unsafe_marks(mark):
    with pytest.raises(ValidationError):
        AnnotationNoticeSectionUpdate(content_json=document(mark))


class FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *_args):
        return self

    def with_for_update(self):
        return self

    def options(self, *_args):
        return self

    def first(self):
        return self.row

    def one(self):
        return self.row


class FakeDb:
    def __init__(self, row):
        self.row = row
        self.commits = 0

    def query(self, *_args):
        return FakeQuery(self.row)

    def commit(self):
        self.commits += 1


def notice_row(updated_at=None):
    return SimpleNamespace(
        id=uuid4(), section_key="customer_quote", title="A. 客户报价", sort_order=1,
        content_json=None, updated_by=None, updated_at=updated_at,
        editor=SimpleNamespace(full_name="测试用户", username="tester"),
    )


def test_notice_update_records_user_and_time(monkeypatch):
    row = notice_row()
    db = FakeDb(row)
    user_id = uuid4()
    monkeypatch.setattr(annotation_notice_service, "ensure_annotation_notice_sections", lambda _db: None)

    result = update_annotation_notice_section(
        db,
        "customer_quote",
        AnnotationNoticeSectionUpdate(content_json=document()),
        user_id,
    )

    assert db.commits == 1
    assert row.updated_by == user_id
    assert row.updated_at is not None
    assert result["updated_by_name"] == "测试用户"


def test_notice_update_rejects_stale_version(monkeypatch):
    current = datetime(2026, 9, 7, 12, 0, 0)
    row = notice_row(current)
    db = FakeDb(row)
    monkeypatch.setattr(annotation_notice_service, "ensure_annotation_notice_sections", lambda _db: None)

    with pytest.raises(StaleUpdateError):
        update_annotation_notice_section(
            db,
            "customer_quote",
            AnnotationNoticeSectionUpdate(
                content_json=document(),
                expected_updated_at=current - timedelta(minutes=1),
            ),
            uuid4(),
        )

    assert db.commits == 0


def test_notice_update_rejects_unknown_section(monkeypatch):
    monkeypatch.setattr(annotation_notice_service, "ensure_annotation_notice_sections", lambda _db: None)
    assert update_annotation_notice_section(
        FakeDb(notice_row()),
        "unknown",
        AnnotationNoticeSectionUpdate(content_json=document()),
        uuid4(),
    ) is None
