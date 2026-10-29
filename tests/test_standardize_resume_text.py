"""简历字段化试点的来源、证据与断点续跑测试。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from tools import standardize_resume_text as stage
from tools.pack_resume_standardization_pilot import package


def make_collection(root: Path, count: int = 2) -> Path:
    root.mkdir()
    (root / "texts").mkdir()
    (root / "segments").mkdir()
    db = sqlite3.connect(root / "state.sqlite3")
    db.execute("""CREATE TABLE files (
        path TEXT PRIMARY KEY, root TEXT, relative_path TEXT, extension TEXT,
        size INTEGER, mtime_ns INTEGER, modified_at TEXT, sha256 TEXT, status TEXT,
        reason TEXT, characters INTEGER, segments INTEGER, processed_at TEXT,
        file_id TEXT
    )""")
    for index in range(count):
        path = rf"\\Win-server\共享\英语\简历{index}.docx"
        file_id = hashlib.sha256(path.encode()).hexdigest()
        text = "姓名：甲\n第一外语：英语\n\n姓名：乙\n第一外语：法语"
        segments = [{"location": "第 1 段", "text": "姓名：甲\n第一外语：英语"},
                    {"location": "第 2 段", "text": "姓名：乙\n第一外语：法语"}]
        (root / "texts" / f"{file_id}.txt").write_text(text, encoding="utf-8")
        (root / "segments" / f"{file_id}.json").write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
        db.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (path, str(root), f"英语\\简历{index}.docx", ".docx", 100, 1,
                    "2026-10-29T09:00:00+08:00", "a" * 64, "success", "", len(text), 2,
                    "2026-10-29T09:00:00+08:00", file_id))
    db.commit()
    db.close()
    return root


def fake_response():
    return {"people": [
        {"facts": [{"field": "full_name", "value": "甲", "quote": "姓名：甲"}],
         "language_skills": [{"language": "英语", "role": "foreign", "priority": 1, "quote": "第一外语：英语"}]},
        {"facts": [{"field": "full_name", "value": "乙", "quote": "姓名：乙"}],
         "language_skills": [{"language": "法语", "role": "foreign", "priority": 1, "quote": "第一外语：法语"}]},
    ], "file_review_flags": []}


def test_multiple_people_keep_source_and_evidence(tmp_path: Path, monkeypatch):
    collection = make_collection(tmp_path / "source")
    output = tmp_path / "output"
    config = tmp_path / "gateway.yaml"
    config.write_text("model_list:\n  - litellm_params:\n      api_base: https://example.test/v1\n      api_key: synthetic\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(stage, "verify_model", lambda *_: None)

    def fake_call(*args):
        calls.append(1)
        return {"choices": [{"message": {"content": json.dumps(fake_response(), ensure_ascii=False)}}],
                "model": "synthetic", "usage": {"prompt_tokens": 100, "completion_tokens": 50}}, 200

    monkeypatch.setattr(stage, "call_model", fake_call)
    report = stage.run([collection], output, config, "synthetic", 2, 2000, 1, 10)
    assert report["selected_files"] == 2
    assert report["processed_files"] == 2
    assert report["person_records"] == 4
    assert report["model_calls"] == 2
    records = [json.loads(path.read_text(encoding="utf-8")) for path in (output / "records").glob("*/*.json")]
    assert len(records) == 4
    assert {record["person_fields"]["full_name"] for record in records} == {"甲", "乙"}
    assert all(record["person_fields"]["resume_path"].startswith("\\\\Win-server") for record in records)
    assert {record["relations"]["language_skills"][0]["language_label"] for record in records} == {"英语", "法语"}
    assert all(record["evidence"]["person_fields"]["full_name"]["location"] for record in records)

    stage.run([collection], output, config, "synthetic", 2, 2000, 1, 10)
    assert len(calls) == 2
    assert len(list((output / "records").glob("*/*.json"))) == 4


def test_unverified_fact_is_rejected():
    text = "姓名：甲\n第一外语：英语"
    segments = [{"location": "第 1 页", "text": text}]
    facts = [
        {"field": "full_name", "value": "甲", "quote": "姓名：甲"},
        {"field": "primary_phone", "value": "13800000000", "quote": "姓名：甲"},
        {"field": "primary_email", "value": "invented@example.com", "quote": "不存在的原文"},
    ]
    fields, proofs, flags = stage.valid_person_fields(facts, text, segments)
    assert fields == {"full_name": "甲"}
    assert set(proofs) == {"full_name"}
    assert "value_not_in_evidence" in flags
    assert "invalid_evidence_or_value" in flags


def test_cross_person_evidence_is_removed():
    path = r"\\Win-server\共享\多人.docx"
    text = "姓名：甲\n邮箱：a@example.com\n\n姓名：乙\n第一外语：法语"
    segments = [{"location": "第 1 段", "text": "姓名：甲\n邮箱：a@example.com"},
                {"location": "第 2 段", "text": "姓名：乙\n第一外语：法语"}]
    record = {"path": path, "root": r"\\Win-server\共享", "relative_path": "多人.docx",
              "file_id": "a" * 64, "sha256": "b" * 64, "extension": ".docx", "size": 100,
              "modified_at": "2026-10-29T09:00:00+08:00"}
    raw = {"people": [
        {"facts": [{"field": "full_name", "value": "甲", "quote": "姓名：甲"}]},
        {"facts": [{"field": "full_name", "value": "乙", "quote": "姓名：乙"},
                   {"field": "primary_email", "value": "a@example.com", "quote": "邮箱：a@example.com"}]},
    ]}
    people, flags = stage.normalized_people(raw, record, Path("C:/synthetic"), text, segments,
                                            False, "synthetic", {})
    assert len(people) == 2
    assert "primary_email" not in people[1]["person_fields"]
    assert "cross_person_evidence_removed" in people[1]["review_flags"]
    assert flags == []


def test_prepare_only_selects_without_model(tmp_path: Path):
    collection = make_collection(tmp_path / "source", count=3)
    output = tmp_path / "output"
    report = stage.run([collection], output, tmp_path / "missing.yaml", stage.DEFAULT_MODEL,
                       2, 2000, 1, 10, prepare_only=True)
    assert report["selected_files"] == 2
    assert report["model_calls"] == 0
    assert report["processed_files"] == 0
    report2 = stage.run([collection], output, tmp_path / "missing.yaml", stage.DEFAULT_MODEL,
                        2, 2000, 1, 10, prepare_only=True)
    assert report2["selected_files"] == 2


def test_snapshot_keeps_original_collection_reference(tmp_path: Path):
    collection = make_collection(tmp_path / "source", count=3)
    output = tmp_path / "output"
    stage.run([collection], output, tmp_path / "missing.yaml", stage.DEFAULT_MODEL,
              2, 2000, 1, 10, prepare_only=True)
    staging = tmp_path / "input_snapshot"
    archive = tmp_path / "input_snapshot.zip"
    result = package(output / "state.sqlite3", staging, archive)
    assert result["copied"] == 2
    assert result["deferred"] == 0
    assert archive.is_file()
    assert json.loads((staging / collection.name / "origin.json").read_text(encoding="utf-8"))["collection"] == str(collection)
    with sqlite3.connect(staging / collection.name / "state.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 2
