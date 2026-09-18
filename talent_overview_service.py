"""人才概览快照、确定性语种映射和历史映射审计。"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from interpretation_models import InterpretationLanguage, InterpretationLanguageAlias
from language_catalog import normalize_language_search_text


DATA_PATH = Path(__file__).resolve().parent / "data" / "talent_overview.json"


def _numeric_count(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


@lru_cache(maxsize=1)
def load_talent_overview_data() -> dict:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []
    column_keys = [column["key"] for column in columns]
    overview_keys = [row["overview_key"] for row in rows]
    if len(column_keys) != len(set(column_keys)):
        raise RuntimeError("人才概览来源列键重复")
    if len(overview_keys) != len(set(overview_keys)):
        raise RuntimeError("人才概览语种关联键重复")

    column_totals = {key: 0 for key in column_keys}
    normalized_rows = []
    for row in rows:
        counts = {key: row.get("counts", {}).get(key) for key in column_keys}
        row_total = sum(_numeric_count(value) for value in counts.values())
        for key, value in counts.items():
            column_totals[key] += _numeric_count(value)
        normalized_rows.append({**row, "counts": counts, "row_total": row_total})
    return {
        **payload,
        "rows": normalized_rows,
        "column_totals": column_totals,
        "grand_total": sum(column_totals.values()),
    }


@lru_cache(maxsize=1)
def _overview_indexes() -> tuple[dict[str, dict], dict[str, set[str]]]:
    data = load_talent_overview_data()
    rows_by_key = {row["overview_key"]: row for row in data["rows"]}
    keys_by_normalized_name: dict[str, set[str]] = {}
    for row in data["rows"]:
        for value in (row["language"], *(row.get("aliases") or [])):
            normalized = normalize_language_search_text(value)
            if normalized:
                keys_by_normalized_name.setdefault(normalized, set()).add(row["overview_key"])
    return rows_by_key, keys_by_normalized_name


def _language_candidate_values(language: InterpretationLanguage) -> list[str]:
    values = [
        language.label,
        language.code,
        language.name_zh,
        language.name_en,
        language.short_name_zh,
        language.short_name_en,
    ]
    values.extend(item.alias for item in (language.aliases or []) if item.is_active)
    return list(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))


def resolve_overview_for_text(value: object) -> tuple[dict | None, str | None]:
    """仅按规范名或明确别名精确解析，不执行包含匹配或相似度猜测。"""
    normalized = normalize_language_search_text(value)
    if not normalized:
        return None, None
    rows_by_key, keys_by_name = _overview_indexes()
    keys = keys_by_name.get(normalized, set())
    if len(keys) != 1:
        return None, "ambiguous" if len(keys) > 1 else None
    key = next(iter(keys))
    row = rows_by_key[key]
    match_type = (
        "canonical"
        if normalized == normalize_language_search_text(row["language"])
        else "alias"
    )
    return row, match_type


def resolve_overview_for_language(
    language: InterpretationLanguage,
) -> tuple[dict | None, str | None]:
    rows_by_key, keys_by_name = _overview_indexes()
    if language.talent_overview_key:
        row = rows_by_key.get(language.talent_overview_key)
        if row:
            return row, "stable_key"

    matched_keys: set[str] = set()
    match_types: set[str] = set()
    for value in _language_candidate_values(language):
        normalized = normalize_language_search_text(value)
        keys = keys_by_name.get(normalized, set())
        matched_keys.update(keys)
        if keys:
            match_types.add(
                "canonical"
                if any(
                    normalized == normalize_language_search_text(rows_by_key[key]["language"])
                    for key in keys
                )
                else "alias"
            )
    if len(matched_keys) != 1:
        return None, "ambiguous" if len(matched_keys) > 1 else None
    key = next(iter(matched_keys))
    return rows_by_key[key], "canonical" if "canonical" in match_types else "alias"


def _audit_candidate_rows(language: InterpretationLanguage, *, limit: int = 5) -> list[dict]:
    """仅为人工治理报告生成相似候选，不参与运行时解析或自动落库。"""
    data = load_talent_overview_data()
    source_values = [
        normalize_language_search_text(value)
        for value in _language_candidate_values(language)
    ]
    source_values = [value for value in source_values if value]
    scored: list[tuple[float, dict, str]] = []
    for row in data["rows"]:
        target_values = [
            normalize_language_search_text(value)
            for value in (row["language"], *(row.get("aliases") or []))
        ]
        best_score = 0.0
        best_reason = "similarity"
        for source in source_values:
            for target in target_values:
                if not target:
                    continue
                contained = min(len(source), len(target)) >= 2 and (
                    source in target or target in source
                )
                score = SequenceMatcher(None, source, target).ratio()
                if contained:
                    score = max(score, 0.85)
                if score > best_score:
                    best_score = score
                    best_reason = "contains" if contained else "similarity"
        if best_score >= 0.5:
            scored.append((best_score, row, best_reason))
    scored.sort(key=lambda item: (-item[0], item[1]["language"]))
    return [
        {
            "overview_key": row["overview_key"],
            "overview_language": row["language"],
            "score": round(score, 4),
            "reason": reason,
        }
        for score, row, reason in scored[:limit]
    ]


def get_talent_overview() -> dict:
    return load_talent_overview_data()


def lookup_language_reserves(db: Session, language_ids: Iterable[UUID]) -> list[dict]:
    ordered_ids = list(dict.fromkeys(language_ids))
    if not ordered_ids:
        return []
    languages = (
        db.query(InterpretationLanguage)
        .options(selectinload(InterpretationLanguage.aliases))
        .filter(InterpretationLanguage.id.in_(ordered_ids))
        .all()
    )
    by_id = {language.id: language for language in languages}
    results = []
    for language_id in ordered_ids:
        language = by_id.get(language_id)
        if language is None:
            results.append({
                "language_id": language_id,
                "requested_label": None,
                "matched": False,
                "total": None,
            })
            continue
        row, match_type = resolve_overview_for_language(language)
        if row is None:
            results.append({
                "language_id": language_id,
                "requested_label": language.label,
                "matched": False,
                "total": None,
                "match_type": match_type,
            })
            continue
        results.append({
            "language_id": language_id,
            "requested_label": language.label,
            "matched": True,
            "overview_key": row["overview_key"],
            "overview_language": row["language"],
            "updated_at": row.get("updated_at"),
            "total": row["row_total"],
            "non_deduplicated": True,
            "match_type": match_type,
        })
    return results


def audit_language_mappings(db: Session, *, apply: bool = False) -> dict:
    """审计全部共享语种；应用时只落确定性映射并安全规范一对一名称。"""
    languages = (
        db.query(InterpretationLanguage)
        .options(selectinload(InterpretationLanguage.aliases))
        .order_by(InterpretationLanguage.label.asc())
        .all()
    )
    canonical = []
    aliases = []
    ambiguous_candidates = []
    unmatched = []
    grouped: dict[str, list[InterpretationLanguage]] = {}
    resolved_rows: dict[UUID, tuple[dict, str]] = {}
    for language in languages:
        row, match_type = resolve_overview_for_language(language)
        item = {"id": str(language.id), "label": language.label}
        if row is None:
            candidates = _audit_candidate_rows(language)
            item["reason"] = match_type or "candidate_review" if candidates else "unmatched"
            if candidates:
                item["candidates"] = candidates
                ambiguous_candidates.append(item)
            else:
                unmatched.append(item)
            continue
        item.update({
            "overview_key": row["overview_key"],
            "overview_language": row["language"],
            "match_type": match_type,
        })
        label_is_canonical = (
            normalize_language_search_text(language.label)
            == normalize_language_search_text(row["language"])
        )
        item["audit_category"] = "canonical" if label_is_canonical else "alias"
        (canonical if label_is_canonical else aliases).append(item)
        grouped.setdefault(row["overview_key"], []).append(language)
        resolved_rows[language.id] = (row, match_type or "alias")

    renamed = []
    if apply:
        existing_labels = {language.label.casefold(): language.id for language in languages}
        for language in languages:
            resolved_item = resolved_rows.get(language.id)
            if not resolved_item:
                continue
            row, match_type = resolved_item
            language.talent_overview_key = row["overview_key"]
            group = grouped[row["overview_key"]]
            canonical_label = row["language"]
            can_rename = (
                len(group) == 1
                and language.label != canonical_label
                and canonical_label.casefold() not in existing_labels
            )
            if can_rename:
                old_label = language.label
                language.label = canonical_label
                normalized_old = normalize_language_search_text(old_label)
                if normalized_old and not any(
                    alias.normalized_alias == normalized_old for alias in language.aliases
                ):
                    language.aliases.append(InterpretationLanguageAlias(
                        alias=old_label,
                        normalized_alias=normalized_old,
                        alias_type="historical",
                    ))
                renamed.append({
                    "id": str(language.id),
                    "from": old_label,
                    "to": canonical_label,
                })
        db.commit()

    return {
        "apply": apply,
        "summary": {
            "total": len(languages),
            "canonical": len(canonical),
            "alias": len(aliases),
            "resolved": len(canonical) + len(aliases),
            "ambiguous_candidates": len(ambiguous_candidates),
            "unmatched": len(unmatched),
            "renamed": len(renamed),
        },
        "canonical": canonical,
        "alias": aliases,
        "ambiguous_candidates": ambiguous_candidates,
        "unmatched": unmatched,
        "renamed": renamed,
    }
