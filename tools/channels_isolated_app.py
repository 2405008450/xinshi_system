"""渠道管理真实接口验收入口，拒绝任何业务库连接。"""
import os
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException

if os.getenv('CHANNEL_RESOURCE_QA') != '1':
    raise RuntimeError('仅允许显式隔离验收')

import main  # noqa: E402，注册模型，不启动主应用。
from database import engine, get_db  # noqa: E402
from models import AppUser  # noqa: E402
from routers import auth, resource_development  # noqa: E402

if engine.url.host != '127.0.0.1' or engine.url.username != 'channel_test':
    raise RuntimeError('验收只允许本机专用渠道隔离库')

IDS = {'isolated-channel-editor': UUID(int=101), 'isolated-channel-reader': UUID(int=102)}


def current_user(authorization: str = Header(''), db=Depends(get_db)):
    user_id = IDS.get(authorization.removeprefix('Bearer '))
    if not user_id:
        raise HTTPException(401, '隔离验收身份无效')
    return db.get(AppUser, user_id)


def permissions(_, user_id):
    return ['talents:read'] if user_id == IDS['isolated-channel-reader'] else ['talents:read', 'talents:write']


auth.get_user_permission_codes = permissions
resource_development.user_has_permission = lambda db, uid, code: code in permissions(db, uid)
resource_development.is_admin = lambda db, user: user.id == IDS['isolated-channel-editor']
resource_development.can_delegate = resource_development.is_admin
app = FastAPI()
app.dependency_overrides[auth.get_current_user] = current_user
app.include_router(resource_development.router)


@app.get('/auth/session')
def session(user=Depends(current_user)):
    return {'user_id': str(user.id), 'username': user.username, 'full_name': user.full_name, 'roles': ['admin'], 'permissions': permissions(None, user.id)}


@app.get('/notifications/unread-count')
@app.get('/project-chat/unread-count')
def unread():
    return {'count': 0}
