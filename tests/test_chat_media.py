"""音视频附件测试仅使用临时文件、模拟上游和独立测试数据库。"""
import asyncio
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from chat_file_types import MEDIA_TYPES, MEDIA_MAX_BYTES, validate_media
from test_chat_phase_one import environment

SAMPLES = {
    '.mp4': b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42',
    '.m4a': b'\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A mp42',
    '.mp3': b'\xff\xfb\x90\x64' + b'\x00' * 413,
    '.wav': b'RIFF' + b'\x00' * 4 + b'WAVEfmt ' + b'\x00' * 28,
    '.webm': b'\x1a\x45\xdf\xa3\x87\x42\x82\x84webm',
}

@pytest.mark.parametrize('suffix', MEDIA_TYPES)
def test_media_signature(suffix):
    validate_media(suffix, SAMPLES[suffix])
    for content in (b'', b'MZfake', b'ID3fake', b'\x00\x00\x00\x08ftyp'):
        with pytest.raises(HTTPException) as exc:
            validate_media(suffix, content)
        assert exc.value.status_code == 415

@pytest.mark.parametrize('content_type', MEDIA_TYPES.values())
def test_remote_media_read(monkeypatch, content_type):
    import chat_attachment_storage as storage
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'media'
    monkeypatch.setattr(storage, 'make_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, stream=Stream(), headers={'Content-Type': content_type}))))
    async def run():
        result = await storage.read_remote_attachment('https://cloud/files', uuid4(), 'Bearer test', None, allow_files=True)
        assert result.media_type == content_type
        assert b''.join([part async for part in result.body_iterator]) == b'media'
    asyncio.run(run())

@pytest.mark.parametrize('scope', ['annotation', 'direct'])
def test_media_upload_send_download_and_permissions(environment, monkeypatch, tmp_path, scope):
    import main
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from annotation_models import AnnotationProject
    import direct_chat_service
    db, users, engine = environment
    monkeypatch.setenv('CHAT_STORAGE_MODE', 'local')
    monkeypatch.setenv('CHAT_UPLOAD_DIR', str(tmp_path))
    monkeypatch.setenv('CHAT_UPLOADS_PAUSED', 'false')
    if scope == 'annotation':
        project = AnnotationProject(order_no='MEDIA-' + uuid4().hex[:20], project_name='音视频验收', project_types=[], created_by=users[0].id)
        db.add(project); db.commit(); cid = project.id
        base = f'/project-chat/annotation/{cid}'
        project2 = AnnotationProject(order_no='MEDIA-' + uuid4().hex[:20], project_name='隔离项目', project_types=[], created_by=users[0].id)
        db.add(project2); db.commit()
        import annotation_chat_service
        annotation_chat_service.add_member(db, cid, users[0].id)
        annotation_chat_service.add_member(db, project2.id, users[0].id)
        db.commit(); other = f'/project-chat/annotation/{project2.id}'
    else:
        cid = direct_chat_service.open_conversation(db, users[0], users[1].id)['id']
        base = f'/chat/direct/{cid}'
        cid2 = direct_chat_service.open_conversation(db, users[0], users[2].id)['id']
        other = f'/chat/direct/{cid2}'
    actor = [users[0]]
    main.app.dependency_overrides[get_db] = lambda: db
    main.app.dependency_overrides[get_current_user] = lambda: actor[0]
    client = TestClient(main.app)
    ids = []
    for suffix, content in SAMPLES.items():
        result = client.post(base + '/files', files={'file': ('中文素材' + suffix.upper(), content, 'application/octet-stream')})
        assert result.status_code == 201, result.text
        assert result.json()['content_type'] == MEDIA_TYPES[suffix]
        fid = result.json()['id']; ids.append(fid)
        assert client.get(base + '/files/' + fid).content == content
        assert client.get(other + '/files/' + fid).status_code == 404
    payload = {'content': '', 'attachment_ids': ids, 'client_message_id': str(uuid4())}
    sent = client.post(base + '/messages', json=payload)
    assert sent.status_code == 201, sent.text
    assert len(sent.json()['attachments']) == 5
    bad = client.post(other + '/messages', json={**payload, 'client_message_id': str(uuid4())})
    assert bad.status_code in (400, 404)
    too_many = client.post(base + '/messages', json={**payload, 'attachment_ids': [str(uuid4()) for _ in range(10)]})
    assert too_many.status_code == 422
    for content in (b'', b'MZfake', b'x' * (MEDIA_MAX_BYTES + 1)):
        response = client.post(base + '/files', files={'file': ('bad.mp4', content, 'video/mp4')})
        assert response.status_code == (415 if content == b'MZfake' else 413)
    boundary = SAMPLES['.mp3'] + b'\x00' * (MEDIA_MAX_BYTES - len(SAMPLES['.mp3']))
    response = client.post(base + '/files', files={'file': ('边界.mp3', boundary, 'audio/mpeg')})
    assert response.status_code == 201, response.text
    actor[0] = users[3]
    assert client.get(base + '/files/' + ids[0]).status_code in (403, 404)
    actor[0] = users[0]
    recalled = client.post(base + '/messages/' + sent.json()['id'] + '/recall')
    assert recalled.status_code == 200, recalled.text
    assert client.get(base + '/files/' + ids[0]).status_code == 404


@pytest.mark.parametrize('scope', ['annotation', 'direct'])
def test_media_remote_upload_routes(monkeypatch, scope):
    from io import BytesIO
    from types import SimpleNamespace
    from starlette.datastructures import UploadFile
    from starlette.requests import Request
    import chat_attachment_storage as storage
    import chat_common_handlers as handlers
    import routers.project_chat
    user = SimpleNamespace(id=uuid4())
    pid, aid = uuid4(), uuid4()
    attachment = SimpleNamespace(uploaded_by=user.id)
    db = SimpleNamespace(get=lambda *args, **kwargs: attachment, commit=lambda: None)
    service = SimpleNamespace(require_project=lambda *args: None)
    monkeypatch.setenv('CHAT_STORAGE_MODE', 'remote')
    monkeypatch.setenv('CHAT_REMOTE_ORIGIN', 'https://cloud.example')
    monkeypatch.setenv('CHAT_UPLOADS_PAUSED', 'false')
    async def forwarded(url, content, filename, content_type, authorization, forwarded):
        prefix = 'project-chat/annotation' if scope == 'annotation' else 'chat/direct'
        assert url == f'https://cloud.example/api/{prefix}/{pid}/files'
        assert content == SAMPLES['.mp4'] and content_type == 'video/mp4'
        assert authorization == 'Bearer test'
        return SimpleNamespace(id=aid)
    monkeypatch.setattr(storage, 'upload_remote_attachment', forwarded)
    request = Request({'type': 'http', 'headers': [(b'authorization', b'Bearer test')]})
    result = asyncio.run(handlers.upload_chat_file(service, scope, pid, request,
        UploadFile(BytesIO(SAMPLES['.mp4']), filename='素材.mp4'), db, user))
    assert result.id == aid
    assert getattr(attachment, 'direct_conversation_id' if scope == 'direct' else 'annotation_project_id') == pid
