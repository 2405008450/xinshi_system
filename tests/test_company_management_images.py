"""正文图片在隔离库中的鉴权、生命周期和事务验收。"""
import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from starlette.datastructures import Headers
from sqlalchemy import text
from sqlalchemy.orm import Session

import company_management_image_service as images
import company_management_attachment_service as files
import company_management_service as sections
from annotation_notice_schemas import AnnotationNoticeSectionUpdate
from company_management_schemas import CompanyManagementSectionUpdate
from company_management_models import CompanyManagementSection
from concurrency import StaleUpdateError
from database import get_db
from models import AppUser
from routers.auth import get_current_user
from routers.company_management import router
from test_company_management import db, doc


def png(format="PNG"):
    result = io.BytesIO()
    Image.new("RGB", (64, 48), "#123456").save(result, format=format)
    return result.getvalue()


def image_doc(*saved):
    return {"type": "doc", "content": [{"type": "image", "attrs": {
        "src": image["src"], "alt": "中文截图", "title": None, "width": None, "height": None,
    }} for image in saved]}


def upload_image(session, section_id, user, content=None, mime="image/png"):
    return asyncio.run(images.save_image(session, section_id, UploadFile(
        filename="中文截图.png", file=io.BytesIO(png() if content is None else content),
        headers=Headers({"content-type": mime}),
    ), user.id))


def test_company_schema_only_accepts_controlled_images():
    image = {"src": f"/api/company-management/sections/{uuid4()}/images/{uuid4()}"}
    valid = image_doc(image)
    assert CompanyManagementSectionUpdate(content_json=valid).content_json == valid
    with pytest.raises(ValidationError):
        AnnotationNoticeSectionUpdate(content_json=valid)
    for src in ["data:image/png;base64,abc", "blob:https://example.com/a", "https://example.com/a.png", "javascript:alert(1)", image["src"] + "?token=test"]:
        with pytest.raises(ValidationError):
            CompanyManagementSectionUpdate(content_json=image_doc({"src": src}))
    for key, value in [("onclick", "alert(1)"), ("width", 500), ("alt", "a" * 256)]:
        invalid = image_doc(image)
        invalid["content"][0]["attrs"][key] = value
        with pytest.raises(ValidationError):
            CompanyManagementSectionUpdate(content_json=invalid)


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_image_formats_and_mismatch(format, mime):
    normalized, detected, _ = images.normalize_image(png(format), mime)
    assert detected == mime
    with Image.open(io.BytesIO(normalized)) as result:
        assert result.size == (64, 48)
    with pytest.raises(HTTPException):
        images.normalize_image(png(format), "image/gif")


def test_image_content_validation(monkeypatch):
    for content in [b"", b"<svg onload='alert(1)' />", png()[:30]]:
        with pytest.raises(HTTPException) as error:
            images.normalize_image(content, "image/png")
        assert error.value.status_code == 400
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 20)
    with pytest.raises(HTTPException) as error:
        images.normalize_image(png(), "image/png")
    assert error.value.status_code == 413
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 20 * 1024 * 1024)
    monkeypatch.setattr(images, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(HTTPException, match="") as error:
        images.normalize_image(png(), "image/png")
    assert error.value.status_code == 400


def test_save_reload_remove_and_attachment_separation(db, monkeypatch):
    session, user = db
    root, other = sections.list_company_management_tree(session)[:2]
    first = upload_image(session, root["id"], user)
    assert files.list_attachments(session, root["id"]) == []
    monkeypatch.setattr(files, "MAX_FILES_PER_SECTION", 1)
    asyncio.run(files.save_attachment(session, root["id"], UploadFile(filename="制度.pdf", file=io.BytesIO(b"file")), user.id))
    assert len(files.list_attachments(session, root["id"])) == 1
    with pytest.raises(HTTPException):
        files.delete_attachment(session, root["id"], first["id"])
    with pytest.raises(HTTPException):
        images.get_image(session, other["id"], first["id"])
    with pytest.raises(ValueError, match="不属于"):
        sections.update_company_management_content(session, other["id"], CompanyManagementSectionUpdate(content_json=image_doc(first)), user.id)
    saved = sections.update_company_management_content(session, root["id"], CompanyManagementSectionUpdate(content_json=image_doc(first)), user.id)
    assert sections.get_company_management_section(session, root["id"])["content_json"] == image_doc(first)
    assert sections.get_company_management_section(session, root["id"])["updated_by"] == user.id
    row = images.get_image(session, root["id"], first["id"])
    path = files.attachment_path(row.storage_name)
    with pytest.raises(HTTPException) as error:
        images.delete_draft(session, root["id"], first["id"], user.id)
    assert error.value.status_code == 409
    with pytest.raises(StaleUpdateError):
        sections.update_company_management_content(session, root["id"], CompanyManagementSectionUpdate(content_json=doc()), user.id)
    assert path.exists()
    sections.update_company_management_content(session, root["id"], CompanyManagementSectionUpdate(content_json=doc(), expected_updated_at=saved["updated_at"]), user.id)
    assert not path.exists()
    assert images.image_rows(session, root["id"]).count() == 0
    assert len(files.list_attachments(session, root["id"])) == 1


def test_draft_ownership_expiry_and_limits(db, monkeypatch):
    session, user = db
    root = sections.list_company_management_tree(session)[0]
    first = upload_image(session, root["id"], user)
    saved = sections.update_company_management_content(session, root["id"], CompanyManagementSectionUpdate(content_json=image_doc(first)), user.id)
    second = upload_image(session, root["id"], user)
    for image in [first, second]:
        images.get_image(session, root["id"], image["id"]).uploaded_at = datetime.now() - timedelta(days=2)
    session.commit()
    monkeypatch.setattr(images, "MAX_IMAGES_PER_SECTION", 2)
    third = upload_image(session, root["id"], user)
    assert images.image_rows(session, root["id"]).count() == 2
    assert images.get_image(session, root["id"], first["id"])
    with pytest.raises(HTTPException) as error:
        upload_image(session, root["id"], user)
    assert error.value.status_code == 400
    with pytest.raises(HTTPException) as error:
        images.delete_draft(session, root["id"], third["id"], uuid4())
    assert error.value.status_code == 403
    images.delete_draft(session, root["id"], third["id"], user.id)
    assert images.image_rows(session, root["id"]).count() == 1
    assert saved["content_json"] == image_doc(first)


def test_failed_image_transactions_restore_files(db, monkeypatch):
    session, user = db
    root = sections.list_company_management_tree(session)[0]
    real_commit = session.commit
    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("模拟提交失败")))
    with pytest.raises(RuntimeError):
        upload_image(session, root["id"], user)
    assert list(files.upload_dir().iterdir()) == []
    monkeypatch.setattr(session, "commit", real_commit)
    first = upload_image(session, root["id"], user)
    saved = sections.update_company_management_content(session, root["id"], CompanyManagementSectionUpdate(content_json=image_doc(first)), user.id)
    path = files.attachment_path(images.get_image(session, root["id"], first["id"]).storage_name)
    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("模拟提交失败")))
    with pytest.raises(RuntimeError):
        sections.update_company_management_content(session, root["id"], CompanyManagementSectionUpdate(content_json=doc(), expected_updated_at=saved["updated_at"]), user.id)
    monkeypatch.setattr(session, "commit", real_commit)
    assert path.exists()
    assert sections.get_company_management_section(session, root["id"])["content_json"] == image_doc(first)


def test_image_api_auth_and_save_validation(db):
    session, user = db
    root, other = sections.list_company_management_tree(session)[:2]
    section_id = root["id"]
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        path = f"/company-management/sections/{section_id}/images"
        assert client.post(path, files={"file": ("截图.png", png(), "image/png")}).status_code == 401
        assert client.get(path + f"/{uuid4()}").status_code == 401
        assert client.delete(path + f"/{uuid4()}").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        response = client.post(path, files={"file": ("截图.png", png(), "image/png")})
        assert response.status_code == 201
        image = response.json()
        fetched = client.get(path + "/" + image["id"])
        assert fetched.status_code == 200
        assert fetched.headers["content-type"] == "image/png"
        assert fetched.headers["x-content-type-options"] == "nosniff"
        assert "storage_name" not in image
        assert client.get(f"/company-management/sections/{other['id']}/images/{image['id']}").status_code == 404
        assert client.put(f"/company-management/sections/{section_id}/content", json={"content_json": image_doc({"src": "blob:test"})}).status_code == 422
        assert client.put(f"/company-management/sections/{section_id}/content", json={"content_json": image_doc(image)}).status_code == 200
        assert client.delete(path + "/" + image["id"]).status_code == 409
        assert client.get(f"/company-management/sections/{section_id}/attachments").json() == []


def test_inline_image_migration_preserves_legacy_rows(db):
    session, _ = db
    engine = session.get_bind().engine
    schema = "image_migration_" + uuid4().hex
    sql = (Path(__file__).resolve().parents[1] / "data/migrations/20261009_company_management_inline_images.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
        try:
            connection.exec_driver_sql(f"SET search_path TO {schema}")
            connection.exec_driver_sql("CREATE TABLE company_management_attachment (id INTEGER PRIMARY KEY, original_name TEXT)")
            connection.exec_driver_sql("INSERT INTO company_management_attachment VALUES (1, '旧附件.pdf')")
            connection.exec_driver_sql(sql)
            connection.exec_driver_sql(sql)
            assert connection.exec_driver_sql("SELECT original_name, is_inline_image FROM company_management_attachment").one() == ("旧附件.pdf", False)
        finally:
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")


def test_parallel_content_saves_have_one_winner(db):
    session, _ = db
    engine = session.get_bind().engine
    user_id, section_id = uuid4(), uuid4()
    with Session(engine) as setup:
        setup.add(AppUser(id=user_id, username="image_race_" + uuid4().hex, password_hash="unused"))
        setup.add(CompanyManagementSection(id=section_id, section_key="race_" + uuid4().hex,
            title="并发验收", sort_order=9999, has_content=True, is_active=True, search_text=""))
        setup.commit()
    barrier = Barrier(2)

    def save(value):
        with Session(engine) as concurrent:
            barrier.wait(timeout=5)
            try:
                sections.update_company_management_content(concurrent, section_id,
                    CompanyManagementSectionUpdate(content_json=doc(value)), user_id)
                return "saved"
            except StaleUpdateError:
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(save, ["第一份正文", "第二份正文"])) == ["conflict", "saved"]
    finally:
        with engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM company_management_section WHERE id=:id"), {"id": section_id})
            cleanup.execute(text("DELETE FROM app_user WHERE id=:id"), {"id": user_id})
