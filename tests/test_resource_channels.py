"""渠道资料回归，数据库测试仅在局域网隔离环境运行，逐例回滚。"""
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
        pytest.skip("数据库回归需在局域网显式启用")
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    assert engine.url.host in {"localhost", "127.0.0.1", "192.168.31.144"}, "禁止连接生产数据库"
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
