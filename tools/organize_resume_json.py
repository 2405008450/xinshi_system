"""将简历采集结果按第一外语归档为逐文件 JSON，不复制原文件。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))
from language_catalog import LANGUAGE_ENGLISH_NAMES, LANGUAGE_VARIANTS  # noqa: E402


SCHEMA_VERSION = 1
CLASSIFIER_VERSION = 1
TZ = timezone(timedelta(hours=8))
UNKNOWN = "待确认"
AMBIGUOUS_FOLDER_NAMES = {"多语种", "瑞士语", "埃及语", "日耳曼语", "哈萨克斯坦语", "塔塔尔斯坦语", "第一外语", "第二外语", "其他外语"}
EXTRA_LANGUAGES = (
    "立陶宛语", "拉脱维亚语", "尼泊尔语", "阿尔巴尼亚语", "阿塞拜疆语", "土库曼语",
    "吉尔吉斯语", "塔塔尔语", "乌兹别克语", "库尔德语", "奥罗莫语", "泰米尔语",
    "僧伽罗语", "马拉地语", "菲律宾语", "克罗地亚语", "斯洛文尼亚语", "粤语",
    "中文繁体", "普通话", "越南语", "阿拉伯语", "印尼语", "柬埔寨语", "哈萨克语",
)
FIELD_RE = re.compile(
    r"(?:第一外语|外语一|首要外语|first\s+foreign\s+language|1st\s+foreign\s+language)"
    r"[ \t]*[:：=\-]?[ \t]*([^\r\n]{0,90})(?:\r?\n([^\r\n]{0,60}))?",
    re.IGNORECASE,
)
FOLDER_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*\s*[.、]?\s*")


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def build_aliases() -> list[tuple[str, str]]:
    aliases: dict[str, str] = {}
    for item in LANGUAGE_VARIANTS:
        label = item["label"].split("（", 1)[0]
        for alias in (label, *item.get("aliases", [])):
            if len(alias) >= 2:
                aliases.setdefault(alias.casefold(), label)
        english = LANGUAGE_ENGLISH_NAMES.get(item["code"], "").split(" (", 1)[0]
        if english:
            aliases.setdefault(english.casefold(), label)
    for label in EXTRA_LANGUAGES:
        aliases.setdefault(label.casefold(), label)
    aliases.update({
        "英文": "英语", "english": "英语", "法文": "法语", "french": "法语",
        "德文": "德语", "german": "德语", "日文": "日语", "japanese": "日语",
        "西语": "西班牙语", "葡语": "葡萄牙语", "阿语": "阿拉伯语",
        "印尼语": "印度尼西亚语", "柬埔寨语": "高棉语", "台繁": "中文繁体",
    })
    return sorted(aliases.items(), key=lambda pair: len(pair[0]), reverse=True)


ALIASES = build_aliases()


def languages_in(value: str) -> list[str]:
    matches = []
    lower = value.casefold()
    for alias, label in ALIASES:
        for match in re.finditer(re.escape(alias), lower):
            if alias.isascii():
                before = lower[match.start() - 1] if match.start() else " "
                after = lower[match.end()] if match.end() < len(lower) else " "
                if before.isalpha() or after.isalpha():
                    continue
            matches.append((match.start(), -len(alias), label))
    matches.sort()
    result = []
    for _, _, label in matches:
        if label not in result:
            result.append(label)
    return result


def first_foreign_from_text(text: str) -> tuple[str | None, str]:
    found = []
    saw_field = False
    for match in FIELD_RE.finditer(text):
        saw_field = True
        value = match.group(1).strip() or (match.group(2) or "").strip()
        value = re.split(r"(?:第二外语|其他外语|其它外语|母语|second\s+foreign\s+language)", value, maxsplit=1, flags=re.IGNORECASE)[0]
        candidates = languages_in(value)
        if candidates:
            found.append(candidates[0])
    distinct = list(dict.fromkeys(found))
    if len(distinct) == 1:
        return distinct[0], "explicit_first_foreign"
    if len(distinct) > 1:
        return None, "conflicting_first_foreign"
    return None, "explicit_unrecognized" if saw_field else "not_stated"


def folder_language(relative_path: str) -> str | None:
    folders = Path(relative_path).parts[:-1]
    for folder in folders:
        value = FOLDER_NUMBER_RE.sub("", folder).strip()
        if value in AMBIGUOUS_FOLDER_NAMES:
            continue
        exact = [label for alias, label in ALIASES if alias == value.casefold()]
        if exact:
            return exact[0]
        if value.endswith("语") and value.count("语") == 1 and 2 <= len(value) <= 12:
            return value
        if value == "台繁":
            return "中文繁体"
    return None


def classify(text: str, relative_path: str, extension: str) -> tuple[str, str, str | None, bool]:
    folder = folder_language(relative_path)
    if extension not in {".xls", ".xlsx"}:
        explicit, basis = first_foreign_from_text(text)
        if explicit:
            return explicit, basis, folder, bool(folder and folder != explicit)
        if basis == "conflicting_first_foreign":
            return UNKNOWN, basis, folder, False
    if folder:
        return folder, "source_directory", folder, False
    return UNKNOWN, "undetermined", None, False


def ensure_paths(output: Path, collections: list[Path]) -> None:
    resolved = output.resolve()
    if resolved == REPOSITORY or REPOSITORY in resolved.parents:
        raise ValueError("归档目录必须位于仓库外")
    for collection in collections:
        if not (collection / "state.sqlite3").is_file():
            raise FileNotFoundError(collection / "state.sqlite3")
        if resolved == collection.resolve() or collection.resolve() in resolved.parents:
            raise ValueError("归档目录不能位于单批次采集目录内")


def open_state(output: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(output / "organize_state.sqlite3")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS records (
        file_id TEXT PRIMARY KEY, source_path TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
        language TEXT NOT NULL, json_path TEXT NOT NULL, extraction_status TEXT NOT NULL,
        classification_basis TEXT NOT NULL, organized_at TEXT NOT NULL
    )""")
    connection.commit()
    return connection


def text_and_locations(collection: Path, file_id: str, status: str) -> tuple[str | None, list[dict]]:
    if status != "success":
        return None, []
    text_path = collection / "texts" / f"{file_id}.txt"
    segments_path = collection / "segments" / f"{file_id}.json"
    text = text_path.read_text(encoding="utf-8")
    segments = json.loads(segments_path.read_text(encoding="utf-8"))
    locations = []
    position = 0
    for segment in segments:
        value = segment.get("text", "")
        if not value.strip():
            continue
        if locations:
            position += 2
        locations.append({"location": segment.get("location", ""), "start": position, "end": position + len(value)})
        position += len(value)
    return text, locations


def save_record(output: Path, state: sqlite3.Connection, collection: Path, row: sqlite3.Row) -> bool:
    file_id = row["file_id"]
    fingerprint = hashlib.sha256(json.dumps(
        [SCHEMA_VERSION, CLASSIFIER_VERSION, row["sha256"], row["status"], row["processed_at"], row["root"], row["relative_path"]],
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    old = state.execute("SELECT source_fingerprint,json_path FROM records WHERE file_id=?", (file_id,)).fetchone()
    if old and old[0] == fingerprint and (output / old[1]).is_file():
        return False

    text, locations = text_and_locations(collection, file_id, row["status"])
    language, basis, folder, conflict = classify(text or "", row["relative_path"], row["extension"])
    relative = f"{language}/{file_id}.json"
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_path": row["path"], "source_root": row["root"], "source_relative_path": row["relative_path"],
        "source_sha256": row["sha256"] or None, "source_size": row["size"],
        "source_modified_at": row["modified_at"], "source_extension": row["extension"],
        "extraction_status": row["status"], "extraction_reason": row["reason"] or None,
        "primary_language": language, "classification_basis": basis,
        "source_folder_language": folder, "folder_conflict": conflict,
        "raw_text": text, "segment_locations": locations,
        "organized_at": now_iso(),
    }
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", prefix=".resume-", dir=target.parent, delete=False) as temp:
        json.dump(record, temp, ensure_ascii=False, indent=2)
        temp_path = Path(temp.name)
    os.replace(temp_path, target)
    state.execute("""INSERT INTO records VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(file_id) DO UPDATE SET source_path=excluded.source_path,
        source_fingerprint=excluded.source_fingerprint,language=excluded.language,
        json_path=excluded.json_path,extraction_status=excluded.extraction_status,
        classification_basis=excluded.classification_basis,organized_at=excluded.organized_at""",
        (file_id, row["path"], fingerprint, language, relative, row["status"], basis, record["organized_at"]),
    )
    state.commit()
    if old and old[1] != relative:
        former = (output / old[1]).resolve()
        if output.resolve() in former.parents:
            former.unlink(missing_ok=True)
    return True


def export_summary(output: Path, state: sqlite3.Connection, limited: bool, errors: list[dict]) -> dict:
    index_path = output / "index.csv"
    pending_path = output / "pending_review.csv"
    statuses = Counter()
    languages = Counter()
    bases = Counter()
    with index_path.open("w", encoding="utf-8-sig", newline="") as index_file, pending_path.open("w", encoding="utf-8-sig", newline="") as pending_file:
        columns = ["file_id", "source_path", "language", "classification_basis", "extraction_status", "json_path"]
        index = csv.DictWriter(index_file, fieldnames=columns)
        pending = csv.DictWriter(pending_file, fieldnames=columns)
        index.writeheader()
        pending.writeheader()
        for row in state.execute("SELECT file_id,source_path,language,classification_basis,extraction_status,json_path FROM records ORDER BY language,source_path"):
            item = dict(zip(columns, row))
            index.writerow(item)
            statuses[item["extraction_status"]] += 1
            languages[item["language"]] += 1
            bases[item["classification_basis"]] += 1
            if item["language"] == UNKNOWN or item["extraction_status"] != "success":
                pending.writerow(item)
    report = {
        "generated_at": now_iso(), "schema_version": SCHEMA_VERSION,
        "limited_run": limited, "total": sum(statuses.values()),
        "by_extraction_status": dict(statuses), "by_language": dict(languages),
        "by_classification_basis": dict(bases), "organize_errors": errors,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def organize(collections: list[Path], output: Path, limit: int | None = None) -> dict:
    ensure_paths(output, collections)
    output.mkdir(parents=True, exist_ok=True)
    state = open_state(output)
    errors = []
    visited = set()
    handled = 0
    for collection in collections:
        source = sqlite3.connect(f"file:{(collection / 'state.sqlite3').as_posix()}?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        try:
            for row in source.execute("SELECT * FROM files ORDER BY path"):
                if row["file_id"] in visited:
                    continue
                visited.add(row["file_id"])
                try:
                    save_record(output, state, collection, row)
                except Exception as exc:
                    errors.append({"file_id": row["file_id"], "reason": type(exc).__name__})
                handled += 1
                if handled % 500 == 0:
                    print(f"已归档检查 {handled} 个采集记录", flush=True)
                if limit is not None and handled >= limit:
                    break
        finally:
            source.close()
        if limit is not None and handled >= limit:
            break
    report = export_summary(output, state, limit is not None, errors)
    state.close()
    print(json.dumps({"total": report["total"], "errors": len(errors), "limited_run": report["limited_run"]}, ensure_ascii=False), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", action="append", type=Path, required=True, help="采集输出目录；可重复指定")
    parser.add_argument("--output", type=Path, required=True, help="服务器仓库外的集中归档目录")
    parser.add_argument("--limit", type=int, help="仅用于小批量验收")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit 必须大于 0")
    report = organize(args.collection, args.output, args.limit)
    return 1 if report["organize_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
