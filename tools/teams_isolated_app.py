"""仅供临时团队资源验收的后端；拒绝加载任何业务数据库。"""
import os
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

if os.getenv("TEAM_RESOURCE_QA") != "1":
    raise RuntimeError("此入口仅供显式隔离验收")

import main  # noqa: E402，注册模型，不执行主应用启动逻辑。
from database import engine, get_db  # noqa: E402
from error_localization import localize_http_detail, localize_validation_errors  # noqa: E402
from models import AppUser  # noqa: E402
from routers import auth, teams  # noqa: E402
import team_resource_service  # noqa: E402

if engine.url.host != "127.0.0.1" or engine.url.username != "team_test" or engine.url.database != "teams_test":
    raise RuntimeError("验收入口仅允许专用本机团队隔离库")

IDS = {"isolated-team-editor": UUID(int=101), "isolated-team-reader": UUID(int=102), "isolated-team-other": UUID(int=103)}


def current_user(authorization: str = Header(""), db=Depends(get_db)):
    user_id = IDS.get(authorization.removeprefix("Bearer "))
    if not user_id:
        raise HTTPException(401, "隔离验收身份无效")
    return db.get(AppUser, user_id)


def permissions(_, user_id):
    return ["talents:read"] if user_id == IDS["isolated-team-reader"] else ["talents:read", "talents:write"]


# 权限及身份替身局限于专用验收进程，团队接口与数据库服务使用真实实现。
auth.get_user_permission_codes = permissions
teams.user_has_permission = lambda db, uid, code: code in permissions(db, uid)
teams.can_view_talent_contacts = team_resource_service.can_view_talent_contacts = lambda _db, user: user.id == IDS['isolated-team-editor']
app = FastAPI()
app.dependency_overrides[auth.get_current_user] = current_user
app.include_router(teams.router)


@app.get("/auth/session")
def session(user=Depends(current_user)):
    return {"user_id": str(user.id), "username": user.username, "full_name": user.full_name, "roles": ["admin"], "permissions": permissions(None, user.id)}


@app.get("/notifications/unread-count")
@app.get("/project-chat/unread-count")
def unread():
    return {"count": 0}


@app.exception_handler(StarletteHTTPException)
async def http_error(_, error):
    return JSONResponse(status_code=error.status_code, content={"detail": jsonable_encoder(localize_http_detail(error.detail, error.status_code))})


@app.exception_handler(RequestValidationError)
async def validation_error(_, error):
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(localize_validation_errors(error.errors()))})
