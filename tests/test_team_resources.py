"""团队资源契约、权限与数据库回归；数据库仅允许显式隔离库。"""
import os
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from team_resource_schemas import TeamWrite


def payload(**fields):
    return TeamWrite(**({"short_name": "测试团队", "team_type": "small_team", "resource_types": ["annotation"]} | fields))


@pytest.fixture(autouse=True)
def contact_permissions(monkeypatch):
    import team_resource_service
    from routers import teams
    monkeypatch.setattr(team_resource_service, "can_view_talent_contacts", lambda *_: True)
    monkeypatch.setattr(teams, "can_view_talent_contacts", lambda *_: True)


def test_contact_contract():
    assert payload(contacts=[{"name": " 张三 ", "nickname": " 小张 "}]).contacts[0].name == "张三"
    assert payload(contacts=[{"nickname": "小张"}]).contacts[0].name == ""
    assert payload().contacts is None
    for contacts in [[{}], [{"contact_info": "123"}], [{"name": "甲"}] * 4, [{"name": "字" * 101}],
                     [{"name": "甲", "contact_info": "字" * 1001}], [{"id": str(uuid4()), "name": "甲", "unknown": "字段"}]]:
        with pytest.raises(ValidationError):
            payload(contacts=contacts)
    contact_id = str(uuid4())
    with pytest.raises(ValidationError):
        payload(contacts=[{"id": contact_id, "name": "甲"}, {"id": contact_id, "name": "乙"}])


def test_contact_privacy_preparation():
    from team_resource_service import prepare_contacts
    existing = [{"id": str(uuid4()), "name": "甲", "nickname": "小甲", "contact_info": "secret-phone"},
                {"id": str(uuid4()), "name": "乙", "nickname": "", "contact_info": "secret-email"}]
    changed = [{"id": item["id"], "name": item["name"] + "修改"} for item in reversed(existing)]
    retained = prepare_contacts(payload(contacts=changed), existing, contacts_visible=False)
    assert [item["contact_info"] for item in retained] == ["secret-email", "secret-phone"]
    assert prepare_contacts(payload(), existing, contacts_visible=False) == existing
    for contacts in [[], [{"name": "新联系人", "contact_info": "illegal"}], [changed[0]], [{"id": str(uuid4()), "name": "伪造"}]]:
        with pytest.raises(HTTPException):
            prepare_contacts(payload(contacts=contacts), existing, contacts_visible=False)
    assert prepare_contacts(payload(contacts=[]), existing, contacts_visible=True) == []


def test_contact_api_privacy_and_audit(db, people, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import auth, teams
    import team_resource_service as service
    from team_resource_models import TeamResourceAudit
    visible = [True]
    monkeypatch.setattr(auth, "get_user_permission_codes", lambda *_: ["talents:write"])
    monkeypatch.setattr(teams, "user_has_permission", lambda *_: True)
    monkeypatch.setattr(teams, "can_view_talent_contacts", lambda *_: visible[0])
    monkeypatch.setattr(service, "can_view_talent_contacts", lambda *_: visible[0])
    app = FastAPI(); app.include_router(teams.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: people[0]
    client = TestClient(app)
    row = client.post('/teams', json=payload(contacts=[{"name": "张三", "nickname": "小张", "contact_info": "private-phone"}]).model_dump(mode='json')).json()
    assert row['contacts'][0]['contact_info'] == 'private-phone'
    contact_id = row['contacts'][0]['id']
    assert client.get('/teams/' + row['id']).json()['contacts'][0]['contact_info'] == 'private-phone'
    visible[0] = False
    assert client.get('/teams/options').json()['can_view_contacts'] is False
    for path in ['/teams', '/teams/' + row['id']]:
        response = client.get(path)
        assert 'private-phone' not in response.text
        data = response.json()['items'][0] if path == '/teams' else response.json()
        assert data['contact_restricted'] is True and data['contacts'][0]['contact_info'] == '******'
    changed = payload(revision=1, contacts=[{"id": contact_id, "name": "李三", "nickname": "小李"}]).model_dump(mode='json')
    saved = client.put('/teams/' + row['id'], json=changed)
    assert saved.status_code == 200 and 'private-phone' not in saved.text
    assert service.get_team(db, row['id']).contacts[0]['contact_info'] == 'private-phone'
    # 老客户端省略联系人仍须保留，不能把隐藏明文覆盖为脱敏占位符。
    legacy = payload(revision=2).model_dump(mode='json'); legacy.pop('contacts')
    assert client.put('/teams/' + row['id'], json=legacy).status_code == 200
    for contacts in [[], [{"id": contact_id, "name": "李三", "contact_info": "******"}]]:
        response = client.put('/teams/' + row['id'], json=payload(revision=3, contacts=contacts).model_dump(mode='json'))
        assert response.status_code == 403
    assert client.post('/teams', json=payload(short_name='禁止录入', contacts=[{'name': '甲', 'contact_info': 'illegal'}]).model_dump(mode='json')).status_code == 403
    audits = db.query(TeamResourceAudit).filter_by(team_id=row['id']).all()
    assert all('private-phone' not in str(a.before) + str(a.after) for a in audits)
    visible[0] = True
    assert client.get('/teams/' + row['id']).json()['contacts'][0]['contact_info'] == 'private-phone'
    assert client.put('/teams/' + row['id'], json=payload(revision=3, contacts=[]).model_dump(mode='json')).status_code == 200


def test_contract_and_conditional_validation():
    row = payload(short_name="  中文团队  ", resource_types=["annotation", "annotation"], introduction="第一行\n第二行", other_resource_description="旧说明")
    assert row.short_name == "中文团队" and row.resource_types == ["annotation"]
    assert row.introduction == "第一行\n第二行" and row.other_resource_description == ""
    for fields in [{"short_name": " "}, {"short_name": "字" * 101}, {"full_name": "字" * 256}, {"resource_types": []}, {"resource_types": ["invalid"]},
                   {"team_type": "invalid"}, {"resource_types": ["other"]}, {"resource_types": ["other"], "other_resource_description": " "},
                   {"introduction": "字" * 5001}, {"resource_situation": "字" * 5001}, {"remarks": "字" * 2001}, {"created_at": "2026-10-12"}, {"revision": -1}]:
        with pytest.raises(ValidationError):
            payload(**fields)
    assert payload(resource_types=["other"], other_resource_description="采集").other_resource_description == "采集"


@pytest.fixture
def db():
    if os.getenv("RUN_TEAM_RESOURCE_DB_TESTS") != "1":
        pytest.skip("数据库回归需显式启用本机团队隔离库")
    import main  # noqa: F401，注册现有映射，禁止启动服务。
    from database import engine
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from team_resource_models import TeamResource, TeamResourceAudit
    assert engine.url.host == "127.0.0.1" and engine.url.username == "team_test" and engine.url.database == "teams_test", "禁止使用业务数据库"
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            # 隐藏浏览器验收种子；外层回滚后自动恢复，逐例数据互不干扰。
            session.execute(delete(TeamResource)); session.execute(delete(TeamResourceAudit))
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def people(db):
    from models import AppUser
    users = [AppUser(id=uuid4(), username="team_" + uuid4().hex, full_name=name, password_hash="isolated-no-login", is_active=active)
             for name, active in [("操作人", True), ("对接人", True), ("跟进人", True), ("历史人员", False)]]
    db.add_all(users); db.flush()
    return users


def create(db, people, **fields):
    from team_resource_service import save_team
    return save_team(db, people[0], payload(**fields))


def test_crud_audit_dates_and_versions(db, people):
    from team_resource_models import TeamResourceAudit
    from team_resource_service import delete_team, get_team, save_team, serialize_many
    row = create(db, people, contact_user_id=people[1].id, follow_up_user_id=people[1].id, contact_date=date(2026, 10, 12), introduction="简介\n第二行")
    assert row["revision"] == 1 and row["contact_date"] == "2026-10-12"
    assert row["created_at"].endswith("+08:00") and row["updated_at"].endswith("+08:00")
    updated = save_team(db, people[0], payload(revision=1, introduction="修改后的简介"), row["id"])
    assert updated["revision"] == 2 and updated["contact_user_id"] is None
    assert serialize_many(db, [get_team(db, row["id"])])[0]["introduction"] == "修改后的简介"
    for operation in [lambda: save_team(db, people[0], payload(revision=1), row["id"]), lambda: delete_team(db, people[0], row["id"], 1)]:
        with pytest.raises(HTTPException) as conflict:
            operation()
        assert conflict.value.status_code == 409 and conflict.value.detail["code"] == "team_revision_conflict"
    delete_team(db, people[0], row["id"], 2); db.flush()
    with pytest.raises(HTTPException) as missing:
        get_team(db, row["id"])
    assert missing.value.status_code == 404
    audits = db.query(TeamResourceAudit).filter_by(team_id=row["id"]).order_by(TeamResourceAudit.occurred_at).all()
    assert [a.action for a in audits] == ["create", "update", "delete"]
    assert audits[-1].before["introduction"] == "修改后的简介" and audits[-1].after is None


def test_duplicate_warning_confirmation_and_self_exclusion(db, people):
    from team_resource_service import save_team
    row = create(db, people, short_name="Team A", full_name="正式名称")
    for fields in [{"short_name": "  TEAM A "}, {"short_name": "不同简称", "full_name": " 正式名称 "}]:
        with pytest.raises(HTTPException) as duplicate:
            create(db, people, **fields)
        assert duplicate.value.detail["code"] == "team_duplicate_warning"
        assert duplicate.value.detail["candidates"][0]["id"] == row["id"]
    updated = save_team(db, people[0], payload(short_name="Team A", full_name="正式名称", revision=1), row["id"])
    assert updated["revision"] == 2
    another = create(db, people, short_name="TEAM A", allow_duplicate=True)
    assert another["id"] != row["id"]


def test_inactive_people_retained_only_in_original_field(db, people):
    from team_resource_service import people_options, save_team
    row = create(db, people, contact_user_id=people[1].id)
    people[1].is_active = False; db.flush()
    updated = save_team(db, people[0], payload(contact_user_id=people[1].id, revision=1), row["id"])
    assert updated["contact_user"]["is_active"] is False
    assert any(p["id"] == str(people[1].id) for p in people_options(db))
    assert not any(p["id"] == str(people[3].id) for p in people_options(db))
    for fields in [{"follow_up_user_id": people[1].id}, {"contact_user_id": people[3].id}, {"contact_user_id": uuid4()}]:
        with pytest.raises(HTTPException) as invalid:
            save_team(db, people[0], payload(revision=2, **fields), row["id"])
        assert invalid.value.status_code == 422


def test_combined_filters_literal_search_and_pagination(db, people):
    from team_resource_service import list_teams
    a = create(db, people, short_name="团队%_A", full_name="客户资源甲", contact_date=date(2026, 10, 1), contact_user_id=people[1].id,
               follow_up_user_id=people[2].id, resource_types=["annotation", "interpretation"])
    b = create(db, people, short_name="团队B", full_name="客户资源乙", contact_date=date(2026, 10, 12), contact_user_id=people[2].id,
               team_type="small_medium_company", resource_types=["written_translation"])
    assert list_teams(db, keyword="客户资源")["total"] == 2
    assert list_teams(db, keyword="%_")["items"][0]["id"] == a["id"]
    result = list_teams(db, resource_types=["annotation", "written_translation"], skip=1, limit=1)
    assert result["total"] == 2 and result["items"][0]["id"] == a["id"]
    assert list_teams(db, contact_user_id=people[2].id, resource_types=["annotation"])["total"] == 0
    assert list_teams(db, contact_start=date(2026, 10, 12), contact_end=date(2026, 10, 12))["items"][0]["id"] == b["id"]
    assert list_teams(db, contact_user_id=people[1].id, follow_up_user_id=people[2].id, team_type="small_team")["total"] == 1
    with pytest.raises(HTTPException):
        list_teams(db, contact_start=date(2026, 10, 12), contact_end=date(2026, 10, 1))


def test_api_permissions_validation_and_module_guard(db, people, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import auth, teams
    permissions = []
    monkeypatch.setattr(auth, "get_user_permission_codes", lambda *_: permissions)
    monkeypatch.setattr(teams, "user_has_permission", lambda _, uid, code: code in permissions)
    app = FastAPI(); app.include_router(teams.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: people[0]
    client = TestClient(app)
    row = create(db, people)
    assert client.get("/teams").status_code == 200
    assert client.get("/teams/options").json()["can_write"] is False
    assert client.get("/teams/" + row["id"]).status_code == 200
    assert client.post("/teams", json=payload().model_dump(mode="json")).status_code == 403
    assert client.put("/teams/" + row["id"], json=payload(revision=1).model_dump(mode="json")).status_code == 403
    assert client.delete("/teams/" + row["id"], params={"revision": 1}).status_code == 403
    permissions.append("translators:write")
    assert client.get("/teams/options").json()["can_write"] is True
    response = client.post("/teams", json=payload(short_name="新团队").model_dump(mode="json"))
    assert response.status_code == 201
    assert client.get("/teams", params=[("resource_types", "annotation"), ("resource_types", "written_translation")]).json()["total"] == 2
    assert client.get("/teams", params={"resource_types": "invalid"}).status_code == 422
    assert client.delete("/teams/" + response.json()["id"], params={"revision": 1}).status_code == 204
    from sqlalchemy import text
    db.execute(text("ALTER TABLE resource_team RENAME TO resource_team_hidden"))
    response = client.get("/teams")
    assert response.status_code == 503 and response.json()["detail"]["code"] == "team_module_uninitialized"
    db.execute(text("ALTER TABLE resource_team_hidden RENAME TO resource_team"))


def test_database_constraints(db):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    for team_type, types, other in [("invalid", '["annotation"]', ''), ("small_team", '[]', ''), ("small_team", '["invalid"]', ''), ("small_team", '["other"]', '')]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text("INSERT INTO resource_team (id,short_name,team_type,resource_types,other_resource_description) VALUES (:id,'约束测试',:type,CAST(:resources AS jsonb),:other)"),
                       {"id": uuid4(), "type": team_type, "resources": types, "other": other})


def test_concurrent_updates_accept_only_one_current_version():
    if os.getenv("RUN_TEAM_RESOURCE_DB_TESTS") != "1":
        pytest.skip("并发回归需显式启用本机团队隔离库")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import main  # noqa: F401
    from database import engine
    from models import AppUser
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from team_resource_service import delete_team, get_team, save_team
    assert engine.url.host == "127.0.0.1" and engine.url.username == "team_test" and engine.url.database == "teams_test"
    actor_id = uuid4()
    with Session(engine) as session:
        actor = AppUser(id=actor_id, username="team_concurrent_" + uuid4().hex, full_name="并发验收", password_hash="isolated-no-login", is_active=True)
        session.add(actor); session.flush()
        row = save_team(session, actor, payload(short_name="并发团队" + uuid4().hex))
        session.commit()
    barrier = Barrier(2)

    def update(remark):
        with Session(engine) as session:
            actor = session.get(AppUser, actor_id)
            barrier.wait(timeout=10)
            try:
                result = save_team(session, actor, payload(short_name=row["short_name"], revision=1, remarks=remark), row["id"])
                session.commit()
                return result["revision"]
            except HTTPException as error:
                session.rollback()
                return error.detail["code"]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(update, "用户甲修改")
            second = pool.submit(update, "用户乙修改")
            assert sorted([str(first.result(timeout=15)), str(second.result(timeout=15))]) == ["2", "team_revision_conflict"]
    finally:
        with Session(engine) as session:
            actor = session.get(AppUser, actor_id)
            current = get_team(session, row["id"])
            delete_team(session, actor, current.id, current.revision)
            session.flush()
            session.execute(delete(AppUser).where(AppUser.id == actor_id))
            session.commit()
