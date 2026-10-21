"""回收站隔离回归；复用临时 SQLite / 专用 PostgreSQL，不访问业务库。"""
import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_annotation_materials import env, stage, change
from test_annotation_office import ctx, start, force, result
from annotation_material_models import AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialUpload as Upload, AnnotationMaterialDeletion as Deletion, AnnotationMaterialFolder as Folder
from annotation_material_schemas import MaterialChanges
import annotation_material_service as materials
import annotation_material_trash_service as trash
import annotation_office_service as office
from routers import annotation_materials as api
from routers import auth


def saved(env, category='project', folder=None):
    db, user, project, _ = env
    first = stage(db, user, '中文说明.txt')
    material, _ = materials.attach_upload(db, project, first.id, user.id, category, folder_id=folder)
    db.commit()
    second = stage(db, user, '新版说明.txt')
    materials.attach_upload(db, project, second.id, user.id, category, material.id)
    db.commit()
    return material, [first, second]


@pytest.mark.parametrize('category', ['project', 'quotation', 'contract'])
def test_trash_keeps_all_versions_until_explicit_purge(env, category):
    db, user, project, _ = env
    material, uploads = saved(env, category)
    trash.trash_file(db, material, user.id, '验收人'); db.commit()
    token = material.trash_token
    assert materials.versions(db, project) == []
    assert db.query(Version).count() == 2 and db.query(Deletion).count() == 0
    entry = trash.catalog(db, project)['items'][0]
    assert entry['deleted_at'].endswith('+08:00') and entry['deleted_by_name'] == '验收人'
    assert entry['version_count'] == 2 and entry['category'] == category
    assert trash.catalog(db, project, '说明 验收')['total'] == 1
    material.deleted_at -= timedelta(days=3650); db.commit()
    materials.cleanup(db)
    assert all(materials.storage_path(upload.storage_key).exists() for upload in uploads)
    trash.restore_file(db, material, token, user.id); db.commit()
    assert [row['version_no'] for row in materials.versions(db, project)] == [2, 1]
    trash.restore_file(db, material, token, user.id); db.commit()  # 恢复重试幂等。
    trash.trash_file(db, material, user.id, '验收人'); db.commit()
    assert material.trash_token != token
    for operation in (trash.restore_file, trash.purge_file):
        with pytest.raises(HTTPException) as error: operation(db, material, token, user.id)
        assert error.value.status_code == 409
    trash.purge_file(db, material, material.trash_token, user.id); db.commit()
    assert db.query(Version).count() == 0 and db.query(Deletion).count() == 2
    materials.cleanup(db)
    assert db.query(Upload).count() == 0


def test_restore_folder_and_missing_directory_fallback(env):
    db, user, project, _ = env
    directory = Folder(project_id=project, name='原目录'); db.add(directory); db.commit()
    material, _ = saved(env, folder=directory.id)
    trash.trash_file(db, material, user.id, '验收人'); db.commit()
    assert trash.catalog(db, project)['items'][0]['original_folder_path'] == '项目资料 / 原目录'
    trash.restore_file(db, material, material.trash_token, user.id); db.commit()
    assert material.folder_id == directory.id
    trash.trash_file(db, material, user.id, '验收人'); db.commit()
    db.delete(directory); db.commit(); db.refresh(material)
    trash.restore_file(db, material, material.trash_token, user.id); db.commit()
    assert material.folder_id is None


def test_form_rollback_and_purge_shared_upload_reference(env):
    db, user, project, other = env
    material, uploads = saved(env)
    clone = Material(project_id=other, category='project'); db.add(clone); db.flush()
    db.add_all(Version(file_id=clone.id, upload_id=upload.id, version_no=i+1) for i, upload in enumerate(uploads)); db.commit()
    materials.apply_changes(db, project, MaterialChanges(removed_file_ids=[material.id]), user.id); db.rollback()
    assert materials.versions(db, project)
    materials.apply_changes(db, project, MaterialChanges(removed_file_ids=[material.id]), user.id); db.commit()
    trash.purge_file(db, material, material.trash_token, user.id); db.commit()
    assert db.query(Deletion).count() == 0 and len(materials.versions(db, other)) == 2


def test_office_writer_blocks_and_old_callbacks_cannot_restore_versions(ctx, monkeypatch):
    db, user, project, _, material, *_ = ctx
    session = start(ctx)
    for state in ('open', 'saving'):
        session.state = state; db.commit()
        with pytest.raises(ValueError, match='在线编辑'): trash.trash_file(db, material, user.id, user.full_name)
        db.rollback()
    session.state = 'open'; session.lease_until = office.now() - timedelta(seconds=1); db.commit()
    trash.trash_file(db, material, user.id, user.full_name); db.commit()
    assert session.state == 'discarded'
    async def never_fetch(*args): raise AssertionError('迟到回调不得下载或落盘')
    monkeypatch.setattr(office, 'fetch_result', never_fetch)
    asyncio.run(office.callback(db, session.id, {'key': session.document_key, 'status': 6, 'url': 'https://office.example.test/result.docx'}))
    assert db.query(Version).count() == 1
    with pytest.raises(HTTPException): office.create_session(db, project, user, file_id=material.id)
    trash.restore_file(db, material, material.trash_token, user.id); db.commit()
    asyncio.run(office.callback(db, session.id, {'key': session.document_key, 'status': 6, 'url': 'https://office.example.test/result.docx'}))
    fresh = start(ctx)
    assert fresh.id != session.id and fresh.document_key != session.document_key and fresh.mode == 'edit'


def test_late_callback_after_download_is_fenced_by_trash(ctx, monkeypatch):
    db, user, project, _, material, *_ = ctx
    session = start(ctx)
    async def fetch_then_delete(*args):
        session.lease_until = office.now() - timedelta(seconds=1); db.commit()
        trash.trash_file(db, material, user.id, user.full_name); db.commit()
        return ctx[-1]
    monkeypatch.setattr(office, 'fetch_result', fetch_then_delete)
    asyncio.run(office.callback(db, session.id, {'key': session.document_key, 'status': 2, 'url': 'https://office.example.test/result.docx'}))
    assert material.deleted_at and db.query(Version).count() == 1


@pytest.fixture
def web(env, monkeypatch):
    db, user, *_ = env
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: user
    monkeypatch.setattr(auth, 'user_has_permission', lambda *args: True)
    monkeypatch.setattr(auth, 'get_user_roles_with_role_names', lambda *args: ['超级管理员'])
    with TestClient(app) as client: yield client


def test_api_access_download_history_tokens_and_idempotency(env, web, monkeypatch):
    db, user, project, other = env
    material, _ = saved(env)
    row = materials.versions(db, project)[0]
    base = f'/projects/annotation/{project}'
    file = f'{base}/materials/{material.id}'
    assert web.post(f'/projects/annotation/{other}/materials/{material.id}/trash').status_code == 404
    response = web.post(file+'/trash'); assert response.status_code == 200, response.text
    token = response.json()['trash_token']
    assert web.post(file+'/trash').json()['trash_token'] == token
    assert web.get(file+'/versions').status_code == 410
    assert web.get(file+f"/versions/{row['id']}/download").status_code == 404
    assert web.post(file+'/online-versions', json={'upload_id': str(uuid4()), 'base_version_id': str(row['id'])}).status_code == 404
    assert web.get(base+'/material-trash').json()['total'] == 1
    assert web.post(file+'/restore', json={'trash_token': str(uuid4())}).status_code == 409
    db.rollback()
    assert web.post(file+'/restore', json={'trash_token': token}).status_code == 200
    assert web.post(file+'/restore', json={'trash_token': token}).status_code == 200
    assert web.request('DELETE', base+f'/material-trash/{material.id}', json={'trash_token': token}).status_code == 409
    db.rollback()
    token = web.post(file+'/trash').json()['trash_token']
    monkeypatch.setattr(auth, 'get_user_roles_with_role_names', lambda *args: ['项目经理'])
    assert web.request('DELETE', base+f'/material-trash/{material.id}', json={'trash_token': token}).status_code == 403
    monkeypatch.setattr(auth, 'get_user_roles_with_role_names', lambda *args: ['超级管理员'])
    assert web.request('DELETE', base+f'/material-trash/{material.id}', json={'trash_token': token}).status_code == 204
    assert web.request('DELETE', base+f'/material-trash/{material.id}', json={'trash_token': token}).status_code == 204
    monkeypatch.setattr(auth, 'user_has_permission', lambda *args: False)
    assert web.get(base+'/material-trash').status_code == 403
    assert web.post(file+'/trash').status_code == 403


def test_remote_forwarding_preserves_cloud_lock_message(env, monkeypatch):
    from types import SimpleNamespace
    import annotation_material_storage as storage
    request = SimpleNamespace(method='POST', headers={'authorization': 'Bearer isolated'})
    class Response:
        status_code = 409
        def json(self): return {'detail': '该文件正在由测试人在线编辑，请稍后重试'}
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def request(self, method, url, **kwargs):
            assert url == 'https://example.test/api/projects/annotation/test/materials/file/trash'
            assert kwargs['headers'][storage.FORWARDED] == '1'
            return Response()
    monkeypatch.setattr(storage, 'client', Client)
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.forward_material_operation('https://example.test', request, 'test/materials/file/trash'))
    assert error.value.status_code == 409 and '测试人' in error.value.detail


def test_child_copy_excludes_trashed_materials(env):
    from annotation_child_copy_service import copy_materials
    db, user, project, other = env
    hidden, _ = saved(env)
    active, _ = saved(env, 'quotation')
    trash.trash_file(db, hidden, user.id, user.full_name); db.commit()
    copy_materials(db, project, other); db.commit()
    assert [row['category'] for row in materials.versions(db, other)] == ['quotation', 'quotation']


def test_postgres_trash_and_new_writer_are_serialized(ctx):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.orm import Session
    db, user, project, _, material, *_ = ctx
    if db.bind.dialect.name != 'postgresql': pytest.skip('需要本机隔离 PostgreSQL 验证并发锁')
    trash.trash_file(db, material, user.id, user.full_name)
    def open_another():
        with Session(db.bind) as other:
            with pytest.raises(HTTPException) as error:
                office.create_session(other, project, user, file_id=material.id)
            assert error.value.status_code == 404
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(open_another)
        import time
        time.sleep(.15)
        assert not future.done()
        db.commit()
        future.result(timeout=5)


def test_postgres_restore_wins_against_stale_purge(env):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.orm import Session
    db, user, project, _ = env
    if db.bind.dialect.name != 'postgresql': pytest.skip('需要本机隔离 PostgreSQL 验证并发锁')
    material, _ = saved(env)
    trash.trash_file(db, material, user.id, user.full_name); db.commit()
    file_id, token, actor_id = material.id, material.trash_token, user.id
    material = trash.lock_file(db, project, file_id)
    trash.restore_file(db, material, token, actor_id)
    def stale_purge():
        with Session(db.bind) as other:
            row = trash.lock_file(other, project, file_id)
            with pytest.raises(HTTPException) as error: trash.purge_file(other, row, token, actor_id)
            assert error.value.status_code == 409
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(stale_purge)
        import time
        time.sleep(.15)
        assert not future.done()
        db.commit(); future.result(timeout=5)
    assert materials.versions(db, project)
