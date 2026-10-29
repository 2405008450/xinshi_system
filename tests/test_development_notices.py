"""仅使用内存 SQLite，验证开拓须知共用行为和业务隔离。"""
import asyncio
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import FastAPI,HTTPException,UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import JSON,MetaData,create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from annotation_notice_schemas import AnnotationNoticeSectionCreate,AnnotationNoticeSectionUpdate,AnnotationNoticeSectionEdit,AnnotationNoticeReorder
from development_notice_models import DevelopmentNoticeSection,DevelopmentNoticeAttachment
from project_notice_models import ProjectNoticeSection,ProjectNoticeAttachment
from models import AppUser
from database import get_db
from routers import auth
from routers.project_notices import router
from concurrency import StaleUpdateError
import project_notice_service as sections
import project_notice_attachment_service as files

@pytest.fixture
def store(monkeypatch,tmp_path):
    import main
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    meta=MetaData()
    users=AppUser.__table__.to_metadata(meta)
    users.c.fixed_tasks.type=JSON();users.c.fixed_tasks.server_default=None
    users.indexes.clear()  # 用户目录索引含 PostgreSQL btrim，本测试只验证须知表。
    for model in [ProjectNoticeSection,ProjectNoticeAttachment,DevelopmentNoticeSection,DevelopmentNoticeAttachment]:
        table=model.__table__.to_metadata(meta)
        if 'content_json' in table.c:table.c.content_json.type=JSON()
    meta.create_all(engine)
    monkeypatch.setattr(sections,'_lock_structure',lambda db,module:sections.require_ready(db,module))
    monkeypatch.setenv('PROJECT_NOTICE_UPLOAD_DIR',str(tmp_path))
    with Session(engine) as db:
        user=AppUser(id=uuid4(),username='notice-test',full_name='须知测试',password_hash='unused',fixed_tasks=[])
        db.add(user);db.commit()
        yield db,user,engine
    engine.dispose()

def create(db,module='development',title='开拓流程',parent=None):
    return sections.create_section(db,module,AnnotationNoticeSectionCreate(title=title,parent_id=parent))

def document(text):return {'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':text}]}]}

@pytest.mark.parametrize('module',['development','translation','interpretation','recruitment'])
def test_tree_content_search_order_and_versions(store,module):
    db,user,_=store
    root=create(db,module);child=create(db,module,'联系注意事项',root['id']);leaf=create(db,module,'第三层',child['id'])
    with pytest.raises(ValueError,match='三级'):create(db,module,parent=leaf['id'])
    saved=sections.update_content(db,module,child['id'],AnnotationNoticeSectionUpdate(content_json=document('先联系 微信 再确认 50%_完成')),user.id)
    assert saved['updated_at'].endswith('+08:00')
    assert saved['updated_by_name']=='须知测试'
    assert sections.list_tree(db,module)[0]['children'][0]['children'][0]['title']=='第三层'
    assert sections.search_sections(db,module,'确认 微信')['total']==1
    assert sections.search_sections(db,module,'50%_')['total']==1
    assert sections.search_sections(db,module,'50X')['total']==0
    with pytest.raises(StaleUpdateError):sections.update_content(db,module,child['id'],AnnotationNoticeSectionUpdate(content_json=document('过期')),user.id)
    renamed=sections.update_structure(db,module,leaf['id'],AnnotationNoticeSectionEdit(title='第三层改名',has_content=True,expected_structure_updated_at=leaf['structure_updated_at']))
    rows=[root,child,renamed]
    sections.reorder_sections(db,module,AnnotationNoticeReorder(placements=[{'id':row['id'],'parent_id':row['parent_id'],'sort_order':row['sort_order'],'expected_structure_updated_at':row['structure_updated_at']} for row in rows]))
    with pytest.raises(ValueError):sections.delete_section(db,module,root['id'])
    assert sections.delete_section(db,module,leaf['id'])
    assert sections.delete_section(db,module,child['id'])
    assert sections.delete_section(db,module,root['id'])
    assert sections.list_tree(db,module)==[]

def test_development_isolation_and_attachments(store):
    db,user,_=store
    development=create(db);translation=create(db,'translation')
    assert db.get(DevelopmentNoticeSection,development['id']) is not None
    assert db.get(ProjectNoticeSection,development['id']) is None
    assert sections.get_section(db,'development',translation['id']) is None
    with pytest.raises(HTTPException):create(db,parent=translation['id'])
    attachment=asyncio.run(files.save_attachment(db,'development',development['id'],UploadFile(filename='开拓手册.pdf',file=BytesIO(b'pdf-content')),user.id))
    assert attachment['uploaded_at'].endswith('+08:00')
    assert files.list_attachments(db,'development',development['id'])[0]['id']==attachment['id']
    assert files.attachment_path('development',db.get(DevelopmentNoticeAttachment,attachment['id']).storage_name).read_bytes()==b'pdf-content'
    with pytest.raises(HTTPException):files.get_attachment(db,'translation',development['id'],attachment['id'])
    files.delete_attachment(db,'development',development['id'],attachment['id'])
    assert files.list_attachments(db,'development',development['id'])==[]

def test_api_permissions_are_isolated(store,monkeypatch):
    db,user,_=store;permissions=set()
    monkeypatch.setattr(auth,'user_has_permission',lambda _db,_id,code:code in permissions)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *_:list(permissions))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:
        assert client.get('/project-notices/development/tree').status_code==401
        app.dependency_overrides[auth.get_current_user]=lambda:user
        assert client.get('/project-notices/development/tree').json()==[]
        assert client.get('/project-notices/translation/tree').status_code==403
        assert client.post('/project-notices/development/sections',json={'title':'须知'}).status_code==403
        permissions.add('projects:write')
        assert client.post('/project-notices/development/sections',json={'title':'须知'}).status_code==403
        assert client.post('/project-notices/translation/sections',json={'title':'须知'}).status_code==201
        permissions.clear();permissions.add('translators:write')
        response=client.post('/project-notices/development/sections',json={'title':'须知'})
        assert response.status_code==201,response.text
        assert client.get('/project-notices/invalid/tree').status_code==422

def test_new_tables_migration_is_idempotent(store):
    db,_,_=store
    from tools.apply_development_notices_migration import apply_migration
    apply_migration(db.connection());apply_migration(db.connection())
