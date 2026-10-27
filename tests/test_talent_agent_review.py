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


def test_v2_partial_merge_preserves_disjoint_pairs_and_invalidates_changed_context(monkeypatch):
    a,b,c,d,e = [SimpleNamespace(id=value, version='v1') for value in 'abcde']
    monkeypatch.setattr(service, 'comparison_fingerprint', lambda person: person.version)
    pairs = [dict(person_ids=list(ids), classification='same', confidence='high', reason='独立证据', evidence_version='ctx') for ids in ('ab','cd')]
    report = dict(format_version=2, report_id='r', groups={'Anna':dict(fingerprints={p.id:p.version for p in [a,b,c,d,e]},pairs=pairs)})
    evidence = [dict(person_ids=list(ids),evidence_version='ctx') for ids in ('ab','cd')]
    review = service.group_review(report,'Anna',[a,b,c,d,e],evidence=evidence)
    identities = service.identity_subgroups('abcde',evidence,review)
    assert [group['person_ids'] for group in identities['subgroups']] == [['a','b'],['c','d']]
    assert identities['standalone_ids'] == ['e'] and identities['counts']['unresolved_pairs'] == 10
    a.version = 'merged'
    review = service.group_review(report,'Anna',[a,c,d,e],evidence=evidence)
    assert [pair['person_ids'] for pair in review['pairs']] == [['c','d']]
    assert service.identity_subgroups('acde',evidence,review)['subgroups'][0]['person_ids'] == ['c','d']
    evidence[1]['evidence_version'] = 'shared-account-changed'
    assert not service.group_review(report,'Anna',[a,c,d,e],evidence=evidence)['pairs']


def test_overlapping_edges_conflicts_and_incomplete_cliques_never_force_partition():
    def suggestion(ids):
        return dict(person_ids=list(ids),classification='same',confidence='high',reason='合成证据')
    chain = dict(pairs=[suggestion('ab'),suggestion('bc')])
    result = service.identity_subgroups('abc',[],chain)
    assert not result['subgroups'] and len(result['ambiguous_pairs']) == 2
    full = dict(pairs=[*chain['pairs'],suggestion('ac')])
    assert len(service.identity_subgroups('abc',[],full)['subgroups']) == 1
    assert not service.identity_subgroups('abc',[dict(person_ids=['a','c'],identity_conflicts=['性别不同'])],full)['subgroups']
    assert not service.identity_subgroups('abc',[],full,{('a','c'):'different'})['subgroups']


def test_new_report_keeps_unjudged_pairs_unreviewed_and_rejects_blanket_default(tmp_path, monkeypatch):
    a,b,c = 'abc'
    source,decisions,target = [tmp_path/name for name in ('source.json','decisions.json','report.json')]
    source.write_text(json.dumps(dict(format_version=2,created_at='2026-10-27T12:00:00+08:00',groups=[dict(key='Anna',fingerprints={a:'1',b:'2',c:'3'},pairs=[
        dict(person_ids=[a,b],codes=['A','B'],evidence_version='v'),dict(person_ids=[a,c],codes=['A','C'],evidence_version='v')])])),encoding='utf-8')
    judgments = dict(reviewer='当前 Agent',scope_note='合成测试',pairs=[dict(index=[0,0],classification='same',confidence='high',reason='合成证据')])
    decisions.write_text(json.dumps(judgments),encoding='utf-8')
    build(source,decisions,target)
    monkeypatch.setattr(service,'REVIEW_PATH',target)
    report = service.load_report()
    assert report['format_version'] == 2 and len(report['groups']['Anna']['pairs']) == 1
    judgments['default'] = dict(classification='same',confidence='high',reason='错误默认')
    decisions.write_text(json.dumps(judgments),encoding='utf-8')
    import pytest
    with pytest.raises(ValueError,match='不能默认高置信度'):
        build(source,decisions,target)


def test_scan_checkpoint_publishes_partial_evidence_and_resumes_without_database(tmp_path,monkeypatch):
    import tools.export_talent_agent_review as scan
    calls = []
    pressure = dict(connections=40,active=0,idle_transactions=0,old_transactions=0)
    def first_page(engine,after,limit,on_pressure=None):
        calls.append(after)
        if after:
            raise scan.ScanPaused('合成负载保护',pressure)
        return ['a'],[],{},{}
    monkeypatch.setattr(scan,'read_page',first_page)
    monkeypatch.setattr(scan,'serialize_groups',lambda keys,*args: [dict(key=key,pairs=[],fingerprints={}) for key in keys])
    import pytest
    with pytest.raises(scan.ScanPaused):
        scan.export(tmp_path,interval=0,scan_engine=object())
    partial = json.loads((tmp_path/'input.json').read_text(encoding='utf-8'))
    assert not partial['complete'] and partial['group_count'] == 1
    assert json.loads((tmp_path/'paused.json').read_text(encoding='utf-8'))['pressure'] == pressure
    def remaining(engine,after,limit,on_pressure=None):
        calls.append(after)
        return (['b'],[],{},{}) if after == 'a' else ([],[],{},{})
    monkeypatch.setattr(scan,'read_page',remaining)
    completed = scan.export(tmp_path,interval=0,scan_engine=object())
    assert completed['complete'] and [group['key'] for group in completed['groups']] == ['a','b']
    assert calls == ['','a','a','b'] and not (tmp_path/'paused.json').exists()
