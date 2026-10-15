"""项目须知真实 PostgreSQL 回归，仅允许专用本机隔离库。"""
import asyncio
import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from annotation_notice_schemas import AnnotationNoticeReorder, AnnotationNoticeSectionCreate, AnnotationNoticeSectionEdit, AnnotationNoticeSectionUpdate
from concurrency import StaleUpdateError
from database import get_db
from models import AppUser
from project_notice_models import ProjectNoticeSection
import project_notice_service as sections
import project_notice_attachment_service as files
from routers import auth
from routers.project_notices import router


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = os.getenv('NOTICE_TEST_DATABASE_URL')
    if not url:
        pytest.skip('需要独立 PostgreSQL NOTICE_TEST_DATABASE_URL')
    engine = create_engine(url)
    if engine.url.host != '127.0.0.1' or engine.url.username != 'notice_test' or engine.url.database != 'notices_test':
        raise RuntimeError('拒绝连接非专用本机隔离库')
    import main  # 注册 ORM，不执行主应用启动。
    AppUser.__table__.create(engine, checkfirst=True)
    sql = Path('data/migrations/20261018_project_notices.sql').read_text(encoding='utf-8')
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql('TRUNCATE project_notice_attachment, project_notice_section')
    monkeypatch.setenv('PROJECT_NOTICE_UPLOAD_DIR', str(tmp_path / 'uploads'))
    with Session(engine) as session:
        user = AppUser(id=uuid4(), username='project_notice_qa_' + uuid4().hex, password_hash='unused', full_name='须知验收员')
        session.add(user)
        session.commit()
        yield session, user, engine
    engine.dispose()


def create(session, module='translation', title='流程须知', parent=None, content=True):
    return sections.create_section(session, module, AnnotationNoticeSectionCreate(title=title, parent_id=parent, has_content=content))


def document(value='注意事项 50%_完成'):
    return {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': value}]}]}


def upload(session, module, sid, uid, name='中文资料.pdf', content=b'%PDF-1.4 notice'):
    return asyncio.run(files.save_attachment(session, module, sid, UploadFile(filename=name, file=io.BytesIO(content)), uid))


def test_missing_schema_and_invalid_module():
    with Session(create_engine('sqlite://')) as session:
        with pytest.raises(HTTPException) as error:
            sections.list_tree(session, 'translation')
        assert error.value.status_code == 503
        with pytest.raises(HTTPException) as error:
            sections.list_tree(session, '../annotation')
        assert error.value.status_code == 404


@pytest.mark.parametrize('module', sorted(sections.MODULES))
def test_initial_empty_crud_search_and_soft_delete(db, module):
    session, user, _ = db
    assert sections.list_tree(session, module) == []
    root = create(session, module, '项目流程', content=False)
    child = create(session, module, '流程须知', root['id'])
    assert root['structure_updated_at'].endswith('+08:00')
    with pytest.raises(ValueError, match='两级'):
        create(session, module, parent=child['id'])
    with pytest.raises(ValueError, match='二级栏目'):
        sections.delete_section(session, module, root['id'])
    with pytest.raises(ValueError, match='仅用于分组'):
        sections.update_content(session, module, root['id'], AnnotationNoticeSectionUpdate(content_json=document()), user.id)
    saved = sections.update_content(session, module, child['id'], AnnotationNoticeSectionUpdate(content_json=document()), user.id)
    assert saved['updated_by_name'] == '须知验收员'
    assert saved['updated_at'].endswith('+08:00')
    hit = sections.search_sections(session, module, '50%_')
    assert hit['total'] == 1 and hit['items'][0]['breadcrumb'] == '项目流程 / 流程须知'
    assert sections.search_sections(session, module, '流程', skip=1, limit=1)['total'] == 2
    assert len(sections.search_sections(session, module, '流程', skip=1, limit=1)['items']) == 1
    renamed = sections.update_structure(session, module, child['id'], AnnotationNoticeSectionEdit(
        title='新版须知', has_content=True, expected_structure_updated_at=child['structure_updated_at']))
    assert renamed['title'] == '新版须知'
    assert sections.delete_section(session, module, child['id'])
    assert sections.get_section(session, module, child['id']) is None
    assert sections.delete_section(session, module, root['id'])
    assert sections.list_tree(session, module) == []  # 删除后刷新不重新生成栏目。


def test_module_isolation_for_every_operation(db):
    session, user, _ = db
    roots = {module: create(session, module) for module in sections.MODULES}
    sid = roots['translation']['id']
    attached = upload(session, 'translation', sid, user.id)
    assert sections.get_section(session, 'recruitment', sid) is None
    assert sections.search_sections(session, 'recruitment', '不存在')['total'] == 0
    for action in [
        lambda: create(session, 'recruitment', parent=sid),
        lambda: sections.update_structure(session, 'recruitment', sid, AnnotationNoticeSectionEdit(title='错误', has_content=True)),
        lambda: sections.update_content(session, 'recruitment', sid, AnnotationNoticeSectionUpdate(content_json=document()), user.id),
        lambda: files.list_attachments(session, 'recruitment', sid),
        lambda: upload(session, 'recruitment', sid, user.id),
        lambda: files.get_attachment(session, 'recruitment', sid, attached['id']),
        lambda: files.delete_attachment(session, 'recruitment', sid, attached['id']),
    ]:
        with pytest.raises(HTTPException) as error:
            action()
        assert error.value.status_code == 404
    assert not sections.delete_section(session, 'recruitment', sid)
    with pytest.raises(ValueError, match='结构已变化'):
        sections.reorder_sections(session, 'recruitment', AnnotationNoticeReorder(placements=[{
            'id': sid, 'parent_id': None, 'sort_order': 1, 'expected_structure_updated_at': roots['translation']['structure_updated_at']}]))
    assert files.attachment_path('translation', attached['id'].hex + '.pdf').parent.name == 'translation'
    with pytest.raises(ValueError):
        files.attachment_path('translation', '../escape.pdf')


def test_reorder_and_precise_timezone_versions(db):
    session, user, _ = db
    a, b = create(session, title='A'), create(session, title='B')
    placements = [{'id': row['id'], 'sort_order': index, 'expected_structure_updated_at': row['structure_updated_at']} for index, row in enumerate([b, a], 1)]
    tree = sections.reorder_sections(session, 'translation', AnnotationNoticeReorder(placements=placements))
    assert [row['title'] for row in tree] == ['B', 'A']
    with pytest.raises(StaleUpdateError):
        sections.reorder_sections(session, 'translation', AnnotationNoticeReorder(placements=placements))
    current = sections.update_content(session, 'translation', a['id'], AnnotationNoticeSectionUpdate(content_json=document()), user.id)
    equivalent_utc = datetime.fromisoformat(current['updated_at']).astimezone(timezone.utc)
    updated = sections.update_content(session, 'translation', a['id'], AnnotationNoticeSectionUpdate(content_json=document('新版'), expected_updated_at=equivalent_utc), user.id)
    assert updated['content_json'] == document('新版')
    with pytest.raises(StaleUpdateError):
        sections.update_content(session, 'translation', a['id'], AnnotationNoticeSectionUpdate(content_json=document(), expected_updated_at=equivalent_utc), user.id)
    now = datetime(2026, 10, 9, 17, 18, 43, 123456, tzinfo=sections.BUSINESS_TIMEZONE)
    sections._assert_version(now, now.astimezone(timezone.utc))
    with pytest.raises(StaleUpdateError):
        sections._assert_version(now, now.replace(microsecond=123455))


def test_attachment_limits_soft_delete_and_transaction_cleanup(db, monkeypatch):
    session, user, _ = db
    sid = create(session)['id']
    first = upload(session, 'translation', sid, user.id)
    for name, content, status in [('执行.exe', b'x', 400), ('空.pdf', b'', 400), ('大.pdf', b'x' * (files.MAX_FILE_BYTES + 1), 413)]:
        with pytest.raises(HTTPException) as error:
            upload(session, 'translation', sid, user.id, name, content)
        assert error.value.status_code == status
    original_commit = session.commit
    monkeypatch.setattr(session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('commit failed')))
    with pytest.raises(RuntimeError):
        upload(session, 'translation', sid, user.id)
    with pytest.raises(RuntimeError):
        files.delete_attachment(session, 'translation', sid, first['id'])
    monkeypatch.setattr(session, 'commit', original_commit)
    assert len(list(files.upload_dir('translation').iterdir())) == 1
    stored = files.get_attachment(session, 'translation', sid, first['id'])
    assert files.attachment_path('translation', stored.storage_name).read_bytes().startswith(b'%PDF')
    files.delete_attachment(session, 'translation', sid, first['id'])
    assert files.list_attachments(session, 'translation', sid) == []
    upload(session, 'translation', sid, user.id)
    sections.delete_section(session, 'translation', sid)
    with pytest.raises(HTTPException) as error:
        files.list_attachments(session, 'translation', sid)
    assert error.value.status_code == 404


def test_concurrent_creation_and_upload_limit(db):
    session, user, engine = db
    uid = user.id
    def concurrent_create(_):
        with Session(engine) as db_session:
            return create(db_session)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(concurrent_create, range(2)))
    assert sorted(row['sort_order'] for row in rows) == [1, 2]
    sid = rows[0]['id']
    for _ in range(49):
        upload(session, 'translation', sid, uid)
    session.rollback()  # 释放读取事务，再启动独立上传会话。
    def concurrent_upload(_):
        with Session(engine) as db_session:
            try:
                upload(db_session, 'translation', sid, uid)
                return 201
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(concurrent_upload, range(2))) == [201, 400]
    assert len(files.list_attachments(session, 'translation', sid)) == 50


def test_api_permissions_versions_and_download(db, monkeypatch):
    session, user, _ = db
    permissions = set()
    monkeypatch.setattr(auth, 'user_has_permission', lambda _db, _id, code: code in permissions)
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda _db, _id: list(permissions))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    @app.exception_handler(StaleUpdateError)
    async def conflict(_request, _exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={'detail': '栏目已被更新'})
    with TestClient(app) as client:
        base = '/project-notices/translation'
        assert client.get(base + '/tree').status_code == 401
        app.dependency_overrides[auth.get_current_user] = lambda: user
        assert client.get(base + '/tree').status_code == 403
        permissions.add('projects:read')
        assert client.get(base + '/tree').json() == []
        assert client.post(base + '/sections', json={'title': '流程'}).status_code == 403
        permissions.add('projects:write')
        response = client.post(base + '/sections', json={'title': '流程'})
        assert response.status_code == 201, response.text
        path = base + '/sections/' + response.json()['id']
        data = client.put(path + '/content', json={'content_json': document()}).json()
        assert data['updated_at'].endswith('+08:00')
        assert client.put(path + '/content', json={'content_json': document()}).status_code == 409
        file_response = client.post(path + '/attachments', files={'file': ('中文.pdf', b'payload')})
        assert file_response.status_code == 201, file_response.text
        attachment = file_response.json()
        assert attachment['uploaded_at'].endswith('+08:00') and 'storage_name' not in attachment
        permissions.remove('projects:write')
        download = client.get(path + '/attachments/' + attachment['id'])
        assert download.content == b'payload' and download.headers['x-content-type-options'] == 'nosniff'
        assert client.delete(path).status_code == 403
        assert client.get('/project-notices/annotation/tree').status_code == 422
