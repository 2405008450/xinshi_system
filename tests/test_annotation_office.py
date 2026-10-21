"""Office 集成隔离回归；复用资料测试临时数据库和文件目录。"""
import asyncio
from datetime import timedelta
from uuid import UUID, uuid4
from types import SimpleNamespace
import io
import logging
import zipfile
import httpx
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_annotation_materials import env, stage
from annotation_office_models import OFFICE_TABLES, AnnotationOfficeSession as OfficeSession, AnnotationOfficeSave as OfficeSave
from annotation_material_models import AnnotationMaterialVersion as Version, AnnotationMaterialUpload as Upload
import annotation_material_service as materials
import annotation_office_service as office
from routers import annotation_office as routes


@pytest.fixture
def ctx(env, monkeypatch):
    db, user, project, other = env
    if db.bind.dialect.name == 'postgresql':
        sql = (Path(__file__).resolve().parents[1] / 'data/migrations/20261021_annotation_office_sessions.sql').read_text(encoding='utf-8')
        sql = sql.strip().removeprefix('BEGIN;').removesuffix('COMMIT;')
        db.execute(text(sql)); db.execute(text(sql)); db.commit()
    else:
        for table in OFFICE_TABLES:
            table.create(db.get_bind(), checkfirst=True)
    monkeypatch.setenv('ANNOTATION_OFFICE_ENABLED', 'true')
    monkeypatch.setenv('ANNOTATION_OFFICE_SERVER_ORIGIN', 'https://office.example.test')
    monkeypatch.setenv('ANNOTATION_OFFICE_PUBLIC_ORIGIN', 'https://oa.example.test')
    monkeypatch.setenv('ANNOTATION_OFFICE_JWT_SECRET', 'isolated-office-test-secret-not-for-deployment')
    monkeypatch.setattr(office, 'require_access', lambda *args, **kwargs: None)
    monkeypatch.setattr(office, 'user_has_permission', lambda *args: True)
    upload = stage(db, user, '上传的说明.docx')
    data = office.blank_docx()
    materials.storage_path(upload.storage_key).write_bytes(data)
    upload.file_size = len(data)
    material, version = materials.attach_upload(db, project, upload.id, user.id, 'project')
    db.commit()
    return db, user, project, other, material, version, data


def start(ctx):
    db, user, project, _, material, *_ = ctx
    return office.create_session(db, project, user, file_id=material.id)


def force(ctx, session, monkeypatch, code=0, revision=0):
    async def command(data):
        return {'error': code, 'key': data['key']}
    monkeypatch.setattr(office, 'command', command)
    task_id = uuid4()
    asyncio.run(office.request_save(ctx[0], session, task_id, revision))
    return task_id


def result(ctx, session, task_id, monkeypatch, status=6):
    async def fetch(_url, _kind='docx'):
        return ctx[-1]
    monkeypatch.setattr(office, 'fetch_result', fetch)
    asyncio.run(office.callback(ctx[0], session.id, {'key': session.document_key, 'status': status,
        'url': 'https://office.example.test/cache/files/result.' + office.file_kind(session.original_name), 'userdata': str(task_id)}))


@pytest.fixture
def xlsx_ctx(ctx):
    db, user, project, other, material, base, _ = ctx
    upload = db.get(Upload, base.upload_id)
    data = office.blank_xlsx()
    upload.original_name = '上传的预算.XLSX'
    upload.content_type = office.FORMATS['xlsx']['mime']
    upload.file_size = len(data)
    materials.storage_path(upload.storage_key).write_bytes(data)
    db.commit()
    return db, user, project, other, material, base, data


def test_xlsx_uploaded_save_lock_and_mime(xlsx_ctx, monkeypatch):
    db, user, project, _, material, base, data = xlsx_ctx
    session = start(xlsx_ctx)
    config = office.describe(db, session, config=True)['config']
    assert config['documentType'] == 'cell' and config['document']['fileType'] == 'xlsx'
    assert start(xlsx_ctx).mode == 'view'
    with pytest.raises(ValueError, match='在线编辑'):
        materials.remove_material(db, material)
    db.rollback()
    source = routes.source(session.id, office.scope_token(session, 'source'), db)
    assert source.media_type == office.FORMATS['xlsx']['mime']
    task = force(xlsx_ctx, session, monkeypatch, revision=1)
    result(xlsx_ctx, session, task, monkeypatch)
    result(xlsx_ctx, session, task, monkeypatch)
    assert session.state == 'saved' and db.query(Version).count() == 2
    saved = db.get(Version, session.saved_version_id)
    upload = db.get(Upload, saved.upload_id)
    assert upload.original_name.endswith('.XLSX') and upload.content_type == office.FORMATS['xlsx']['mime']
    assert materials.storage_path(upload.storage_key).read_bytes() == data


def test_xlsx_new_readonly_and_cancel(xlsx_ctx, monkeypatch):
    db, user, project, *_ = xlsx_ctx
    session = start(xlsx_ctx)
    viewer = start(xlsx_ctx)
    with pytest.raises(HTTPException) as exc:
        force(xlsx_ctx, viewer, monkeypatch)
    assert exc.value.status_code == 403
    task = force(xlsx_ctx, session, monkeypatch)
    session.state = 'discarded'; db.commit()
    result(xlsx_ctx, session, task, monkeypatch)
    assert db.query(Version).count() == 1
    new = office.create_session(db, project, user, name='新建预算.xlsx')
    force(xlsx_ctx, new, monkeypatch, code=4)
    assert new.state == 'saved' and new.file_id
    assert office.create_session(db, project, user, file_id=new.file_id).mode == 'edit'


def test_xlsx_format_mismatch_and_invalid_parts(ctx, monkeypatch):
    with pytest.raises(HTTPException):
        office.validate_office(ctx[-1], 'xlsx')
    with pytest.raises(HTTPException):
        office.validate_docx(office.blank_xlsx())
    for part, value in [('xl/vbaProject.bin', b'macro'),
                        ('xl/worksheets/sheet1.xml', b'<not-a-worksheet/>'),
                        ('xl/workbook.xml', b'<!DOCTYPE foo [<!ENTITY x "boom">]><foo>&x;</foo>'),
                        ('xl/_rels/workbook.xml.rels', b'<Relationships/>')]:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(office.blank_xlsx())) as source, zipfile.ZipFile(output, 'w') as target:
            for item in source.infolist():
                if item.filename != part:
                    target.writestr(item.filename, source.read(item.filename))
            target.writestr(part, value)
        with pytest.raises(HTTPException) as exc:
            office.validate_office(output.getvalue(), 'xlsx')
        assert exc.value.status_code == 400
    original = httpx.AsyncClient
    monkeypatch.setattr(office.httpx, 'AsyncClient', lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=ctx[-1])), **kwargs))
    with pytest.raises(HTTPException):
        asyncio.run(office.fetch_result('https://office.example.test/cache/files/renamed.xlsx', 'xlsx'))


def test_uploaded_word_open_source_and_single_writer(ctx):
    db, user, project, other, material, base, data = ctx
    session = start(ctx)
    assert session.mode == 'edit'
    second = start(ctx)
    assert second.mode == 'view' and second.document_key != session.document_key
    description = office.describe(db, second, config=True)
    assert description['occupant'] == user.full_name
    assert description['config']['document']['permissions']['edit'] is False
    assert description['config']['editorConfig']['mode'] == 'view'
    assert description['lease_until'].endswith('+08:00')
    assert materials.storage_path(db.get(Upload, session.source_upload_id).storage_key).read_bytes() == data
    assert db.query(Version).count() == 1
    with pytest.raises(ValueError, match='在线编辑'):
        materials.remove_material(db, material)
    db.rollback()
    new = stage(db, user)
    with pytest.raises(ValueError, match='在线编辑'):
        materials.attach_upload(db, project, new.id, user.id, 'project', material.id)
    db.rollback()
    with pytest.raises(HTTPException) as exc:
        office.create_session(db, other, user, file_id=material.id)
    assert exc.value.status_code == 404


def test_save_callback_idempotent_and_history_retained(ctx, monkeypatch):
    db = ctx[0]
    session = start(ctx)
    task_id = force(ctx, session, monkeypatch)
    assert session.state == 'saving'
    assert db.query(Version).count() == 1
    result(ctx, session, task_id, monkeypatch)
    assert session.state == 'saved'
    assert db.get(OfficeSave, task_id).state == 'complete'
    assert db.query(Version).count() == 2
    result(ctx, session, task_id, monkeypatch)
    asyncio.run(office.request_save(db, session, task_id))
    assert db.query(Version).count() == 2
    saved = db.get(Version, session.saved_version_id)
    assert materials.storage_path(db.get(Upload, saved.upload_id).storage_key).read_bytes() == ctx[-1]


def test_autosave_only_stages_and_discard_fences_late_callback(ctx, monkeypatch):
    db = ctx[0]
    session = start(ctx)
    async def fetch(_url, _kind='docx'):
        return ctx[-1]
    monkeypatch.setattr(office, 'fetch_result', fetch)
    asyncio.run(office.callback(db, session.id, {'key': session.document_key, 'status': 6,
                                               'url': 'https://office.example.test/cache/files/a.docx'}))
    assert session.staged_upload_id
    assert db.query(Version).count() == 1
    session.state = 'discarded'; db.commit()
    result(ctx, session, uuid4(), monkeypatch)
    assert db.query(Version).count() == 1
    assert start(ctx).mode == 'edit'


def test_expired_lock_cannot_save_or_renew(ctx, monkeypatch):
    db, user, *_ = ctx
    old = start(ctx)
    old.lease_until = office.now() - timedelta(seconds=1); db.commit()
    new = start(ctx)
    assert old.state == 'expired' and new.mode == 'edit'
    with pytest.raises(HTTPException):
        force(ctx, old, monkeypatch)
    assert office.owned_session(db, old.id, user).state == 'expired'
    result(ctx, old, uuid4(), monkeypatch)
    assert db.query(Version).count() == 1


def test_no_changes_and_new_word(ctx, monkeypatch):
    db, user, project, *_ = ctx
    old = start(ctx)
    force(ctx, old, monkeypatch, code=4)
    assert old.state == 'saved' and db.query(Version).count() == 1
    new = office.create_session(db, project, user, name='新建文档.docx')
    force(ctx, new, monkeypatch, code=4)
    assert new.state == 'saved' and new.file_id
    assert db.query(Version).count() == 2
    assert office.create_session(db, project, user, file_id=new.file_id).mode == 'edit'


def test_new_word_name_conflict_uses_current_version(ctx, monkeypatch):
    db, user, project, _, material, *_ = ctx
    upload = stage(db, user, '更名说明.docx')
    materials.attach_upload(db, project, upload.id, user.id, 'project', file_id=material.id); db.commit()
    # 已经更名的历史文件名可重新使用；最新文件名仍然拒绝重名。
    new = office.create_session(db, project, user, name='上传的说明.docx')
    force(ctx, new, monkeypatch, code=4)
    assert new.state == 'saved'
    duplicate = office.create_session(db, project, user, name='更名说明.docx')
    with pytest.raises(HTTPException) as exc:
        force(ctx, duplicate, monkeypatch, code=4)
    assert exc.value.status_code == 409 and duplicate.state == 'open'


def test_readonly_denied_conflict_and_save_failure_retry(ctx, monkeypatch):
    db = ctx[0]
    session = start(ctx)
    readonly = start(ctx)
    with pytest.raises(HTTPException) as exc:
        force(ctx, readonly, monkeypatch)
    assert exc.value.status_code == 403
    async def failed(_data):
        raise HTTPException(503, '模拟服务中断')
    monkeypatch.setattr(office, 'command', failed)
    with pytest.raises(HTTPException):
        asyncio.run(office.request_save(db, session, uuid4()))
    assert session.state == 'open'
    task_id = force(ctx, session, monkeypatch)
    # 模拟不遵循租约的旧客户端，验证最终乐观锁仍然拒绝覆盖。
    base = ctx[-2]
    db.add(Version(file_id=session.file_id, upload_id=base.upload_id, version_no=2)); db.commit()
    result(ctx, session, task_id, monkeypatch)
    assert db.get(OfficeSave, task_id).state == 'failed'
    assert '更新' in db.get(OfficeSave, task_id).error
    assert session.staged_upload_id and db.query(Version).count() == 2


@pytest.mark.parametrize('url', ['http://office.example.test/cache/files/a', 'https://evil.test/cache/files/a',
    'https://office.example.test@evil.test/cache/files/a', 'https://office.example.test/internal',
    'https://office.example.test.evil.test/cache/files/a'])
def test_callback_download_rejects_untrusted_urls(ctx, url):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(office.fetch_result(url))
    assert exc.value.status_code == 403


def test_signatures_source_and_callback_endpoints(ctx, monkeypatch):
    db, user, *_ = ctx
    session = start(ctx)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda: db
    app.dependency_overrides[routes.get_current_user] = lambda: user
    for route in routes.router.routes:
        for dependency in route.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: user
    root = f'/projects/annotation/office/sessions/{session.id}'
    with TestClient(app) as client:
        source_token = office.scope_token(session, 'source')
        assert client.get(root + '/source?token=invalid').status_code == 403
        assert client.get(root + '/source?token=' + source_token).content == ctx[-1]
        assert client.post(root + '/callback?token=' + source_token, json={}).status_code == 403
        callback_token = office.scope_token(session, 'callback')
        payload = {'key': session.document_key, 'status': 1}
        assert client.post(root + '/callback?token=' + callback_token, json=payload).status_code == 403
        signed = office.sign({'payload': payload})
        assert client.post(root + '/callback?token=' + callback_token, json=payload,
                           headers={'Authorization': 'Bearer ' + signed}).json() == {'error': 0}
        assert client.post(root + '/callback?token=' + callback_token, json={**payload, 'status': 6},
                           headers={'Authorization': 'Bearer ' + signed}).status_code == 403
        assert client.post(root + '/heartbeat').status_code == 200
        assert client.post(root + '/discard').json()['state'] == 'discarded'
        assert client.post(root + '/heartbeat').status_code == 409
        assert client.get(root + '/source?token=' + source_token).status_code == 410


def test_disabled_and_invalid_documents(ctx, monkeypatch):
    for value in (b'not a zip', b'', b'PK'):
        with pytest.raises(HTTPException):
            office.validate_docx(value)
    monkeypatch.setenv('ANNOTATION_OFFICE_ENABLED', 'false')
    with pytest.raises(HTTPException) as exc:
        start(ctx)
    assert exc.value.status_code == 503


def test_old_save_callback_cannot_commit_new_task(ctx, monkeypatch):
    db = ctx[0]
    session = start(ctx)
    old_id = force(ctx, session, monkeypatch, revision=1)
    old = db.get(OfficeSave, old_id)
    old.state, session.state = 'failed', 'open'; db.commit()
    new_id = force(ctx, session, monkeypatch, revision=2)
    result(ctx, session, old_id, monkeypatch)
    assert db.query(Version).count() == 1 and session.staged_upload_id is None
    result(ctx, session, new_id, monkeypatch)
    assert db.query(Version).count() == 2


def test_no_changes_response_waits_for_matching_inflight_snapshot(ctx, monkeypatch):
    db = ctx[0]
    session = start(ctx)
    old_id = force(ctx, session, monkeypatch, revision=1)
    db.get(OfficeSave, old_id).state, session.state = 'failed', 'open'; db.commit()
    new_id = force(ctx, session, monkeypatch, code=4, revision=1)
    assert db.get(OfficeSave, new_id).state == 'pending_snapshot'
    assert session.state == 'saving' and db.query(Version).count() == 1
    result(ctx, session, old_id, monkeypatch)
    assert db.get(OfficeSave, new_id).state == 'complete'
    assert session.state == 'saved' and db.query(Version).count() == 2


def test_access_revocation_and_foreign_owner(ctx, monkeypatch):
    db = ctx[0]
    session = start(ctx)
    with pytest.raises(HTTPException) as exc:
        office.owned_session(db, session.id, SimpleNamespace(id=uuid4()))
    assert exc.value.status_code == 404
    task = force(ctx, session, monkeypatch)
    def forbidden(*_args, **_kwargs):
        raise HTTPException(403, '账号权限已撤销')
    monkeypatch.setattr(office, 'require_access', forbidden)
    with pytest.raises(HTTPException) as exc:
        result(ctx, session, task, monkeypatch)
    assert exc.value.status_code == 403 and db.query(Version).count() == 1


def test_zip_macro_and_xml_entity_rejected(ctx):
    for name, body in [('word/vbaProject.bin', b'macro'),
                       ('word/document.xml', b'<!DOCTYPE foo [<!ENTITY x "boom">]><foo>&x;</foo>')]:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(ctx[-1])) as source, zipfile.ZipFile(output, 'w') as target:
            for entry in source.infolist():
                if entry.filename != name:
                    target.writestr(entry.filename, source.read(entry.filename))
            target.writestr(name, body)
        with pytest.raises(HTTPException) as exc:
            office.validate_docx(output.getvalue())
        assert exc.value.status_code == 400


def test_result_download_bytes_redirect_and_limits(ctx, monkeypatch):
    original = httpx.AsyncClient
    responses = [httpx.Response(200, content=ctx[-1]), httpx.Response(302, headers={'Location': 'https://evil.test/a'}),
                 httpx.Response(200, content=b'not a Word file')]
    def request(_request):
        return responses.pop(0)
    monkeypatch.setattr(office.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(request), **kwargs))
    url = 'https://office.example.test/cache/files/a.docx'
    assert asyncio.run(office.fetch_result(url)) == ctx[-1]
    with pytest.raises(HTTPException):
        asyncio.run(office.fetch_result(url))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(office.fetch_result(url))
    assert exc.value.status_code == 400


def test_virtual_path_preserves_result_allowlist(ctx, monkeypatch):
    monkeypatch.setenv('ANNOTATION_OFFICE_SERVER_ORIGIN', 'https://office.example.test/office/')
    assert office.settings()['server'] == 'https://office.example.test/office'
    session = start(ctx)
    assert office.describe(ctx[0], session, config=True)['script_url'].startswith('https://office.example.test/office/')
    original = httpx.AsyncClient
    monkeypatch.setattr(office.httpx, 'AsyncClient', lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=ctx[-1])), **kwargs))
    assert asyncio.run(office.fetch_result('https://office.example.test/office/cache/files/a.docx')) == ctx[-1]
    for path in ['/cache/files/a.docx', '/office/cache/files/../../../api/a',
                 '/office/cache/files/%2e%2e/api/a', '/office2/cache/files/a.docx']:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(office.fetch_result('https://office.example.test' + path))
        assert exc.value.status_code == 403
    for path in ['/office/../api', '/office%2fapi', '/office?x=1']:
        monkeypatch.setenv('ANNOTATION_OFFICE_SERVER_ORIGIN', 'https://office.example.test' + path)
        with pytest.raises(HTTPException):
            office.settings()


def test_expired_url_and_access_log_redaction(ctx):
    session = start(ctx)
    token = office.sign({'sid': str(session.id), 'scope': 'source', 'exp': 1})
    with pytest.raises(HTTPException) as exc:
        office.verify_scope(session, token, 'source')
    assert exc.value.status_code == 403
    record = logging.makeLogRecord({'args': ('127.0.0.1', 'GET', '/office/sessions/abc/source?token=secret&x=1', '1.1', 200)})
    routes.OfficeAccessLogFilter().filter(record)
    assert record.args[2].endswith('token=[REDACTED]&x=1')


def test_remote_control_forwards_to_authoritative_storage(ctx, monkeypatch):
    from starlette.requests import Request
    from annotation_material_storage import FORWARDED
    captured = []
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def request(self, method, url, **kwargs):
            captured.append((method, url, kwargs))
            return httpx.Response(201, json={'id': 'cloud-session'})
    monkeypatch.setenv('ANNOTATION_MATERIAL_STORAGE_MODE', 'remote')
    monkeypatch.setenv('ANNOTATION_MATERIAL_REMOTE_ORIGIN', 'https://storage.example.test')
    monkeypatch.setattr(routes, 'client', FakeClient)
    request = Request({'type': 'http', 'method': 'POST', 'path': '/projects/annotation/test/office/sessions',
                       'headers': [(b'authorization', b'Bearer isolated-token')], 'query_string': b''})
    request._body = b'{"file_id":"test"}'
    response = asyncio.run(routes.forward(request))
    assert response.status_code == 201
    assert captured[0][1] == 'https://storage.example.test/api/projects/annotation/test/office/sessions'
    assert captured[0][2]['headers'][FORWARDED] == '1'
    assert captured[0][2]['headers']['Authorization'] == 'Bearer isolated-token'
    assert captured[0][2]['content'] == request._body
    with pytest.raises(HTTPException) as exc:
        routes.server_session(ctx[0], uuid4(), '', 'source')
    assert exc.value.status_code == 503


def test_postgres_parallel_windows_obtain_one_write_lease(ctx):
    if ctx[0].bind.dialect.name != 'postgresql':
        pytest.skip('需本机隔离 PostgreSQL 验证跨连接行锁与唯一索引')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    engine, user, project, file_id = ctx[0].bind, ctx[1], ctx[2], ctx[4].id
    barrier = Barrier(2)
    def open_window():
        with Session(engine) as connection:
            barrier.wait(timeout=5)
            return office.create_session(connection, project, user, file_id=file_id).mode
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(open_window), pool.submit(open_window)
        assert sorted([first.result(timeout=15), second.result(timeout=15)]) == ['edit', 'view']
