"""开拓问题专用隔离后端，不运行主应用 startup。"""
import os
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

if os.getenv('RESOURCE_ISSUES_QA') != '1':
    raise RuntimeError('仅允许显式隔离验收')
import main
from database import engine, get_db
from models import AppUser
from permission_service import get_user_permission_codes
from crud import get_user_roles_with_role_names
from routers import auth, resource_issues, resource_development, project_chat, direct_chat, chat_sessions, chat_topics
from tools.resource_issues_fixture import IDS
from error_localization import localize_http_detail, localize_validation_errors

if engine.url.host!='127.0.0.1' or engine.url.username!='issue_test' or engine.url.database!='issues_test':
    raise RuntimeError('拒绝连接非专用隔离库')


def current_user(authorization: str = Header(''), db=Depends(get_db)):
    name=authorization.removeprefix('Bearer isolated-issue-')
    if name not in IDS:
        raise HTTPException(401,'隔离验收身份无效')
    return db.get(AppUser,IDS[name])


app=FastAPI()
app.dependency_overrides[auth.get_current_user]=current_user
for router in (resource_issues.router,resource_development.router,project_chat.router,direct_chat.router,chat_sessions.router,chat_topics.router):
    app.include_router(router)


@app.get('/auth/session')
def session(user=Depends(current_user),db=Depends(get_db)):
    return dict(user_id=str(user.id),username=user.username,full_name=user.full_name,
                roles=get_user_roles_with_role_names(db,user.id),permissions=get_user_permission_codes(db,user.id))


@app.get('/qa/fixtures')
def fixtures(user=Depends(current_user),db=Depends(get_db)):
    from models import ChatProjectMessage
    from resource_issue_models import DevelopmentIssue
    return dict(messages={kind:str(db.query(ChatProjectMessage).filter(column.is_not(None)).order_by(ChatProjectMessage.sequence_no).first().id)
                          for kind,column in [('translation',ChatProjectMessage.project_id),('annotation',ChatProjectMessage.annotation_project_id),('direct',ChatProjectMessage.direct_conversation_id)]},
                people={key:str(value) for key,value in IDS.items()},
                issues=[str(row.id) for row in db.query(DevelopmentIssue).order_by(DevelopmentIssue.created_at)])


@app.get('/notifications/unread-count')
def unread(): return {'count':0}


@app.exception_handler(StarletteHTTPException)
async def http_error(_,error):
    return JSONResponse(status_code=error.status_code,content={'detail':jsonable_encoder(localize_http_detail(error.detail,error.status_code))})


@app.exception_handler(RequestValidationError)
async def validation_error(_,error):
    return JSONResponse(status_code=422,content={'detail':jsonable_encoder(localize_validation_errors(error.errors()))})
