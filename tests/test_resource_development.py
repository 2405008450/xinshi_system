"""开拓核心回归；数据库测试仅在显式启用的局域网调试库运行，逐例回滚。"""
import os
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from resource_development_schemas import RecordWrite, WorkWrite


def test_work_period_validation():
    common = dict(work_date=date(2026, 9, 24), owner_id=uuid4())
    good = WorkWrite(**common, periods=[dict(start="09:00", end="10:30"), dict(start="11:00", end="12:00")], deduction=15)
    assert good.duration_minutes == 135
    for periods, deduction in [([dict(start="10:00", end="09:00")], 0),
                                ([dict(start="09:00", end="11:00"), dict(start="10:00", end="12:00")], 0),
                                ([dict(start="09:00", end="10:00")], 61),
                                ([dict(start="25:00", end="26:00")], 0)]:
        with pytest.raises(ValidationError):
            WorkWrite(**common, periods=periods, deduction=deduction)
    with pytest.raises(ValidationError):
        WorkWrite(**common, completed=False, explanation=" ")


def test_dates_and_report_merge():
    from resource_development_service import previous_workday
    from task_service import merge_daily_report_items
    assert previous_workday(date(2026, 9, 28)) == date(2026, 9, 25)
    assert previous_workday(date(2026, 9, 27)) == date(2026, 9, 25)
    assert previous_workday(date(2026, 9, 24)) == date(2026, 9, 23)
    source = dict(source_type="system_event", source_id=uuid4(), duration_minutes=70, display_metadata={"source": "resource_development"})
    result = merge_daily_report_items([{**source, "duration_minutes": 999}, dict(source_type="manual", duration_minutes=5)], [source])
    assert [r["duration_minutes"] for r in result] == [5, 70]
    assert merge_daily_report_items([], [dict(source_type="system_event", duration_minutes=99)])[0]["duration_minutes"] == 0


@pytest.fixture
def db():
    if os.getenv("RUN_RESOURCE_DEVELOPMENT_DB_TESTS") != "1":
        pytest.skip("数据库回归需在局域网显式启用")
    # 注册应用所有 ORM 类型；不运行 startup，不触发邮件或项目任务。
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    # 调试机默认配置可能指向云端，回滚测试也不能连接生产数据库。
    assert engine.url.host in {'localhost', '127.0.0.1', '192.168.31.144'}, '数据库回归仅允许连接局域网或隔离数据库'
    with engine.connect() as conn:
        transaction = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def context(db):
    from models import AppUser
    from resource_development_models import DevelopmentOption
    user = AppUser(id=uuid4(), username="development_test_" + uuid4().hex, full_name="开拓测试人员", password_hash="not-a-login", is_active=True)
    other = AppUser(id=uuid4(), username="development_test_" + uuid4().hex, full_name="其他测试人员", password_hash="not-a-login", is_active=True)
    platform = DevelopmentOption(id=uuid4(), kind="platform", category="national", name="测试平台" + uuid4().hex, code="TEST" + uuid4().hex[:12])
    db.add_all([user, other, platform]); db.flush()
    return user, other, platform


def make_payload(context, **kwargs):
    user, _, platform = context
    return RecordWrite(**(dict(id=uuid4(), platform_id=platform.id, work_date=date(2026, 9, 24), owner_id=user.id,
                               full_name="测试资源" + uuid4().hex, phone="", wechat="") | kwargs))


def test_xiaohongshu_validation():
    common = dict(id=uuid4(), platform_id=uuid4(), work_date=date(2026, 10, 8), owner_id=uuid4(), full_name="小红书校验")
    assert RecordWrite(**common).xiaohongshu == ""
    assert RecordWrite(**common, xiaohongshu="  xhs_001  ").xiaohongshu == "xhs_001"
    assert RecordWrite(**common, xiaohongshu="   ").xiaohongshu == ""
    assert RecordWrite(**common, xiaohongshu="x" * 100).xiaohongshu == "x" * 100
    with pytest.raises(ValidationError):
        RecordWrite(**common, xiaohongshu="x" * 101)


def test_xiaohongshu_migration_backfills_history_and_is_repeatable(db):
    from pathlib import Path
    from sqlalchemy import text
    # 临时表遮蔽同名业务表，避免迁移测试修改真实结构或数据。
    db.execute(text("CREATE TEMP TABLE resource_development_record (id integer PRIMARY KEY) ON COMMIT DROP"))
    try:
        db.execute(text("INSERT INTO resource_development_record (id) VALUES (1)"))
        sql = (Path(__file__).resolve().parents[1] / "data/migrations/20261008_resource_development_xiaohongshu.sql").read_text(encoding="utf-8")
        sql = sql.replace("BEGIN;", "").replace("COMMIT;", "")
        db.connection().exec_driver_sql(sql)
        db.connection().exec_driver_sql(sql)
        assert db.execute(text("SELECT xiaohongshu FROM resource_development_record WHERE id=1")).scalar() == ""
        db.execute(text("INSERT INTO resource_development_record (id) VALUES (2)"))
        assert db.execute(text("SELECT xiaohongshu FROM resource_development_record WHERE id=2")).scalar() == ""
    finally:
        db.execute(text("DROP TABLE pg_temp.resource_development_record"))


def test_xiaohongshu_api_save_search_permissions_and_clear(db, context):
    import json
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_development import router
    from resource_development_service import save_record
    user, other, _ = context
    token = "xhs_" + uuid4().hex
    foreign = save_record(db, other, make_payload(context, owner_id=other.id, xiaohongshu=token + "_other"))
    historical = seed_name_check_record(db, context, "历史空账号" + uuid4().hex)
    assert historical.xiaohongshu == ""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    payload = make_payload(context, xiaohongshu="  " + token + "  ").model_dump(mode="json")
    with TestClient(app) as client, patch("routers.auth.get_user_permission_codes", return_value=["talents:read", "talents:write"]), patch("resource_development_service.can_delegate", return_value=False):
        created = client.post("/resource-development/records", json=payload)
        assert created.status_code == 200, created.text
        record = created.json()
        assert record["xiaohongshu"] == token and not record["person_id"]
        url = "/resource-development/records/" + record["id"]
        assert client.get(url).json()["xiaohongshu"] == token
        for params in [{"keyword": token}, {"column_filters": json.dumps({"xiaohongshu": token})}]:
            listing = client.get("/resource-development/records", params=params)
            assert listing.status_code == 200, listing.text
            assert listing.json()["total"] == 1
            assert listing.json()["items"][0]["id"] == record["id"]
            days = client.get("/resource-development/days", params=params).json()
            assert days["total"] == 1 and days["items"][0]["count"] == 1
        masked = client.get("/resource-development/records/" + str(foreign.id)).json()
        assert masked["xiaohongshu"] == "******" and masked["audit"] == []
        with patch("resource_development_service.can_delegate", return_value=True):
            assert client.get("/resource-development/records", params={"keyword": token}).json()["total"] == 2
            assert client.get("/resource-development/records", params={"column_filters": json.dumps({"xiaohongshu": token})}).json()["total"] == 2
            assert client.get("/resource-development/records/" + str(foreign.id)).json()["xiaohongshu"] == token + "_other"
        edited = client.post("/resource-development/records", json={**payload, "revision": record["revision"], "xiaohongshu": "edited_" + token})
        assert edited.status_code == 200 and edited.json()["xiaohongshu"] == "edited_" + token
        legacy_payload = {key: value for key, value in payload.items() if key != "xiaohongshu"}
        legacy_edit = client.post("/resource-development/records", json={**legacy_payload, "revision": edited.json()["revision"]})
        assert legacy_edit.status_code == 200 and legacy_edit.json()["xiaohongshu"] == "edited_" + token
        overlength = client.post("/resource-development/records", json={**payload, "revision": legacy_edit.json()["revision"], "xiaohongshu": "x" * 101})
        assert overlength.status_code == 422
        cleared = client.post("/resource-development/records", json={**payload, "revision": legacy_edit.json()["revision"], "xiaohongshu": "  "})
        assert cleared.status_code == 200 and cleared.json()["xiaohongshu"] == ""
        assert client.get(url).json()["xiaohongshu"] == ""


def seed_name_check_record(db, context, name, **kwargs):
    from resource_development_models import DevelopmentRecord
    user, _, platform = context
    row = DevelopmentRecord(id=uuid4(), greeting_no="QA-" + uuid4().hex,
                            full_name=name, platform_id=platform.id, owner_id=user.id,
                            work_date=date(2026, 9, 24), created_by=user.id, updated_by=user.id)
    for key, value in kwargs.items():
        setattr(row, key, value)
    db.add(row); db.flush()
    return row


def test_record_name_duplicates_exact_global_and_pagination(db, context):
    from resource_development_service import record_name_duplicates
    from resource_development_models import DevelopmentOption
    user, other, _ = context
    name = "姓名核实" + uuid4().hex
    platform = DevelopmentOption(id=uuid4(), kind="platform", category="national", name="其他平台" + uuid4().hex, code="QA" + uuid4().hex[:12])
    db.add(platform); db.flush()
    old = seed_name_check_record(db, context, "  " + name.upper() + "  ", historical_only=True, work_date=date(2025, 1, 1))
    new = seed_name_check_record(db, context, name, owner_id=other.id, platform_id=platform.id, work_date=date(2026, 10, 8))
    seed_name_check_record(db, context, name + "不同名")
    page = record_name_duplicates(db, user, " " + name + " ", limit=1)
    assert page["total"] == 2 and page["items"][0]["id"] == str(new.id)
    assert page["items"][0]["platform_name"] == platform.name
    assert record_name_duplicates(db, user, name, skip=1, limit=1)["items"][0]["id"] == str(old.id)
    assert record_name_duplicates(db, user, name, skip=2)["items"] == []
    assert record_name_duplicates(db, user, "   ") == {"items": [], "total": 0}


def test_record_name_duplicates_contact_permissions(db, context):
    from resource_development_service import record_name_duplicates
    user, other, _ = context
    name = "联系方式核实" + uuid4().hex
    own = seed_name_check_record(db, context, name, phone="13812345678", wechat="own_wechat")
    foreign = seed_name_check_record(db, context, name, owner_id=other.id, phone="13987654321", wechat="private_wechat")
    with patch("resource_development_service.can_delegate", return_value=False):
        items = {p["id"]: p for p in record_name_duplicates(db, user, name)["items"]}
        assert items[str(own.id)]["wechat"] == "own_wechat" and not items[str(own.id)]["contact_restricted"]
        assert items[str(foreign.id)]["wechat"] == items[str(foreign.id)]["phone"] == ""
        assert items[str(foreign.id)]["contact_restricted"]
        assert "private_wechat" not in str(items) and "13987654321" not in str(items)
    with patch("resource_development_service.can_delegate", return_value=True):
        items = {p["id"]: p for p in record_name_duplicates(db, user, name)["items"]}
        assert items[str(foreign.id)]["wechat"] == "private_wechat" and not items[str(foreign.id)]["contact_restricted"]


def test_record_name_duplicates_never_queries_talent_pool(db, context):
    from sqlalchemy import event
    from resource_models import ResourcePerson
    from resource_development_service import record_name_duplicates
    user, _, _ = context
    name = "仅人才库" + uuid4().hex
    db.add(ResourcePerson(id=uuid4(), full_name=name, resource_code="QA-" + uuid4().hex))
    db.flush()
    statements = []
    def capture(conn, cursor, statement, parameters, execution_context, executemany):
        statements.append(statement)
    connection = db.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        assert record_name_duplicates(db, user, name) == {"items": [], "total": 0}
        seed_name_check_record(db, context, name)
        assert record_name_duplicates(db, user, name)["total"] == 1
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert all("resource_person" not in sql.lower() for sql in statements)


def test_record_same_name_remains_advisory(db, context):
    from resource_development_service import save_record, record_name_duplicates
    user, _, _ = context
    name = "同名允许保存" + uuid4().hex
    seed_name_check_record(db, context, name)
    saved = save_record(db, user, make_payload(context, full_name=name))
    assert saved.person_id is None and not saved.duplicate_note
    assert record_name_duplicates(db, user, name)["total"] == 2


def test_record_name_duplicates_api_permissions_and_validation(db, context):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_development import router
    user, _, _ = context
    name = "接口姓名核实" + uuid4().hex
    seed_name_check_record(db, context, name, wechat="api_wechat")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        with patch("routers.auth.get_user_permission_codes", return_value=["talents:read"]):
            assert client.get("/resource-development/record-duplicates", params={"full_name": name}).status_code == 403
        with patch("routers.auth.get_user_permission_codes", return_value=["talents:write"]):
            result = client.get("/resource-development/record-duplicates", params={"full_name": name})
            assert result.status_code == 200 and result.json()["total"] == 1
            assert result.json()["items"][0]["wechat"] == "api_wechat"
            for params in [{}, {"full_name": ""}, {"full_name": "a" * 256}, {"full_name": name, "skip": -1}, {"full_name": name, "limit": 101}]:
                assert client.get("/resource-development/record-duplicates", params=params).status_code == 422


def test_historical_import_and_edit_never_enroll(db, context):
    from resource_development_service import save_record, serialize_record
    user, other, _ = context
    payload = make_payload(context, actions=[action(user, "已添加")])
    with patch("resource_development_service.create_talent") as create:
        row = save_record(db, user, payload, historical_markers={"wechat": {"status": "已添加", "raw": "原本标注员"}})
        assert row.historical_only and row.person_id is None
        assert save_record(db, user, payload).id == row.id
        edited = payload.model_copy(update={"revision": row.revision, "remarks": "修改历史记录"})
        save_record(db, user, edited)
        create.assert_not_called()
    assert serialize_record(db, other, row)["historical_markers"] == {}
    undated = save_record(db, user, make_payload(context), historical_markers={"wechat": {"status": "已添加", "raw": "原本标注员"}})
    assert undated.wechat_status == "已添加"
    assert serialize_record(db, user, undated)["progress"]["wechat"]["action_date"] is None
    with pytest.raises(ValidationError):
        RecordWrite(**(payload.model_dump() | {"historical_only": True}))


def action(user, status="已发请求", channel="wechat"):
    return dict(id=uuid4(), channel=channel, status=status, action_date=date(2026, 9, 24), operator_id=user.id)


def test_numbering_ownership_actions_and_idempotency(db, context):
    from resource_development_service import save_record, serialize_record
    from resource_development_models import DevelopmentRecord, DevelopmentAction
    user, other, _ = context
    payload = make_payload(context, phone="13912340000", remarks="有联系方式的备注", actions=[action(user), action(user)])
    row = save_record(db, user, payload)
    assert row.greeting_no.endswith("-260924-001")
    assert db.query(DevelopmentAction).filter_by(record_id=row.id).count() == 2
    assert save_record(db, user, payload).id == row.id
    assert db.query(DevelopmentRecord).filter_by(owner_id=user.id).count() == 1
    detail = serialize_record(db, user, row, True)
    assert [a["request_number"] for a in detail["actions"]] == [1, 2]
    masked = serialize_record(db, other, row, True)
    assert masked["phone"] == "******" and masked["remarks"] == "受限内容" and masked["audit"] == []
    update = payload.model_copy(update={"revision": row.revision, "work_date": date(2026, 9, 23)})
    original = row.greeting_no
    assert save_record(db, user, update).greeting_no == original
    with pytest.raises(HTTPException) as exc:
        save_record(db, other, update.model_copy(update={"owner_id": other.id}))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        save_record(db, user, update)
    assert exc.value.status_code == 409


def test_enrollment_duplicates_and_transaction(db, context):
    from resource_development_service import save_record, duplicates
    from resource_models import ResourcePerson
    user, _, _ = context
    payload = make_payload(context, capabilities=["annotation", "recruitment"], actions=[action(user, "已添加")])
    row = save_record(db, user, payload)
    person = db.get(ResourcePerson, row.person_id)
    assert person.resource_code and person.career_profile is not None
    assert person.capabilities[0].capability_type == "annotation"
    updated = payload.model_copy(update={"revision": row.revision, "actions": [*payload.actions, type(payload.actions[0])(**action(user, "已添加", "enterprise"))]})
    assert save_record(db, user, updated).person_id == person.id
    candidate = duplicates(db, payload.full_name, "", "")
    assert candidate[0]["match_fields"] == ["name"] and "primary_phone" not in candidate[0]
    linked = make_payload(context, full_name=payload.full_name, actions=[action(user, "已添加")], link_person_id=person.id)
    assert save_record(db, user, linked).person_id == person.id
    same_name = make_payload(context, full_name=payload.full_name, actions=[action(user, "已添加")], duplicate_note="确认不是同一人", capabilities=["annotation"])
    assert save_record(db, user, same_name).person_id != person.id
    person.wechat = "unique_" + uuid4().hex; db.flush()
    conflict = make_payload(context, wechat=person.wechat, actions=[action(user, "已添加")], duplicate_note="不能绕过", capabilities=["annotation"])
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException) as exc:
            save_record(db, user, conflict)
        assert exc.value.status_code == 409
        nested.rollback()
    # 人才创建已 flush 后发生异常，外层事务仍可完整回滚。
    rollback_payload = make_payload(context, actions=[action(user, "已添加")], capabilities=["annotation"])
    with db.begin_nested() as nested:
        created = save_record(db, user, rollback_payload); created_person_id = created.person_id
        nested.rollback()
    assert db.get(ResourcePerson, created_person_id) is None


def test_independent_progress_preserves_history_and_does_not_enroll(db, context):
    from resource_development_service import save_record, serialize_record
    from resource_development_models import DevelopmentAction
    from resource_development_schemas import ActionWrite
    user, other, _ = context
    payload = make_payload(context, actions=[action(user)])
    row = save_record(db, user, payload)
    first = db.get(DevelopmentAction, payload.actions[0].id)
    original_audit = (first.updated_by, first.updated_at)
    additions = [ActionWrite(**action(other, status, channel)) for channel, status in [
        ('group', '已邀进群'), ('communication', '已沟通'), ('project', '已入项')]]
    updated = payload.model_copy(update={'revision': row.revision, 'actions': [*payload.actions, *additions]})
    save_record(db, user, updated)
    assert row.person_id is None and row.wechat_status == '一次请求'
    assert (first.updated_by, first.updated_at) == original_audit
    detail = serialize_record(db, user, row, True)
    assert set(detail['progress']) == {'wechat', 'group', 'communication', 'project'}
    assert detail['progress']['project']['operator_name'] == other.full_name
    assert detail['latest_follow_up'] == '' and detail['follow_up_count'] == 0
    assert len(detail['actions']) == 4
    with pytest.raises(HTTPException) as error:
        save_record(db, other, updated.model_copy(update={'revision': row.revision}))
    assert error.value.status_code == 403


def test_delegate_permission_is_module_scoped_and_preserves_owner(db, context):
    from models import Role, RolePermission, UserRole
    from resource_development_service import save_record, serialize_record, filtered_records, report_item
    from routers.resource_development import options, delete_record
    from talent_privacy import can_view_talent_contacts
    user, operator, _ = context
    role = Role(id=uuid4(), role_name='代录回归_' + uuid4().hex)
    db.add(role); db.flush()
    db.add_all([RolePermission(role_id=role.id, permission_code='resource_development:delegate'), UserRole(user_id=user.id, role_id=role.id)])
    db.flush()
    assert options(db, user)['can_delegate'] and options(db, user)['can_write']
    assert not can_view_talent_contacts(db, user)
    payload = make_payload(context, owner_id=operator.id, phone='13977771234', actions=[action(operator, '已沟通', 'communication')])
    row = save_record(db, user, payload)
    assert row.owner_id == operator.id and row.created_by == user.id
    detail = serialize_record(db, user, row, True)
    assert detail['phone'] == '13977771234' and detail['can_edit'] and not detail['can_delete']
    assert detail['actions'][0]['created_by'] == str(user.id)
    assert detail['actions'][0]['operator_id'] == str(operator.id)
    assert filtered_records(db, user, payload.work_date, payload.work_date, keyword='13977771234').count() == 1
    assert report_item(db, user.id, payload.work_date) is None
    assert report_item(db, operator.id, payload.work_date) is not None
    edited = payload.model_copy(update={'revision': row.revision, 'phone': '13977774321'})
    save_record(db, user, edited)
    assert row.phone == '13977774321' and row.owner_id == operator.id and row.updated_by == user.id
    with pytest.raises(HTTPException) as error:
        delete_record(row.id, row.revision, db, user)
    assert error.value.status_code == 403
    db.query(RolePermission).filter_by(role_id=role.id).delete(); db.flush()
    assert serialize_record(db, user, row)['phone'] == '******'
    with pytest.raises(HTTPException):
        save_record(db, user, payload.model_copy(update={'revision': row.revision}))


def test_column_filters_combine_and_match_latest_progress(db, context):
    from resource_development_service import save_record, filtered_records
    from routers.resource_development import days, records
    user, other, platform = context
    first = make_payload(context, full_name='筛选甲', phone='13855556666', actions=[action(user, '已邀进群', 'group'), action(user, '未处理', 'group')])
    save_record(db, user, first)
    save_record(db, user, make_payload(context, full_name='筛选乙', actions=[action(user, '已沟通', 'communication')]))
    params = dict(start=first.work_date, end=first.work_date, keyword=None, owner_id=None, platform_id=None, account_id=None, state=None,
                  column_filters={'platform_name':[str(platform.id)], 'full_name':'筛选', 'communication_status':['已沟通']})
    result = days(params, 0, 7, db, user)
    assert result['items'][0]['count'] == 1 and result['items'][0]['people'][0]['count'] == 1
    assert records(params, 0, 1, db, user)['total'] == 1
    assert filtered_records(db,user,first.work_date,first.work_date,column_filters={'group_status':['已邀进群']}).count() == 0
    assert filtered_records(db,user,first.work_date,first.work_date,column_filters={'phone':'5555'}).count() == 1
    assert filtered_records(db,other,first.work_date,first.work_date,column_filters={'phone':'5555'}).count() == 0
    assert filtered_records(db,user,first.work_date,first.work_date,column_filters={'latest_follow_up':user.full_name}).count() == 0


def test_cross_date_status_records_use_channel_or_and_current_status(db, context):
    from routers.resource_development import records
    from resource_development_service import save_record
    user, _, platform = context
    combinations = [
        ('未处理', '未处理'), ('未处理', '已添加'), ('已添加', '未处理'),
        ('一次请求', '一次请求'), ('一次请求', '已添加'), ('已添加', '一次请求'),
        ('一次请求未通过', '二次请求'), ('已添加', '已添加'), ('已发请求', '搜不到'),
    ]
    seeded = []
    for index, (wechat, enterprise) in enumerate(combinations):
        seeded.append(seed_name_check_record(db, context, f'跨日状态{index}',
            work_date=date(2026, 10, 1) + timedelta(days=index),
            wechat_status=wechat, enterprise_status=enterprise))
    # 曾经一次请求、目前已二次请求的记录不能再进入一次请求列表。
    payload = make_payload(context, full_name='已转二次请求', actions=[action(user, '一次请求')])
    changed = save_record(db, user, payload)
    save_record(db, user, RecordWrite.model_validate(payload.model_dump() | {
        'revision': changed.revision, 'actions': [*[entry.model_dump() for entry in payload.actions], action(user, '二次请求')]}))
    base = dict(start=None, end=None, owner_id=user.id, platform_id=platform.id)
    for state, expected in [('未处理', seeded[:3] + [changed]), ('一次请求', seeded[3:6] + [seeded[8]])]:
        result = records(dict(base, state=state), 0, 100, db, user)
        ids = [item['id'] for item in result['items']]
        assert result['total'] == len(expected) == len(set(ids))
        assert set(ids) == {str(row.id) for row in expected}
        paged = records(dict(base, state=state), 1, 2, db, user)
        assert paged['total'] == len(expected) and len(paged['items']) == 2
    bounded = records(dict(base, state='一次请求', start=date(2026, 10, 4), end=date(2026, 10, 5)), 0, 100, db, user)
    assert bounded['total'] == 2
    assert {item['id'] for item in bounded['items']} == {str(row.id) for row in seeded[3:5]}
    named = records(dict(base, state='一次请求', column_filters={'full_name': '状态4'}), 0, 100, db, user)
    assert named['total'] == 1 and named['items'][0]['id'] == str(seeded[4].id)


def test_cross_date_records_http_combines_common_and_column_filters(db, context):
    import json
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from models import Role, UserRole
    from routers.auth import get_current_user
    from routers.resource_development import router
    from resource_development_models import DevelopmentOption
    user, other, platform = context
    role = Role(id=uuid4(), role_name='admin')
    account = DevelopmentOption(id=uuid4(), kind='account', name='隔离测试账号')
    db.add_all([role, account]); db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id)); db.flush()
    wanted = seed_name_check_record(db, context, '综合筛选命中', work_date=date(2026, 10, 6),
        account_id=account.id, wechat_status='一次请求', enterprise_status='已添加')
    seed_name_check_record(db, context, '综合筛选其他账号', work_date=date(2026, 10, 7),
        wechat_status='一次请求', enterprise_status='一次请求')
    seed_name_check_record(db, context, '综合筛选其他人员', work_date=date(2026, 10, 6),
        owner_id=other.id, account_id=account.id, wechat_status='一次请求', enterprise_status='已添加')
    seed_name_check_record(db, context, '综合筛选请求未通过', work_date=date(2026, 10, 6),
        account_id=account.id, wechat_status='一次请求未通过', enterprise_status='已添加')
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    params = dict(state='一次请求', start='2026-10-06', end='2026-10-07', keyword='综合筛选',
        owner_id=str(user.id), platform_id=str(platform.id), account_id=str(account.id),
        column_filters=json.dumps({'wechat_status': ['一次请求'], 'full_name': '命中'}), limit=1)
    with TestClient(app) as client:
        response = client.get('/resource-development/records', params=params)
        assert response.status_code == 200, response.text
        assert response.json()['total'] == 1
        assert [row['id'] for row in response.json()['items']] == [str(wanted.id)]
        response = client.get('/resource-development/records', params={**params, 'skip': 1})
        assert response.status_code == 200 and response.json() == {'items': [], 'total': 1}
        cleared = client.get('/resource-development/records', params={'state': '', 'owner_id': str(user.id)})
        assert cleared.status_code == 200 and cleared.json()['total'] == 3
        assert client.get('/resource-development/records', params={**params, 'start': '无效日期'}).status_code == 422


def test_filtered_totals_contact_search_work_and_report(db, context):
    from resource_development_service import save_record, filtered_records, save_work, report_item, refresh_draft
    from task_models import DailyReport
    user, other, _ = context
    for i in range(3):
        save_record(db, user, make_payload(context, phone="13988880000"))
    params = dict(start=date(2026, 9, 24), end=date(2026, 9, 24), owner_id=user.id)
    assert filtered_records(db, user, **params).count() == 3
    assert len(filtered_records(db, user, **params).limit(2).all()) == 2
    assert filtered_records(db, other, **params, keyword="13988880000").count() == 0
    assert filtered_records(db, user, **params, keyword="13988880000").count() == 3
    work = save_work(db, user, WorkWrite(work_date=params['start'], owner_id=user.id, periods=[dict(start="09:00",end="10:30")], deduction=10, completed=False, explanation="继续联系"))
    assert report_item(db, user.id, params['start'])["duration_minutes"] == 80
    report = DailyReport(user_id=user.id, report_date=params['start'], status="draft")
    db.add(report); db.flush()
    refresh_draft(db, user.id, params['start']); db.flush()
    refresh_draft(db, user.id, params['start']); db.flush()
    assert len(report.items) == 1 and report.items[0].duration_minutes == 80
    report.status = "finalized"; db.flush()
    save_work(db, user, WorkWrite(work_date=params['start'], owner_id=user.id, revision=work.revision, periods=[dict(start="09:00",end="11:00")]))
    assert report.items[0].duration_minutes == 80
    with pytest.raises(HTTPException):
        save_work(db, other, WorkWrite(work_date=params['start'], owner_id=user.id))


def test_grouped_day_totals_and_work_only_days(db, context):
    from resource_development_service import save_record, save_work
    from routers.resource_development import days
    user, _, _ = context
    for i in range(3):
        save_record(db, user, make_payload(context))
    save_work(db, user, WorkWrite(work_date=date(2026,9,23), owner_id=user.id))
    params = dict(start=date(2026,9,23), end=date(2026,9,24), keyword=None, owner_id=user.id, platform_id=None, account_id=None, state=None)
    result = days(params=params, skip=0, limit=7, db=db, user=user)
    assert result['total'] == 2
    assert [d['count'] for d in result['items']] == [3, 0]
    assert result['items'][0]['people'][0]['count'] == 3


def test_default_query_finds_history_and_skips_work_only_dates(db, context):
    from resource_development_service import save_record, save_work
    from routers.resource_development import days, filters, records
    user, _, _ = context
    latest = date.today() - timedelta(days=30)
    older = latest - timedelta(days=1)
    for i in range(12):
        save_record(db, user, make_payload(context, work_date=latest))
    save_record(db, user, make_payload(context, work_date=older))
    save_work(db, user, WorkWrite(work_date=date.today(), owner_id=user.id))
    params = filters(keyword=None, owner_id=user.id, platform_id=None, account_id=None, state=None, column_filters=None)
    assert params['start'] is None and params['end'] is None
    result = days(params, 0, 3, db, user)
    assert result['total'] == 2
    assert [d['date'] for d in result['items']] == [latest, older]
    assert [d['count'] for d in result['items']] == [12, 1]
    page = records(params, 0, 10, db, user)
    assert page['total'] == 13 and len(page['items']) == 10
    assert all(r['work_date'] == latest.isoformat() for r in page['items'])
    day_params = dict(params, start=latest, end=latest)
    assert records(day_params, 10, 10, db, user)['total'] == 12
    assert len(records(day_params, 10, 10, db, user)['items']) == 2
    assert records(dict(params, end=older), 0, 10, db, user)['total'] == 1
    bounded = days(dict(params, start=older, end=date.today()), 0, 3, db, user)
    assert [d['count'] for d in bounded['items']] == [0, 12, 1]
    assert records(dict(params, start=date.today(), end=date.today()), 0, 10, db, user)['total'] == 0
    with pytest.raises(HTTPException) as exc:
        filters(start=latest, end=older)
    assert exc.value.status_code == 422


def test_screenshot_and_delete_permissions(db, context):
    from io import BytesIO
    from PIL import Image
    from starlette.datastructures import UploadFile
    from resource_development_service import save_record, save_work
    from routers.resource_development import upload_screenshot, read_screenshot, delete_screenshot, delete_record
    from resource_development_models import DevelopmentRecord, DevelopmentScreenshot
    user, other, _ = context
    row = save_record(db, user, make_payload(context))
    work = save_work(db, user, WorkWrite(work_date=row.work_date, owner_id=user.id))
    image = BytesIO(); Image.new('RGB', (5, 5)).save(image, format='PNG'); image.seek(0)
    result = upload_screenshot(work.id, UploadFile(filename='test.png', file=image), db, user)
    from uuid import UUID
    screenshot_id = UUID(result['id'])
    assert read_screenshot(screenshot_id, db, user).media_type == 'image/png'
    with pytest.raises(HTTPException) as exc:
        read_screenshot(screenshot_id, db, other)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        upload_screenshot(work.id, UploadFile(filename='bad.png', file=BytesIO(b'not an image')), db, user)
    with pytest.raises(HTTPException):
        delete_record(row.id, row.revision, db, other)
    with patch('resource_development_service.is_admin', return_value=True):
        assert read_screenshot(screenshot_id, db, other).status_code == 200
    delete_screenshot(screenshot_id, db, user)
    assert db.get(DevelopmentScreenshot, screenshot_id) is None
    row_id = row.id
    delete_record(row_id, row.revision, db, user)
    assert db.get(DevelopmentRecord, row_id) is None


def test_concurrent_numbering_in_isolated_schema():
    if os.getenv('RUN_RESOURCE_DEVELOPMENT_DB_TESTS') != '1':
        pytest.skip('需要局域网 PostgreSQL')
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from database import engine
    from resource_development_service import allocate_greeting
    assert engine.url.host in {'localhost', '127.0.0.1', '192.168.31.144'}, '数据库回归仅允许连接局域网或隔离数据库'
    schema = 'test_development_' + uuid4().hex
    platform = SimpleNamespace(id=uuid4(), code='BOSS1')
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'CREATE TABLE "{schema}".resource_development_counter (platform_id uuid, work_date date, value integer NOT NULL, PRIMARY KEY(platform_id,work_date))'))
        def allocate(_):
            with engine.begin() as conn:
                conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                with Session(bind=conn) as session:
                    return allocate_greeting(session, platform, date(2026,9,24))
        with ThreadPoolExecutor(max_workers=6) as pool:
            numbers = list(pool.map(allocate, range(18)))
        assert len(set(numbers)) == 18
        assert set(numbers) == {f'BOSS1-260924-{i:03d}' for i in range(1,19)}
        with engine.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".resource_development_counter SET value=999'))
        assert allocate(0) == 'BOSS1-260924-1000'
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

@pytest.mark.parametrize('channel,status', [('wechat','已添加'),('enterprise','已添加'),('group','已进群'),('group_large','已进群')])
@pytest.mark.parametrize('historical', [False, True])
def test_private_entry_new_followup_enrolls_once(db, context, channel, status, historical):
    from resource_development_service import save_record
    from resource_models import ResourcePerson
    from resource_development_schemas import ActionWrite
    user, _, _ = context
    payload = make_payload(context, capabilities=['annotation'])
    row = save_record(db, user, payload, historical_markers={} if historical else None)
    confirmed = ActionWrite(**action(user, status, channel))
    changed = payload.model_copy(update={'revision':row.revision, 'actions':[confirmed]})
    row = save_record(db, user, changed)
    person_id = row.person_id
    assert person_id and db.get(ResourcePerson, person_id).full_name == payload.full_name
    assert row.historical_only == historical
    # 另一渠道成功以及重复提交不重复建档。
    if channel in {'group', 'group_large'}:
        from resource_development_service import serialize_record
        confirmed = ActionWrite(**{key: value for key, value in serialize_record(db, user, row, True)['actions'][0].items() if key in ActionWrite.model_fields})
    changed = changed.model_copy(update={'revision':row.revision, 'actions':[confirmed, ActionWrite(**action(user,'已添加','enterprise'))]})
    assert save_record(db, user, changed).person_id == person_id
    assert db.query(ResourcePerson).filter_by(full_name=payload.full_name).count() == 1
    # 撤销成功状态不删除已关联的人才。
    from resource_development_service import serialize_record
    from resource_development_schemas import ActionWrite
    saved = [ActionWrite(**{key: value for key, value in entry.items() if key in ActionWrite.model_fields}) for entry in serialize_record(db, user, row, True)['actions']]
    changed = changed.model_copy(update={'revision':row.revision, 'actions':saved + [ActionWrite(**action(user, '已退群', channel))] if channel in {'group', 'group_large'} else [a.model_copy(update={'status':'未处理'}) for a in changed.actions]})
    assert save_record(db, user, changed).person_id == person_id
    assert db.get(ResourcePerson, person_id)


def test_historical_group_append_only_success_triggers(db, context):
    from resource_development_service import save_record
    user, _, _ = context
    payload = make_payload(context, actions=[action(user,'已邀进群','group')], capabilities=['annotation'])
    row = save_record(db,user,payload,historical_markers={'wechat':{'status':'已添加'}})
    from resource_development_service import serialize_record
    from resource_development_schemas import ActionWrite
    saved = [ActionWrite(**{key: value for key, value in entry.items() if key in ActionWrite.model_fields}) for entry in serialize_record(db, user, row, True)['actions']]
    edited = payload.model_copy(update={'revision':row.revision,'remarks':'只修正备注','actions':saved})
    save_record(db,user,edited)
    assert row.person_id is None
    edited = edited.model_copy(update={'revision':row.revision,'actions':saved + [ActionWrite(**action(user, '已进群', 'group'))]})
    assert save_record(db,user,edited).person_id


@pytest.mark.parametrize('channel,status', [('group','已邀进群'),('group','已退群'),('group_large','已发码'),('group_large','已退群'),('communication','已沟通'),('project','已入项'),('wechat','自定义已添加好友')])
def test_non_private_states_do_not_enroll(db, context, channel, status):
    from resource_development_service import save_record
    user, _, _ = context
    assert save_record(db,user,make_payload(context,actions=[action(user,status,channel)])).person_id is None


def test_group_action_server_identity_history_and_alias(db, context):
    from resource_development_service import save_record, serialize_record, group_action_date, filtered_records
    from resource_development_schemas import ActionWrite
    from resource_development_models import DevelopmentAction
    user, other, _ = context
    old = action(other, '已邀进群', 'group')
    payload = make_payload(context, actions=[old])
    row = save_record(db, user, payload)
    detail = serialize_record(db, user, row, True)
    assert detail['progress']['group']['status'] == '已拉群'
    first = db.get(DevelopmentAction, old['id'])
    assert first.operator_id == user.id and first.action_date == group_action_date()
    saved = ActionWrite(**{key: value for key, value in detail['actions'][0].items() if key in ActionWrite.model_fields})
    latest = ActionWrite(**action(other, '已发码', 'group_large'))
    row = save_record(db, user, payload.model_copy(update={'revision': row.revision, 'actions': [saved, latest]}))
    result = serialize_record(db, user, row, True)
    assert result['progress']['group']['status'] == '已拉群'
    assert result['progress']['group_large']['status'] == '已发码'
    assert len(result['actions']) == 2 and result['actions'][-1]['operator_name'] == user.full_name
    for field, status in [('group_status', '已拉群'), ('group_large_status', '已发码')]:
        assert filtered_records(db, user, payload.work_date, payload.work_date, column_filters={field: [status]}).filter_by(id=row.id).count() == 1
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException, match='已保存的群操作记录不能修改'):
            save_record(db, user, payload.model_copy(update={'revision': row.revision, 'actions': [saved.model_copy(update={'status': '已退群'}), latest]}))
        nested.rollback()
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException, match='支持的状态'):
            save_record(db, user, make_payload(context, actions=[action(user, '已发码', 'group')]))
        nested.rollback()
    historical = save_record(db, user, make_payload(context), historical_markers={'group': {'status': '已邀进群', 'operator_name': '旧操作人', 'action_date': '2025-01-01', 'source': '私密来源'}})
    with patch('resource_development_service.can_delegate', return_value=False):
        public = serialize_record(db, other, historical, True)
    assert public['historical_markers'] == {}
    assert public['historical_progress']['group']['status'] == '已拉群'
    assert 'source' not in public['historical_progress']['group']


def test_group_quick_action_permissions_conflict_and_idempotency(db, context):
    from routers.resource_development import write_group_action
    from resource_development_service import save_record, serialize_record
    from resource_development_schemas import GroupActionWrite
    user, other, _ = context
    row = save_record(db, user, make_payload(context))
    payload = GroupActionWrite(id=uuid4(), revision=row.revision, channel='group_large', status='已发码')
    with patch('resource_development_service.can_delegate', return_value=False):
        with pytest.raises(HTTPException) as exc:
            write_group_action(row.id, payload, db, other)
        assert exc.value.status_code == 403
    result = write_group_action(row.id, payload, db, user)
    assert result['progress']['group_large']['status'] == '已发码'
    assert len(write_group_action(row.id, payload, db, user)['actions']) == 1
    with pytest.raises(HTTPException) as exc:
        write_group_action(row.id, payload.model_copy(update={'id': uuid4()}), db, user)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        write_group_action(row.id, GroupActionWrite(id=uuid4(), revision=row.revision, channel='group', status='已进群'), db, user)
    assert exc.value.detail['code'] == 'enrollment_required'
    assert len(serialize_record(db, user, row, True)['actions']) == 1


def test_private_entry_final_status_and_transaction_rollback(db, context):
    from resource_development_service import save_record
    from resource_models import ResourcePerson
    from resource_development_models import DevelopmentAction, DevelopmentRecord
    user, _, _ = context
    # 同次提交最后状态不是成功时不建档。
    row = save_record(db,user,make_payload(context,actions=[action(user,'已进群','group'),action(user,'未处理','group')]))
    assert row.person_id is None
    payload = make_payload(context,actions=[action(user,'已进群','group')])
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException) as exc:
            save_record(db,user,payload)
        assert exc.value.status_code == 422
        nested.rollback()
    assert db.get(DevelopmentRecord,payload.id) is None
    assert db.query(DevelopmentAction).filter_by(record_id=payload.id).count() == 0
    with db.begin_nested() as nested:
        created = save_record(db,user,payload.model_copy(update={'capabilities':['annotation']}))
        person_id = created.person_id
        nested.rollback()
    assert db.get(ResourcePerson,person_id) is None
    assert db.get(DevelopmentRecord,payload.id) is None


def test_friend_follow_up_uses_actual_operator_and_latest_friend_channel(db, context):
    from resource_development_service import save_record, serialize_record, filtered_records
    user, other, _ = context
    payload = make_payload(context, actions=[action(other, '二次添加'), action(user, '已沟通', 'communication')])
    row = save_record(db, user, payload)
    detail = serialize_record(db, user, row, True)
    assert detail['add_friend_follow_up'] == f'二次请求 · 2026-09-24 · {other.full_name} · 微信'
    assert detail['actions'][0]['request_number'] == 2
    assert row.person_id is None
    assert filtered_records(db, user, row.work_date, row.work_date, column_filters={'latest_follow_up': other.full_name}).count() == 0
    assert filtered_records(db, user, row.work_date, row.work_date, column_filters={'latest_follow_up': '已沟通'}).count() == 0


def test_keyword_language_search_matches_list_and_day_totals(db, context):
    from interpretation_models import InterpretationLanguage
    from resource_development_service import save_record
    from routers.resource_development import days, records
    user, _, _ = context
    language = InterpretationLanguage(id=uuid4(), label='测试检索方言' + uuid4().hex[:8], language_type='dialect', is_active=True)
    db.add(language); db.flush()
    payload = make_payload(context, language_ids=[language.id])
    save_record(db, user, payload)
    params = dict(start=payload.work_date, end=payload.work_date, keyword=language.label, owner_id=None, platform_id=None, account_id=None, state=None, column_filters={})
    assert records(params, 0, 10, db, user)['total'] == 1
    assert days(params, 0, 7, db, user)['items'][0]['count'] == 1


def test_keyword_platform_search_matches_pagination_and_day_totals(db, context):
    from resource_development_models import DevelopmentOption
    from resource_development_service import save_record
    from routers.resource_development import days, records
    user, other, platform = context
    fragment = '平台检索' + uuid4().hex[:8]
    platform.name = 'QA-' + fragment + '-Platform'
    unrelated = DevelopmentOption(id=uuid4(), kind='platform', category='national', name='其他平台' + uuid4().hex, code='OTHER' + uuid4().hex[:12])
    db.add(unrelated); db.flush()
    payload = make_payload(context)
    first = save_record(db, user, payload)
    second = save_record(db, user, make_payload(context, work_date=payload.work_date - timedelta(days=1)))
    save_record(db, user, make_payload(context, platform_id=unrelated.id))
    params = dict(start=None, end=None, keyword='  qa-' + fragment + '  ', owner_id=None, platform_id=None, account_id=None, state=None, column_filters={})
    # 平台名称支持部分匹配、忽略大小写和首尾空格，并沿用公开字段的可见范围。
    page = records(params, 0, 1, db, other)
    assert page['total'] == 2 and [r['id'] for r in page['items']] == [str(first.id)]
    next_page = records(params, 1, 1, db, other)
    assert next_page['total'] == 2 and [r['id'] for r in next_page['items']] == [str(second.id)]
    grouped = days(params, 0, 7, db, other)
    assert grouped['total'] == 2 and [d['count'] for d in grouped['items']] == [1, 1]
    assert records(dict(params, platform_id=unrelated.id), 0, 10, db, other)['total'] == 0
    assert records(dict(params, keyword='不存在' + fragment), 0, 10, db, other)['total'] == 0


@pytest.mark.parametrize('channel', ['wechat', 'enterprise'])
@pytest.mark.parametrize('old,new', [('已发请求', '一次请求'), ('二次添加', '二次请求'), ('三次添加', '三次请求')])
def test_friend_status_alias_preserves_history_and_matches_filters(db, context, channel, old, new):
    from resource_development_service import save_record, serialize_record, filtered_records
    from resource_development_models import DevelopmentAction, DevelopmentAudit
    from resource_development_schemas import ActionWrite
    user, other, _ = context
    payload = make_payload(context, phone='13912340000', actions=[action(user, new, channel)])
    row = save_record(db, user, payload)
    saved = db.get(DevelopmentAction, payload.actions[0].id)
    # 模拟升级前已保存的记录，不运行迁移、不重写历史审计。
    saved.status = old
    setattr(row, channel + '_status', old)
    db.flush()
    audit_count = db.query(DevelopmentAudit).filter_by(entity_id=saved.id).count()
    updated_at, updated_by = saved.updated_at, saved.updated_by
    for viewer in [user, other]:
        detail = serialize_record(db, viewer, row, True)
        assert detail[channel + '_status'] == new
        assert detail['progress'][channel]['status'] == new
        assert detail['actions'][0]['status'] == new
        assert detail['add_friend_follow_up'].startswith(new + ' · ')
    assert serialize_record(db, other, row)['phone'] == '******'
    for value in [old, new]:
        assert filtered_records(db, other, row.work_date, row.work_date, state=value).count() == 1
        assert filtered_records(db, other, row.work_date, row.work_date, column_filters={channel + '_status': [value]}).count() == 1
    assert filtered_records(db, user, row.work_date, row.work_date, column_filters={'latest_follow_up': new[:2]}).count() == 0
    normalized = ActionWrite(**{key: detail['actions'][0][key] for key in ['id', 'channel', 'status', 'action_date', 'operator_id', 'account_id']})
    save_record(db, user, payload.model_copy(update={'revision': row.revision, 'actions': [normalized]}))
    assert saved.status == old and getattr(row, channel + '_status') == old
    assert (saved.updated_at, saved.updated_by) == (updated_at, updated_by)
    assert db.query(DevelopmentAudit).filter_by(entity_id=saved.id).count() == audit_count
    historical = save_record(db, user, make_payload(context), historical_markers={channel: {'status': old}})
    assert serialize_record(db, other, historical)['progress'][channel]['status'] == new
    assert filtered_records(db, other, row.work_date, row.work_date, state=new).count() == 2
    assert filtered_records(db, other, row.work_date, row.work_date, column_filters={channel + '_status': [new]}).count() == 2
    # 新版和旧版客户端新增的操作均按规范名称保存。
    fresh = save_record(db, user, make_payload(context, actions=[action(user, old, channel)]))
    assert getattr(fresh, channel + '_status') == new


@pytest.mark.parametrize('channel', ['wechat', 'enterprise'])
@pytest.mark.parametrize('status', ['一次请求', '二次请求', '三次请求', '一次请求未通过', '二次请求未通过', '三次请求未通过', '（对方）已删'])
def test_friend_non_success_status_is_public_and_does_not_enroll(db, context, channel, status):
    from resource_development_service import save_record, serialize_record, filtered_records
    user, other, _ = context
    row = save_record(db, user, make_payload(context, actions=[action(user, status, channel)], phone='13912340000'))
    assert row.person_id is None
    detail = serialize_record(db, other, row, True)
    assert detail[channel + '_status'] == status
    assert detail['progress'][channel]['status'] == status
    assert detail['actions'][0]['status'] == status
    assert detail['add_friend_follow_up'].startswith(status + ' · ')
    assert detail['phone'] == '******'
    assert filtered_records(db, other, row.work_date, row.work_date, state=status).count() == 1
    assert filtered_records(db, other, row.work_date, row.work_date, column_filters={channel + '_status': [status]}).count() == 1
    if status.endswith('未通过') or status == '（对方）已删':
        assert detail['actions'][0]['request_number'] == 0


def test_friend_request_failures_do_not_increment_request_count(db, context):
    from resource_development_service import save_record, serialize_record
    user, _, _ = context
    statuses = ['一次请求', '一次请求未通过', '二次请求', '二次请求未通过', '三次请求', '三次请求未通过', '（对方）已删']
    row = save_record(db, user, make_payload(context, actions=[action(user, status) for status in statuses]))
    assert [a['request_number'] for a in serialize_record(db, user, row, True)['actions']] == [1, 0, 2, 0, 3, 0, 0]
    assert row.person_id is None


@pytest.mark.parametrize('channel', ['wechat', 'enterprise'])
def test_friend_deleted_retains_existing_talent(db, context, channel):
    from resource_development_service import save_record
    from resource_development_schemas import ActionWrite
    from resource_models import ResourcePerson
    user, _, _ = context
    payload = make_payload(context, actions=[action(user, '已添加', channel)], capabilities=['annotation'])
    row = save_record(db, user, payload)
    person_id = row.person_id
    changed = payload.model_copy(update={'revision': row.revision, 'actions': [*payload.actions, ActionWrite(**action(user, '（对方）已删', channel))]})
    assert save_record(db, user, changed).person_id == person_id
    assert db.get(ResourcePerson, person_id)
