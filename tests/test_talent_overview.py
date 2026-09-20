from types import SimpleNamespace
from uuid import uuid4

from routers.annotation_projects import router as annotation_router
from routers.talents import router as talent_router
from talent_overview_service import (
    _prepare_saved_payload,
    get_talent_overview,
    lookup_language_reserves,
    resolve_overview_for_language,
    resolve_overview_for_text,
)
from talent_overview_models import TalentOverviewSnapshot
from talent_overview_schemas import TalentOverviewWrite


def language(label, *, overview_key=None, aliases=None):
    return SimpleNamespace(
        id=uuid4(),
        label=label,
        talent_overview_key=overview_key,
        code=None,
        name_zh=None,
        name_en=None,
        short_name_zh=None,
        short_name_en=None,
        aliases=[
            SimpleNamespace(alias=value, is_active=True)
            for value in (aliases or [])
        ],
    )


class FakeLanguageQuery:
    def __init__(self, rows):
        self.rows = rows

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model, *_args):
        return FakeLanguageQuery([] if model is TalentOverviewSnapshot else self.rows)


def test_talent_overview_preserves_snapshot_totals_and_nulls():
    payload = get_talent_overview()
    assert len(payload["rows"]) == 132
    assert len(payload["columns"]) == 14
    assert payload["grand_total"] == 42447
    assert [payload["column_totals"][item["key"]] for item in payload["columns"]] == [
        8657, 8972, 10215, 1164, 2853, 2288, 2083,
        172, 4612, 513, 75, 0, 79, 764,
    ]
    english = next(row for row in payload["rows"] if row["language"] == "英语")
    assert english["counts"]["hr4Wecom"] is None
    assert english["counts"]["hr3Wecom"] == 0


def test_reviewed_aliases_resolve_exactly_without_fuzzy_matching():
    zulu, zulu_match = resolve_overview_for_text(" 南非ＺＵＬＵ语 ")
    afrikaans, afrikaans_match = resolve_overview_for_text("AFRIKAANS")
    unknown, unknown_match = resolve_overview_for_text("南非祖语近似名称")

    assert (zulu["language"], zulu["row_total"], zulu_match) == ("祖鲁语", 3, "alias")
    assert (afrikaans["language"], afrikaans["row_total"], afrikaans_match) == (
        "阿非利卡语（南非语）", 3, "alias",
    )
    assert unknown is None
    assert unknown_match is None


def test_stable_key_has_priority_and_unknown_is_not_zero():
    zulu_language = language("历史名称", overview_key="lang-zu")
    unknown_language = language("没有对应概览的语种")
    resolved, match_type = resolve_overview_for_language(zulu_language)
    results = lookup_language_reserves(
        FakeDb([zulu_language, unknown_language]),
        [zulu_language.id, zulu_language.id, unknown_language.id],
    )

    assert resolved["language"] == "祖鲁语"
    assert match_type == "stable_key"
    assert len(results) == 2
    assert results[0]["total"] == 3
    assert results[1]["matched"] is False
    assert results[1]["total"] is None


def test_region_variants_map_to_overview_base_language():
    english = language("英语（美国）")
    spanish = language("西班牙语（拉丁美洲）")
    assert resolve_overview_for_language(english)[0]["language"] == "英语"
    assert resolve_overview_for_language(spanish)[0]["language"] == "西班牙语"


def test_overview_and_annotation_lookup_routes_are_separate():
    overview_route = next(
        route for route in talent_router.routes
        if route.path == "/talents/overview" and route.methods == {"GET"}
    )
    lookup_route = next(
        route for route in annotation_router.routes
        if route.path == "/projects/annotation/language-reserves/lookup"
        and route.methods == {"POST"}
    )
    update_route = next(
        route for route in talent_router.routes
        if route.path == "/talents/overview" and route.methods == {"PUT"}
    )
    assert overview_route.dependant.dependencies
    assert len(update_route.dependant.dependencies) > len(overview_route.dependant.dependencies)
    assert lookup_route.dependant.dependencies


def test_editable_snapshot_adds_column_and_row_and_recalculates_totals():
    previous = get_talent_overview()
    column_key = "col-00000000-0000-4000-8000-000000000001"
    row_key = "row-00000000-0000-4000-8000-000000000001"
    columns = [
        {key: item[key] for key in ("key", "label", "group", "width")}
        for item in previous["columns"]
    ]
    columns.append({"key": column_key, "label": "新增企微", "group": "wecom", "width": 120})
    rows = [{
        "overview_key": row["overview_key"],
        "language": row["language"],
        "updated_at": row.get("updated_at"),
        "counts": {**row["counts"], column_key: None},
    } for row in previous["rows"]]
    rows.append({
        "overview_key": row_key,
        "language": "测试语种",
        "updated_at": "2026-09-20",
        "counts": {**{item["key"]: None for item in previous["columns"]}, column_key: 7},
    })

    saved = _prepare_saved_payload(previous, TalentOverviewWrite(
        expected_revision=1, columns=columns, rows=rows,
    ))

    assert saved["rows"][-1]["row_total"] == 7
    assert saved["column_totals"][column_key] == 7
    assert saved["grand_total"] == previous["grand_total"] + 7


def test_renaming_language_keeps_old_name_as_hidden_alias():
    previous = get_talent_overview()
    columns = [
        {key: item[key] for key in ("key", "label", "group", "width")}
        for item in previous["columns"]
    ]
    rows = [{
        "overview_key": row["overview_key"],
        "language": "英文" if row["language"] == "英语" else row["language"],
        "updated_at": row.get("updated_at"),
        "counts": row["counts"],
    } for row in previous["rows"]]

    saved = _prepare_saved_payload(previous, TalentOverviewWrite(
        expected_revision=1, columns=columns, rows=rows,
    ))
    renamed = next(row for row in saved["rows"] if row["overview_key"] == "overview-001")
    old_match, match_type = resolve_overview_for_text("英语", data=saved)

    assert "英语" in renamed["aliases"]
    assert old_match["language"] == "英文"
    assert match_type == "alias"
