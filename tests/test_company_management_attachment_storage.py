"""公司普通附件在共享数据库部署中的云端转发。"""

import asyncio
import io
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

import company_management_attachment_storage as storage
from database import get_db
from routers.auth import get_current_user
from routers.company_management import router


@pytest.fixture(autouse=True)
def local_mode(monkeypatch):
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_STORAGE_MODE", "local")


def request(forwarded=False):
    headers = {"Authorization": "Bearer test-token"}
    if forwarded:
        headers[storage.FORWARDED] = "1"
    return SimpleNamespace(headers=Headers(headers))


@pytest.mark.parametrize("origin", ["", "http://cloud.example", "https://u:p@cloud.example",
    "https://cloud.example/path", "https://cloud.example?x=1", "https://cloud.example:444"])
def test_remote_origin_rejects_unsafe_values(monkeypatch, origin):
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_STORAGE_MODE", "remote")
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_REMOTE_ORIGIN", origin)
    with pytest.raises(HTTPException) as error:
        storage.remote_origin()
    assert error.value.status_code == 503


def test_mode_and_loop_guard(monkeypatch):
    assert storage.remote_origin() is None
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_STORAGE_MODE", "remote")
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_REMOTE_ORIGIN", "https://cloud.example/")
    assert storage.remote_origin() == "https://cloud.example"
    with pytest.raises(HTTPException):
        storage.request_headers(request(True))
    client = storage.make_client()
    assert not client.follow_redirects and not client.trust_env
    asyncio.run(client.aclose())


def test_remote_routes_use_cloud_and_do_not_touch_local_storage(monkeypatch):
    section_id, attachment_id, user_id = uuid4(), uuid4(), uuid4()
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_STORAGE_MODE", "remote")
    monkeypatch.setenv("COMPANY_MANAGEMENT_ATTACHMENT_REMOTE_ORIGIN", "https://cloud.example")
    observed = []
    result = dict(id=str(attachment_id), section_id=str(section_id), original_name="合同.docx",
        file_size=4, content_type="application/octet-stream", uploaded_by=str(user_id),
        uploaded_by_name="验收", uploaded_at="2026-10-27T12:00:00+08:00")

    def handler(req):
        observed.append((req.method, str(req.url), req.headers))
        assert req.headers[storage.FORWARDED] == "1"
        assert req.headers["Authorization"] == "Bearer test-token"
        if req.method == "POST":
            return httpx.Response(201, json=result)
        if req.method == "GET":
            return httpx.Response(200, headers={"content-disposition": "attachment; filename=test.docx"},
                stream=httpx.ByteStream(b"docx"))
        return httpx.Response(204)

    monkeypatch.setattr(storage, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)
    path = f"/company-management/sections/{section_id}/attachments"
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        assert client.post(path, files={"file": ("合同.docx", b"docx")}).status_code == 201
        read = client.get(f"{path}/{attachment_id}")
        assert read.content == b"docx"
        assert read.headers["cache-control"] == "private, no-store"
        assert client.delete(f"{path}/{attachment_id}").status_code == 204
    assert [method for method, _, _ in observed] == ["POST", "GET", "DELETE"]
    assert all(url.startswith("https://cloud.example/api/company-management/") for _, url, _ in observed)


def test_missing_remote_file_and_oversize_upload(monkeypatch):
    monkeypatch.setattr(storage, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(404, json={"detail": "附件文件不存在"}))))
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_download("https://cloud.example", request(), "/attachments/id"))
    assert error.value.status_code == 404
    assert error.value.detail == "附件文件不存在"
    monkeypatch.setattr(storage, "MAX_FILE_BYTES", 3)
    file = UploadFile(filename="large.docx", file=io.BytesIO(b"1234"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_upload("https://cloud.example", request(), "/attachments", file))
    assert error.value.status_code == 413
    assert file.file.closed
