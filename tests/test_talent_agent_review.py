"""Agent 建议只读、过期失效及报告保守分流的隔离验收。"""
import json
from types import SimpleNamespace
from uuid import uuid4

import talent_agent_review_service as service
from tools.build_talent_agent_review_report import build


def test_group_changes_invalidate_entire_suggestion(monkeypatch):
    a, b, c = [SimpleNamespace(id=uuid4(), version="v1") for _ in range(3)]
    monkeypatch.setattr(service, "comparison_fingerprint", lambda person: person.version)
    report = {"created_at": "2026-10-10T15:00:00+08:00", "reviewer": "当前 Agent", "groups": {
        "测试姓名": {"fingerprints": {str(a.id): "v1", str(b.id): "v1"}, "pairs": [
            {"person_ids": [str(a.id), str(b.id)], "classification": "same", "confidence": "high", "reason": "合成测试证据"}]}}}
    assert service.group_review(report, "测试姓名", [a, b])["buckets"] == ["high_same"]
    assert service.group_review(report, "测试姓名", [a, b, c])["state"] == "stale"
    a.version = "v2"
    outdated = service.group_review(report, "测试姓名", [a, b])
    assert outdated["state"] == "stale" and not outdated["pairs"]


def test_missing_or_malformed_report_does_not_break_manual_workbench(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    monkeypatch.setattr(service, "REVIEW_PATH", path)
    assert service.load_report() == {}
    path.write_text("{broken", encoding="utf-8")
    assert service.load_report() == {}
    path.write_text(json.dumps({"format_version": 99}), encoding="utf-8")
    assert service.load_report() == {}


def test_unreviewed_pairs_are_not_inferred_transitively(tmp_path, monkeypatch):
    a, b, c = [str(uuid4()) for _ in range(3)]
    source, decisions, target = [tmp_path / filename for filename in ("input.json", "decisions.json", "latest.json")]
    source.write_text(json.dumps({"created_at": "2026-10-10T15:00:00+08:00", "groups": [
        {"key": "合成人员", "fingerprints": {a: "a", b: "b", c: "c"}, "pairs": [
            {"person_ids": [a, b], "codes": ["QA1", "QA2"]},
            {"person_ids": [b, c], "codes": ["QA2", "QA3"]},
            {"person_ids": [a, c], "codes": ["QA1", "QA3"]}]}]}), encoding="utf-8")
    decisions.write_text(json.dumps({"reviewer": "当前 Agent", "scope_note": "合成测试", "default": {
        "classification": "uncertain", "confidence": "low", "reason": "缺少依据"}, "pairs": [
            {"index": [0, 0], "classification": "same", "confidence": "high", "reason": "A/B 的独立证据"},
            {"index": [0, 1], "classification": "same", "confidence": "high", "reason": "B/C 的独立证据"}]}), encoding="utf-8")
    build(source, decisions, target)
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["groups"][0]["pairs"][2]["classification"] == "uncertain"
    assert result["created_at"].endswith("+08:00")
    monkeypatch.setattr(service, "REVIEW_PATH", target)
    assert len(service.load_report()["groups"]["合成人员"]["pairs"]) == 3


def test_unsupported_judgment_is_ignored(tmp_path, monkeypatch):
    a, b = str(uuid4()), str(uuid4())
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"format_version": 1, "groups": [{"key": "合成人员", "fingerprints": {a: "a", b: "b"},
        "pairs": [{"person_ids": [a, b], "classification": "auto_delete", "confidence": "high", "reason": "不得执行"}]}]}), encoding="utf-8")
    monkeypatch.setattr(service, "REVIEW_PATH", path)
    assert service.load_report()["groups"]["合成人员"]["pairs"] == []
