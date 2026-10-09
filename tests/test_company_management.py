"""公司管理真实PostgreSQL隔离验收，不写入业务库。"""
import asyncio
import inspect
import io
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import company_management_attachment_service as files
import company_management_service as sections
from annotation_notice_schemas import AnnotationNoticeSectionCreate, AnnotationNoticeSectionEdit, AnnotationNoticeSectionUpdate, AnnotationNoticeReorder
from company_management_models import CompanyManagementAttachment, CompanyManagementSection
from concurrency import StaleUpdateError
from database import get_db
from models import AppUser, Role, RolePermission, UserRole
from permission_registry import PERMISSION_CODES
from permission_service import get_role_permission_codes, get_user_permission_codes, set_role_permission_codes
from routers.auth import get_current_user
from routers.company_management import router
from schemas import RoleResponse



@pytest.fixture
def db(tmp_path, monkeypatch):
    url = os.getenv("COMPANY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("需要独立 PostgreSQL COMPANY_TEST_DATABASE_URL")
    import main  # 注册所有现有 ORM 关联，不启动应用
    engine = create_engine(url)
    tables = [AppUser.__table__, Role.__table__, UserRole.__table__, RolePermission.__table__,
              CompanyManagementSection.__table__, CompanyManagementAttachment.__table__]
    for table in tables:
        table.create(engine, checkfirst=True)
    sql = (Path(__file__).resolve().parents[1] / "data/migrations/20261006_add_company_management.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as migration:
        migration.exec_driver_sql(sql)
        migration.exec_driver_sql(sql)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(connection, join_transaction_mode="create_savepoint")
    monkeypatch.setenv("COMPANY_MANAGEMENT_UPLOAD_DIR", str(tmp_path / "uploads"))
    user = AppUser(id=uuid4(), username="company_qa_" + uuid4().hex, password_hash="unused", full_name="验收维护员")
    session.add(user)
    session.flush()
    sections.ensure_company_management_sections(session)
    try:
        yield session, user
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def doc(value="公司管理验收正文"):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": value}]}]}


def upload(db, section, user, name="中文资料.pdf", content=b"company-file"):
    return asyncio.run(files.save_attachment(db, section, UploadFile(filename=name, file=io.BytesIO(content)), user.id))


def test_tree_versions_search_and_soft_delete(db):
    session, user = db
    tree = sections.list_company_management_tree(session)
    assert [row["title"] for row in tree] == ["公司制度", "人事行政", "财务规范", "常用模板"]
    root = tree[0]
    child = sections.create_company_management_section(session, AnnotationNoticeSectionCreate(title="二级资料", parent_id=root["id"]))
    with pytest.raises(ValueError, match="两级"):
        sections.create_company_management_section(session, AnnotationNoticeSectionCreate(title="三级", parent_id=child["id"]))
    with pytest.raises(ValueError, match="二级栏目"):
        sections.delete_company_management_section(session, root["id"])
    saved = sections.update_company_management_content(session, child["id"], AnnotationNoticeSectionUpdate(content_json=doc()), user.id)
    with pytest.raises(StaleUpdateError):
        sections.update_company_management_content(session, child["id"], AnnotationNoticeSectionUpdate(content_json=doc("旧保存")), user.id)
    group = sections.update_company_management_structure(session, child["id"], AnnotationNoticeSectionEdit(
        title="资料分组", has_content=False, expected_structure_updated_at=child["structure_updated_at"]))
    assert group["content_json"] == saved["content_json"]
    with pytest.raises(StaleUpdateError):
        sections.update_company_management_structure(session, child["id"], AnnotationNoticeSectionEdit(title="旧栏目", has_content=True))
    sections.update_company_management_structure(session, child["id"], AnnotationNoticeSectionEdit(
        title="搜索资料", has_content=True, expected_structure_updated_at=group["structure_updated_at"]))
    result = sections.search_company_management_sections(session, "验收正文", 0, 1)
    assert result["total"] == 1 and result["items"][0]["id"] == child["id"]
    assert sections.search_company_management_sections(session, "%")["total"] == 0
    assert sections.search_company_management_sections(session, "资料", 1, 1)["items"] == []
    assert sections.delete_company_management_section(session, child["id"])
    assert sections.get_company_management_section(session, child["id"]) is None
    sections.delete_company_management_section(session, root["id"])
    sections.ensure_company_management_sections(session)
    assert len(sections.list_company_management_tree(session)) == 3


def test_reorder_rejects_cycles_and_preserves_versions(db):
    session, _ = db
    tree = sections.list_company_management_tree(session)
    placements = [dict(id=row["id"], parent_id=None, sort_order=i+1, expected_structure_updated_at=row["structure_updated_at"]) for i, row in enumerate(tree)]
    placements[0]["parent_id"] = placements[0]["id"]
    with pytest.raises(ValueError, match="自己的父级"):
        sections.reorder_company_management_sections(session, AnnotationNoticeReorder(placements=placements))
    placements[0]["parent_id"] = None
    placements[0]["sort_order"], placements[1]["sort_order"] = 2, 1
    result = sections.reorder_company_management_sections(session, AnnotationNoticeReorder(placements=placements))
    assert result[0]["title"] == "人事行政"
    with pytest.raises(StaleUpdateError):
        sections.reorder_company_management_sections(session, AnnotationNoticeReorder(placements=placements))


def test_attachments_validate_ownership_limits_and_cleanup(db, monkeypatch):
    session, user = db
    root, other = sections.list_company_management_tree(session)[:2]
    first = upload(session, root["id"], user)
    second = upload(session, root["id"], user)
    assert first["id"] != second["id"]
    assert first["uploaded_by_name"] == "验收维护员"
    assert "storage_name" not in first
    assert len(files.list_attachments(session, root["id"])) == 2
    with pytest.raises(HTTPException) as exc:
        files.get_attachment(session, other["id"], first["id"])
    assert exc.value.status_code == 404
    for name, content, status in [("执行.exe", b"x", 400), ("空.pdf", b"", 400), ("大.pdf", b"x" * (files.MAX_FILE_BYTES + 1), 413)]:
        with pytest.raises(HTTPException) as exc:
            upload(session, root["id"], user, name, content)
        assert exc.value.status_code == status
    assert len(list(files.upload_dir().iterdir())) == 2
    interrupted = UploadFile(filename="取消.pdf", file=io.BytesIO(b"cancel"))
    async def cancelled_read(_size):
        raise asyncio.CancelledError()
    interrupted.read = cancelled_read
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(files.save_attachment(session, root["id"], interrupted, user.id))
    assert len(list(files.upload_dir().iterdir())) == 2
    monkeypatch.setattr(files, "MAX_FILES_PER_SECTION", 2)
    with pytest.raises(HTTPException, match=""):
        upload(session, root["id"], user)
    files.delete_attachment(session, root["id"], first["id"])
    assert len(list(files.upload_dir().iterdir())) == 1
    monkeypatch.setattr(files, "MAX_FILES_PER_SECTION", 50)
    # 提交失败后附件文件必须回收。
    real_commit = session.commit
    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
    with pytest.raises(RuntimeError, match="commit failed"):
        upload(session, root["id"], user)
    monkeypatch.setattr(session, "commit", real_commit)
    assert len(list(files.upload_dir().iterdir())) == 1
    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("delete commit failed")))
    with pytest.raises(RuntimeError, match="delete commit failed"):
        files.delete_attachment(session, root["id"], second["id"])
    monkeypatch.setattr(session, "commit", real_commit)
    retained = files.get_attachment(session, root["id"], second["id"])
    assert files.attachment_path(retained.storage_name).is_file()
    sections.delete_company_management_section(session, root["id"])
    with pytest.raises(HTTPException) as exc:
        files.list_attachments(session, root["id"])
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException):
        upload(session, root["id"], user)


def test_api_all_logged_in_users_can_write_and_download(db):
    session, user = db
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        assert client.get("/company-management/tree").status_code == 401
        sid, aid = uuid4(), uuid4()
        # 全部维护接口仍要求登录。
        anonymous_requests = [
            ("POST", "/sections", {"json": {"title": "未登录新增"}}),
            ("PUT", "/sections/reorder", {"json": {"placements": [{"id": str(sid), "sort_order": 1}]}}),
            ("PATCH", f"/sections/{sid}", {"json": {"title": "未登录编辑", "has_content": True}}),
            ("DELETE", f"/sections/{sid}", {}),
            ("PUT", f"/sections/{sid}/content", {"json": {"content_json": doc()}}),
            ("POST", f"/sections/{sid}/attachments", {"files": {"file": ("test.pdf", b"test")}}),
            ("DELETE", f"/sections/{sid}/attachments/{aid}", {}),
        ]
        for method, path, kwargs in anonymous_requests:
            assert client.request(method, "/company-management" + path, **kwargs).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert client.get("/company-management/tree").status_code == 200
        assert get_user_permission_codes(session, user.id) == []
        created = client.post("/company-management/sections", json={"title": "API资料"})
        assert created.status_code == 201
        sid = created.json()["id"]
        edited = client.patch(f"/company-management/sections/{sid}", json={
            "title": "普通用户编辑资料", "has_content": True,
            "expected_structure_updated_at": created.json()["structure_updated_at"],
        })
        assert edited.status_code == 200
        assert edited.json()["title"] == "普通用户编辑资料"
        saved = client.put(f"/company-management/sections/{sid}/content", json={"content_json": doc("普通用户保存正文")})
        assert saved.status_code == 200
        assert saved.json()["updated_by"] == str(user.id)
        tree = client.get("/company-management/tree").json()
        reordered = client.put("/company-management/sections/reorder", json={"placements": [
            dict(id=row["id"], sort_order=index + 1, expected_structure_updated_at=row["structure_updated_at"])
            for index, row in enumerate(reversed(tree))
        ]})
        assert reordered.status_code == 200
        assert reordered.json()[0]["id"] == sid
        response = client.post(f"/company-management/sections/{sid}/attachments", files={"file": ("中文.pdf", b"test-download", "application/pdf")})
        assert response.status_code == 201
        aid = response.json()["id"]
        assert "storage_name" not in response.json()
        read = client.get(f"/company-management/sections/{sid}/attachments/{aid}")
        assert read.status_code == 200 and read.content == b"test-download"
        assert "filename*=utf-8" in read.headers["content-disposition"].lower()
        assert client.delete(f"/company-management/sections/{sid}/attachments/{aid}").status_code == 204
        assert client.delete(f"/company-management/sections/{sid}").status_code == 204
        assert client.get(f"/company-management/sections/{sid}").status_code == 404


def test_retired_company_permission_does_not_break_role_configuration(db):
    session, user = db
    assert "company_management:write" not in PERMISSION_CODES
    role = Role(id=uuid4(), role_name="company_qa_" + uuid4().hex)
    session.add(role)
    session.flush()
    session.add_all([
        UserRole(user_id=user.id, role_id=role.id),
        RolePermission(role_id=role.id, permission_code="company_management:write"),
        RolePermission(role_id=role.id, permission_code="projects:read"),
    ])
    session.commit()
    # 历史授权不再出现在角色配置中，其他权限可以继续读取和保存。
    assert get_role_permission_codes(session, role.id) == ["projects:read"]
    assert RoleResponse.model_validate(role).permissions == ["projects:read"]
    assert get_user_permission_codes(session, user.id) == ["projects:read"]
    assert set_role_permission_codes(session, role.id, get_role_permission_codes(session, role.id)) == ["projects:read"]
