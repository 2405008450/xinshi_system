"""渠道资料回归，数据库测试仅在本机隔离环境运行，逐例回滚。"""
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from resource_channel_schemas import ChannelWrite, ChannelDescriptionWrite


def test_validation_and_member_deduplication():
    person = uuid4()
    payload = ChannelWrite(name="  渠道  ", category="national", maintainer_ids=[person, person], user_ids=[person])
    assert payload.name == "渠道" and payload.maintainer_ids == [person] and payload.user_ids == [person]
    for fields in [dict(name=" "), dict(name="x" * 101), dict(category="other"), dict(purpose="x" * 2001), dict(description="x" * 5001), dict(created_by=person)]:
        with pytest.raises(ValidationError):
            ChannelWrite(**(dict(name="渠道", category="national") | fields))
    with pytest.raises(ValidationError):
        ChannelDescriptionWrite(description="说明", revision=0)


@pytest.fixture
def db():
    if os.getenv("RUN_RESOURCE_DEVELOPMENT_DB_TESTS") != "1":
        pytest.skip("数据库回归需在本机隔离库显式启用")
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    assert engine.url.host in {"localhost", "127.0.0.1"}, "只允许本机隔离数据库"
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def people(db):
    from models import AppUser
    rows = [AppUser(id=uuid4(), username="channel_test_" + uuid4().hex, full_name=name, password_hash="no-login", is_active=active)
            for name, active in [("操作人员", True), ("维护人员", True), ("使用人员", True), ("已停用人员", False)]]
    db.add_all(rows); db.flush()
    return rows


def new_channel(db, people, **fields):
    from resource_channel_service import save_channel
    payload = ChannelWrite(**(dict(name="渠道测试" + uuid4().hex, category="national", purpose="招聘与寻访", description="原说明",
                                  maintainer_ids=[people[1].id], user_ids=[people[1].id, people[2].id]) | fields))
    return save_channel(db, people[0], payload)


def test_arrangement_platform_metadata_is_readonly_and_compatible(db, people, monkeypatch):
    import resource_channel_service as service
    from resource_development_models import DevelopmentOption
    from routers.resource_development import options

    one = new_channel(db, people, category="local", description="账号自身说明")
    two = new_channel(db, people, category="international")
    parent = new_channel(db, people, is_group=True, category="national", account_ids=[one["id"], two["id"]],
                         account_revisions={one["id"]: 1, two["id"]: 1})
    standalone = new_channel(db, people, category="local")
    stored = db.get(DevelopmentOption, one["id"])
    before = (stored.category, stored.revision, stored.code, stored.description)
    result = options(db, people[0])
    metadata = {item["id"]: item for item in result["arrangement_platforms"]}
    assert metadata[one["id"]]["parent_id"] == parent["id"]
    assert metadata[one["id"]]["parent_name"] == parent["name"]
    assert metadata[one["id"]]["category"] == "national"
    assert metadata[one["id"]]["description"] == "账号自身说明"
    assert metadata[parent["id"]]["has_accounts"] is True
    assert metadata[parent["id"]]["kind"] == "channel_group"
    assert metadata[standalone["id"]]["parent_id"] is None
    assert metadata[standalone["id"]]["category"] == "local"
    legacy = {item["id"]: item for item in result["options"]}
    assert legacy[one["id"]]["category"] == "local" and parent["id"] not in legacy
    assert (stored.category, stored.revision, stored.code, stored.description) == before

    # 未迁移归属关系表的环境只读取原账号，不访问关系表或猜测归属。
    monkeypatch.setattr(service, "hierarchy_available", lambda _: False)
    fallback = {item["id"]: item for item in service.arrangement_platforms(db)}
    assert fallback[one["id"]]["parent_id"] is None
    assert fallback[one["id"]]["category"] == "local"
    assert fallback[parent["id"]]["has_accounts"] is False


def test_options_default_date_uses_business_clock(db, people, monkeypatch):
    from datetime import datetime
    import routers.resource_development as route
    monkeypatch.setattr(route, "business_now", lambda: datetime(2026, 10, 13, 0, 1))
    assert route.options(db, people[0])["default_date"] == "2026-10-12"


def test_shared_description_preserves_members_and_audits(db, people):
    from resource_channel_service import save_description, read_channel
    from resource_development_models import DevelopmentAudit
    from resource_development_schemas import OptionWrite
    from routers.resource_development import update_option, options
    row = new_channel(db, people)
    assert row["created_by"] == str(people[0].id) and row["created_at"]
    # 旧说明接口与独立说明接口共用平台版本和分工，旧请求没有用途字段也不会清空用途。
    updated = update_option(row["id"], OptionWrite(kind="platform", name=row["name"], category="national", description="开拓入口说明", revision=1), db, people[0])
    assert updated["revision"] == 2 and updated["purpose"] == row["purpose"]
    assert updated["maintainers"] == row["maintainers"] and updated["users"] == row["users"]
    with pytest.raises(HTTPException) as conflict:
        save_description(db, people[0], row["id"], "旧版本覆盖", 1)
    assert conflict.value.status_code == 409
    latest = save_description(db, people[2], row["id"], "渠道入口说明", 2)
    assert latest["revision"] == 3 and read_channel(db, row["id"])["description"] == "渠道入口说明"
    entry = next(item for item in options(db, people[0])["options"] if item["id"] == row["id"])
    assert entry["description"] == "渠道入口说明"
    db.flush()
    audit = db.query(DevelopmentAudit).filter_by(entity_id=row["id"], action="update").order_by(DevelopmentAudit.created_at.desc()).first()
    assert audit.before["description"] == "开拓入口说明" and audit.after["description"] == "渠道入口说明"
    assert audit.after["maintainers"] == row["maintainers"]


def test_rename_category_duplicate_and_identifier_stability(db, people):
    from resource_channel_service import save_channel, read_channel
    from resource_development_models import DevelopmentOption, DevelopmentCounter
    from resource_development_service import allocate_greeting
    from datetime import date
    row = new_channel(db, people)
    stored = db.get(DevelopmentOption, row["id"])
    number = allocate_greeting(db, stored, date(2026, 10, 8))
    updated = save_channel(db, people[0], ChannelWrite(name="更名" + uuid4().hex, category="international", revision=1), row["id"])
    assert updated["id"] == row["id"] and updated["code"] == row["code"]
    assert number.startswith(row["code"]) and db.get(DevelopmentCounter, (stored.id, date(2026, 10, 8))).value == 1
    with pytest.raises(HTTPException) as duplicate:
        new_channel(db, people, name="  " + updated["name"].upper() + "  ")
    assert duplicate.value.status_code == 409
    assert read_channel(db, row["id"])["category"] == "international"


def test_filter_roles_and_literal_keyword_pagination(db, people):
    from resource_channel_service import list_channels, save_channel
    from resource_development_models import DevelopmentOption
    prefix = "筛选" + uuid4().hex
    first = new_channel(db, people, name=prefix + "A", purpose="包含%_文字")
    second = new_channel(db, people, name=prefix + "B", category="local", maintainer_ids=[people[2].id], user_ids=[people[1].id])
    db.add(DevelopmentOption(kind="account", name=prefix + "账号")); db.flush()
    assert list_channels(db, keyword=prefix)["total"] == 2
    page = list_channels(db, keyword=prefix, skip=1, limit=1)
    assert page["total"] == 2 and page["items"][0]["id"] == second["id"]
    assert list_channels(db, keyword="%_")["items"][0]["id"] == first["id"]
    assert list_channels(db, keyword=prefix, maintainer_ids=[people[1].id, people[2].id])["total"] == 2
    assert list_channels(db, keyword=prefix, maintainer_ids=[people[2].id], user_ids=[people[2].id])["total"] == 0
    assert list_channels(db, keyword=prefix, category="local", user_ids=[people[1].id])["total"] == 1


def test_inactive_people_only_retained_in_original_role(db, people):
    from resource_channel_service import read_channel, save_channel
    from resource_development_models import DevelopmentChannelMember
    from routers.resource_channels import read_people
    from resource_development_models import DevelopmentOption
    row = new_channel(db, people)
    platform_id = db.get(DevelopmentOption, row["id"]).id
    db.add(DevelopmentChannelMember(platform_id=platform_id, user_id=people[3].id, role="maintainer")); db.flush()
    payload = ChannelWrite(name=row["name"], category="national", maintainer_ids=[people[3].id], revision=1)
    saved = save_channel(db, people[0], payload, row["id"])
    assert saved["maintainers"][0]["is_active"] is False
    assert any(p["id"] == str(people[3].id) for p in read_people(db))
    with pytest.raises(HTTPException) as inactive:
        save_channel(db, people[0], payload.model_copy(update={"revision": 2, "user_ids": [people[3].id]}), row["id"])
    assert inactive.value.status_code == 422
    with pytest.raises(HTTPException):
        new_channel(db, people, maintainer_ids=[uuid4()])
    save_channel(db, people[0], payload.model_copy(update={"revision": 2, "maintainer_ids": []}), row["id"])
    assert not read_channel(db, row["id"])["maintainers"]


def test_read_and_write_permissions_and_multivalue_query(db, people, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import auth
    from routers.resource_development import router
    permissions = ["talents:read"]
    monkeypatch.setattr(auth, "get_user_permission_codes", lambda *_: permissions)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: people[0]
    client = TestClient(app)
    row = new_channel(db, people)
    path = "/resource-development/channels"
    response = client.get(path, params=[("maintainer_ids", str(people[1].id)), ("maintainer_ids", str(people[2].id)), ("keyword", row["name"])])
    assert response.status_code == 200 and response.json()["total"] == 1
    assert client.get(path + "/people").status_code == 200
    assert client.get(path + "/" + row["id"]).status_code == 200
    assert client.post(path, json={"name": "无权限", "category": "national"}).status_code == 403
    assert client.put(path + "/" + row["id"] + "/description", json={"description": "无权限", "revision": 1}).status_code == 403
    permissions[:] = ["talents:write"]
    assert client.put(path + "/" + row["id"] + "/description", json={"description": "有权限", "revision": 1}).status_code == 200
    permissions.clear()
    assert client.get(path).status_code == 403


def test_account_cannot_be_read_as_channel(db, people):
    from resource_channel_service import read_channel
    from resource_development_models import DevelopmentOption
    account = DevelopmentOption(kind="account", name="账号" + uuid4().hex)
    db.add(account); db.flush()
    with pytest.raises(HTTPException) as error:
        read_channel(db, account.id)
    assert error.value.status_code == 404


def channel_payload(row, **fields):
    return ChannelWrite(**(dict(name=row['name'], category=row['category'], purpose=row['purpose'], description=row['description'],
                               revision=row['revision'], maintainer_ids=[p['id'] for p in row['direct_maintainers']],
                               user_ids=[p['id'] for p in row['direct_users']]) | fields))


def test_account_group_preserves_history_and_deduplicates_roles(db, people):
    from datetime import date
    from resource_channel_service import save_channel, read_channel, list_channels
    from resource_development_models import DevelopmentOption, DevelopmentRecord, DevelopmentArrangement, DevelopmentArrangementCell
    from resource_development_service import allocate_greeting
    from routers.resource_development import options
    one = new_channel(db, people, name='BOSS 1 ' + uuid4().hex)
    two = new_channel(db, people, name='BOSS 2 ' + uuid4().hex)
    stored = db.get(DevelopmentOption, one['id'])
    record = DevelopmentRecord(platform_id=stored.id, greeting_no=allocate_greeting(db, stored, date(2026, 10, 12)),
                               work_date=date(2026, 10, 12), owner_id=people[0].id, full_name='历史人员', created_by=people[0].id, updated_by=people[0].id)
    day = DevelopmentArrangement(work_date=date(2040, 10, 12), created_by=people[0].id, updated_by=people[0].id)
    db.add_all([record, day]); db.flush()
    cell = DevelopmentArrangementCell(arrangement_id=day.id, platform_id=stored.id, platform_name=one['name'], remarks='历史备注', completed=True)
    db.add(cell); db.flush()
    old = (record.platform_id, record.greeting_no, cell.platform_id, cell.platform_name, cell.remarks, cell.completed, stored.code)
    parent = new_channel(db, people, name='BOSS直聘 ' + uuid4().hex, is_group=True,
                         account_ids=[one['id'], two['id']], account_revisions={one['id']: 1, two['id']: 1},
                         maintainer_ids=[people[0].id], user_ids=[])
    assert parent['kind'] == 'channel_group' and len(parent['accounts']) == 2
    assert [p['id'] for p in parent['maintainers']] == [str(people[1].id)]
    assert {p['id'] for p in parent['users']} == {str(people[1].id), str(people[2].id)}
    assert all(a['description'] == '原说明' and a['parent_id'] == parent['id'] for a in parent['accounts'])
    assert read_channel(db, one['id'])['id'] == one['id']
    assert (record.platform_id, record.greeting_no, cell.platform_id, cell.platform_name, cell.remarks, cell.completed, stored.code) == old
    result = list_channels(db, keyword=one['name'])
    assert result['total'] == 1 and result['items'][0]['id'] == parent['id'] and result['items'][0]['expand_accounts']
    choices = options(db, people[0])['options']
    assert one['id'] in {o['id'] for o in choices} and parent['id'] not in {o['id'] for o in choices}
    assert parent['created_at'].endswith('+08:00')


def test_group_filters_use_effective_roles_and_restore_direct_members(db, people):
    from resource_channel_service import save_channel, read_channel, list_channels
    from resource_development_models import DevelopmentOption
    one = new_channel(db, people)
    parent = new_channel(db, people, maintainer_ids=[people[0].id], user_ids=[])
    parent = save_channel(db, people[0], channel_payload(parent, account_ids=[one['id']], account_revisions={one['id']: 1}), parent['id'])
    assert parent['direct_maintainers'][0]['id'] == str(people[0].id)
    assert list_channels(db, keyword=parent['name'], maintainer_ids=[people[0].id])['total'] == 0
    assert list_channels(db, keyword=parent['name'], maintainer_ids=[people[1].id], user_ids=[people[2].id])['total'] == 1
    assert list_channels(db, keyword=parent['name'], maintainer_ids=[people[1].id], user_ids=[people[0].id])['total'] == 0
    parent = save_channel(db, people[0], channel_payload(parent, account_ids=[], account_revisions={one['id']: 2}), parent['id'])
    assert not parent['accounts'] and parent['maintainers'][0]['id'] == str(people[0].id)
    assert read_channel(db, one['id'])['parent_id'] is None
    assert db.get(DevelopmentOption, one['id']) is not None


def test_group_transfer_versions_and_legacy_child_write(db, people):
    from resource_channel_service import save_channel, read_channel, save_description
    from resource_channel_models import ChannelAccountLink
    one = new_channel(db, people)
    parent = new_channel(db, people, is_group=True, account_ids=[one['id']], account_revisions={one['id']: 1})
    # 旧客户端不携带归属字段时保持关系，修改子账号同步使父平台版本过期。
    child = read_channel(db, one['id'])
    child = save_channel(db, people[0], channel_payload(child, user_ids=[people[0].id]), child['id'])
    assert child['parent_id'] == parent['id']
    latest_parent = read_channel(db, parent['id'])
    assert latest_parent['revision'] == parent['revision'] + 1
    assert latest_parent['users'][0]['id'] == str(people[0].id)
    with pytest.raises(HTTPException) as stale:
        save_channel(db, people[0], channel_payload(parent, account_ids=[]), parent['id'])
    assert stale.value.status_code == 409
    target = new_channel(db, people, is_group=True)
    with pytest.raises(HTTPException) as stale_account:
        save_channel(db, people[0], channel_payload(target, account_ids=[one['id']], account_revisions={one['id']: 2}), target['id'])
    assert stale_account.value.status_code == 409
    moved = save_channel(db, people[0], channel_payload(target, account_ids=[one['id']], account_revisions={one['id']: child['revision']}), target['id'])
    assert moved['accounts'][0]['id'] == one['id'] and not read_channel(db, parent['id'])['accounts']
    assert db.query(ChannelAccountLink).filter_by(account_id=one['id']).count() == 1
    child = read_channel(db, one['id'])
    saved = save_description(db, people[0], child['id'], '账号独立说明', child['revision'])
    assert saved['description'] == '账号独立说明'
    assert read_channel(db, target['id'])['description'] == target['description']


def test_group_prevents_cycles_nested_groups_and_invalid_accounts(db, people):
    from resource_channel_service import save_channel
    one = new_channel(db, people)
    parent = new_channel(db, people, is_group=True, account_ids=[one['id']], account_revisions={one['id']: 1})
    for ids in [[parent['id']], [uuid4()]]:
        with pytest.raises(HTTPException) as error:
            save_channel(db, people[0], channel_payload(parent, account_ids=ids), parent['id'])
        assert error.value.status_code == 422
    child = parent['accounts'][0]
    with pytest.raises(HTTPException) as nested:
        save_channel(db, people[0], channel_payload(child, account_ids=[parent['id']]), child['id'])
    assert nested.value.status_code == 422


def test_hierarchy_missing_table_legacy_read_and_write(db, people, monkeypatch):
    import resource_channel_service as service
    monkeypatch.setattr(service, 'hierarchy_available', lambda _: False)
    row = new_channel(db, people)
    result = service.list_channels(db, keyword=row['name'])
    assert result['total'] == 1 and not result['hierarchy_available'] and not result['items'][0]['accounts']
    updated = service.save_channel(db, people[0], channel_payload(row, description='兼容说明'), row['id'])
    assert updated['description'] == '兼容说明'
    with pytest.raises(HTTPException) as blocked:
        service.save_channel(db, people[0], channel_payload(updated, account_ids=[uuid4()]), row['id'])
    assert blocked.value.status_code == 503
