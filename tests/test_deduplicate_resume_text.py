"""简历原文去重的版本选择与防误合并测试。"""

import hashlib
import json
import sqlite3
from pathlib import Path

from tools import deduplicate_resume_text as dedup


def source(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    root = tmp_path / "source"
    (root / "texts").mkdir(parents=True)
    db = sqlite3.connect(root / "state.sqlite3")
    db.execute("""CREATE TABLE files (
        path TEXT PRIMARY KEY, root TEXT, relative_path TEXT, extension TEXT,
        size INTEGER, mtime_ns INTEGER, modified_at TEXT, sha256 TEXT, status TEXT,
        reason TEXT, characters INTEGER, segments INTEGER, processed_at TEXT,
        file_id TEXT
    )""")
    return root, db


def add(root: Path, db: sqlite3.Connection, name: str, text: str, mtime: int,
        extension: str = ".docx", file_hash: str | None = None) -> str:
    path = rf"\\Win-server\共享\{name}{extension}"
    fid = hashlib.sha256(path.encode()).hexdigest()
    (root / "texts" / f"{fid}.txt").write_text(text, encoding="utf-8")
    digest = file_hash or hashlib.sha256((name + text).encode()).hexdigest()
    db.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (path, r"\\Win-server\共享", f"{name}{extension}", extension,
                len(text), mtime, f"2026-10-29T{mtime:02d}:00:00+08:00", digest,
                "success", "", len(text), 1, "2026-10-29T10:00:00+08:00", fid))
    db.commit()
    return fid


def decisions(output: Path) -> dict[str, tuple[str, str | None, str]]:
    with sqlite3.connect(output / "state.sqlite3") as db:
        return {fid: (status, representative, reason) for fid, status, representative, reason
                in db.execute("SELECT file_id,status,representative_id,reason FROM decisions")}


def test_latest_version_shared_email_multiple_people_and_rerun(tmp_path: Path):
    root, db = source(tmp_path)
    old = add(root, db, "old", "甲的简历 13800000000 a@example.com " + "旧经历" * 80, 1)
    new = add(root, db, "new", "甲的简历 13800000000 a@example.com " + "新经历" * 80, 5)
    shared_new = add(root, db, "shared_new", "联系人 team@example.com " + "翻译项目" * 80, 6)
    shared_old = add(root, db, "shared_old", "联系人 team@example.com " + "完全不同的课程" * 80, 2)
    exact_new = add(root, db, "exact_new", "没有联系方式的相同正文" * 30, 8)
    exact_old = add(root, db, "exact_old", "没有联系方式的相同正文" * 30, 3)
    sheet = add(root, db, "sheet", "甲 13800000000 a@example.com\n乙 13900000000 b@example.com", 9, ".xlsx")
    db.close()

    output = tmp_path / "dedup"
    report = dedup.run([root], output)
    found = decisions(output)
    assert found[old] == ("superseded", new, "same_phone_and_email")
    assert found[new][0] == "keep"
    assert found[shared_new][0] == "keep"
    assert found[shared_old] == ("review", None, "shared_contact_different_text")
    assert found[exact_old] == ("superseded", exact_new, "exact_text")
    assert found[sheet] == ("review", None, "multiple_or_uncertain_people")
    assert report["source_files"] == 7
    assert sum(report["by_status"].values()) == 7
    assert len((output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()) == 7

    second = dedup.run([root], output)
    assert second["scan"]["unchanged"] == 7
    assert decisions(output) == found


def test_single_contact_similarity_and_newer_source_replaces_representative(tmp_path: Path):
    root, db = source(tmp_path)
    body = "姓名甲 邮箱 only@example.com " + "教育经历和翻译项目" * 70
    first = add(root, db, "first", body, 1)
    second = add(root, db, "second", body + "补充", 2)
    db.close()
    output = tmp_path / "dedup"
    dedup.run([root], output)
    assert decisions(output)[first] == ("superseded", second, "same_contact_similar_text")

    with sqlite3.connect(root / "state.sqlite3") as db:
        db.execute("UPDATE files SET mtime_ns=3,modified_at='2026-10-29T03:00:00+08:00',processed_at='2026-10-29T11:00:00+08:00' WHERE file_id=?", (first,))
    dedup.run([root], output)
    assert decisions(output)[second] == ("superseded", first, "same_contact_similar_text")
    assert decisions(output)[first][0] == "keep"


def test_pilot_audit_does_not_modify_pilot(tmp_path: Path):
    root, db = source(tmp_path)
    old = add(root, db, "old", "甲 13800000000 a@example.com " + "旧" * 300, 1)
    add(root, db, "new", "甲 13800000000 a@example.com " + "新" * 300, 2)
    db.close()
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    with sqlite3.connect(pilot / "state.sqlite3") as c:
        c.execute("CREATE TABLE documents(file_id TEXT)")
        c.execute("INSERT INTO documents VALUES (?)", (old,))
    output = tmp_path / "dedup"
    report = dedup.run([root], output, pilot)
    assert report["pilot_228_audit"] == {"superseded": 1}
    audit = [json.loads(line) for line in (output / "pilot_audit.jsonl").read_text().splitlines()]
    assert audit[0]["file_id"] == old
    with sqlite3.connect(pilot / "state.sqlite3") as c:
        assert c.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
