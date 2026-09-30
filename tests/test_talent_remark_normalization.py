"""仅使用虚构人才与 SQLite 隔离库，不连接生产数据库。"""
import json
from datetime import datetime

import pytest
from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, create_engine, update

from tools.talent_remark_rules import Languages, digest, extract, plan_person, split_values
from tools.normalize_talent_remarks import (PERSON, TABLES, atomic_json, apply_plan,
    expected_state, mutate, rollback, state, validate_record, VERSION, file_hash)


def language_catalog():
    return [{"id": "11111111-1111-1111-1111-111111111111", "label": "英语", "name_en": "English"},
            {"id": "22222222-2222-2222-2222-222222222222", "label": "阿拉伯语", "name_en": "Arabic"},
            {"id": "33333333-3333-3333-3333-333333333333", "label": "纳吉德阿拉伯语"}]


def person(note, **fields):
    return {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "full_name": "测试人才", "resource_code": "TEST-1", "remarks": note, **fields}


def planned(note, relations=None, **fields):
    return plan_person(person(note, **fields), relations or {}, Languages(language_catalog(), []), {"nationality": 100, "other_contact": 255})


def test_clear_values_and_placeholder_do_not_override_existing():
    result = planned("国籍：测试国\n民族：测试民族\n原表年龄：28\n最高学历：本科", nationality="未知")
    assert result["changes"]["ethnicity"] == "测试民族"
    assert result["changes"]["reported_age"] == 28
    assert result["changes"]["highest_education"] == "bachelor"
    assert "nationality" not in result["changes"]


@pytest.mark.parametrize("note", ["年龄：20-30", "出生日期：2020-99-99", "职业状态：可能在职", "性别：不详"])
def test_ambiguous_values_do_not_write(note):
    assert not planned(note)["changes"]


def test_multiple_source_conflict_and_multiline_experience():
    r = planned("国籍：甲国\n国籍：乙国\n标注项目经验：第一项目\n第二项目\n来源：问卷")
    assert "nationality" not in r["changes"]
    assert r["changes"]["annotation_experience"] == "第一项目\n第二项目"


def test_identity_mismatch_blocks_section():
    r = planned("姓名：另一人才\n国籍：甲国\n邮箱：another@example.test")
    assert not r["changes"]
    assert any(x["reason"] == "当前来源段姓名与档案不一致" for x in r["decisions"])


def test_long_text_preserved_without_truncation():
    r = planned("国籍：" + "字" * 101)
    assert not r["changes"]
    assert any("超出" in d["reason"] for d in r["decisions"])


def test_prices_test_status_and_explicit_preservation_never_become_scores():
    r = planned("单价：USD 0.05/word\n是否已做测试：已回\n原表第5列分数：9（仅保留）\n原表第4列意愿值：是（未转换）")
    assert not r["changes"] and not r["adds"]


def test_missing_wechat_account_placeholder_never_fills_account():
    r = planned("原表所在微信：暂时找不到")
    assert not r["changes"]
    assert any(d["status"] == "pending" for d in r["decisions"])


def test_contacts_fill_dedupe_and_only_redact_saved_values():
    r = planned("邮箱：One@example.test、two@example.test\n邮箱：One@example.test\n微信号：synthetic_wechat", primary_email="existing@example.test", wechat="occupied")
    assert r["changes"]["secondary_email"] == "one@example.test"
    assert r["changes"]["other_contact"] == "two@example.test"
    assert "One@example.test" not in r["changes"]["remarks"]
    assert "two@example.test" not in r["changes"]["remarks"]
    assert "synthetic_wechat" in r["changes"]["remarks"]
    assert "wechat" not in r["changes"]


def test_excess_contact_length_remains_in_notes():
    r = planned("邮箱：third@example.test", primary_email="one@example.test", secondary_email="two@example.test", other_contact="占用")
    assert not r["changes"]


def test_json_keys_and_history_not_assigned_to_person():
    raw = {"batch": "test", "sources": [{"客户名称": "测试人才", "邮箱": "one@example.test", "添加人账号": "operator@example.test"}], "incremental_updates": [{"previous_values": {"邮箱": "old@example.test"}}]}
    r = planned(json.dumps(raw, ensure_ascii=False))
    assert r["changes"]["primary_email"] == "one@example.test"
    after = json.loads(r["changes"]["remarks"])
    assert after["sources"][0]["添加人账号"] == "operator@example.test"
    assert after["incremental_updates"] == raw["incremental_updates"]
    assert after["sources"][0]["邮箱"] == "（已转入联系字段）"


def test_actual_history_conflict_blocks_stale_root_field():
    raw = {"sources": [{"客户名称": "测试人才", "邮箱": "old@example.test"}], "incremental_updates": [{"source_changes": [{"previous_values": {"邮箱": "old@example.test"}, "values": {"邮箱": "new@example.test"}}]}]}
    r = planned(json.dumps(raw, ensure_ascii=False))
    assert not r["changes"]
    assert any("旧快照" in d["reason"] for d in r["decisions"])


def test_json_sources_wrong_name_not_mapped():
    r = planned(json.dumps({"sources": [{"客户名称": "其他人", "邮箱": "other@example.test"}]}))
    assert not r["changes"]


def test_numeric_json_phone_is_redacted_but_row_number_is_preserved():
    raw = {"sources": [{"客户名称": "测试人才", "手机": 12025550123, "row": 12025550123}]}
    r = planned(json.dumps(raw, ensure_ascii=False), primary_phone="12025550123")
    result = json.loads(r["changes"]["remarks"])
    assert result["sources"][0]["手机"] == "（已转入联系字段）"
    assert result["sources"][0]["row"] == 12025550123


def test_email_adjacent_chinese_note_text_is_redacted():
    r = planned("邮箱：one@example.test已联系", primary_email="one@example.test")
    assert "one@example.test" not in r["changes"]["remarks"]
    assert "已联系" in r["changes"]["remarks"]


def test_row_provenance_not_part_of_identity_or_value():
    r = planned("译员名字：测试人才【第12行】\n国籍：测试国【原表第12,13行】\n邮箱：one@example.test【第12行】")
    assert r["changes"]["nationality"] == "测试国"
    assert r["changes"]["primary_email"] == "one@example.test"
    assert "【第12行】" in r["changes"]["remarks"]
    assert r["decisions"][0]["row_source"] == "【第12行】"


def test_task_decorated_source_name_requires_exact_existing_name_and_lineage():
    raw = {"original_names": "英语测试人才质检(测试地区)", "sources": [{"客户名称": "英语测试人才质检(测试地区)", "邮箱": "one@example.test", "地址": "公司地址"}]}
    r = planned(json.dumps(raw, ensure_ascii=False))
    assert r["changes"]["primary_email"] == "one@example.test"
    assert "residence_address" not in r["changes"]
    raw["original_names"] = "英语另一人才质检(测试地区)"
    assert not planned(json.dumps(raw, ensure_ascii=False))["changes"]


def test_education_conflicting_highest_level_does_not_misassign_school():
    r = planned("最高学历：硕士\n毕业院校：测试大学", highest_education="bachelor")
    assert not r["adds"]


def test_equivalent_certificate_names_not_duplicated():
    r = planned("证书及等级：英语六级", {"resource_certificate": [{"name": "CET-6"}]})
    assert not r["adds"]


def test_languages_explicit_multiple_native_and_ambiguity():
    r = planned("母语：阿语、纳吉德阿拉伯语、蒙古语？\n第一外语：English")
    skills = [x["values"] for x in r["adds"]]
    assert len(skills) == 3
    assert sum(x["role"] == "native" for x in skills) == 2
    assert any(x["role"] == "foreign" and x["priority"] == 1 for x in skills)
    assert any(d["normalized"] == "蒙古语？" and d["status"] == "pending" for d in r["decisions"])
    assert split_values("英语（English）、German (Germany)/法语") == ["英语（English）", "German (Germany)", "法语"]


def test_english_alias_without_catalog_english_metadata():
    language = Languages([{ "id": "id", "label": "英语"}], [])
    assert language.resolve("English") == "id"


def test_no_language_role_or_capability_inference():
    r = planned("语种：英语\n语言对：中英\n项目评价：很好")
    assert not r["adds"] and not r["changes"]


def test_existing_language_role_conflict_is_pending():
    relations = {"resource_language_skill": [{"id": "x", "language_id": language_catalog()[0]["id"], "role": "foreign"}]}
    r = planned("母语：英语", relations)
    assert not r["adds"]
    assert any(d["reason"] == "同语种语言角色冲突" for d in r["decisions"])


def test_existing_dialect_language_fills_proficiency_without_changing_role():
    old = {"id": "skill", "language_id": language_catalog()[0]["id"], "role": "native", "proficiency": None}
    r = planned("中国方言/民族语言：英语\n方言熟练程度：非常熟练（从小说到大）", {"resource_language_skill": [old]})
    assert not r["adds"]
    assert r["updates"] == [{"table": "resource_language_skill", "id": "skill", "changes": {"proficiency": "very_familiar"}}]


def test_proficiency_different_source_row_does_not_attach():
    old = {"id": "skill", "language_id": language_catalog()[0]["id"], "role": "dialect_ethnic", "proficiency": None}
    r = planned("中国方言/民族语言：英语【第1行】\n方言熟练程度：非常熟练（从小说到大）【第2行】", {"resource_language_skill": [old]})
    assert not r["updates"]


def test_education_create_and_certificate_dedupe():
    r = planned("最高学历：本科\n毕业院校：测试大学\n所学专业：测试专业\n证书及等级：英语六级、英语六级")
    assert len([x for x in r["adds"] if x["table"] == "resource_education_experience"]) == 1
    assert len([x for x in r["adds"] if x["table"] == "resource_certificate"]) == 1
    validate_record(r)


def test_education_only_fills_matching_row_and_protects_nonempty():
    old = {"id": "edu", "education_level": "bachelor", "institution": "测试大学", "major": None, "sort_order": 0}
    r = planned("最高学历：本科\n毕业院校：测试大学\n所学专业：测试专业", {"resource_education_experience": [old]}, highest_education="bachelor")
    assert r["updates"] == [{"table": "resource_education_experience", "id": "edu", "changes": {"major": "测试专业"}}]
    r = planned("最高学历：本科\n毕业院校：其他大学\n所学专业：测试专业", {"resource_education_experience": [old]}, highest_education="bachelor")
    assert not r["adds"] and not r["updates"]


@pytest.fixture
def isolated(tmp_path):
    engine = create_engine("sqlite://")
    meta = MetaData()
    tables = {}
    tables[PERSON] = Table(PERSON, meta, Column("id", String, primary_key=True), Column("full_name", String), Column("resource_code", String), Column("remarks", String), Column("nationality", String), Column("primary_email", String), Column("updated_at", DateTime))
    for name in TABLES:
        if name == PERSON: continue
        if name == "interpretation_language": columns = [Column("id", String, primary_key=True), Column("label", String)]
        elif name == "interpretation_language_alias": columns = [Column("id", String, primary_key=True), Column("language_id", String), Column("alias", String)]
        elif name.endswith("_profile"): columns = [Column("person_id", String, primary_key=True), Column("remarks", String)]
        elif name == "resource_language_skill": columns = [Column("id", String, primary_key=True), Column("person_id", String), Column("language_id", String), Column("role", String), Column("priority", Integer), Column("sort_order", Integer), Column("proficiency", String), Column("remarks", String)]
        elif name == "resource_certificate": columns = [Column("id", String, primary_key=True), Column("person_id", String), Column("certificate_type", String), Column("name", String), Column("material_received", Boolean), Column("sort_order", Integer), Column("remarks", String)]
        elif name == "resource_education_experience": columns = [Column("id", String, primary_key=True), Column("person_id", String), Column("education_level", String), Column("institution", String), Column("major", String), Column("sort_order", Integer)]
        else: columns = [Column("id", String, primary_key=True), Column("person_id", String)]
        tables[name] = Table(name, meta, *columns)
    meta.create_all(engine)
    with engine.begin() as c:
        c.execute(tables[PERSON].insert().values(**person("国籍：测试国", nationality=None, primary_email=None, updated_at=datetime(2020, 1, 1))))
        c.execute(tables["resource_annotation_profile"].insert().values(person_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", remarks="既有专业档案"))
    with engine.connect() as c: before = state(c, tables, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    r = plan_person(before["person"], before["relations"], Languages([], []), {})
    plan = {"version": VERSION, "records": [r], "catalog_sha256": digest({"interpretation_language": [], "interpretation_language_alias": []})}
    atomic_json(tmp_path / "plan.json", plan)
    return engine, tables, tmp_path, plan


def test_apply_idempotency_and_rollback(isolated):
    engine, tables, path, plan = isolated
    ledger = apply_plan(engine, tables, path, plan)
    assert ledger["records"][plan["records"][0]["id"]]["status"] == "committed"
    with engine.connect() as c: after = state(c, tables, plan["records"][0]["id"])
    assert after["person"]["nationality"] == "测试国"
    apply_plan(engine, tables, path, plan)
    with engine.connect() as c: assert state(c, tables, plan["records"][0]["id"]) == after
    rollback(engine, tables, path, plan)
    with engine.connect() as c: assert state(c, tables, plan["records"][0]["id"]) == plan["records"][0]["before"]


def test_concurrent_edit_blocks_apply(isolated):
    engine, tables, path, plan = isolated
    with engine.begin() as c: c.execute(update(tables[PERSON]).values(nationality="并发填写"))
    ledger = apply_plan(engine, tables, path, plan)
    assert ledger["records"][plan["records"][0]["id"]]["status"] == "blocked_concurrent"
    with engine.connect() as c: assert state(c, tables, plan["records"][0]["id"])["person"]["nationality"] == "并发填写"


def test_later_edit_blocks_rollback(isolated):
    engine, tables, path, plan = isolated
    apply_plan(engine, tables, path, plan)
    with engine.begin() as c: c.execute(update(tables[PERSON]).values(nationality="后续编辑"))
    rollback(engine, tables, path, plan)
    ledger = json.loads((path / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["records"][plan["records"][0]["id"]]["rollback_status"] == "blocked_later_edit"


def test_transaction_failure_does_not_leave_partial_write(isolated, monkeypatch):
    engine, tables, path, plan = isolated
    import tools.normalize_talent_remarks as tool
    original = tool.mutate
    def fail(c, t, r):
        original(c, t, r)
        raise RuntimeError("模拟事务失败")
    monkeypatch.setattr(tool, "mutate", fail)
    ledger = apply_plan(engine, tables, path, plan)
    assert ledger["records"][plan["records"][0]["id"]]["status"] == "failed"
    with engine.connect() as c: assert state(c, tables, plan["records"][0]["id"]) == plan["records"][0]["before"]


def test_committed_prepared_journal_recovers(isolated):
    engine, tables, path, plan = isolated
    r = plan["records"][0]
    with engine.begin() as c:
        mutate(c, tables, r)
        after = state(c, tables, r["id"])
    atomic_json(path / "ledger.json", {"plan_sha256": file_hash(path / "plan.json"), "records": {r["id"]: {"status": "prepared", "before": r["before"], "after": after}}, "batches": []})
    ledger = apply_plan(engine, tables, path, plan)
    assert ledger["records"][r["id"]]["status"] == "committed"
    with engine.connect() as c: assert state(c, tables, r["id"]) == after


def test_unplanned_business_change_fails_verification(isolated):
    engine, tables, path, plan = isolated
    r = plan["records"][0]
    with engine.begin() as c:
        mutate(c, tables, r)
        c.execute(update(tables[PERSON]).values(full_name="其他人"))
        assert not expected_state(r, state(c, tables, r["id"]))


def test_tampered_nonempty_plan_is_rejected():
    r = planned("国籍：测试国", nationality="已有国籍")
    r["changes"]["nationality"] = "覆盖"
    with pytest.raises(ValueError, match="覆盖非空"): validate_record(r)


def test_association_creation_and_rollback_are_complete(isolated):
    engine, tables, path, plan = isolated
    r = plan["records"][0]
    extra = planned("母语：英语\n证书及等级：英语六级")
    r["adds"] = extra["adds"]
    atomic_json(path / "plan.json", plan)
    apply_plan(engine, tables, path, plan)
    with engine.connect() as c:
        after = state(c, tables, r["id"])
        assert len(after["relations"]["resource_language_skill"]) == 1
        assert len(after["relations"]["resource_certificate"]) == 1
        assert expected_state(r, after)
    rollback(engine, tables, path, plan)
    with engine.connect() as c: assert state(c, tables, r["id"]) == r["before"]


def test_build_plan_preserves_counts_and_no_personal_data_in_stdout(isolated, capsys):
    from tools.normalize_talent_remarks import build_plan
    engine, tables, path, plan = isolated
    snapshot = {"database": {}, "git_commit": "test", "limits": {}, "tables": {name: [] for name in TABLES}}
    before = plan["records"][0]["before"]
    snapshot["tables"][PERSON] = [before["person"]]
    atomic_json(path / "snapshot.json", snapshot)
    build_plan(path)
    output = capsys.readouterr().out
    assert "测试人才" not in output and "测试国" not in output
    actual = json.loads((path / "plan.json").read_text(encoding="utf-8"))
    assert actual["summary"]["fields"] == {"nationality": 1}
