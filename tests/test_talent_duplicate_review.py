"""核重真实 PostgreSQL 回归；只能由临时独立实例运行，不连接业务数据库。"""
import copy
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

import main  # 注册全部模型，不运行应用 startup/lifespan。
from business_time import business_now
from models import Base
from resource_models import ResourcePerson, ResourceLanguageSkill, ResourceCertificate, ResourcePersonAttachment, ResourceCapability
from resource_schemas import ResourcePersonCreate
from resource_service import create_talent, get_talent, get_talents, count_talents, update_talent_status, find_duplicate_talents
from talent_duplicate_models import TalentDuplicateOperation
from talent_duplicate_schemas import DuplicateReviewRequest, DuplicateReviewCommit
from talent_duplicate_service import (commit, undo, preview, groups, group_detail, name_key,
    contact_identifiers, detail_inheritance, full_snapshot, digest, review_ready)

ACTOR = SimpleNamespace(id=uuid4(), username="qa", full_name="核重测试员")


def test_slow_worker_preserves_audit_and_retries_idempotently(db):
    from models import AppUser, Role, UserRole
    from tools.run_talent_name_merge_slow import candidate_keys, propose, execute_one
    from talent_retention_service import original_data
    actor = AppUser(id=uuid4(), username='slow_qa', password_hash='synthetic', is_active=True)
    role = Role(id=uuid4(), role_name='超级管理员')
    db.add_all([actor, role]); db.flush()
    db.add(UserRole(id=uuid4(), user_id=actor.id, role_id=role.id)); db.commit()
    a, b = person(db), person(db, remarks='来源原文\n第二行')
    assert candidate_keys(db) == ['王测试']
    request = propose(db, '王测试')
    db.rollback()
    with Session(db.get_bind()) as worker:
        result = execute_one(worker, request, 'slow_qa')
    with Session(db.get_bind()) as worker:
        assert execute_one(worker, request, 'slow_qa')['id'] == result['id']
    assert db.query(TalentDuplicateOperation).count() == 1
    archived = get_talent(db, b.id)
    assert archived.archived_into_id == a.id
    frozen = original_data(db, UUID(result['id']), b.id)
    assert frozen['integrity_recorded']
    assert frozen['snapshot']['person']['remarks'] == '来源原文\n第二行'


def test_slow_worker_yields_to_online_write_lock_and_rejects_non_admin(db):
    from models import AppUser, Role, UserRole
    from tools.run_talent_name_merge_slow import propose, execute_one, PauseTask
    actor = AppUser(id=uuid4(), username='slow_lock_qa', password_hash='synthetic', is_active=True)
    ordinary = AppUser(id=uuid4(), username='ordinary_qa', password_hash='synthetic', is_active=True)
    role = Role(id=uuid4(), role_name='超级管理员')
    db.add_all([actor, ordinary, role]); db.flush()
    db.add(UserRole(id=uuid4(), user_id=actor.id, role_id=role.id)); db.commit()
    a, b = person(db), person(db)
    request = propose(db, '王测试'); db.rollback()
    with Session(db.get_bind()) as worker:
        with pytest.raises(PauseTask, match='有效超级管理员'):
            execute_one(worker, request, 'ordinary_qa')
    with Session(db.get_bind()) as online:
        online.execute(text('SELECT pg_advisory_xact_lock(724092401)'))
        with Session(db.get_bind()) as worker:
            with pytest.raises(PauseTask, match='本任务让行'):
                execute_one(worker, request, 'slow_lock_qa')
        online.rollback()
    assert db.query(TalentDuplicateOperation).count() == 0
    assert not get_talent(db, b.id).archived_into_id


def test_two_worker_queue_merges_once_and_resumes_out_of_order(db, tmp_path):
    from models import AppUser, Role, UserRole
    from tools.run_talent_name_merge_slow import run_queue, candidate_keys
    actor = AppUser(id=uuid4(), username='two_worker_qa', password_hash='synthetic', is_active=True)
    role = Role(id=uuid4(), role_name='超级管理员')
    db.add_all([actor, role]); db.flush()
    db.add(UserRole(id=uuid4(), user_id=actor.id, role_id=role.id)); db.commit()
    for name in ['甲测试', '乙测试', '丙测试', '丁测试']:
        person(db, name); person(db, name)
    keys = candidate_keys(db); db.rollback()
    state = {'keys': keys, 'requests': {}, 'results': [], 'index': 0, 'operator': actor.username,
             'status': 'running', 'started_at': '2026-10-13T12:00:00+08:00', 'workers': 2,
             'interval_seconds': 0.2}
    path = tmp_path/'status.json'
    run_queue(db.get_bind(), state, path, tmp_path/'STOP', actor.username, 2, 0.2)
    assert state['index'] == 4 and len(state['processed_keys']) == 4
    assert {result['worker_id'] for result in state['results']} == {1, 2}
    assert len({result['id'] for result in state['results']}) == 4
    assert db.query(TalentDuplicateOperation).count() == 4
    # 前缀未追上但乱序完成项已记录时，续跑仍不得重复提交或遗漏。
    state['index'] = 0
    run_queue(db.get_bind(), state, path, tmp_path/'STOP', actor.username, 2, 0.2)
    assert db.query(TalentDuplicateOperation).count() == 4


def test_two_workers_stop_before_commit_on_failure(tmp_path, monkeypatch):
    from tools import run_talent_name_merge_slow as runner
    from contextlib import nullcontext
    monkeypatch.setattr(runner, 'Session', lambda _: nullcontext(SimpleNamespace(execute=lambda _: None, rollback=lambda: None)))
    monkeypatch.setattr(runner, 'read_pressure', lambda _: {'connections': 0, 'active': 0, 'idle_transactions': 0, 'old_transactions': 0})
    def failure(*args):
        raise runner.PauseTask('模拟线上负载升高')
    monkeypatch.setattr(runner, 'propose', failure)
    commits = []
    monkeypatch.setattr(runner, 'execute_one', lambda *args: commits.append(args))
    state = {'keys': ['甲测试', '乙测试'], 'index': 0, 'requests': {}, 'results': []}
    with pytest.raises(runner.PauseTask, match='模拟线上负载升高'):
        runner.run_queue(None, state, tmp_path/'status.json', tmp_path/'STOP', 'qa', 2, 0.1)
    assert not commits and state['index'] == 0
    assert state['failure_details']['stage'] == '预览'
    assert state['pressure_checked_at'].endswith('+08:00')


def test_slow_worker_error_diagnostics_do_not_expose_sql_parameters():
    from sqlalchemy.exc import OperationalError
    from tools.run_talent_name_merge_slow import failure_details, pause_reason
    original = SimpleNamespace(pgcode='57014')
    error = OperationalError('SELECT private_contact FROM resource_person',
                             {'private_contact': 'secret@example.test'}, original)
    assert failure_details(error) == {'type': 'OperationalError', 'sqlstate': '57014'}
    reason = pause_reason(error)
    assert '数据库查询超时' in reason and '57014' in reason
    assert 'private_contact' not in reason and 'secret@example.test' not in reason


@pytest.mark.parametrize('pressure', [
    {'connections': 40, 'active': 0, 'idle_transactions': 0, 'old_transactions': 0},
    {'connections': 15, 'active': 5, 'idle_transactions': 0, 'old_transactions': 0},
    {'connections': 15, 'active': 0, 'idle_transactions': 3, 'old_transactions': 0},
    {'connections': 15, 'active': 0, 'idle_transactions': 0, 'old_transactions': 1},
])
def test_slow_worker_pauses_under_database_pressure(pressure):
    from tools.run_talent_name_merge_slow import assert_quiet, PauseTask
    with pytest.raises(PauseTask, match='数据库负载升高'):
        assert_quiet(pressure)


@pytest.fixture(autouse=True)
def isolated_retention_files(tmp_path, monkeypatch):
    monkeypatch.setenv("TALENT_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("TALENT_REVIEW_ARCHIVE_DIR", str(tmp_path / "retained"))


@pytest.fixture
def db():
    url = os.environ.get("TALENT_DUPLICATE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("使用 tools/run_talent_duplicate_review_tests.py 创建独立测试实例")
    parsed = make_url(url)
    assert parsed.host == "127.0.0.1" and parsed.username == "review_test" and parsed.database == "postgres"
    schema = "review_" + uuid4().hex
    bootstrap = create_engine(url)
    with bootstrap.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public"))
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-c search_path={schema},public -c timezone=Asia/Hong_Kong"})
    with engine.begin() as conn:
        conn.execute(text("CREATE SEQUENCE chat_message_sequence"))
    Base.metadata.create_all(engine)
    migration = (Path(__file__).resolve().parents[1] / "data/migrations/20261009_talent_duplicate_review.sql").read_text(encoding="utf-8")
    with engine.connect() as conn:
        conn.execute(text(migration))
        conn.commit()
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        # 精确生成的独立 schema，bootstrap 只能连接该临时测试实例。
        with bootstrap.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        bootstrap.dispose()


def person(db, name="王测试", **values):
    row = ResourcePerson(id=uuid4(), resource_code="QA" + uuid4().hex[:12], full_name=name,
                         status="standby", created_at=business_now(), updated_at=business_now(), **values)
    db.add(row)
    db.commit()
    return get_talent(db, row.id)


def process(db, ids, target=None, action="keep", decisions=None, note=""):
    request = DuplicateReviewRequest(action=action, person_ids=ids, target_id=target, decisions=decisions or {}, note=note)
    result = preview(db, request)
    assert not result["conflicts"], result["conflicts"]
    payload = DuplicateReviewCommit(**request.model_dump(), preview_token=result["preview_token"], idempotency_key=str(uuid4()))
    return commit(db, payload, ACTOR), payload


def test_group_order_search_counts_and_audit_filters(db):
    from routers.talents import _field_filters
    for _ in range(2):
        person(db, "甲同名")
    person(db, "乙同名")
    person(db, "乙同名", residence_address="北京")
    person(db, "丙同名", primary_email="match@example.org")
    person(db, "丙同名", secondary_email="match@example.org")
    result = groups(db, status="all", contacts_visible=True)
    assert [item["key"] for item in result["items"]] == ["丙同名", "乙同名", "甲同名"]
    searched = groups(db, keyword="乙", status="all")
    assert searched["total"] == 1 and searched["counts"]["pending"] == 1
    row = person(db, "操作筛选", operator_name="核重操作员", operated_at=business_now())
    matched = get_talents(db, field_filters=_field_filters('{"operator_name":{"value":"核重操作","op":"contains"}}'))
    assert [item.id for item in matched] == [row.id]
    assert count_talents(db, field_filters={"operator_name": {"value": "不存在", "op": "contains"}}) == 0
    today = business_now().date().isoformat()
    dated = get_talents(db, field_filters=_field_filters('{"operated_at":{"op":"between","from":"' + today + '","to":"' + today + '"}}'))
    assert [item.id for item in dated] == [row.id]


def test_agent_review_filter_privacy_and_group_version(db, tmp_path, monkeypatch):
    import json
    import talent_agent_review_service as agent
    from talent_duplicate_service import comparison_fingerprint
    a, b, c = person(db), person(db), person(db)
    output = tmp_path / "latest.json"
    report = {"format_version": 1, "created_at": "2026-10-10T15:00:00+08:00", "reviewer": "当前 Agent", "groups": [{
        "key": "王测试", "fingerprints": {str(p.id): comparison_fingerprint(p) for p in [a, b, c]}, "pairs": [
            {"person_ids": [str(a.id), str(b.id)], "classification": "same", "confidence": "high", "reason": "合成测试的独立证据"},
            {"person_ids": [str(a.id), str(c.id)], "classification": "uncertain", "confidence": "low", "reason": "信息不足"}]}]}
    output.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(agent, "REVIEW_PATH", output)
    assert groups(db, contacts_visible=True, agent_bucket="high_same")["total"] == 1
    detail = group_detail(db, "王测试", contacts_visible=True)
    assert len(detail["agent_review"]["pairs"]) == 2
    assert detail["agent_review"]["pairs"][0]["person_ids"] == [str(a.id), str(b.id)]
    assert "agent_review" not in group_detail(db, "王测试", contacts_visible=False)
    assert "agent_summary" not in groups(db, contacts_visible=False)
    process(db, [a.id, b.id], action="different")
    assert groups(db, contacts_visible=True, agent_bucket="high_same")["total"] == 0
    assert len(group_detail(db, "王测试", contacts_visible=True)["agent_review"]["pairs"]) == 1
    c.residence_address = "上海"
    db.commit()
    assert group_detail(db, "王测试", contacts_visible=True)["agent_review"]["state"] == "stale"
    assert groups(db, contacts_visible=True, agent_bucket="high_same")["total"] == 0
    assert groups(db, contacts_visible=True, agent_bucket="unreviewed")["total"] == 1


def test_migration_is_repeatable(db):
    a, b = person(db), person(db)
    script = (Path(__file__).resolve().parents[1] / "data/migrations/20261009_talent_duplicate_review.sql").read_text(encoding="utf-8")
    db.rollback()
    with db.get_bind().connect() as connection:
        connection.execute(text(script))
        connection.commit()
    assert groups(db, status="all")["total"] == 1
    assert get_talent(db, a.id).name_duplicate and get_talent(db, b.id).name_duplicate


def test_final_preview_matches_normal_form_name_and_text_normalization(db):
    a = person(db, "王测试（甲）", chinese_name="王测试")
    b = person(db, "王测试（乙）", chinese_name="王测试", residence_address="上海")
    decisions = {"full_name": {"person_id": str(b.id)}, "residence_address": {"value": "  北京  "}}
    request = DuplicateReviewRequest(action="merge", person_ids=[a.id, b.id], target_id=a.id, decisions=decisions)
    proposed = preview(db, request)
    assert proposed["final_values"]["full_name"] == "王测试"
    assert proposed["final_values"]["residence_address"] == "北京"
    process(db, [a.id, b.id], a.id, "merge", decisions)
    retained = get_talent(db, a.id)
    assert retained.full_name == proposed["final_values"]["full_name"]
    assert retained.residence_address == proposed["final_values"]["residence_address"]


def test_name_rules_and_all_contacts():
    assert name_key("　王测试（英文名） (其他名字)　") == "王测试"
    assert name_key(" JOHN\n  SMITH ") == "john smith"
    assert name_key("(仅括号)") == "(仅括号)"
    row = SimpleNamespace(primary_email=" a@sample.org; B@sample.org ", secondary_email="CV中没有提供",
                          other_contact="电话 +86 138-0000-0000; c@sample.org", wechat="shared", wechat_accounts=["公司账号"])
    found = contact_identifiers(row)
    assert found["email"] == {"a@sample.org", "b@sample.org", "c@sample.org"}
    assert found["phone"] == {"8613800000000"} and found["wechat"] == {"shared"}


def test_grouping_cross_category_and_nontransitive_pairs(db):
    a = person(db, "王测试（英文名）", primary_email="shared@example.org", gender="男")
    b = person(db, " 王测试 ", secondary_email="shared@example.org", wechat="same_wechat")
    c = person(db, "王测试", wechat="same_wechat", gender="女")
    db.add_all([ResourceCapability(id=uuid4(), person_id=a.id, capability_type="annotation", status="active", source="manual"),
                ResourceCapability(id=uuid4(), person_id=b.id, capability_type="written_translation", status="active", source="manual")])
    db.commit()
    result = groups(db, contacts_visible=True)
    assert result["total"] == 1 and result["items"][0]["count"] == 3
    detail = group_detail(db, "王测试", contacts_visible=True)
    assert len(detail["pairs"]) == 3
    conflict_pair = next(pair for pair in detail["pairs"] if set(pair["person_ids"]) == {str(a.id), str(c.id)})
    assert conflict_pair["identity_conflicts"] == ["性别不同"]
    assert not conflict_pair["contact_matches"]
    process(db, [a.id, b.id], a.id)
    assert count_talents(db) == 2 and get_talent(db, c.id).archived_into_id is None
    assert group_detail(db, "王测试", contacts_visible=True)["members"]


def test_missing_fields_are_complements_and_company_account_not_identity(db):
    a = person(db, primary_phone="13800000000", wechat_accounts=["公司账号"])
    b = person(db, gender="女", wechat_accounts=["公司账号"])
    detail = group_detail(db, "王测试", True)
    assert not detail["pairs"][0]["contact_matches"]
    assert next(field for field in detail["fields"] if field["key"] == "primary_phone")["state"] == "complement"
    assert detail["pairs"][0]["complement_count"] > 0


def test_keep_archive_search_and_undo(db):
    a = person(db, primary_email="a@example.org")
    b = person(db, secondary_email="second@example.org", remarks="原文保留")
    proposed = preview(db, DuplicateReviewRequest(action="keep", person_ids=[a.id, b.id], target_id=a.id))
    retained_email = next(field for field in proposed["fields"] if field["key"] == "primary_email")
    assert retained_email["value"] == "a@example.org"
    assert retained_email["options"][0]["person_id"] == str(a.id)
    assert "second@example.org" in str(proposed["omitted_fields"])
    before = full_snapshot(db, [a.id, b.id])
    result, payload = process(db, [a.id, b.id], a.id)
    assert get_talent(db, b.id).archived_into_id == a.id
    assert get_talent(db, a.id).remarks is None
    assert count_talents(db) == 1
    assert [row.id for row in get_talents(db, keyword="second@example.org")] == [a.id]
    assert detail_inheritance(db, a.id, True)["inherited_contacts"][0]["value"] == "second@example.org"
    assert not detail_inheritance(db, a.id, False)["inherited_contacts"]
    assert commit(db, payload, ACTOR)["id"] == result["id"]
    with pytest.raises(HTTPException) as caught:
        update_talent_status(db, b.id, "active")
    assert caught.value.status_code == 409
    db.rollback()
    undo(db, UUID(result["id"]), ACTOR)
    assert count_talents(db) == 2
    assert digest(full_snapshot(db, [a.id, b.id])) == digest(before)


def test_merge_conflicts_complements_notes_and_sources(db):
    a = person(db, gender="男", primary_email="a@example.org", remarks="原项目评价")
    b = person(db, gender="女", secondary_email="b@example.org", remarks="第二来源评价", residence_address="北京")
    request = DuplicateReviewRequest(action="merge", person_ids=[a.id, b.id], target_id=a.id)
    conflict = preview(db, request)
    assert any(item["key"] == "gender" for item in conflict["conflicts"])
    result, _ = process(db, [a.id, b.id], a.id, "merge", {"gender": {"person_id": str(a.id)}})
    merged = get_talent(db, a.id)
    assert merged.gender == "男" and merged.residence_address == "北京" and merged.secondary_email == "b@example.org"
    assert "原项目评价" in merged.remarks and "第二来源评价" in merged.remarks and "来源" in merged.remarks
    assert get_talent(db, b.id).gender == "女" and get_talent(db, b.id).remarks == "第二来源评价"
    undo(db, UUID(result["id"]), ACTOR)
    assert get_talent(db, a.id).remarks == "原项目评价" and get_talent(db, a.id).residence_address is None


def test_individual_decisions_invalidated_on_identity_change(db):
    a, b = person(db), person(db, gender="女")
    result, _ = process(db, [a.id, b.id], action="different")
    assert groups(db, status="different")["total"] == 1
    b.gender = "男"
    db.commit()
    assert groups(db)["total"] == 1
    with pytest.raises(HTTPException) as caught:
        undo(db, UUID(result["id"]), ACTOR)
    assert caught.value.status_code == 409


def test_defer_new_member_does_not_inherit_decision(db):
    a, b = person(db), person(db)
    process(db, [a.id, b.id], action="defer")
    assert groups(db, status="deferred")["total"] == 1
    person(db)
    assert groups(db, status="pending")["total"] == 1


def test_stale_preview_and_concurrent_commit(db):
    a, b = person(db), person(db)
    request = DuplicateReviewRequest(action="keep", person_ids=[a.id, b.id], target_id=a.id)
    old = preview(db, request)
    b.residence_address = "上海"
    db.commit()
    payload = DuplicateReviewCommit(**request.model_dump(), preview_token=old["preview_token"], idempotency_key=str(uuid4()))
    with pytest.raises(HTTPException) as caught:
        commit(db, payload, ACTOR)
    assert caught.value.status_code == 409
    db.rollback()
    payload.preview_token = preview(db, request)["preview_token"]
    db.rollback()
    def execute():
        with Session(db.get_bind()) as connection:
            return commit(connection, payload, ACTOR)["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(), range(2)))
    assert len(set(results)) == 1 and db.query(TalentDuplicateOperation).count() == 1


def test_continuous_merge_flattens_and_blocks_earlier_undo(db):
    a, b, c = person(db), person(db), person(db)
    first, _ = process(db, [a.id, b.id], a.id)
    second, _ = process(db, [a.id, c.id], c.id)
    assert get_talent(db, a.id).archived_into_id == c.id and get_talent(db, b.id).archived_into_id == c.id
    with pytest.raises(HTTPException) as caught:
        undo(db, UUID(first["id"]), ACTOR)
    assert caught.value.status_code == 409
    db.rollback()
    undo(db, UUID(second["id"]), ACTOR)
    assert get_talent(db, b.id).archived_into_id == a.id


def test_redaction_and_http_write_permissions(db, monkeypatch):
    a = person(db, primary_email="private@example.org", wechat="secret_wechat", remarks="微信：secret_wechat",
               residence_address="联系微信 secret_wechat，邮箱 private@example.org")
    person(db, secondary_email="private@example.org")
    detail = group_detail(db, "王测试", contacts_visible=False)
    encoded = str(detail)
    assert "private@example.org" not in encoded and "secret_wechat" not in encoded
    assert "contact_matches" not in encoded and not detail["can_commit"]
    from routers import talent_duplicate_review as router
    from routers.auth import get_current_user, get_user_roles_with_role_names
    from database import get_db
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: ACTOR
    monkeypatch.setattr("routers.auth.get_user_roles_with_role_names", lambda *_args: ["普通用户"])
    client = TestClient(app)
    request = dict(action="keep", person_ids=[str(a.id), str(uuid4())], target_id=str(a.id))
    assert client.post("/talents/duplicate-review/preview", json=request).status_code == 403
    assert client.post("/talents/duplicate-review/operations/" + str(uuid4()) + "/undo").status_code == 403
    assert client.get("/talents/duplicate-review/name-merge/groups").status_code == 403
    assert client.post("/talents/duplicate-review/name-merge/preview", json={"group_key": "王测试", "group_version": "a" * 64}).status_code == 403
    assert client.post("/talents/duplicate-review/name-merge/commit", json={"group_key": "王测试", "group_version": "a" * 64, "preview_token": "a" * 64, "idempotency_key": str(uuid4())}).status_code == 403
    assert client.get("/talents/duplicate-review/operations/" + str(uuid4())).status_code == 403
    operation_root = "/talents/duplicate-review/operations/" + str(uuid4()) + "/original-data"
    assert client.get(operation_root).status_code == 403
    assert client.get(operation_root + "/export").status_code == 403
    assert client.get(operation_root + "/attachments/" + str(uuid4())).status_code == 403


def test_retention_master_original_survives_later_edits_catalog_changes_and_repeat_merge(db):
    from interpretation_models import InterpretationLanguage
    from talent_retention_service import original_data, export_original_data
    language = InterpretationLanguage(id=uuid4(), label="原始语种名")
    db.add(language); db.commit()
    a, b, c = person(db, remarks="原主档备注\n第二行"), person(db, residence_address="泉州"), person(db)
    a.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id, role="native", priority=0))
    db.commit()
    operation, _ = process(db, [a.id, b.id], a.id, "merge")
    operation_id = UUID(operation["id"])
    retained = original_data(db, operation_id, a.id)
    assert retained["snapshot"]["person"]["remarks"] == "原主档备注\n第二行"
    assert retained["snapshot"]["person"]["residence_address"] is None
    assert retained["integrity_recorded"] and retained["frozen_at"].endswith("+08:00")
    assert next(item for item in retained["people"] if item["id"] == str(a.id))["role"] == "原主档"
    assert "原始语种名" in str(retained["fields"])
    a = get_talent(db, a.id); a.remarks = "主档后来编辑的备注"
    language.label = "后来目录名称"
    db.commit()
    process(db, [a.id, c.id], c.id, "keep")
    again = original_data(db, operation_id, a.id)
    assert again["snapshot"] == retained["snapshot"]
    assert "原始语种名" in str(again["fields"]) and "后来目录名称" not in str(again["fields"])
    assert {item["id"] for item in again["people"]} == {str(a.id), str(b.id)}
    exported = export_original_data(db, operation_id)
    assert exported["before_snapshot"]["people"][str(a.id)] == retained["snapshot"]
    exported["before_snapshot"]["people"][str(a.id)]["person"]["remarks"] = "修改客户端副本"
    assert original_data(db, operation_id, a.id)["snapshot"]["person"]["remarks"] == "原主档备注\n第二行"
    with pytest.raises(HTTPException) as caught:
        original_data(db, operation_id, uuid4())
    assert caught.value.status_code == 404


def test_retention_keeps_binary_original_after_live_attachment_deleted_and_blocks_corruption(db):
    from talent_attachment_service import attachment_path, delete_talent_attachment
    from talent_retention_service import original_data, original_attachment, _blob_path
    content = b"synthetic original photo bytes"
    a, b = person(db), person(db)
    attachment = ResourcePersonAttachment(id=uuid4(), person_id=a.id, category="photo", original_name="合成照片.png", storage_name="synthetic.png", content_type="image/png", file_size=len(content))
    db.add(attachment); db.commit()
    attachment_path(attachment.storage_name).write_bytes(content)
    operation, _ = process(db, [a.id, b.id], a.id, "merge")
    operation_id = UUID(operation["id"])
    retained = original_data(db, operation_id)
    assert retained["attachments"][0]["state"] == "archived"
    archived, item = original_attachment(db, operation_id, attachment.id)
    assert archived.read_bytes() == content
    assert delete_talent_attachment(db, a.id, attachment.id)
    assert not attachment_path(attachment.storage_name).exists()
    archived, _ = original_attachment(db, operation_id, attachment.id)
    assert archived.read_bytes() == content
    assert original_data(db, operation_id, a.id)["snapshot"]["attachments"][0]["id"] == str(attachment.id)
    archived.write_bytes(b"tampered")
    with pytest.raises(HTTPException) as caught:
        original_attachment(db, operation_id, attachment.id)
    assert caught.value.status_code == 409


def test_retention_survives_undo_missing_files_are_explicit_and_legacy_files_protected(db):
    from talent_attachment_service import attachment_path, delete_talent_attachment
    from talent_retention_service import original_data, original_attachment
    a, b = person(db), person(db)
    missing = ResourcePersonAttachment(id=uuid4(), person_id=b.id, category="photo", original_name="缺失照片.png", storage_name="missing.png", content_type="image/png", file_size=99)
    legacy = ResourcePersonAttachment(id=uuid4(), person_id=a.id, category="photo", original_name="旧照片.png", storage_name="legacy.png", content_type="image/png", file_size=6)
    db.add_all([missing, legacy]); db.commit()
    attachment_path(legacy.storage_name).write_bytes(b"legacy")
    operation, _ = process(db, [a.id, b.id], a.id, "keep")
    operation_id = UUID(operation["id"])
    data = original_data(db, operation_id)
    assert next(item for item in data["attachments"] if item["attachment_id"] == str(missing.id))["state"] == "missing_at_merge"
    undo(db, operation_id, ACTOR)
    assert original_data(db, operation_id)["operation"]["undone_at"]
    assert original_attachment(db, operation_id, legacy.id)[0].read_bytes() == b"legacy"
    op = db.get(TalentDuplicateOperation, operation_id)
    op.decisions = {key: value for key, value in op.decisions.items() if key != "retention"}
    db.commit()
    assert not original_data(db, operation_id)["integrity_recorded"]
    with pytest.raises(HTTPException) as caught:
        delete_talent_attachment(db, a.id, legacy.id)
    assert caught.value.status_code == 409
    db.rollback()
    assert attachment_path(legacy.storage_name).read_bytes() == b"legacy"


def test_retention_fails_before_merging_when_file_store_unwritable(db, monkeypatch):
    import talent_retention_service as retention
    from talent_attachment_service import attachment_path
    a, b = person(db), person(db)
    attachment = ResourcePersonAttachment(id=uuid4(), person_id=a.id, category="photo", original_name="测试.png", storage_name="qa.png", content_type="image/png", file_size=2)
    db.add(attachment); db.commit(); attachment_path(attachment.storage_name).write_bytes(b"qa")
    request = DuplicateReviewRequest(action="keep",person_ids=[a.id,b.id],target_id=a.id)
    proposed = preview(db,request)
    payload = DuplicateReviewCommit(**request.model_dump(),preview_token=proposed["preview_token"],idempotency_key=str(uuid4()))
    def failure(*_args, **_kwargs):
        raise OSError("模拟磁盘留存失败")
    monkeypatch.setattr(retention.tempfile,"NamedTemporaryFile",failure)
    with pytest.raises(HTTPException) as caught:
        commit(db,payload,ACTOR)
    assert caught.value.status_code == 503
    db.rollback()
    assert not get_talent(db,b.id).archived_into_id and db.query(TalentDuplicateOperation).count() == 0


def test_retention_http_export_and_snapshot_integrity(db):
    from sqlalchemy.orm.attributes import flag_modified
    from routers import talent_duplicate_review as router
    from routers.auth import get_current_user, require_super_admin
    from database import get_db
    a, b = person(db, resume_path="https://example.org/external-cv.pdf", primary_email="synthetic@example.org"), person(db)
    operation, _ = process(db, [a.id,b.id], a.id, "keep")
    app = FastAPI(); app.include_router(router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: ACTOR
    app.dependency_overrides[require_super_admin] = lambda: ACTOR
    client = TestClient(app)
    root = "/talents/duplicate-review/operations/" + operation["id"] + "/original-data"
    response = client.get(root,params={"person_id":str(a.id)})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["snapshot"]["person"]["primary_email"] == "synthetic@example.org"
    assert response.json()["external_references"][0]["state"] == "reference_only"
    exported = client.get(root+"/export")
    assert exported.status_code == 200 and "attachment;" in exported.headers["content-disposition"]
    assert exported.json()["before_snapshot"]["people"][str(a.id)]["person"]["resume_path"] == a.resume_path
    op = db.get(TalentDuplicateOperation,UUID(operation["id"]))
    op.before_snapshot["people"][str(a.id)]["person"]["remarks"] = "模拟快照损坏"
    flag_modified(op,"before_snapshot"); db.commit()
    assert client.get(root).status_code == 409 and client.get(root+"/export").status_code == 409


def test_customer_name_rule_boundaries():
    from talent_name_merge_service import name_kind
    for name in ["张小真", "王测试（英文名）", "欧阳测试", "張測試", " 张\t小 真 "]:
        assert name_kind(name) == "chinese"
    for name in ["王露", "夏优（泰语）", "张 三"]:
        assert name_kind(name) == "short_chinese"
    for name in ["William Zhao", " WILLIAM\n  Zhao ", "José da Silva", "Mary-Jane O’Neill", "J. Smith"]:
        assert name_kind(name) == "english"
    for name in ["William", "王露 Zhao", "ABC 123", "Иван Петров", "", "-(备注)"]:
        assert name_kind(name) == "other"


def test_name_merge_preview_all_members_field_audit_and_idempotency(db):
    from talent_name_merge_service import list_groups, preview_group, commit_group
    from talent_duplicate_schemas import NameMergePreviewRequest, NameMergeCommitRequest
    from talent_duplicate_service import operation_detail
    a = person(db, "张小真", gender="女", primary_email="first@example.org", remarks="主档备注\n第二行")
    b = person(db, "张小真（来源甲）", gender="男", primary_email="second@example.org", residence_address="泉州", remarks="来源备注")
    c = person(db, "张小真", secondary_phone="1234567890")
    person(db, "王露"), person(db, "王露")
    person(db, "WILLIAM Zhao"), person(db, "William  Zhao")
    rows = list_groups(db, limit=100)
    assert rows["total"] == 2 and rows["archive_count"] == 3
    assert rows["counts"]["short_chinese"] == 1
    group = next(item for item in rows["items"] if item["key"] == "张小真")
    assert group["target_id"] == str(a.id) and group["count"] == 3
    request = NameMergePreviewRequest(group_key=group["key"], group_version=group["group_version"])
    proposed = preview_group(db, request)
    assert not proposed["conflicts"]
    assert proposed["final_values"]["gender"] == "女"
    assert proposed["final_values"]["primary_email"] == "first@example.org"
    assert proposed["final_values"]["residence_address"] == "泉州"
    assert "主档备注\n第二行" in proposed["final_values"]["remarks"] and "来源备注" in proposed["final_values"]["remarks"]
    assert len(proposed["audit"]["participants"]) == 3
    assert all(not get_talent(db, row.id).archived_into_id for row in [a, b, c])
    payload = NameMergeCommitRequest(**request.model_dump(), preview_token=proposed["preview_token"], idempotency_key=str(uuid4()))
    result = commit_group(db, payload, ACTOR)
    assert commit_group(db, payload, ACTOR)["id"] == result["id"]
    assert db.query(TalentDuplicateOperation).count() == 1
    detail = operation_detail(db, UUID(result["id"]))
    field = next(row for row in detail["audit"]["fields"] if row["key"] == "gender")
    assert field["value"] == "女" and {row["value"] for row in field["options"]} == {"女", "男", None}
    assert len(detail["audit"]["archive_ids"]) == 2 and detail["created_at"].endswith("+08:00")
    assert get_talent(db, a.id).resource_code == a.resource_code
    assert get_talent(db, b.id).gender == "男" and get_talent(db, b.id).archived_into_id == a.id
    assert get_talent(db, c.id).archived_into_id == a.id
    assert "second@example.org" in str(detail_inheritance(db, a.id, True)["inherited_contacts"])
    altered = payload.model_copy(update={"group_key": "其他同名"})
    with pytest.raises(HTTPException) as caught:
        commit_group(db, altered, ACTOR)
    assert caught.value.status_code == 409
    undo(db, UUID(result["id"]), ACTOR)
    assert all(not get_talent(db, row.id).archived_into_id for row in [a, b, c])
    assert get_talent(db, a.id).residence_address is None


def test_name_merge_rejects_short_names_stale_members_and_business_links(db):
    from talent_name_merge_service import list_groups, preview_group, commit_group
    from talent_duplicate_schemas import NameMergePreviewRequest, NameMergeCommitRequest
    a, b = person(db), person(db, residence_address="北京")
    group = list_groups(db)["items"][0]
    request = NameMergePreviewRequest(group_key=group["key"], group_version=group["group_version"])
    with pytest.raises(HTTPException) as caught:
        preview_group(db, NameMergePreviewRequest(group_key="王露", group_version=group["group_version"]))
    assert caught.value.status_code == 422
    person(db)
    with pytest.raises(HTTPException) as caught:
        preview_group(db, request)
    assert caught.value.status_code == 409
    group = list_groups(db)["items"][0]
    request = NameMergePreviewRequest(group_key=group["key"], group_version=group["group_version"])
    proposed = preview_group(db, request)
    with db.get_bind().begin() as conn:
        conn.execute(text("CREATE TABLE merge_business(id uuid PRIMARY KEY, person_id uuid REFERENCES resource_person(id), note text)"))
    db.execute(text("INSERT INTO merge_business VALUES (:id,:person,'新关联')"), {"id": uuid4(), "person": a.id})
    db.commit()
    payload = NameMergeCommitRequest(**request.model_dump(), preview_token=proposed["preview_token"], idempotency_key=str(uuid4()))
    with pytest.raises(HTTPException) as caught:
        commit_group(db, payload, ACTOR)
    assert caught.value.status_code == 409
    db.rollback()
    assert not get_talent(db, b.id).archived_into_id and not db.query(TalentDuplicateOperation).count()


def test_name_merge_collection_conflict_keeps_master_attachments_and_capacity(db):
    from interpretation_models import InterpretationLanguage
    from talent_name_merge_service import list_groups, preview_group, commit_group
    from talent_duplicate_schemas import NameMergePreviewRequest, NameMergeCommitRequest
    from talent_duplicate_service import operation_detail
    language = InterpretationLanguage(id=uuid4(), label="合成英语")
    db.add(language); db.commit()
    a = person(db, registration_source="甲" * 200)
    b = person(db, registration_source="乙" * 200)
    c = person(db)
    a.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id, role="native", priority=0))
    b.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id, role="foreign", priority=0))
    c.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id, role="native", priority=0))
    attachment = ResourcePersonAttachment(id=uuid4(), person_id=b.id, category="resume", original_name="合成简历.pdf", storage_name="qa.pdf", content_type="application/pdf", file_size=12)
    db.add(attachment); db.commit()
    group = list_groups(db)["items"][0]
    request = NameMergePreviewRequest(group_key=group["key"], group_version=group["group_version"])
    proposed = preview_group(db, request)
    assert not proposed["conflicts"] and proposed["final_values"]["language_skills"][0]["role"] == "native"
    assert proposed["final_values"]["registration_source"] == "甲" * 200
    payload = NameMergeCommitRequest(**request.model_dump(), preview_token=proposed["preview_token"], idempotency_key=str(uuid4()))
    result = commit_group(db, payload, ACTOR)
    audit = operation_detail(db, UUID(result["id"]))["audit"]
    attachment_field = next(row for row in audit["fields"] if row["key"] == "attachments")
    assert attachment_field["value"][0]["readonly"] and attachment_field["value"][0]["id"] == str(attachment.id)
    assert get_talent(db, b.id).language_skills[0].role == "foreign"
    assert detail_inheritance(db, a.id, True)["inherited_attachments"][0]["readonly"]


def test_name_merge_multiple_roles_for_same_language_preserves_originals_and_undo(db):
    from interpretation_models import InterpretationLanguage
    from talent_name_merge_service import list_groups, preview_group, commit_group
    from talent_duplicate_schemas import NameMergePreviewRequest, NameMergeCommitRequest
    language = InterpretationLanguage(id=uuid4(), label="合成多角色语言")
    db.add(language); db.commit()
    a, b = person(db), person(db)
    for role, priority in [("native", 0), ("foreign", 0), ("dialect_ethnic", 0)]:
        a.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id,
                                                       role=role, priority=priority))
    b.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id,
                                                   role="foreign", priority=1))
    db.commit()
    before = full_snapshot(db, [a.id, b.id])
    group = list_groups(db)["items"][0]
    request = NameMergePreviewRequest(group_key=group["key"], group_version=group["group_version"])
    proposed = preview_group(db, request)
    chosen = proposed["final_values"]["language_skills"][0]
    result = commit_group(db, NameMergeCommitRequest(**request.model_dump(),
                         preview_token=proposed["preview_token"], idempotency_key=str(uuid4())), ACTOR)
    merged = get_talent(db, a.id)
    assert len(merged.language_skills) == 1
    assert (merged.language_skills[0].role, merged.language_skills[0].priority) == (chosen["role"], chosen["priority"])
    assert get_talent(db, b.id).language_skills[0].priority == 1
    operation = db.get(TalentDuplicateOperation, UUID(result["id"]))
    assert operation.before_snapshot == before
    undo(db, operation.id, ACTOR)
    assert full_snapshot(db, [a.id, b.id]) == before


def test_name_merge_handles_empty_profile_lists_when_master_has_no_profile(db):
    from resource_models import AnnotationProfile, ResourceCareerProfile
    from talent_name_merge_service import list_groups, preview_group
    from talent_duplicate_schemas import NameMergePreviewRequest
    a, b = person(db), person(db)
    b.capabilities.append(ResourceCapability(id=uuid4(), capability_type="annotation", status="active", source="manual"))
    db.add_all([AnnotationProfile(person_id=b.id), ResourceCareerProfile(person_id=b.id)])
    db.commit()
    group = list_groups(db)["items"][0]
    proposed = preview_group(db, NameMergePreviewRequest(group_key=group["key"], group_version=group["group_version"]))
    assert not proposed["conflicts"]
    for field in ["annotation_profile.task_types", "annotation_profile.tools", "career_profile.industries", "career_profile.job_titles"]:
        assert proposed["final_values"][field] == []
    assert get_talent(db, a.id).annotation_profile is None


def test_language_conflict_and_attachment_preservation(db):
    from interpretation_models import InterpretationLanguage
    language = InterpretationLanguage(id=uuid4(), label="测试英语")
    db.add(language)
    db.commit()
    a, b = person(db), person(db)
    a.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id, role="native", priority=0))
    b.language_skills.append(ResourceLanguageSkill(id=uuid4(), language_id=language.id, role="foreign", priority=0, proficiency="familiar"))
    certificate = ResourceCertificate(id=uuid4(), person_id=b.id, certificate_type="language", name="测试证书", material_received=True)
    db.add(certificate)
    attachment = ResourcePersonAttachment(id=uuid4(), person_id=b.id, certificate_id=certificate.id, category="certificate",
                                          original_name="测试证书.pdf", storage_name="synthetic-file.pdf", content_type="application/pdf", file_size=42)
    db.add(attachment)
    db.commit()
    request = DuplicateReviewRequest(action="merge", person_ids=[a.id, b.id], target_id=a.id)
    result = preview(db, request)
    conflict = next(item for item in result["conflicts"] if item["key"].startswith("language_skills:"))
    option = next(item for item in conflict["options"] if item["person_id"] == str(b.id))
    operation, _ = process(db, [a.id, b.id], a.id, "merge", {conflict["key"]: {"person_id": str(b.id), "value_hash": option["value_hash"]}})
    merged = get_talent(db, a.id)
    assert len(merged.language_skills) == 1 and merged.language_skills[0].role == "foreign"
    assert len(merged.certificates) == 1 and len(get_talent(db, b.id).certificates) == 1
    inherited = detail_inheritance(db, a.id, True)["inherited_attachments"]
    assert inherited[0]["id"] == str(attachment.id) and inherited[0]["readonly"]
    undo(db, UUID(operation["id"]), ACTOR)
    assert get_talent(db, a.id).language_skills[0].role == "native"
    assert not get_talent(db, a.id).certificates and db.get(ResourcePersonAttachment, attachment.id)


def test_original_business_links_and_descendants_protect_undo(db):
    # 模拟未来业务模块，动态外键发现必须覆盖新增关联及下游记录。
    with db.get_bind().begin() as conn:
        conn.execute(text("CREATE TABLE review_business(id uuid PRIMARY KEY, person_id uuid REFERENCES resource_person(id), note text)"))
        conn.execute(text("CREATE TABLE review_business_note(id uuid PRIMARY KEY, business_id uuid REFERENCES review_business(id), note text)"))
    a, b = person(db), person(db)
    business, child = uuid4(), uuid4()
    db.execute(text("INSERT INTO review_business VALUES (:id,:person,'原记录')"), dict(id=business, person=b.id))
    db.execute(text("INSERT INTO review_business_note VALUES (:id,:parent,'原备注')"), dict(id=child, parent=business))
    db.commit()
    result, _ = process(db, [a.id, b.id], a.id)
    assert db.execute(text("SELECT person_id FROM review_business WHERE id=:id"), {"id": business}).scalar() == b.id
    db.execute(text("UPDATE review_business_note SET note='后续跟进' WHERE id=:id"), {"id": child})
    db.commit()
    with pytest.raises(HTTPException) as caught:
        undo(db, UUID(result["id"]), ACTOR)
    assert caught.value.detail["references_changed"]


def test_new_capability_legacy_row_undo_and_future_assignment_guard(db):
    from models import Translator
    a, b = person(db), person(db)
    b.capabilities.append(ResourceCapability(id=uuid4(), capability_type="written_translation", status="active", source="manual"))
    db.commit()
    operation, _ = process(db, [a.id, b.id], a.id, "merge")
    assert db.get(Translator, a.id) is not None
    undo(db, UUID(operation["id"]), ACTOR)
    assert db.get(Translator, a.id) is None
    assert not get_talent(db, a.id).capabilities


def test_unknown_fields_lengths_and_transaction_failure(db, monkeypatch):
    a, b = person(db), person(db, residence_address="上海")
    with pytest.raises(HTTPException):
        preview(db, DuplicateReviewRequest(action="merge", person_ids=[a.id, b.id], target_id=a.id, decisions={"resource_code": {"value": "任意编号"}}))
    with pytest.raises(HTTPException):
        preview(db, DuplicateReviewRequest(action="merge", person_ids=[a.id, b.id], target_id=a.id, decisions={"residence_address": {"value": "长" * 501}}))
    request = DuplicateReviewRequest(action="merge", person_ids=[a.id, b.id], target_id=a.id)
    result = preview(db, request)
    payload = DuplicateReviewCommit(**request.model_dump(), preview_token=result["preview_token"], idempotency_key=str(uuid4()))
    def failure(*_args):
        raise RuntimeError("模拟保存失败")
    monkeypatch.setattr("talent_duplicate_service._apply_merge", failure)
    with pytest.raises(RuntimeError):
        commit(db, payload, ACTOR)
    db.rollback()
    assert get_talent(db, b.id).archived_into_id is None and db.query(TalentDuplicateOperation).count() == 0


def test_before_migration_ordinary_create_list_and_read_only_review(db):
    from sqlalchemy import inspect
    with db.get_bind().begin() as conn:
        for table_name in inspect(conn).get_table_names():
            for trigger in conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgrelid=to_regclass(:name) AND NOT tgisinternal"), {"name": table_name}).scalars():
                conn.execute(text(f'DROP TRIGGER "{trigger}" ON "{table_name}"'))
        conn.execute(text("DROP TABLE talent_duplicate_operation"))
        conn.execute(text("ALTER TABLE resource_person DROP COLUMN archived_into_id CASCADE, DROP COLUMN archived_at"))
        for filename in ("20261012_talent_name_duplicate.sql", "20261013_normalize_talent_duplicate_names.sql"):
            sql = (Path(__file__).resolve().parents[1] / "data/migrations" / filename).read_text(encoding="utf-8").strip().removeprefix("BEGIN;").removesuffix("COMMIT;")
            conn.execute(text(sql))
    db.info.clear()
    assert not review_ready(db)
    a = create_talent(db, ResourcePersonCreate(full_name="迁移前人员", chinese_name="迁移前人员"))
    b = create_talent(db, ResourcePersonCreate(full_name="迁移前人员", chinese_name="迁移前人员"))
    assert count_talents(db) == 2 and len(get_talents(db)) == 2
    assert not group_detail(db, "迁移前人员", True)["ready"]
    with pytest.raises(HTTPException) as caught:
        preview(db, DuplicateReviewRequest(action="keep", person_ids=[a.id, b.id], target_id=a.id))
    assert caught.value.status_code == 503


def test_real_project_histories_performance_filters_and_archive_guard(db):
    from annotation_models import AnnotationProject, AnnotationProjectAssignee
    from annotation_ops_models import AnnotationTrialRecord
    from resource_service import get_talent_project_history, get_talent_annotation_project_performance
    from sqlalchemy.exc import DBAPIError
    a, b = person(db), person(db)
    project = AnnotationProject(id=uuid4(), order_no="QA" + uuid4().hex, project_name="合成核重项目")
    db.add(project)
    db.flush()
    db.add_all([AnnotationProjectAssignee(id=uuid4(), project_id=project.id, person_id=b.id, sequence_no=1, assignment_role="annotator"),
                AnnotationProjectAssignee(id=uuid4(), project_id=project.id, person_id=a.id, sequence_no=2, assignment_role="quality_inspector"),
                AnnotationTrialRecord(id=uuid4(), project_id=project.id, person_id=b.id, sequence_no=1)])
    db.commit()
    operation, _ = process(db, [a.id, b.id], a.id)
    histories = get_talent_project_history(db, a.id)
    assert len(histories) == 1 and histories[0]["trial_count"] == 1
    assert set(histories[0]["roles"]) == {"annotator", "quality_inspector", "试标/试采"}
    original = get_talent_project_history(db, b.id)
    assert len(original) == 1 and set(original[0]["roles"]) == {"annotator", "试标/试采"}
    performance = get_talent_annotation_project_performance(db, a.id, project.id)
    assert len(performance["trials"]) == 1 and len(performance["assignments"]) == 2
    assert [row.id for row in get_talents(db, field_filters={"project_situation": {"value": "合成核重"}})] == [a.id]
    db.add(AnnotationProjectAssignee(id=uuid4(), project_id=project.id, person_id=b.id, sequence_no=3))
    with pytest.raises(DBAPIError):
        db.commit()
    db.rollback()
    original_assignment = db.query(AnnotationProjectAssignee).filter_by(person_id=b.id).first()
    original_assignment.assignment_status = "completed"
    db.commit()
    with pytest.raises(HTTPException) as caught:
        undo(db, UUID(operation["id"]), ACTOR)
    assert caught.value.status_code == 409


def test_catalog_labels_contact_lookup_and_review_tag(db):
    a, b = person(db), person(db, secondary_email="archive@example.org")
    process(db, [a.id, b.id], action="different")
    assert all(row.name_review_state == "different" for row in get_talents(db))
    process(db, [a.id, b.id], a.id)
    assert find_duplicate_talents(db, email="archive@example.org")[0]["id"] == str(a.id)
    assert not find_duplicate_talents(db, email="archive@example.org", exclude_id=a.id)
