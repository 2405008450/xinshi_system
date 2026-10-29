"""只读扫描采集文本，生成可追溯的简历去重清单。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
import uuid
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))
RULE_VERSION = 1
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
SPREADSHEETS = {".xls", ".xlsx", ".csv", ".tsv"}
NAME_LABEL = re.compile(r"(?im)^\s*(?:姓名|name)\s*[:：]")
MAX_SHARED_CONTACT = 20
SIMILARITY_THRESHOLD = 0.90


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def fingerprint(row: sqlite3.Row) -> str:
    data = [row["path"], row["sha256"], row["processed_at"], RULE_VERSION]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode("utf-8")).hexdigest()


def normalized(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold() if ch.isalnum())


def shingles(text: str) -> set[str]:
    value = normalized(text)
    return {value[i:i + 5] for i in range(max(0, len(value) - 4))}


def similarity(left: str, right: str) -> float:
    if min(len(normalized(left)), len(normalized(right))) < 200:
        return 0.0
    a, b = shingles(left), shingles(right)
    return len(a & b) / len(a | b) if a | b else 0.0


def contact_hash(secret: bytes, kind: str, value: str) -> str:
    return hmac.new(secret, (kind + ":" + value).encode("utf-8"), hashlib.sha256).hexdigest()


def contacts(text: str, secret: bytes) -> tuple[set[str], set[str]]:
    phones = {contact_hash(secret, "phone", value) for value in PHONE.findall(text)}
    emails = {contact_hash(secret, "email", value.casefold()) for value in EMAIL.findall(text)}
    return phones, emails


def open_state(output: Path) -> tuple[sqlite3.Connection, bytes]:
    output.mkdir(parents=True, exist_ok=True)
    key_path = output / "contact_hmac.key"
    if not key_path.exists():
        with key_path.open("xb") as target:
            target.write(os.urandom(32))
    secret = key_path.read_bytes()
    if len(secret) != 32:
        raise ValueError("contact_key_invalid")
    db = sqlite3.connect(output / "state.sqlite3")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS files (
        file_id TEXT PRIMARY KEY, collection TEXT NOT NULL, path TEXT NOT NULL,
        fingerprint TEXT NOT NULL, sha256 TEXT NOT NULL, text_sha256 TEXT NOT NULL,
        extension TEXT NOT NULL, mtime_ns INTEGER NOT NULL, modified_at TEXT NOT NULL,
        characters INTEGER NOT NULL, people_hint TEXT NOT NULL,
        scan_status TEXT NOT NULL, seen_run TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS contacts (
        file_id TEXT NOT NULL, kind TEXT NOT NULL, token_hash TEXT NOT NULL,
        PRIMARY KEY(file_id,kind,token_hash)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS contacts_lookup ON contacts(kind,token_hash,file_id)")
    db.execute("CREATE INDEX IF NOT EXISTS files_sha ON files(sha256)")
    db.execute("CREATE INDEX IF NOT EXISTS files_text_sha ON files(text_sha256)")
    db.execute("""CREATE TABLE IF NOT EXISTS decisions (
        file_id TEXT PRIMARY KEY, status TEXT NOT NULL, representative_id TEXT,
        reason TEXT NOT NULL, similarity REAL, decided_at TEXT NOT NULL
    )""")
    db.commit()
    return db, secret


def source_db(collection: Path) -> sqlite3.Connection:
    path = collection / "state.sqlite3"
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def scan(collections: list[Path], output: Path, db: sqlite3.Connection, secret: bytes) -> dict:
    run_id = uuid.uuid4().hex
    stats = Counter()
    for collection in collections:
        with closing(source_db(collection)) as source, closing(source_db(collection)) as current_source:
            for row in source.execute("SELECT * FROM files WHERE status='success'"):
                fid = row["file_id"]
                fp = fingerprint(row)
                old = db.execute("SELECT fingerprint,scan_status FROM files WHERE file_id=?", (fid,)).fetchone()
                if old and old["fingerprint"] == fp and old["scan_status"] == "indexed":
                    db.execute("UPDATE files SET seen_run=?,collection=? WHERE file_id=?",
                               (run_id, str(collection), fid))
                    stats["unchanged"] += 1
                    if sum(stats.values()) % 5000 == 0:
                        db.commit()
                        print(json.dumps({"scanned": sum(stats.values()), "at": now_iso()}), flush=True)
                    continue
                path = collection / "texts" / f"{fid}.txt"
                try:
                    before = path.stat()
                    text = path.read_text(encoding="utf-8")
                    after = path.stat()
                    current = current_source.execute(
                        "SELECT sha256,processed_at,status FROM files WHERE path=?", (row["path"],)
                    ).fetchone()
                    if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                            or current is None or tuple(current) != (row["sha256"], row["processed_at"], "success")):
                        raise RuntimeError("source_changing")
                    phones, emails = contacts(text, secret)
                    hint = ("multiple_or_uncertain" if row["extension"] in SPREADSHEETS
                            or len(phones) > 1 or len(emails) > 1
                            or len(NAME_LABEL.findall(text)) > 1 else "single_candidate")
                    digest = hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()
                    scan_status = "indexed"
                except (OSError, UnicodeError, RuntimeError) as exc:
                    phones, emails = set(), set()
                    hint, digest, scan_status = type(exc).__name__, "", "pending"
                db.execute("""INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(file_id) DO UPDATE SET collection=excluded.collection,path=excluded.path,
                    fingerprint=excluded.fingerprint,sha256=excluded.sha256,text_sha256=excluded.text_sha256,
                    extension=excluded.extension,mtime_ns=excluded.mtime_ns,modified_at=excluded.modified_at,
                    characters=excluded.characters,people_hint=excluded.people_hint,
                    scan_status=excluded.scan_status,seen_run=excluded.seen_run""",
                    (fid, str(collection), row["path"], fp, row["sha256"], digest,
                     row["extension"], row["mtime_ns"], row["modified_at"], row["characters"],
                     hint, scan_status, run_id))
                db.execute("DELETE FROM contacts WHERE file_id=?", (fid,))
                db.executemany("INSERT INTO contacts VALUES (?,?,?)",
                               [(fid, "phone", item) for item in phones] + [(fid, "email", item) for item in emails])
                stats[scan_status] += 1
                if sum(stats.values()) % 5000 == 0:
                    db.commit()
                    print(json.dumps({"scanned": sum(stats.values()), "at": now_iso()}), flush=True)
            db.execute("DELETE FROM contacts WHERE file_id IN (SELECT file_id FROM files WHERE collection=? AND seen_run<>?)", (str(collection), run_id))
            db.execute("DELETE FROM files WHERE collection=? AND seen_run<>?", (str(collection), run_id))
            db.commit()
    return dict(stats)


def classify(db: sqlite3.Connection) -> dict:
    db.execute("DELETE FROM decisions")
    db.commit()
    rows = db.execute("""SELECT * FROM files ORDER BY mtime_ns DESC,characters DESC,path COLLATE BINARY ASC""").fetchall()
    by_id = {row["file_id"]: row for row in rows}
    sha_keep: dict[str, str] = {}
    text_keep: dict[str, str] = {}
    kept_contacts: dict[tuple[str, str], list[str]] = {}
    all_contact_count = dict(db.execute("SELECT kind||':'||token_hash,COUNT(*) FROM contacts GROUP BY kind,token_hash"))
    text_cache: dict[str, str] = {}
    stats = Counter()

    def get_text(row: sqlite3.Row) -> str:
        fid = row["file_id"]
        if fid not in text_cache:
            text_cache[fid] = (Path(row["collection"]) / "texts" / f"{fid}.txt").read_text(encoding="utf-8")
            if hashlib.sha256(normalized(text_cache[fid]).encode("utf-8")).hexdigest() != row["text_sha256"]:
                text_cache.pop(fid)
                raise RuntimeError("source_changing")
            if len(text_cache) > 64:
                text_cache.pop(next(iter(text_cache)))
        return text_cache[fid]

    for index, row in enumerate(rows, 1):
        fid = row["file_id"]
        status, representative, reason, sim = "keep", None, "unique", None
        if row["scan_status"] != "indexed":
            status, reason = "pending", row["people_hint"]
        elif row["people_hint"] != "single_candidate":
            status, reason = "review", "multiple_or_uncertain_people"
        else:
            keys = [(kind, token) for kind, token in db.execute("SELECT kind,token_hash FROM contacts WHERE file_id=?", (fid,))]
            phone = next((token for kind, token in keys if kind == "phone"), None)
            email = next((token for kind, token in keys if kind == "email"), None)
            if row["sha256"] and row["sha256"] in sha_keep:
                status, representative, reason = "superseded", sha_keep[row["sha256"]], "exact_file"
            elif row["text_sha256"] and row["text_sha256"] in text_keep:
                status, representative, reason = "superseded", text_keep[row["text_sha256"]], "exact_text"
            else:
                candidates = list(dict.fromkeys(other for key in keys for other in kept_contacts.get(key, [])))
                frequent = any(all_contact_count.get(kind + ":" + token, 0) > MAX_SHARED_CONTACT for kind, token in keys)
                if frequent:
                    status, reason = "review", "widely_shared_contact"
                else:
                    for other in candidates:
                        other_keys = {(k, t) for k, t in db.execute("SELECT kind,token_hash FROM contacts WHERE file_id=?", (other,))}
                        both = bool(phone and email and ("phone", phone) in other_keys and ("email", email) in other_keys)
                        if both:
                            status, representative, reason = "superseded", other, "same_phone_and_email"
                            break
                        try:
                            score = similarity(get_text(row), get_text(by_id[other]))
                        except (OSError, UnicodeError, RuntimeError):
                            status, reason = "pending", "source_changing"
                            break
                        if score >= SIMILARITY_THRESHOLD:
                            status, representative, reason, sim = "superseded", other, "same_contact_similar_text", score
                            break
                    if status == "keep" and candidates:
                        status, reason = "review", "shared_contact_different_text"
            if status in {"keep", "review"}:
                if row["sha256"]:
                    sha_keep.setdefault(row["sha256"], fid)
                if row["text_sha256"]:
                    text_keep.setdefault(row["text_sha256"], fid)
                for key in keys:
                    kept_contacts.setdefault(key, []).append(fid)
        db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?)", (fid, status, representative, reason, sim, now_iso()))
        stats[status] += 1
        if index % 1000 == 0:
            db.commit()
            print(json.dumps({"classified": index, "at": now_iso()}), flush=True)
    db.commit()
    return dict(stats)


def atomic_text(path: Path, write) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent,
                                     prefix=".tmp-", delete=False) as target:
        write(target)
        temporary = Path(target.name)
    os.replace(temporary, path)


def export(output: Path, db: sqlite3.Connection, scan_stats: dict, pilot: Path | None = None) -> dict:
    counts = dict(db.execute("SELECT status,COUNT(*) FROM decisions GROUP BY status"))
    by_collection = {}
    for collection, status, count in db.execute("""SELECT f.collection,d.status,COUNT(*) FROM files f
        JOIN decisions d ON d.file_id=f.file_id GROUP BY f.collection,d.status"""):
        by_collection.setdefault(collection, {})[status] = count
    def manifest(target):
        for row in db.execute("""SELECT f.*,d.status,d.representative_id,d.reason,d.similarity
            FROM files f JOIN decisions d ON d.file_id=f.file_id ORDER BY f.path"""):
            record = {key: row[key] for key in ("file_id", "collection", "path", "sha256", "modified_at",
                        "mtime_ns", "characters", "status", "representative_id", "reason", "similarity")}
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
    atomic_text(output / "manifest.jsonl", manifest)
    def review_csv(target):
        writer = csv.writer(target)
        writer.writerow(["file_id", "source_path", "status", "reason"])
        writer.writerows(db.execute("""SELECT f.file_id,f.path,d.status,d.reason FROM files f
            JOIN decisions d ON d.file_id=f.file_id WHERE d.status IN ('review','pending') ORDER BY f.path"""))
    atomic_text(output / "pending_review.csv", review_csv)
    pilot_stats = None
    if pilot and (pilot / "state.sqlite3").is_file():
        with closing(sqlite3.connect(f"file:{(pilot / 'state.sqlite3').as_posix()}?mode=ro", uri=True)) as old:
            processed = [item[0] for item in old.execute("SELECT file_id FROM documents")]
        audit = []
        for fid in processed:
            decision = db.execute("SELECT status,representative_id,reason FROM decisions WHERE file_id=?", (fid,)).fetchone()
            audit.append({"file_id": fid, "status": decision[0] if decision else "not_indexed",
                          "representative_id": decision[1] if decision else None,
                          "reason": decision[2] if decision else "not_indexed"})
        atomic_text(output / "pilot_audit.jsonl", lambda target: [target.write(json.dumps(item) + "\n") for item in audit])
        pilot_stats = dict(Counter(item["status"] for item in audit))
    report = {"generated_at": now_iso(), "rule_version": RULE_VERSION,
              "source_files": db.execute("SELECT COUNT(*) FROM files").fetchone()[0],
              "by_status": counts, "by_collection": by_collection,
              "scan": scan_stats, "pilot_228_audit": pilot_stats,
              "similarity_threshold": SIMILARITY_THRESHOLD,
              "shared_contact_review_limit": MAX_SHARED_CONTACT}
    atomic_text(output / "report.json", lambda target: json.dump(report, target, ensure_ascii=False, indent=2))
    return report


def run(collections: list[Path], output: Path, pilot: Path | None = None) -> dict:
    repository = Path(__file__).resolve().parents[1]
    if output.resolve() == repository or repository in output.resolve().parents:
        raise ValueError("output_must_be_outside_repository")
    if not collections or len({str(p.resolve()) for p in collections}) != len(collections):
        raise ValueError("collections_invalid")
    db, secret = open_state(output)
    try:
        scan_stats = scan(collections, output, db, secret)
        classify(db)
        report = export(output, db, scan_stats, pilot)
    finally:
        db.close()
    print(json.dumps({"source_files": report["source_files"], "by_status": report["by_status"],
                      "generated_at": report["generated_at"]}, ensure_ascii=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot-output", type=Path)
    args = parser.parse_args()
    run(args.collection, args.output, args.pilot_output)


if __name__ == "__main__":
    main()
