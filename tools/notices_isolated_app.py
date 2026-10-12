"""标注须知专用验收服务，静态构建与隔离 API 同源，不运行主应用 startup。"""
import os
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

if os.getenv('ANNOTATION_NOTICES_QA') != '1':
    raise RuntimeError('仅允许显式隔离验收')

import main  # 注册完整 ORM，不执行 startup。
from annotation_notice_models import AnnotationNoticeSection, AnnotationNoticeAttachment
from business_time import business_now
from company_management_models import CompanyManagementSection, CompanyManagementAttachment
from database import engine, get_db
from models import AppUser, Role, UserRole, RolePermission
from routers import auth, annotation_notices, company_management

if engine.url.host != '127.0.0.1' or engine.url.username != 'notice_test' or engine.url.database != 'notices_test':
    raise RuntimeError('拒绝连接非专用本机隔离库')

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'frontend/dist'
ADMIN = UUID('10000000-0000-0000-0000-000000000001')
READER = UUID('10000000-0000-0000-0000-000000000002')
GROUP = UUID('20000000-0000-0000-0000-000000000001')
CHILD = UUID('20000000-0000-0000-0000-000000000002')
OTHER = UUID('20000000-0000-0000-0000-000000000003')

for table in (AppUser.__table__, Role.__table__, UserRole.__table__, RolePermission.__table__,
              AnnotationNoticeSection.__table__, CompanyManagementSection.__table__, CompanyManagementAttachment.__table__):
    table.create(engine, checkfirst=True)
sql = (ROOT / 'data/migrations/20261012_annotation_notice_attachments.sql').read_text(encoding='utf-8')
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    connection.exec_driver_sql(sql)

with Session(engine) as db:
    for user_id, name, permissions in [(ADMIN, 'admin', ['projects:read', 'projects:write']), (READER, 'reader', ['projects:read'])]:
        if db.get(AppUser, user_id):
            continue
        role = Role(role_name='notice_qa_' + name)
        user = AppUser(id=user_id, username='notice_ui_' + name, full_name='栏目验收员', password_hash='unused')
        db.add_all([role, user])
        db.flush()
        db.add(UserRole(user_id=user_id, role_id=role.id))
        db.add_all([RolePermission(role_id=role.id, permission_code=code) for code in permissions])
    for sid, parent, title, content in [(GROUP, None, '验收流程分组', False), (OTHER, None, '独立栏目', True), (CHILD, GROUP, '验收二级栏目', True)]:
        if not db.get(AnnotationNoticeSection, sid):
            db.add(AnnotationNoticeSection(id=sid, section_key='ui_' + sid.hex, title=title,
                   parent_id=parent, sort_order=1, has_content=content, structure_updated_at=business_now(),
                   search_text='验收正文', content_json={'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': '验收正文'}]}]}))
            db.flush()
    company_id = UUID('30000000-0000-0000-0000-000000000001')
    if not db.get(CompanyManagementSection, company_id):
        db.add(CompanyManagementSection(id=company_id, section_key='ui_company', title='公司资料验收',
               sort_order=1, has_content=True, structure_updated_at=business_now(), search_text=''))
    db.commit()


def current_user(authorization: str = Header(''), db=Depends(get_db)):
    identities = {'Bearer isolated-notice-admin': ADMIN, 'Bearer isolated-notice-reader': READER}
    if authorization not in identities:
        raise HTTPException(401, '隔离验收身份无效')
    return db.get(AppUser, identities[authorization])


app = FastAPI()
app.dependency_overrides[auth.get_current_user] = current_user
for router in (auth.router, annotation_notices.router, company_management.router):
    app.include_router(router, prefix='/api')


@app.get('/api/notifications/unread-count')
def unread():
    return {'count': 0}


@app.get('/api/notifications')
@app.get('/api/notifications/')
def notifications():
    return []


@app.get('/api/chat/sessions')
def chats():
    return {'items': [], 'total': 0}


@app.get('/api/resource-development/issues/access')
def issues_access():
    return {'ready': False, 'can_enter': False, 'can_resource': False}


@app.get('/{path:path}')
def static(path: str):
    if path.startswith('api/'):
        raise HTTPException(404, '隔离验收未提供该接口')
    target = (DIST / path).resolve()
    if target.is_relative_to(DIST.resolve()) and target.is_file():
        return FileResponse(target)
    return FileResponse(DIST / 'index.html')
