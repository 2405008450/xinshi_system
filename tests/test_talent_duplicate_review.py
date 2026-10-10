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
