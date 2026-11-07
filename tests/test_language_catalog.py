from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from interpretation_schemas import InterpretationLanguageCreate
from language_catalog import (
    normalize_language_pairs,
    validate_language_pairs_against_catalog,
)
from routers.project_languages import router as project_language_router


def test_language_pair_format_accepts_custom_labels_and_removes_duplicates():
    assert normalize_language_pairs(
        " 吴语（上海话） → 英语（美国） ；吴语（上海话）→英语（美国）"
    ) == "吴语（上海话）→英语（美国）"


def test_language_pair_catalog_uses_canonical_labels_and_allows_inactive_entries():
    labels = ["中文（简体）", "吴语（上海话）"]

    assert validate_language_pairs_against_catalog(
        " 中文（简体）→吴语（上海话） ", labels
    ) == "中文（简体）→吴语（上海话）"


def test_language_pair_catalog_rejects_unknown_language():
    with pytest.raises(ValueError, match="不在共享语种目录中"):
        validate_language_pairs_against_catalog(
            "中文（简体）→不存在语种", ["中文（简体）"]
        )


@pytest.mark.parametrize("value, expected", [
    (" 校对 ；校对", "校对"),
    ("校对；中文（简体）→英语（美国）；校对", "校对；中文（简体）→英语（美国）"),
])
def test_proofreading_marker_survives_format_and_catalog_validation(value, expected):
    assert normalize_language_pairs(value) == expected
    assert validate_language_pairs_against_catalog(
        value, ["中文（简体）", "英语（美国）"]
    ) == expected


def test_proofreading_marker_does_not_bypass_direction_validation():
    with pytest.raises(ValueError, match="不在共享语种目录中"):
        validate_language_pairs_against_catalog("校对；中文→未知语种", ["中文"])
    with pytest.raises(ValueError, match="不是有效的翻译方向"):
        normalize_language_pairs("校对；其他业务")


def test_proofreading_filter_matches_standalone_and_combined_values():
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
    from sqlalchemy.orm import Session
    from field_filtering import apply_scalar_filter

    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    projects = Table("projects", metadata, Column("id", Integer, primary_key=True), Column("language_pair", String))
    metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(projects.insert(), [
            {"id": 1, "language_pair": "校对"},
            {"id": 2, "language_pair": "中文→英语；校对"},
            {"id": 3, "language_pair": "中文→英语"},
        ])
        query = apply_scalar_filter(select(projects.c.id), projects.c.language_pair, {"op": "contains", "value": "校对"})
        assert session.execute(query.order_by(projects.c.id)).scalars().all() == [1, 2]
    engine.dispose()


@pytest.mark.parametrize("value", [
    "中文（简体）→中文（简体）",
    "中文（简体）-英语（美国）",
])
def test_language_pair_format_rejects_invalid_direction(value):
    with pytest.raises(ValueError):
        normalize_language_pairs(value)


@pytest.mark.parametrize("label", ["吴语→英语", "吴语；英语", "吴语,英语", "吴语、英语"])
def test_shared_language_rejects_reserved_separators(label):
    with pytest.raises(ValidationError, match="不能包含箭头或列表分隔符"):
        InterpretationLanguageCreate(label=label)


def test_consultation_writer_can_pass_shared_language_create_permission(monkeypatch):
    post_route = next(
        route for route in project_language_router.routes
        if route.path == "/projects/languages" and route.methods == {"POST"}
    )
    permission_dependency = next(
        dependency.call for dependency in post_route.dependant.dependencies
        if dependency.call.__name__ == "permission_dependency"
    )
    monkeypatch.setattr(
        "routers.auth.get_user_permission_codes",
        lambda _db, _user_id: ["consultations:write"],
    )

    user = SimpleNamespace(id="consultation-writer")
    assert permission_dependency(current_user=user, db=object()) is user
