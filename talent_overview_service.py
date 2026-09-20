"""人才概览快照、确定性语种映射和历史映射审计。"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from concurrency import StaleUpdateError
from interpretation_models import InterpretationLanguage, InterpretationLanguageAlias
from language_catalog import normalize_language_search_text
from models import AppUser
from talent_overview_models import TalentOverviewSnapshot
from talent_overview_schemas import TalentOverviewWrite


DATA_PATH = Path(__file__).resolve().parent / "data" / "talent_overview.json"
GROUP_ORDER = ("sheet", "wecom")


def _numeric_count(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _with_totals(payload: dict) -> dict:
    """以行列数据为唯一事实源，统一补齐空单元格并重新计算全部合计。"""
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []
    column_keys = [column["key"] for column in columns]
    column_totals = {key: 0 for key in column_keys}
    normalized_rows = []
    for source_row in rows:
        counts = {key: source_row.get("counts", {}).get(key) for key in column_keys}
        row_total = sum(_numeric_count(value) for value in counts.values())
        for key, value in counts.items():
            column_totals[key] += _numeric_count(value)
        normalized_rows.append({**source_row, "counts": counts, "row_total": row_total})
    return {
        **payload,
        "rows": normalized_rows,
        "column_totals": column_totals,
        "grand_total": sum(column_totals.values()),
    }


def _storage_payload(payload: dict) -> dict:
    """数据库只保存可编辑源数据，不持久化任何派生合计。"""
    return {
        "version": payload.get("version", 1),
        "non_deduplicated": True,
        "columns": copy.deepcopy(payload["columns"]),
        "rows": [
            {key: copy.deepcopy(value) for key, value in row.items() if key != "row_total"}
            for row in payload["rows"]
        ],
    }


@lru_cache(maxsize=1)
def _fixture_payload() -> dict:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []
    column_keys = [column["key"] for column in columns]
    overview_keys = [row["overview_key"] for row in rows]
    if len(column_keys) != len(set(column_keys)):
        raise RuntimeError("人才概览来源列键重复")
    if len(overview_keys) != len(set(overview_keys)):
        raise RuntimeError("人才概览语种关联键重复")
    return _with_totals(payload)


def load_talent_overview_data() -> dict:
    """返回独立的初始化快照，避免调用方修改进程内缓存。"""
    return copy.deepcopy(_fixture_payload())


def _snapshot_row(db: Session):
    return db.query(TalentOverviewSnapshot).filter(TalentOverviewSnapshot.id == 1).first()


def _editor_name(db: Session, user_id: UUID | None) -> str | None:
    if not user_id:
        return None
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    return (user.full_name or user.username) if user else None


def get_talent_overview(db: Session | None = None) -> dict:
    """读取当前共享快照；尚未持久化时使用仓库内初始数据。"""
    if db is None:
        return {**load_talent_overview_data(), "revision": 1, "updated_at": None, "updated_by_name": None}
    snapshot = _snapshot_row(db)
    if snapshot is None:
        return {**load_talent_overview_data(), "revision": 1, "updated_at": None, "updated_by_name": None}
    return {
        **_with_totals(copy.deepcopy(snapshot.payload)),
        "revision": snapshot.revision,
        "updated_at": snapshot.updated_at,
        "updated_by_name": _editor_name(db, snapshot.updated_by),
    }


def _new_custom_key(key: str, prefix: str) -> bool:
    if not key.startswith(f"{prefix}-"):
        return False
    try:
        UUID(key[len(prefix) + 1:])
    except ValueError:
        return False
    return True


def _ensure_unique_labels(items: list[dict], field: str, message: str) -> None:
    normalized = [str(item[field]).strip().casefold() for item in items]
    if len(normalized) != len(set(normalized)):
        raise ValueError(message)


def _validate_structure(previous: dict, columns: list[dict], rows: list[dict]) -> None:
    previous_columns = previous["columns"]
    previous_rows = previous["rows"]
    previous_column_keys = {item["key"] for item in previous_columns}
    previous_row_keys = {item["overview_key"] for item in previous_rows}

    column_keys = [item["key"] for item in columns]
    row_keys = [item["overview_key"] for item in rows]
    if len(column_keys) != len(set(column_keys)):
        raise ValueError("来源列键不能重复")
    if len(row_keys) != len(set(row_keys)):
        raise ValueError("人才概览行键不能重复")
    _ensure_unique_labels(columns, "label", "来源列名称不能重复")
    _ensure_unique_labels(rows, "language", "语种/方言名称不能重复")

    for group in GROUP_ORDER:
        old_keys = [item["key"] for item in previous_columns if item["group"] == group]
        submitted = [item["key"] for item in columns if item["group"] == group]
        submitted_existing = [key for key in submitted if key in previous_column_keys]
        if submitted_existing != old_keys:
            raise ValueError("已有来源列不能删除、调序或修改归类")
        first_new = next((index for index, key in enumerate(submitted) if key not in previous_column_keys), len(submitted))
        if any(key in previous_column_keys for key in submitted[first_new:]):
            raise ValueError("新增来源列只能追加到所属分组末尾")
    if any(item["group"] not in GROUP_ORDER for item in columns):
        raise ValueError("来源列归类无效")
    group_indexes = [GROUP_ORDER.index(item["group"]) for item in columns]
    if group_indexes != sorted(group_indexes):
        raise ValueError("来源列分组顺序不能调整")
    previous_by_key = {item["key"]: item for item in previous_columns}
    for column in columns:
        old = previous_by_key.get(column["key"])
        if old and (column["group"] != old["group"] or column["width"] != old["width"]):
            raise ValueError("已有来源列的归类和宽度不能修改")
        if not old and not _new_custom_key(column["key"], "col"):
            raise ValueError("新增来源列键无效")

    submitted_existing_rows = [key for key in row_keys if key in previous_row_keys]
    previous_order = [item["overview_key"] for item in previous_rows]
    if submitted_existing_rows != previous_order:
        raise ValueError("已有语种行不能删除或调序")
    first_new_row = next((index for index, key in enumerate(row_keys) if key not in previous_row_keys), len(row_keys))
    if any(key in previous_row_keys for key in row_keys[first_new_row:]):
        raise ValueError("新增语种只能追加到表格底部")
    for key in row_keys[first_new_row:]:
        if not _new_custom_key(key, "row"):
            raise ValueError("新增人才概览行键无效")

    expected_count_keys = set(column_keys)
    for row in rows:
        if set(row["counts"]) != expected_count_keys:
            raise ValueError(f"“{row['language']}”的数量列与表头不一致")


def _validate_language_identifiers(rows: list[dict]) -> None:
    owners: dict[str, str] = {}
    for row in rows:
        for value in (row["language"], *(row.get("aliases") or [])):
            normalized = normalize_language_search_text(value)
            if not normalized:
                continue
            owner = owners.get(normalized)
            if owner and owner != row["overview_key"]:
                raise ValueError(f"语种名称或历史别名“{value}”与其他行重复")
            owners[normalized] = row["overview_key"]


def _prepare_saved_payload(previous: dict, payload: TalentOverviewWrite) -> dict:
    columns = [item.model_dump(mode="json") for item in payload.columns]
    submitted_rows = [item.model_dump(mode="json") for item in payload.rows]
    _validate_structure(previous, columns, submitted_rows)

    previous_rows = {row["overview_key"]: row for row in previous["rows"]}
    rows = []
    for submitted in submitted_rows:
        old = previous_rows.get(submitted["overview_key"])
        aliases = list(old.get("aliases") or []) if old else []
        if old and normalize_language_search_text(old["language"]) != normalize_language_search_text(submitted["language"]):
            known = {normalize_language_search_text(value) for value in aliases}
            if normalize_language_search_text(old["language"]) not in known:
                aliases.append(old["language"])
        rows.append({**submitted, "aliases": aliases})
    _validate_language_identifiers(rows)
    return _with_totals({
        "version": previous.get("version", 1),
        "non_deduplicated": True,
        "columns": columns,
        "rows": rows,
    })


def save_talent_overview(
    db: Session,
    payload: TalentOverviewWrite,
    user_id: UUID,
) -> dict:
    """原子保存整张表，并用修订号阻止旧草稿覆盖新数据。"""
    initial = load_talent_overview_data()
    db.execute(
        pg_insert(TalentOverviewSnapshot)
        .values(id=1, payload=_storage_payload(initial), revision=1)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    snapshot = (
        db.query(TalentOverviewSnapshot)
        .filter(TalentOverviewSnapshot.id == 1)
        .with_for_update()
        .one()
    )
    if snapshot.revision != payload.expected_revision:
        db.rollback()
        raise StaleUpdateError("人才概览已被其他人更新，请重新加载后再保存")

    previous = _with_totals(copy.deepcopy(snapshot.payload))
    saved = _prepare_saved_payload(previous, payload)
    snapshot.payload = _storage_payload(saved)
    snapshot.revision += 1
    snapshot.updated_by = user_id
    snapshot.updated_at = datetime.now()
    db.commit()
    db.refresh(snapshot)
    return {
        **saved,
        "revision": snapshot.revision,
        "updated_at": snapshot.updated_at,
        "updated_by_name": _editor_name(db, snapshot.updated_by),
    }


def _overview_indexes(data: dict) -> tuple[dict[str, dict], dict[str, set[str]]]:
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


def resolve_overview_for_text(
    value: object,
    *,
    data: dict | None = None,
    db: Session | None = None,
) -> tuple[dict | None, str | None]:
    """仅按规范名或明确别名精确解析，不执行包含匹配或相似度猜测。"""
    normalized = normalize_language_search_text(value)
    if not normalized:
        return None, None
    rows_by_key, keys_by_name = _overview_indexes(data or get_talent_overview(db))
    keys = keys_by_name.get(normalized, set())
    if len(keys) != 1:
        return None, "ambiguous" if len(keys) > 1 else None
    key = next(iter(keys))
    row = rows_by_key[key]
    match_type = "canonical" if normalized == normalize_language_search_text(row["language"]) else "alias"
    return row, match_type


def resolve_overview_for_language(
    language: InterpretationLanguage,
    *,
    data: dict | None = None,
    db: Session | None = None,
) -> tuple[dict | None, str | None]:
    rows_by_key, keys_by_name = _overview_indexes(data or get_talent_overview(db))
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
                if any(normalized == normalize_language_search_text(rows_by_key[key]["language"]) for key in keys)
                else "alias"
            )
    if len(matched_keys) != 1:
        return None, "ambiguous" if len(matched_keys) > 1 else None
    key = next(iter(matched_keys))
    return rows_by_key[key], "canonical" if "canonical" in match_types else "alias"


def _audit_candidate_rows(language: InterpretationLanguage, data: dict, *, limit: int = 5) -> list[dict]:
    """仅为人工治理报告生成相似候选，不参与运行时解析或自动落库。"""
    source_values = [normalize_language_search_text(value) for value in _language_candidate_values(language)]
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
                contained = min(len(source), len(target)) >= 2 and (source in target or target in source)
                score = SequenceMatcher(None, source, target).ratio()
                if contained:
                    score = max(score, 0.85)
                if score > best_score:
                    best_score = score
                    best_reason = "contains" if contained else "similarity"
        if best_score >= 0.5:
            scored.append((best_score, row, best_reason))
    scored.sort(key=lambda item: (-item[0], item[1]["language"]))
    return [{
        "overview_key": row["overview_key"],
        "overview_language": row["language"],
        "score": round(score, 4),
        "reason": reason,
    } for score, row, reason in scored[:limit]]


def lookup_language_reserves(db: Session, language_ids: Iterable[UUID]) -> list[dict]:
    ordered_ids = list(dict.fromkeys(language_ids))
    if not ordered_ids:
        return []
    data = get_talent_overview(db)
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
            results.append({"language_id": language_id, "requested_label": None, "matched": False, "total": None})
            continue
        row, match_type = resolve_overview_for_language(language, data=data)
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
    data = get_talent_overview(db)
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
        row, match_type = resolve_overview_for_language(language, data=data)
        item = {"id": str(language.id), "label": language.label}
        if row is None:
            candidates = _audit_candidate_rows(language, data)
            item["reason"] = (match_type or "candidate_review") if candidates else "unmatched"
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
        label_is_canonical = normalize_language_search_text(language.label) == normalize_language_search_text(row["language"])
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
            row, _match_type = resolved_item
            language.talent_overview_key = row["overview_key"]
            canonical_label = row["language"]
            can_rename = (
                len(grouped[row["overview_key"]]) == 1
                and language.label != canonical_label
                and canonical_label.casefold() not in existing_labels
            )
            if can_rename:
                old_label = language.label
                language.label = canonical_label
                normalized_old = normalize_language_search_text(old_label)
                if normalized_old and not any(alias.normalized_alias == normalized_old for alias in language.aliases):
                    language.aliases.append(InterpretationLanguageAlias(
                        alias=old_label,
                        normalized_alias=normalized_old,
                        alias_type="historical",
                    ))
                renamed.append({"id": str(language.id), "from": old_label, "to": canonical_label})
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
