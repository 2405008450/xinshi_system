"""隔离 SQLite 验证资料事务和接口，绝不读取或写入业务数据库。"""
import asyncio
import io
import os
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile

import main  # 注册完整 ORM 映射；导入不会启动迁移或数据库连接。
from annotation_material_models import MATERIAL_TABLES, AnnotationMaterialUpload as Upload, AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialDeletion as Deletion
from annotation_material_schemas import MaterialChanges
import annotation_material_service as service
import annotation_material_storage as storage
from routers import annotation_materials as routes


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('ANNOTATION_MATERIAL_STORAGE_MODE', 'local')
    monkeypatch.setenv('ANNOTATION_MATERIAL_DIR', str(tmp_path))
    postgres_url = os.getenv('MATERIAL_TEST_DATABASE_URL')
    schema = 'material_test_' + uuid4().hex
    if postgres_url:
        engine = create_engine(postgres_url, connect_args={'options': f'-csearch_path={schema}'})
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text('CREATE TABLE app_user (id UUID PRIMARY KEY)'))
            connection.execute(text('CREATE TABLE annotation_project (id UUID PRIMARY KEY)'))
            migration = (Path(__file__).resolve().parents[1] / 'data/migrations/20261013_annotation_materials.sql').read_text(encoding='utf-8').strip().removeprefix('BEGIN;').removesuffix('COMMIT;')
            connection.execute(text(migration))
            connection.execute(text(migration))  # 迁移可重复执行。
    else:
        engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        with engine.begin() as connection:
            connection.execute(text('PRAGMA foreign_keys=ON'))
            connection.execute(text('CREATE TABLE app_user (id CHAR(32) PRIMARY KEY)'))
            connection.execute(text('CREATE TABLE annotation_project (id CHAR(32) PRIMARY KEY)'))
        for table in MATERIAL_TABLES:
            table.create(engine)
    user_id, project_id, other_project = uuid4(), uuid4(), uuid4()
    with Session(engine) as db:
        db.execute(text('INSERT INTO app_user VALUES (:id)'), {'id': user_id.hex})
        for value in (project_id, other_project):
            db.execute(text('INSERT INTO annotation_project VALUES (:id)'), {'id': value.hex})
        db.commit()
        user = SimpleNamespace(id=user_id, username='tester', full_name='资料测试')
        yield db, user, project_id, other_project
    if postgres_url:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    engine.dispose()


def stage(db, user, name='资料.txt', expired=False):
    key = uuid4().hex
    service.storage_path(key).write_bytes(b'content')
    row = Upload(uploaded_by=user.id, uploader_name=user.full_name, original_name=name, storage_key=key,
                 file_size=7, content_type='application/octet-stream', sha256='a' * 64,
                 expires_at=datetime.utcnow() + timedelta(hours=-1 if expired else 24))
    db.add(row); db.commit()
    return row


def change(upload, file_id=None, category='project'):
    return MaterialChanges(additions=[{'upload_id': upload.id, 'file_id': file_id, 'category': category}])


def test_versions_same_name_and_transaction_rollback(env):
    db, user, project, _ = env
    first, second = stage(db, user), stage(db, user)
    service.apply_changes(db, project, change(first), user.id); db.commit()
    file_id = service.versions(db, project)[0]['file_id']
    service.apply_changes(db, project, change(second, file_id), user.id)
    db.rollback()
    assert len(service.versions(db, project)) == 1
    assert db.get(Upload, second.id).consumed_at is None
    service.apply_changes(db, project, change(second, file_id), user.id); db.commit()
    assert [row['version_no'] for row in service.versions(db, project)] == [2, 1]
    third = stage(db, user)
    service.apply_changes(db, project, change(third), user.id); db.commit()
    assert db.query(Material).count() == 2
    with pytest.raises(ValueError, match='已使用'):
        service.apply_changes(db, project, change(third), user.id)
    db.rollback()


def test_wrong_owner_expired_foreign_file_and_category(env):
    db, user, project, other_project = env
    upload = stage(db, user)
    with pytest.raises(ValueError):
        service.apply_changes(db, project, change(upload), uuid4())
    db.rollback()
    expired = stage(db, user, expired=True)
    with pytest.raises(ValueError):
        service.apply_changes(db, project, change(expired), user.id)
    db.rollback()
    service.apply_changes(db, project, change(upload), user.id); db.commit()
    file_id = service.versions(db, project)[0]['file_id']
    new = stage(db, user)
    for target, category in ((other_project, 'project'), (project, 'contract')):
        with pytest.raises(ValueError, match='不属于|不匹配'):
            service.apply_changes(db, target, change(new, file_id, category), user.id)
        db.rollback()


def test_removal_only_after_commit_and_cleanup_retry(env, monkeypatch):
    db, user, project, _ = env
    upload = stage(db, user)
    key = upload.storage_key
    service.apply_changes(db, project, change(upload), user.id); db.commit()
    file_id = service.versions(db, project)[0]['file_id']
    changes = MaterialChanges(removed_file_ids=[file_id])
    service.apply_changes(db, project, changes, user.id); db.rollback()
    assert service.versions(db, project)
    service.apply_changes(db, project, changes, user.id); db.commit()
    assert not service.versions(db, project)
    assert service.storage_path(key).exists()
    from pathlib import Path
    original = Path.unlink
    monkeypatch.setattr(Path, 'unlink', lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError('busy')))
    service.cleanup(db)
    assert db.get(Deletion, key).attempts == 1
    monkeypatch.setattr(Path, 'unlink', original)
    service.cleanup(db)
    assert not service.storage_path(key).exists()
    assert db.get(Deletion, key) is None


def test_cleanup_only_expired_unconsumed_and_only_on_cloud(env, monkeypatch):
    db, user, project, _ = env
    expired, fresh, used = stage(db, user, expired=True), stage(db, user), stage(db, user)
    expired_key, fresh_key, used_key = expired.storage_key, fresh.storage_key, used.storage_key
    service.apply_changes(db, project, change(used), user.id); db.commit()
    used.expires_at = datetime.utcnow() - timedelta(days=2); db.commit()
    monkeypatch.setenv('ANNOTATION_MATERIAL_STORAGE_MODE', 'remote')
    service.cleanup(db)
    assert service.storage_path(expired_key).exists()
    monkeypatch.setenv('ANNOTATION_MATERIAL_STORAGE_MODE', 'local')
    service.cleanup(db)
    assert not service.storage_path(expired_key).exists()
    assert service.storage_path(fresh_key).exists() and service.storage_path(used_key).exists()


def test_crash_orphans_cleaned_but_recent_and_linked_files_retained(env):
    import time
    db, user, project, _ = env
    linked = stage(db, user)
    service.apply_changes(db, project, change(linked), user.id); db.commit()
    old, fresh = service.storage_path(uuid4().hex), service.storage_path(uuid4().hex)
    old.write_bytes(b'orphan'); fresh.write_bytes(b'uploading')
    for path in (old, service.storage_path(linked.storage_key)):
        os.utime(path, (time.time() - 90000, time.time() - 90000))
    service.cleanup(db)
    assert not old.exists()
    assert fresh.exists() and service.storage_path(linked.storage_key).exists()


def test_project_deletion_queues_every_version(env):
    db, user, project, _ = env
    first, second = stage(db, user), stage(db, user)
    service.apply_changes(db, project, change(first), user.id); db.commit()
    service.apply_changes(db, project, change(second, service.versions(db, project)[0]['file_id']), user.id); db.commit()
    service.remove_project_materials(db, project); db.commit()
    assert db.query(Version).count() == 0
    assert db.query(Deletion).count() == 2


@pytest.fixture
def client(env, monkeypatch):
    db, user, project, other_project = env
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda: db
    app.dependency_overrides[routes.get_current_user] = lambda: user
    for route in routes.router.routes:
        for dependency in route.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: user
    def require_project(_db, value):
        if value not in (project, other_project):
            raise HTTPException(404)
    monkeypatch.setattr(routes, 'require_project', require_project)
    with TestClient(app) as test_client:
        yield test_client


def test_api_upload_download_cancel_and_cross_project(env, client):
    db, user, project, other_project = env
    response = client.post('/projects/annotation/material-uploads', files={'file': ('中文资料.txt', b'hello')})
    assert response.status_code == 201, response.text
    from uuid import UUID
    upload = db.get(Upload, UUID(response.json()['id']))
    assert upload.original_name == '中文资料.txt'
    service.apply_changes(db, project, change(upload), user.id); db.commit()
    row = client.get(f'/projects/annotation/{project}/materials').json()[0]
    suffix = f"/materials/{row['file_id']}/versions/{row['id']}/download"
    result = client.get(f'/projects/annotation/{project}' + suffix)
    assert result.content == b'hello'
    assert result.headers['content-disposition'].startswith('attachment;')
    assert client.get(f'/projects/annotation/{other_project}' + suffix).status_code == 404
    assert client.delete(f'/projects/annotation/material-uploads/{upload.id}').status_code == 204
    assert db.get(Upload, upload.id) is not None
    assert client.post('/projects/annotation/material-uploads', files={'file': ('empty', b'')}).status_code == 413


def test_upload_boundary_and_midstream_failure(env, monkeypatch):
    db, user, *_ = env
    # 使用较小边界验证实际分块计数，避免测试生成百兆文件；常量单独断言。
    assert routes.MAX_BYTES == 100 * 1024 * 1024
    monkeypatch.setattr(routes, 'MAX_BYTES', 10)
    request = SimpleNamespace(headers={})
    for count, allowed in ((10, True), (11, False)):
        file = UploadFile(io.BytesIO(b'x' * count), filename='size.txt')
        if allowed:
            result = asyncio.run(routes.upload_material(request, file, None, db, user))
            assert result['file_size'] == 10
        else:
            with pytest.raises(HTTPException) as error:
                asyncio.run(routes.upload_material(request, file, None, db, user))
            assert error.value.status_code == 413
    assert db.query(Upload).count() == 1
    assert len(list(service.storage_path('a' * 32).parent.iterdir())) == 1


def test_upload_db_failure_and_stream_interruption_leave_no_file(env, monkeypatch):
    db, user, *_ = env
    def fail_commit(): raise RuntimeError('commit failed')
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', fail_commit)
        with pytest.raises(RuntimeError, match='commit failed'):
            asyncio.run(routes.upload_material(SimpleNamespace(headers={}), UploadFile(io.BytesIO(b'hello'), filename='a'), None, db, user))
    assert db.query(Upload).count() == 0
    assert list(service.storage_path('c' * 32).parent.iterdir()) == []
    class InterruptedUpload(UploadFile):
        async def read(self, size=-1):
            if self.file.tell(): raise RuntimeError('connection lost')
            return await super().read(size)
    with pytest.raises(RuntimeError, match='connection lost'):
        asyncio.run(routes.upload_material(SimpleNamespace(headers={}), InterruptedUpload(io.BytesIO(b'hello'), filename='a'), None, db, user))
    assert list(service.storage_path('c' * 32).parent.iterdir()) == []


def test_remote_configuration_and_auth_fail_closed(monkeypatch):
    monkeypatch.delenv('ANNOTATION_MATERIAL_STORAGE_MODE', raising=False)
    with pytest.raises(HTTPException): storage.remote_origin()
    monkeypatch.setenv('ANNOTATION_MATERIAL_STORAGE_MODE', 'remote')
    for value in ('http://example.com', 'https://example.com/path', 'https://user:pass@example.com', 'https://example.com:8443'):
        monkeypatch.setenv('ANNOTATION_MATERIAL_REMOTE_ORIGIN', value)
        with pytest.raises(HTTPException): storage.remote_origin()
    monkeypatch.setenv('ANNOTATION_MATERIAL_REMOTE_ORIGIN', 'https://example.com')
    assert storage.remote_origin() == 'https://example.com'
    with pytest.raises(HTTPException): storage.forwarding_headers(SimpleNamespace(headers={storage.FORWARDED: '1'}))
    with pytest.raises(HTTPException) as error: storage.check(SimpleNamespace(status_code=401))
    assert error.value.status_code == 502


def test_conflicting_changes_rejected():
    target, upload = uuid4(), uuid4()
    with pytest.raises(ValueError):
        MaterialChanges(additions=[{'upload_id': upload, 'file_id': target, 'category': 'project'}], removed_file_ids=[target])


def test_permissions_read_only_and_unauthenticated(env, monkeypatch):
    db, user, project, _ = env
    from routers import auth
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda: db
    app.dependency_overrides[routes.get_current_user] = lambda: user
    monkeypatch.setattr(auth, 'user_has_permission', lambda _db, _user, permission: permission == 'projects:read')
    monkeypatch.setattr(routes, 'require_project', lambda *_args: None)
    with TestClient(app) as client:
        assert client.get(f'/projects/annotation/{project}/materials').status_code == 200
        assert client.post('/projects/annotation/material-uploads', files={'file': ('a.txt', b'a')}).status_code == 403
        def unauthorized(): raise HTTPException(401)
        app.dependency_overrides[routes.get_current_user] = unauthorized
        assert client.get(f'/projects/annotation/{project}/materials').status_code == 401


def test_cloud_forward_roundtrip_preserves_bytes_name_and_cleanup(env, monkeypatch):
    import httpx
    from uuid import UUID
    db, user, project, _ = env
    app = FastAPI()
    app.include_router(routes.router, prefix='/api')
    app.dependency_overrides[routes.get_db] = lambda: db
    app.dependency_overrides[routes.get_current_user] = lambda: user
    for route in routes.router.routes:
        for dependency in route.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: user
    monkeypatch.setattr(routes, 'require_project', lambda *_args: None)
    monkeypatch.setattr(routes, 'remote_origin', lambda: None)
    monkeypatch.setattr(storage, 'client', lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=app)))
    request = SimpleNamespace(headers={'authorization': 'Bearer isolated-test'})
    content = b'cloud-data' * 120000  # 超过一个传输块。
    result = asyncio.run(storage.forward_upload('https://cloud.test', request, UploadFile(io.BytesIO(content), filename='云端资料.txt')))
    upload = db.get(Upload, UUID(result['id']))
    assert upload.original_name == '云端资料.txt'
    assert service.storage_path(upload.storage_key).read_bytes() == content
    service.apply_changes(db, project, change(upload), user.id); db.commit()
    row = service.versions(db, project)[0]
    async def read_back():
        response = await storage.forward_download('https://cloud.test', request, project, row['file_id'], row['id'])
        assert response.headers['content-disposition'].startswith('attachment;')
        return b''.join([chunk async for chunk in response.body_iterator])
    assert asyncio.run(read_back()) == content
    unused = stage(db, user)
    unused_id = unused.id
    asyncio.run(storage.forward_delete('https://cloud.test', request, unused_id))
    assert db.get(Upload, unused_id) is None


def test_remote_timeout_does_not_create_local_file(env, monkeypatch):
    import httpx
    db, *_ = env
    def handler(_request): raise httpx.ConnectError('offline')
    monkeypatch.setattr(storage, 'client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    request = SimpleNamespace(headers={'authorization': 'Bearer isolated-test'})
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_upload('https://cloud.test', request, UploadFile(io.BytesIO(b'a'), filename='a.txt')))
    assert error.value.status_code == 503
    assert db.query(Upload).count() == 0
    assert list(service.storage_path('b' * 32).parent.iterdir()) == []


def test_postgres_save_lock_prevents_cleanup_of_file_being_saved(env):
    from concurrent.futures import ThreadPoolExecutor
    db, user, project, _ = env
    if db.bind.dialect.name != 'postgresql':
        pytest.skip('需隔离PostgreSQL验证行锁')
    upload = stage(db, user)
    key = upload.storage_key
    service.apply_changes(db, project, change(upload), user.id)
    # 在未提交时，另一事务看到暂存但无法取得行锁，不能清掉正在保存的文件。
    def another_transaction():
        with Session(db.bind) as other:
            candidates = other.query(Upload).filter_by(id=upload.id).with_for_update(skip_locked=True).all()
            return len(candidates)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(another_transaction).result(timeout=10) == 0
    db.commit()
    assert service.storage_path(key).exists()


def test_postgres_concurrent_reuse_only_one_version(env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    db, user, project, _ = env
    if db.bind.dialect.name != 'postgresql':
        pytest.skip('需隔离PostgreSQL验证并发上传消费')
    upload = stage(db, user)
    payload = change(upload)
    service.apply_changes(db, project, payload, user.id)
    started = Event()
    def competing_save():
        with Session(db.bind) as other:
            started.set()
            try:
                service.apply_changes(other, project, payload, user.id)
                other.commit()
                return 'unexpected'
            except ValueError:
                other.rollback()
                return 'rejected'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(competing_save)
        assert started.wait(5)
        db.commit()
        assert future.result(timeout=10) == 'rejected'
    assert db.query(Version).count() == 1
