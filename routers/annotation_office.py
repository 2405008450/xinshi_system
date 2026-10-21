"""浏览器控制接口与文档服务器签名接口分离。"""
from uuid import UUID
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_module_access
from annotation_material_models import AnnotationMaterialUpload as Upload
from annotation_office_models import AnnotationOfficeSession as OfficeSession
from annotation_material_storage import remote_origin, forwarding_headers, client, check
import annotation_office_service as office

router = APIRouter(prefix='/projects/annotation', tags=['annotation_office'])
browser = APIRouter(dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])


class OfficeAccessLogFilter(logging.Filter):
    """签名 URL 是临时访问凭据，不写入 Uvicorn 访问日志。"""
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            if '/office/sessions/' in str(args[2]):
                args[2] = re.sub(r'([?&]token=)[^& ]+', r'\1[REDACTED]', str(args[2]))
                record.args = tuple(args)
        return True


logging.getLogger('uvicorn.access').addFilter(OfficeAccessLogFilter())


class OpenOffice(BaseModel):
    file_id: UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    folder_id: UUID | None = None


class SaveOffice(BaseModel):
    save_id: UUID
    revision: int = Field(default=0, ge=0)


async def forward(request):
    if not office.enabled():
        raise HTTPException(503, 'Word 在线编辑尚未启用，请联系管理员；可使用下载功能')
    origin = remote_origin()
    if not origin:
        return None
    import httpx
    try:
        async with client() as connection:
            response = await connection.request(request.method,
                origin + '/api' + request.url.path.removeprefix('/api'),
                headers={**forwarding_headers(request), 'Content-Type': 'application/json'}, content=await request.body())
            check(response)
            return Response(response.content, status_code=response.status_code, media_type='application/json',
                            headers={'Cache-Control': 'no-store'})
    except httpx.HTTPError as exc:
        raise HTTPException(503, '云端 Office 服务暂不可用') from exc


@browser.post('/{project_id}/office/sessions', status_code=201)
async def open_session(project_id: UUID, payload: OpenOffice, request: Request,
                       response: Response, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    forwarded = await forward(request)
    if forwarded is not None:
        return forwarded
    session = office.create_session(db, project_id, user, payload.file_id, payload.name, payload.folder_id)
    response.headers['Cache-Control'] = 'no-store'
    return office.describe(db, session, config=True)


@browser.get('/office/sessions/{session_id}')
async def status(session_id: UUID, request: Request, response: Response,
                 db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    forwarded = await forward(request)
    if forwarded is not None:
        return forwarded
    session = office.owned_session(db, session_id, user, lock=True)
    task = db.get(office.OfficeSave, session.active_save_id) if session.active_save_id else None
    if task and task.state in ('pending', 'pending_snapshot') and (office.now() - office.aware(task.created_at)).total_seconds() > 60:
        task.state, task.error = 'failed', 'Office 保存回调超时，请重试'
        if session.state == 'saving':
            session.state = 'open'
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return office.describe(db, session)


@browser.post('/office/sessions/{session_id}/heartbeat')
async def heartbeat(session_id: UUID, request: Request,
                    db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    forwarded = await forward(request)
    if forwarded is not None:
        return forwarded
    session = office.owned_session(db, session_id, user, lock=True)
    if session.mode == 'edit':
        office.require_access(db, user.id, write=True)
    if session.state not in office.ACTIVE:
        db.commit()
        raise HTTPException(409, 'Office 会话已结束，请重新打开')
    session.lease_until = office.now() + office.timedelta(seconds=office.LEASE_SECONDS)
    db.commit()
    return office.describe(db, session)


@browser.post('/office/sessions/{session_id}/save')
async def save(session_id: UUID, payload: SaveOffice, request: Request,
               db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    forwarded = await forward(request)
    if forwarded is not None:
        return forwarded
    session = office.owned_session(db, session_id, user, lock=True)
    await office.request_save(db, session, payload.save_id, payload.revision)
    return office.describe(db, session)


@browser.post('/office/sessions/{session_id}/discard')
async def discard(session_id: UUID, request: Request,
                  db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    forwarded = await forward(request)
    if forwarded is not None:
        return forwarded
    session = office.owned_session(db, session_id, user, lock=True)
    if session.state in office.ACTIVE:
        session.state = 'discarded'
    db.commit()
    return office.describe(db, session)


router.include_router(browser)


def server_session(db, session_id, token, scope):
    if remote_origin():
        raise HTTPException(503, 'Office 文件与回调地址必须指向资料存储端')
    office.settings()
    session = db.get(OfficeSession, session_id)
    if not session:
        raise HTTPException(404, 'Office 会话不存在')
    office.verify_scope(session, token, scope)
    return session


@router.get('/office/sessions/{session_id}/source')
def source(session_id: UUID, token: str, db: Session = Depends(get_db)):
    session = server_session(db, session_id, token, 'source')
    office.expire(session)
    if session.state not in office.ACTIVE:
        db.commit()
        raise HTTPException(410, 'Office 会话已结束')
    office.require_access(db, session.owner_id)
    upload = db.get(Upload, session.source_upload_id)
    if not upload:
        raise HTTPException(404, 'Word 源文件不存在')
    path = office.storage_path(upload.storage_key)
    if not path.is_file():
        raise HTTPException(404, 'Word 源文件缺失')
    return FileResponse(path, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/office/sessions/{session_id}/callback')
async def callback(session_id: UUID, token: str, request: Request, db: Session = Depends(get_db)):
    session = server_session(db, session_id, token, 'callback')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise HTTPException(413, 'Office 回调过大')
    import json
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError('回调必须为对象')
        header = request.headers.get('authorization', '')
        signature = header[7:] if header.startswith('Bearer ') else payload.get('token', '')
        claims = office.verify(signature)
        signed = claims.get('payload', claims)
        if not isinstance(signed, dict) or any(signed.get(key) != payload.get(key) for key in ('key', 'status', 'url', 'userdata')):
            raise HTTPException(403, 'Office 回调内容与签名不一致')
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, 'Office 回调格式错误') from exc
    if payload.get('key') != session.document_key:
        raise HTTPException(403, 'Office 文档标识不匹配')
    try:
        await office.callback(db, session_id, payload)
    except BaseException:
        db.rollback()
        raise
    return {'error': 0}
