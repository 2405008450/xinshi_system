import asyncio
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

import chat_attachment_storage as storage


@pytest.mark.parametrize('origin', ['', 'http://example.com', 'https://user:pass@example.com',
                                   'https://example.com/api', 'https://example.com?x=1',
                                   'https://example.com:8000', 'https://example.com/#x'])
def test_remote_requires_fixed_https_origin(monkeypatch, origin):
    monkeypatch.setenv('CHAT_STORAGE_MODE', 'remote')
    monkeypatch.setenv('CHAT_REMOTE_ORIGIN', origin)
    with pytest.raises(HTTPException) as error:
        storage.remote_attachment_url()
    assert error.value.status_code == 503


def test_local_default_and_invalid_mode(monkeypatch):
    monkeypatch.delenv('CHAT_STORAGE_MODE', raising=False)
    assert storage.remote_attachment_url() is None
    monkeypatch.setenv('CHAT_STORAGE_MODE', 'unknown')
    with pytest.raises(HTTPException):
        storage.remote_attachment_url()
    monkeypatch.setenv('CHAT_STORAGE_MODE', 'remote')
    monkeypatch.setenv('CHAT_REMOTE_ORIGIN', 'https://images.example.com/')
    assert storage.remote_attachment_url() == 'https://images.example.com/api/project-chat/attachments'


def mock_client(monkeypatch, handler):
    monkeypatch.setattr(storage, 'make_client', lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False, timeout=storage.TIMEOUT))


def test_upload_forwards_identity_and_returns_original_id(monkeypatch):
    attachment_id = str(uuid4())
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers['authorization'] == 'Bearer test-token'
        assert request.headers['x-chat-attachment-forwarded'] == '1'
        assert b'image/png' in request.content
        return httpx.Response(201, json={'id': attachment_id, 'original_name': 'test.png',
                                        'content_type': 'image/png', 'file_size': 8, 'created_at': None})
    mock_client(monkeypatch, handler)
    result = asyncio.run(storage.upload_remote_attachment('https://cloud/api/project-chat/attachments',
                         b'12345678', 'test.png', 'image/png', 'Bearer test-token', None))
    assert str(result.id) == attachment_id
    assert len(requests) == 1


@pytest.mark.parametrize('status', [301, 302, 401, 403, 404, 413, 415, 500, 503])
def test_upstream_failure_never_redirects_or_retries(monkeypatch, status):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={'Location': 'https://untrusted.example'})
    mock_client(monkeypatch, handler)
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.upload_remote_attachment('https://cloud/api/project-chat/attachments',
                    b'png', 'test.png', 'image/png', 'Bearer test-token', None))
    assert error.value.status_code == (502 if status == 401 else status if status in {403, 404, 413, 415} else 503)
    assert len(requests) == 1


def test_timeout_and_loop_fail_closed(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout('timeout', request=request)
    mock_client(monkeypatch, handler)
    with pytest.raises(HTTPException, match='图片服务暂不可用'):
        asyncio.run(storage.upload_remote_attachment('https://cloud/api/project-chat/attachments',
                    b'png', 'test.png', 'image/png', 'Bearer test-token', None))
    with pytest.raises(HTTPException, match='循环'):
        storage.request_headers('Bearer test-token', '1')


def test_read_streams_without_buffering_and_closes(monkeypatch):
    class Stream(httpx.AsyncByteStream):
        consumed = False
        closed = False
        async def __aiter__(self):
            self.consumed = True
            yield b'first'
            yield b'second'
        async def aclose(self):
            self.closed = True
    stream = Stream()
    mock_client(monkeypatch, lambda request: httpx.Response(200, stream=stream,
                headers={'Content-Type': 'image/png', 'Content-Length': '11'}))
    async def run():
        response = await storage.read_remote_attachment('https://cloud/api/project-chat/attachments',
                                                        uuid4(), 'Bearer test-token', None)
        assert not stream.consumed
        assert response.headers['cache-control'] == 'private, no-store'
        data = b''.join([chunk async for chunk in response.body_iterator])
        assert data == b'firstsecond'
        assert stream.closed
    asyncio.run(run())


def test_remote_upload_does_not_write_local_disk_or_database(monkeypatch):
    from io import BytesIO
    from starlette.requests import Request
    from starlette.datastructures import Headers, UploadFile
    from routers import project_chat

    monkeypatch.setenv('CHAT_STORAGE_MODE', 'remote')
    monkeypatch.setenv('CHAT_REMOTE_ORIGIN', 'https://cloud.example')
    monkeypatch.delenv('CHAT_UPLOADS_PAUSED', raising=False)
    attachment_id = str(uuid4())
    mock_client(monkeypatch, lambda request: httpx.Response(201, json={
        'id': attachment_id, 'original_name': 'test.png', 'content_type': 'image/png',
        'file_size': 8, 'created_at': None,
    }))
    def forbidden():
        raise AssertionError('remote mode must not resolve local storage')
    monkeypatch.setattr(project_chat, 'get_chat_upload_dir', forbidden)
    request = Request({'type': 'http', 'headers': [(b'authorization', b'Bearer test-token')]})
    file = UploadFile(BytesIO(b'\x89PNG\r\n\x1a\n'), filename='test.png', headers=Headers({'content-type': 'image/png'}))
    result = asyncio.run(project_chat.upload_attachment_endpoint(request, file, None, None))
    assert str(result.id) == attachment_id


def test_upload_pause_prevents_forwarding(monkeypatch):
    from routers import project_chat
    monkeypatch.setenv('CHAT_UPLOADS_PAUSED', 'true')
    with pytest.raises(HTTPException, match='维护'):
        asyncio.run(project_chat.upload_attachment_endpoint(None, None, None, None))


def test_remote_read_unauthorized_is_gateway_error_not_local_logout(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(401))
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.read_remote_attachment('https://cloud/api/project-chat/attachments',
                                                  uuid4(), 'Bearer valid-local-token', None))
    assert error.value.status_code == 502
    assert '云端图片服务认证失败' in error.value.detail


def test_missing_local_token_remains_unauthorized():
    with pytest.raises(HTTPException) as error:
        storage.request_headers(None, None)
    assert error.value.status_code == 401
