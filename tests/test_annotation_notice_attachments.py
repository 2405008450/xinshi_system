"""附件真实 PostgreSQL 验收，仅连接专用本机隔离数据库。"""
import asyncio
import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import annotation_notice_attachment_service as files
import annotation_notice_service as sections
from annotation_notice_models import AnnotationNoticeAttachment, AnnotationNoticeSection
from annotation_notice_schemas import AnnotationNoticeAttachmentResponse
from business_time import business_now
from database import get_db
from models import AppUser
from routers import auth
from routers.annotation_notices import router


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = os.getenv('NOTICE_TEST_DATABASE_URL')
    if not url:
        pytest.skip('需要独立 PostgreSQL NOTICE_TEST_DATABASE_URL')
    engine = create_engine(url)
    if engine.url.host != '127.0.0.1' or engine.url.username != 'notice_test' or engine.url.database != 'notices_test':
        raise RuntimeError('拒绝连接非专用本机隔离库')
    import main  # 仅注册 ORM 关联，不启动主应用。
    for table in (AppUser.__table__, AnnotationNoticeSection.__table__):
        table.create(engine, checkfirst=True)
    sql = Path('data/migrations/20261012_annotation_notice_attachments.sql').read_text(encoding='utf-8')
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
    monkeypatch.setenv('ANNOTATION_NOTICE_UPLOAD_DIR', str(tmp_path / 'uploads'))
    with Session(engine) as session:
        user = AppUser(id=uuid4(), username='notice_qa_' + uuid4().hex, password_hash='unused', full_name='附件验收员')
        root = AnnotationNoticeSection(id=uuid4(), section_key=uuid4().hex, title='仅分组', sort_order=1, has_content=False, structure_updated_at=business_now())
        other = AnnotationNoticeSection(id=uuid4(), section_key=uuid4().hex, title='其他', sort_order=2, has_content=True, structure_updated_at=business_now())
        session.add_all([user, root, other])
        session.commit()
        yield session, user, root, other, engine
    engine.dispose()


def upload(session, section_id, user_id, name='中文资料.PDF', content=b'notice-test'):
    return asyncio.run(files.save_attachment(session, section_id, UploadFile(filename=name, file=io.BytesIO(content)), user_id))


def test_missing_schema_returns_503_and_timestamp_has_business_offset():
    with Session(create_engine('sqlite://')) as session:
        with pytest.raises(HTTPException) as error:
            files.list_attachments(session, uuid4())
        assert error.value.status_code == 503
    result = AnnotationNoticeAttachmentResponse(
        id=uuid4(), section_id=uuid4(), original_name='x.pdf', file_size=1, content_type='application/pdf',
        uploaded_by=None, uploaded_by_name=None, uploaded_at=datetime(2026, 10, 9, 9, 18, 43, tzinfo=timezone.utc),
    ).model_dump(mode='json')
    assert result['uploaded_at'] == '2026-10-09T17:18:43+08:00'


def test_upload_ownership_validation_and_soft_delete(db):
    session, user, root, other, _ = db
    child = AnnotationNoticeSection(id=uuid4(), section_key=uuid4().hex, title='二级', parent_id=root.id, sort_order=1, has_content=True)
    session.add(child)
    session.commit()
    first = upload(session, root.id, user.id)
    second = upload(session, child.id, user.id)
    assert first['uploaded_by_name'] == '附件验收员'
    assert first['uploaded_at'].endswith('+08:00') and 'storage_name' not in first
    assert len(files.list_attachments(session, root.id)) == 1
    assert len(files.list_attachments(session, child.id)) == 1
    with pytest.raises(HTTPException) as error:
        files.get_attachment(session, other.id, first['id'])
    assert error.value.status_code == 404
    for name, content, status in [('执行.exe', b'x', 400), ('空.pdf', b'', 400), ('大.pdf', b'x' * (files.MAX_FILE_BYTES + 1), 413), ('x' * 256 + '.pdf', b'x', 400)]:
        with pytest.raises(HTTPException) as error:
            upload(session, root.id, user.id, name, content)
        assert error.value.status_code == status
    assert len(list(files.upload_dir().iterdir())) == 2
    with pytest.raises(ValueError):
        files.attachment_path('../escape.pdf')
    sections.delete_annotation_notice_section(session, child.id)
    assert session.get(AnnotationNoticeAttachment, second['id']) is not None
    with pytest.raises(HTTPException) as error:
        files.list_attachments(session, child.id)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        upload(session, child.id, user.id)


def test_interrupted_upload_and_commit_failure_restore_files(db, monkeypatch):
    session, user, root, _, _ = db
    first = upload(session, root.id, user.id)
    interrupted = UploadFile(filename='取消.pdf', file=io.BytesIO(b'cancel'))
    async def cancelled_read(_size):
        raise asyncio.CancelledError()
    interrupted.read = cancelled_read
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(files.save_attachment(session, root.id, interrupted, user.id))
    real_commit = session.commit
    def fail():
        raise RuntimeError('commit failed')
    monkeypatch.setattr(session, 'commit', fail)
    with pytest.raises(RuntimeError):
        upload(session, root.id, user.id)
    with pytest.raises(RuntimeError):
        files.delete_attachment(session, root.id, first['id'])
    monkeypatch.setattr(session, 'commit', real_commit)
    assert len(list(files.upload_dir().iterdir())) == 1
    retained = files.get_attachment(session, root.id, first['id'])
    assert files.attachment_path(retained.storage_name).read_bytes() == b'notice-test'
    files.delete_attachment(session, root.id, first['id'])
    assert files.list_attachments(session, root.id) == []
    assert list(files.upload_dir().iterdir()) == []


def test_concurrent_uploads_stop_at_50(db):
    session, user, root, _, engine = db
    sid, uid = root.id, user.id
    for _ in range(49):
        upload(session, sid, uid)
    session.commit()
    start = Barrier(2)
    def attempt(_):
        with Session(engine) as worker:
            start.wait(timeout=5)
            try:
                upload(worker, sid, uid)
                return 201
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [201, 400]
    assert len(files.list_attachments(session, sid)) == 50
    assert len(list(files.upload_dir().iterdir())) == 50
    with pytest.raises(HTTPException):
        upload(session, sid, uid)


def test_upload_waiting_for_deleted_section_is_rejected(db):
    session, user, root, _, engine = db
    sid, uid = root.id, user.id
    session.commit()
    locked, started = Event(), Event()
    def remove():
        with Session(engine) as worker:
            row = worker.query(AnnotationNoticeSection).filter_by(id=sid).with_for_update().one()
            locked.set()
            assert started.wait(5)
            assert sections.delete_annotation_notice_section(worker, sid)
    def attempt():
        assert locked.wait(5)
        with Session(engine) as worker:
            started.set()
            with pytest.raises(HTTPException) as error:
                upload(worker, sid, uid)
            return error.value.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        removed = pool.submit(remove)
        waiting = pool.submit(attempt)
        removed.result(timeout=10)
        assert waiting.result(timeout=10) == 404
    assert session.query(AnnotationNoticeAttachment).filter_by(section_id=sid).count() == 0


def test_api_permissions_download_and_deleted_file(db, monkeypatch):
    session, user, root, _, _ = db
    permissions = set()
    monkeypatch.setattr(auth, 'user_has_permission', lambda _db, _id, code: code in permissions)
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda _db, _id: list(permissions))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    path = f'/annotation-notices/sections/{root.id}/attachments'
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        app.dependency_overrides[auth.get_current_user] = lambda: user
        assert client.get(path).status_code == 403
        permissions.add('projects:read')
        assert client.get(path).status_code == 200
        assert client.post(path, files={'file': ('中文.pdf', b'payload')}).status_code == 403
        permissions.add('projects:write')
        response = client.post(path, files={'file': ('中文.pdf', b'payload')})
        assert response.status_code == 201, response.text
        data = response.json()
        assert data['uploaded_at'].endswith('+08:00') and 'storage_name' not in data
        download_path = path + '/' + data['id']
        permissions.remove('projects:write')
        download = client.get(download_path)
        assert download.content == b'payload'
        assert 'filename*=utf-8' in download.headers['content-disposition'].lower()
        assert download.headers['x-content-type-options'] == 'nosniff'
        assert client.delete(download_path).status_code == 403
        permissions.add('projects:write')
        assert client.delete(download_path).status_code == 204
        assert client.get(download_path).status_code == 404
