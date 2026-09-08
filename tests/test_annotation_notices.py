from datetime import datetime, timedelta
import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import annotation_notice_service
from annotation_notice_schemas import AnnotationNoticeSectionUpdate
from annotation_notice_service import (
    ANNOTATION_NOTICE_SECTIONS,
    _alpha_label,
    _display_titles,
    _escape_like_keyword,
    extract_notice_text,
    update_annotation_notice_section,
)
from concurrency import StaleUpdateError
from routers.annotation_notices import router as annotation_notices_router


def document(*marks, text="注意事项"):
    return {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": text, "marks": list(marks)}],
        }],
    }


def test_fixed_notice_sections_keep_legacy_keys_and_expected_titles():
    assert [title for _key, title in ANNOTATION_NOTICE_SECTIONS] == [
        "A. 客户报价", "B. 标注员报价", "C. 试标/试采流程", "D. 音频采集流程",
        "E. 音频标注流程", "F. 音频评测流程", "G. 文本评测流程", "H. 质检流程",
        "I. 测听流程", "J. 扣槽流程", "K. 泛化流程", "L. 翻译流程", "M. AI评测流程",
    ]


def test_alpha_label_supports_more_than_twenty_six_content_sections():
    assert [_alpha_label(value) for value in (1, 26, 27, 28, 52, 53)] == ["A", "Z", "AA", "AB", "AZ", "BA"]


def test_display_titles_follow_preorder_and_skip_group_only_nodes():
    root_a = notice_row(title="客户报价", sort_order=1)
    group = notice_row(title="项目流程", sort_order=2, has_content=False)
    child = notice_row(title="音频采集流程", sort_order=1, parent_id=group.id)
    labels = _display_titles([child, group, root_a])
    assert labels[root_a.id] == "A. 客户报价"
    assert labels[group.id] == "项目流程"
    assert labels[child.id] == "B. 音频采集流程"


def test_extract_notice_text_collects_nested_tiptap_text():
    payload = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "流程说明"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "请先检查音频"}, {"type": "hardBreak"}, {"type": "text", "text": "再提交"}]},
        ],
    }
    text = extract_notice_text(payload)
    assert "流程说明" in text
    assert "请先检查音频" in text
    assert "再提交" in text


def test_search_keyword_escapes_like_wildcards():
    assert _escape_like_keyword(r"50%_完成\确认") == r"50\%\_完成\\确认"


def test_notice_routes_require_project_permissions():
    read_route = next(item for item in annotation_notices_router.routes if item.path == "/annotation-notices/tree")
    write_route = next(item for item in annotation_notices_router.routes if item.path == "/annotation-notices/sections/{section_id}/content")
    read_dependencies = [inspect.getclosurevars(item.call).nonlocals for item in read_route.dependant.dependencies]
    write_dependencies = [inspect.getclosurevars(item.call).nonlocals for item in write_route.dependant.dependencies]
    assert any(item.get("read_permission") == "projects:read" for item in read_dependencies)
    assert any(item.get("permission_codes") == ("projects:write",) for item in write_dependencies)


def test_notice_routes_include_tree_management_search_and_legacy_compatibility():
    paths = {item.path for item in annotation_notices_router.routes}
    assert {
        "/annotation-notices", "/annotation-notices/{section_key}",
        "/annotation-notices/tree", "/annotation-notices/search",
        "/annotation-notices/sections", "/annotation-notices/sections/reorder",
        "/annotation-notices/sections/{section_id}",
        "/annotation-notices/sections/{section_id}/content",
    } <= paths


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

    def filter(self, *_args): return self
    def with_for_update(self): return self
    def options(self, *_args): return self
    def first(self): return self.row
    def one(self): return self.row
    def all(self): return [self.row] if self.row else []


class FakeDb:
    def __init__(self, row):
        self.row = row
        self.commits = 0

    def query(self, *_args): return FakeQuery(self.row)
    def commit(self): self.commits += 1


def notice_row(updated_at=None, *, title="客户报价", sort_order=1, has_content=True, parent_id=None):
    return SimpleNamespace(
        id=uuid4(), section_key="customer_quote", title=title, parent_id=parent_id,
        sort_order=sort_order, has_content=has_content, is_active=True,
        content_json=None, search_text="", updated_by=None, updated_at=updated_at,
        structure_updated_at=None,
        editor=SimpleNamespace(full_name="测试用户", username="tester"),
    )


def test_notice_update_records_user_time_and_search_text(monkeypatch):
    row = notice_row()
    db = FakeDb(row)
    user_id = uuid4()
    monkeypatch.setattr(annotation_notice_service, "ensure_annotation_notice_sections", lambda _db: None)
    monkeypatch.setattr(annotation_notice_service, "_active_rows", lambda _db: [row])
    result = update_annotation_notice_section(
        db, "customer_quote", AnnotationNoticeSectionUpdate(content_json=document(text="可检索正文")), user_id,
    )
    assert db.commits == 1
    assert row.updated_by == user_id
    assert row.updated_at is not None
    assert row.search_text == "可检索正文"
    assert result["updated_by_name"] == "测试用户"


def test_notice_update_rejects_stale_version(monkeypatch):
    current = datetime(2026, 9, 7, 12, 0, 0)
    row = notice_row(current)
    db = FakeDb(row)
    monkeypatch.setattr(annotation_notice_service, "ensure_annotation_notice_sections", lambda _db: None)
    with pytest.raises(StaleUpdateError):
        update_annotation_notice_section(
            db, "customer_quote",
            AnnotationNoticeSectionUpdate(content_json=document(), expected_updated_at=current - timedelta(minutes=1)),
            uuid4(),
        )
    assert db.commits == 0


def test_notice_update_rejects_group_only_section(monkeypatch):
    row = notice_row(has_content=False)
    db = FakeDb(row)
    monkeypatch.setattr(annotation_notice_service, "ensure_annotation_notice_sections", lambda _db: None)
    with pytest.raises(ValueError, match="仅用于分组"):
        update_annotation_notice_section(db, "customer_quote", AnnotationNoticeSectionUpdate(content_json=document()), uuid4())


def test_customization_migration_adds_hierarchy_and_search_indexes():
    migration = Path("data/migrations/20260924_customize_annotation_notice_sections.sql").read_text(encoding="utf-8")
    assert "parent_id UUID" in migration
    assert "search_text TEXT" in migration
    assert "gin_trgm_ops" in migration
    assert "project_flow" in migration
