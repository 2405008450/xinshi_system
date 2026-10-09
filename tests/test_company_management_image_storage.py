"""双服务器正文图片转发：固定源站、凭证保护及本地不落盘。"""
import asyncio
import io
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

import company_management_image_storage as storage
from database import get_db
from routers.auth import get_current_user
from routers.company_management import router


@pytest.fixture(autouse=True)
def local_mode(monkeypatch):
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_STORAGE_MODE", "local")


def request(forwarded=False):
    headers = {"Authorization": "Bearer test-opaque-token"}
    if forwarded:
        headers["X-Company-Image-Forwarded"] = "1"
    return SimpleNamespace(headers=Headers(headers))


@pytest.mark.parametrize("origin", ["http://cloud.example", "https://u:p@cloud.example", "https://cloud.example/path", "https://cloud.example?a=b", "https://cloud.example:444", ""])
def test_remote_rejects_invalid_origins(monkeypatch, origin):
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_STORAGE_MODE", "remote")
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_REMOTE_ORIGIN", origin)
    with pytest.raises(HTTPException) as error:
        storage.remote_origin()
    assert error.value.status_code == 503


def test_default_local_remote_and_loop_guard(monkeypatch):
    assert storage.remote_origin() is None
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_STORAGE_MODE", "remote")
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_REMOTE_ORIGIN", "https://cloud.example/")
    assert storage.remote_origin() == "https://cloud.example"
    with pytest.raises(HTTPException):
        storage.request_headers(request(True))
    with pytest.raises(HTTPException):
        storage.request_headers(SimpleNamespace(headers=Headers()))
    client = storage.make_client()
    assert not client.follow_redirects and not client.trust_env
    asyncio.run(client.aclose())


@pytest.mark.parametrize("status,expected", [(401, 502), (409, 409), (413, 413), (307, 503), (500, 503)])
def test_upstream_errors_do_not_clear_local_login(monkeypatch, status, expected):
    transport = httpx.MockTransport(lambda req: httpx.Response(status, json={"detail": "上游业务错误"}))
    monkeypatch.setattr(storage, "make_client", lambda: httpx.AsyncClient(transport=transport))
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_json("https://cloud.example", request(), "PUT", "/sections/test/content", payload={}))
    assert error.value.status_code == expected


def test_read_stream_errors_and_size_cap(monkeypatch):
    async def check(status, mime, expected):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(status,
            headers={"content-type": mime}, stream=httpx.ByteStream(b'{"detail":"missing"}'))))
        monkeypatch.setattr(storage, "make_client", lambda: client)
        with pytest.raises(HTTPException) as error:
            await storage.forward_image("https://cloud.example", request(), "/sections/test/images/test")
        assert error.value.status_code == expected
        assert client.is_closed
    asyncio.run(check(404, "application/json", 404))
    asyncio.run(check(200, "text/html", 503))


def test_proxy_routes_preserve_contract_without_local_storage(monkeypatch):
    sid, image_id, user_id = uuid4(), uuid4(), uuid4()
    src = f"/api/company-management/sections/{sid}/images/{image_id}"
    observed = []
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_STORAGE_MODE", "remote")
    monkeypatch.setenv("COMPANY_MANAGEMENT_IMAGE_REMOTE_ORIGIN", "https://cloud.example")
    image = dict(id=str(image_id), section_id=str(sid), original_name="截图.png", file_size=9,
        content_type="image/png", uploaded_by=str(user_id), uploaded_by_name="验收", uploaded_at="2026-10-09T12:00:00", src=src)
    document = {"type": "doc", "content": [{"type": "image", "attrs": {"src": src}}]}

    def handler(req):
        observed.append((req.method, str(req.url), req.headers, req.content))
        assert req.headers['Authorization'] == 'Bearer test-opaque-token'
        assert req.headers['X-Company-Image-Forwarded'] == '1'
        if req.method == "POST":
            return httpx.Response(201, json=image)
        if req.method == "GET":
            return httpx.Response(200, headers={"content-type": "image/png", "content-length": "9"}, stream=httpx.ByteStream(b"png-bytes"))
        if req.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json=dict(id=str(sid), section_key="test", title="验收",
            display_title="验收", sort_order=1, content_json=document))

    monkeypatch.setattr(storage, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(router)
    # 转发分支不得读写本地数据库或调用本地文件服务。
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)
    with TestClient(app, headers={"Authorization": "Bearer test-opaque-token"}) as client:
        path = f"/company-management/sections/{sid}"
        assert client.post(path + "/images", files={"file": ("截图.png", b"png-bytes", "image/png")}).json()["src"] == src
        read = client.get(path + "/images/" + str(image_id))
        assert read.status_code == 200 and read.content == b"png-bytes"
        assert read.headers["cache-control"] == "private, no-store"
        assert client.put(path + "/content", json={"content_json": document}).json()["content_json"] == document
        assert client.delete(path + "/images/" + str(image_id)).status_code == 204
    assert len(observed) == 4
    assert all(url.startswith("https://cloud.example/api/company-management/") for _, url, _, _ in observed)


def test_upload_cap_and_network_failure_close_file(monkeypatch):
    monkeypatch.setattr(storage, "MAX_IMAGE_BYTES", 5)
    file = UploadFile(filename="large.png", file=io.BytesIO(b"123456"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_json("https://cloud.example", request(), "POST", "/images", upload=file))
    assert error.value.status_code == 413 and file.file.closed
    def failure(req):
        raise httpx.ConnectTimeout("unavailable")
    monkeypatch.setattr(storage, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(failure)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_json("https://cloud.example", request(), "PUT", "/content", payload={}))
    assert error.value.status_code == 503
