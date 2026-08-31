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
