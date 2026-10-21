"""ONLYOFFICE 接入：数据库租约、签名、暂存和幂等提交。"""
import hashlib
import io
import os
import re
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import select, func

from business_time import BUSINESS_TIMEZONE, business_iso
from models import AppUser
from annotation_models import AnnotationProject
from annotation_material_models import AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialUpload as Upload, AnnotationMaterialFolder as Folder
from annotation_office_models import AnnotationOfficeSession as OfficeSession, AnnotationOfficeSave as OfficeSave
from annotation_office_formats import FORMATS, LIMIT, file_kind, validate_office, blank_xlsx
from annotation_material_service import attach_upload, storage_path
from permission_service import user_has_permission

LEASE_SECONDS = 120
ACTIVE = ('open', 'saving')


def now():
    return datetime.now(BUSINESS_TIMEZONE)


def aware(value):
    # SQLite 测试不保留偏移；timestamptz 在 PostgreSQL 中保留实际时刻。
    return value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value


def enabled():
    return os.getenv('ANNOTATION_OFFICE_ENABLED', '').lower() in ('1', 'true')


def origin(name, allow_path=False):
    value = os.getenv(name, '').strip().rstrip('/')
    parts = urlsplit(value)
    path_ok = not parts.path or (allow_path and re.fullmatch(r'(?:/[A-Za-z0-9_-]+)+', parts.path))
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or not path_ok or parts.query or parts.fragment:
        raise HTTPException(503, f'Office 服务配置无效：{name}')
    return value


def settings():
    if not enabled():
        raise HTTPException(503, 'Office 在线编辑尚未启用，请联系管理员；可使用下载功能')
    secret = os.getenv('ANNOTATION_OFFICE_JWT_SECRET', '')
    if len(secret) < 32:
        raise HTTPException(503, 'Office 签名密钥尚未配置')
    return {'server': origin('ANNOTATION_OFFICE_SERVER_ORIGIN', allow_path=True),
            'public': origin('ANNOTATION_OFFICE_PUBLIC_ORIGIN'), 'secret': secret}


def sign(data):
    return jwt.encode(data, settings()['secret'], algorithm='HS256')


def verify(token):
    try:
        return jwt.decode(token, settings()['secret'], algorithms=['HS256'])
    except JWTError as exc:
        raise HTTPException(403, 'Office 签名无效或已过期') from exc


def scope_token(session, scope):
    return sign({'sid': str(session.id), 'scope': scope,
                 'exp': int((now() + timedelta(hours=24)).timestamp())})


def verify_scope(session, token, scope):
    claims = verify(token)
    if claims.get('sid') != str(session.id) or claims.get('scope') != scope:
        raise HTTPException(403, 'Office 访问范围不匹配')


def require_access(db, user_id, write=False):
    user = db.get(AppUser, user_id) if user_id else None
    code = 'projects:write' if write else 'projects:read'
    if not user or not user.is_active or not (user_has_permission(db, user_id, code) or
                                             (not write and user_has_permission(db, user_id, 'projects:write'))):
        raise HTTPException(403, '当前账号没有项目资料访问权限')


def expire(session):
    if session.state in ACTIVE and aware(session.lease_until) <= now():
        session.state = 'expired'


def assert_file_unlocked(db, file_id, session_id=None):
    if not enabled():
        return
    # 所有修改入口先锁逻辑文件，再锁会话，顺序与保存回调保持一致。
    db.execute(select(Material.id).where(Material.id == file_id).with_for_update()).first()
    sessions = db.query(OfficeSession).filter(OfficeSession.file_id == file_id, OfficeSession.mode == 'edit',
                                            OfficeSession.state.in_(ACTIVE)).with_for_update().all()
    for session in sessions:
        expire(session)
        if session.state in ACTIVE and session.id != session_id:
            raise ValueError(f'该文件正在由 {session.owner_name} 在线编辑，请稍后重试')
    db.flush()


def validate_docx(data):
    validate_office(data, 'docx')


def blank_docx():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/><w:sectPr/></w:body></w:document>')
    return output.getvalue()


def stage_bytes(db, session, data):
    kind = file_kind(session.original_name)
    validate_office(data, kind)
    key = uuid.uuid4().hex
    path = storage_path(key)
    path.write_bytes(data)
    row = Upload(id=uuid.uuid4(), uploaded_by=session.owner_id, uploader_name=session.owner_name,
                 original_name=session.original_name, storage_key=key, file_size=len(data),
                 content_type=FORMATS[kind]['mime'],
                 sha256=hashlib.sha256(data).hexdigest(),
                 # 旧资料表已确认使用无时区 UTC；新会话表使用带时区业务时间。
                 created_at=now().astimezone(timezone.utc).replace(tzinfo=None),
                 expires_at=(now() + timedelta(hours=24)).astimezone(timezone.utc).replace(tzinfo=None))
    try:
        db.add(row)
        db.flush()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return row


def create_session(db, project_id, user, file_id=None, name=None, folder_id=None):
    settings()
    require_access(db, user.id)
    if not db.execute(select(AnnotationProject.id).where(AnnotationProject.id == project_id)).first():
        raise HTTPException(404, '标注项目不存在')
    session = OfficeSession(id=uuid.uuid4(), project_id=project_id, owner_id=user.id,
                            owner_name=user.full_name or user.username, mode='edit', state='open',
                            document_key=uuid.uuid4().hex, created_at=now(), lease_until=now() + timedelta(seconds=LEASE_SECONDS))
    if file_id:
        material = db.query(Material).filter_by(id=file_id, project_id=project_id, category='project').with_for_update().first()
        if not material:
            raise HTTPException(404, '项目资料不存在')
        latest = db.query(Version, Upload).join(Upload, Upload.id == Version.upload_id).filter(Version.file_id == file_id).order_by(Version.version_no.desc()).first()
        if not latest:
            raise HTTPException(404, 'Office 源文件不存在')
        kind = file_kind(latest[1].original_name)
        if latest[1].file_size > LIMIT:
            raise HTTPException(413, 'Office 文件超过20MB，请下载后编辑')
        try:
            with storage_path(latest[1].storage_key).open('rb') as source:
                validate_office(source.read(LIMIT + 1), kind)
        except OSError as exc:
            raise HTTPException(404, 'Office 源文件缺失，请联系管理员') from exc
        session.file_id, session.base_version_id, session.source_upload_id = file_id, latest[0].id, latest[1].id
        session.original_name, session.folder_id = latest[1].original_name, material.folder_id
        try:
            assert_file_unlocked(db, file_id)
        except ValueError:
            session.mode = 'view'
        if not user_has_permission(db, user.id, 'projects:write'):
            session.mode = 'view'
    else:
        db.execute(select(AnnotationProject.id).where(AnnotationProject.id == session.project_id).with_for_update()).first()
        require_access(db, user.id, write=True)
        name = (name or '').strip()
        if not name or len(name) > 255 or any(ord(char) < 32 or char in '/\\' for char in name):
            raise HTTPException(400, '请输入有效的 .docx 或 .xlsx 文件名称')
        kind = file_kind(name)
        if folder_id and not db.query(Folder.id).filter_by(id=folder_id, project_id=project_id).first():
            raise HTTPException(400, '文件夹不属于当前项目或尚未保存')
        session.original_name, session.folder_id = name, folder_id
        session.source_upload_id = stage_bytes(db, session, blank_xlsx() if kind == 'xlsx' else blank_docx()).id
    db.add(session)
    db.commit()
    return session


def owned_session(db, session_id, user, lock=False):
    settings()
    session = db.get(OfficeSession, session_id)
    if not session or session.owner_id != user.id:
        raise HTTPException(404, 'Office 会话不存在')
    if lock:
        lock_session(db, session)
    require_access(db, user.id)
    expire(session)
    return session


def lock_session(db, session):
    # 新建文档锁项目，已有文档锁文件；始终先锁业务对象再锁会话。
    target, target_id = (Material, session.file_id) if session.file_id else (AnnotationProject, session.project_id)
    if not db.execute(select(target.id).where(target.id == target_id).with_for_update()).first():
        raise HTTPException(404, '项目资料已移除')
    if db.query(OfficeSession).filter_by(id=session.id).with_for_update().populate_existing().first() is None:
        raise HTTPException(404, 'Office 会话已移除')


def describe(db, session, config=False):
    task = db.get(OfficeSave, session.active_save_id) if session.active_save_id else None
    owner = db.query(OfficeSession.owner_name).filter(OfficeSession.file_id == session.file_id,
                OfficeSession.mode == 'edit', OfficeSession.state.in_(ACTIVE), OfficeSession.lease_until > now()).first() if session.file_id else None
    result = {'id': str(session.id), 'mode': session.mode, 'state': session.state, 'occupant': owner[0] if owner else None,
              'lease_until': business_iso(aware(session.lease_until)), 'save_id': str(task.id) if task else None,
              'save_state': ('pending' if task.state == 'pending_snapshot' else task.state) if task else None, 'error': task.error if task else None,
              'version_id': str(session.saved_version_id) if session.saved_version_id else None,
              'file_id': str(session.file_id) if session.file_id else None}
    if config:
        cfg = settings()
        root = f"{cfg['public']}/api/projects/annotation/office/sessions/{session.id}"
        kind = file_kind(session.original_name)
        editor = {'documentType': FORMATS[kind]['editor'], 'type': 'desktop', 'width': '100%', 'height': '100%',
                  'document': {'fileType': kind, 'key': session.document_key, 'title': session.original_name,
                               'url': root + '/source?token=' + scope_token(session, 'source'),
                               'permissions': {'edit': session.mode == 'edit', 'review': session.mode == 'edit',
                                               'comment': session.mode == 'edit', 'chat': False}},
                  'editorConfig': {'mode': session.mode, 'lang': 'zh-CN',
                                   'user': {'id': str(session.owner_id), 'name': session.owner_name},
                                   'callbackUrl': root + '/callback?token=' + scope_token(session, 'callback'),
                                   'customization': {'autosave': True, 'forcesave': False, 'macros': False}}}
        editor['token'] = sign(editor)
        result.update({'script_url': cfg['server'] + '/web-apps/apps/api/documents/api.js', 'config': editor})
    return result


async def command(data):
    cfg = settings()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
            response = await client.post(cfg['server'] + '/coauthoring/CommandService.ashx', json={**data, 'token': sign(data)})
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Office 命令响应格式错误')
            return result
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, 'Office 服务暂不可用，请重试') from exc


def commit_staged(db, session, task, upload_id):
    require_access(db, session.owner_id, write=True)
    expire(session)
    if session.state != 'saving' or session.active_save_id != task.id or task.state not in ('pending', 'pending_snapshot'):
        raise HTTPException(409, '会话已结束或保存任务已失效')
    if session.file_id:
        assert_file_unlocked(db, session.file_id, session.id)
        latest = db.query(Version).filter_by(file_id=session.file_id).order_by(Version.version_no.desc()).first()
        if not latest or latest.id != session.base_version_id:
            raise HTTPException(409, '文件已更新，请保留当前内容并重新打开')
    else:
        db.execute(select(AnnotationProject.id).where(AnnotationProject.id == session.project_id).with_for_update()).first()
        if session.folder_id and not db.query(Folder.id).filter_by(id=session.folder_id, project_id=session.project_id).first():
            raise HTTPException(409, '目标文件夹已移除')
        latest_versions = db.query(Version.file_id, func.max(Version.version_no).label('version_no')).group_by(Version.file_id).subquery()
        duplicates = db.query(Material.id).join(latest_versions, latest_versions.c.file_id == Material.id).join(
            Version, (Version.file_id == Material.id) & (Version.version_no == latest_versions.c.version_no)).join(Upload, Upload.id == Version.upload_id).filter(
            Material.project_id == session.project_id, Material.folder_id == session.folder_id,
            Material.category == 'project', func.lower(Upload.original_name) == session.original_name.lower()).first()
        if duplicates:
            raise HTTPException(409, '当前目录已有同名文件，请更换文件名称')
    # attach_upload 不提交事务，版本与任务完成标记一起提交。
    material, version = attach_upload(db, session.project_id, upload_id, session.owner_id, 'project',
                                     file_id=session.file_id, folder_id=session.folder_id, office_session_id=session.id)
    db.flush()
    # 保存只是当前会话的检查点。保留文档 key 与写租约，下一次保存基于刚提交的版本。
    session.file_id, session.saved_version_id, session.base_version_id = material.id, version.id, version.id
    session.source_upload_id, session.state = upload_id, 'open'
    session.staged_upload_id, session.staged_revision = None, None
    task.state, task.version_id, task.completed_at, task.error = 'complete', version.id, now(), None


async def request_save(db, session, save_id, revision=0):
    if session.mode != 'edit':
        raise HTTPException(403, '只读会话不能保存')
    existing = db.get(OfficeSave, save_id)
    if existing:
        if existing.session_id != session.id:
            raise HTTPException(409, '保存请求不属于当前会话')
        return
    require_access(db, session.owner_id, write=True)
    if session.state != 'open':
        raise HTTPException(409, '会话已结束或正在保存')
    # 同一编辑器连续保存使用递增 revision；无新修改不能再次追加相同的业务版本。
    previous = db.query(OfficeSave).filter_by(session_id=session.id, state='complete',
        version_id=session.base_version_id).order_by(OfficeSave.created_at.desc()).first() if session.file_id else None
    if previous and revision <= previous.revision:
        expire(session)
        if session.state != 'open':
            raise HTTPException(409, '编辑会话已过期')
        latest = db.query(Version).filter_by(file_id=session.file_id).order_by(Version.version_no.desc()).first()
        if not latest or latest.id != session.base_version_id:
            raise HTTPException(409, '文件已被更新，请重新打开')
        db.add(OfficeSave(id=save_id, session_id=session.id, state='complete', revision=previous.revision,
            version_id=session.base_version_id, created_at=now(), completed_at=now()))
        session.active_save_id = save_id
        db.commit()
        return
    task = OfficeSave(id=save_id, session_id=session.id, state='pending', revision=revision, created_at=now())
    db.add(task)
    session.state, session.active_save_id = 'saving', task.id
    db.commit()  # 发命令前持久化，回调可以由其他进程处理。
    try:
        result = await command({'c': 'forcesave', 'key': session.document_key, 'userdata': str(task.id)})
        # 网络请求期间回调可能已经完成；重新取锁，不能覆盖已完成状态。
        lock_session(db, session)
        db.refresh(task)
        if task.state != 'pending':
            return
        if result.get('error') == 4:
            # error=4 也可能是上一条强制保存的回调尚未到达，不能当成原文件未修改。
            if revision > 0 and (not session.staged_upload_id or session.staged_revision != revision):
                task.state = 'pending_snapshot'
            elif revision == 0 and not session.staged_upload_id and session.file_id:
                require_access(db, session.owner_id, write=True)
                expire(session)
                if session.state != 'saving':
                    raise HTTPException(409, '编辑会话已过期')
                latest = db.query(Version).filter_by(file_id=session.file_id).order_by(Version.version_no.desc()).first()
                if not latest or latest.id != session.base_version_id:
                    raise HTTPException(409, '文件已被更新，请重新打开')
                session.state, session.saved_version_id = 'open', session.base_version_id
                task.state, task.version_id, task.completed_at = 'complete', session.base_version_id, now()
            else:
                commit_staged(db, session, task, session.staged_upload_id or session.source_upload_id)
        elif result.get('error') != 0:
            raise HTTPException(503, 'Office 暂未完成同步，请稍后重试')
        db.commit()
    except (HTTPException, ValueError) as exc:
        db.rollback()
        db.refresh(session, with_for_update=True)
        db.refresh(task)
        if task.state in ('pending', 'pending_snapshot'):
            task.state, task.error = 'failed', str(getattr(exc, 'detail', exc))[:500]
            if session.state == 'saving':
                session.state = 'open'
            db.commit()
        if isinstance(exc, ValueError):
            raise HTTPException(409, str(exc)) from exc
        raise


async def fetch_result(url, kind='docx'):
    cfg = settings()
    if not isinstance(url, str):
        raise HTTPException(400, 'Office 回传文件地址无效')
    parts = urlsplit(url)
    expected = urlsplit(cfg['server'])
    cache_prefix = expected.path + '/cache/files/'
    if (parts.scheme, parts.netloc) != (expected.scheme, expected.netloc) or parts.username or parts.password or not parts.path.startswith(cache_prefix) or parts.fragment or any(segment in ('.', '..') for segment in parts.path.split('/')) or '%' in parts.path or '\\' in parts.path:
        raise HTTPException(403, 'Office 回传文件地址不在允许范围')
    data = bytearray()
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False) as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > LIMIT:
                        raise HTTPException(413, 'Office 回传文件超过20MB')
    except httpx.HTTPError as exc:
        raise HTTPException(503, 'Office 文件回传失败，请重试保存') from exc
    validate_office(data, kind)
    return bytes(data)


async def callback(db, session_id, payload):
    session = db.get(OfficeSession, session_id)
    if not session or payload.get('key') != session.document_key:
        raise HTTPException(403, 'Office 文档标识不匹配')
    if session.mode != 'edit' or session.state not in ACTIVE:
        return  # 终态回调只确认接收，不写任何业务数据。
    status = payload.get('status')
    if status not in (2, 3, 6, 7):
        return
    incoming = None
    if payload.get('userdata'):
        try:
            incoming = db.get(OfficeSave, uuid.UUID(payload['userdata']))
        except (ValueError, TypeError, AttributeError):
            return
        if not incoming or incoming.session_id != session.id:
            return
        if incoming.state == 'complete':
            return  # 已提交检查点的重复或迟到回调，不能污染后续保存的暂存文件。
    if status in (2, 6):
        data = await fetch_result(payload.get('url', ''), file_kind(session.original_name))
    else:
        data = None
    lock_session(db, session)
    expire(session)
    if session.state not in ACTIVE:
        db.commit()
        return
    if incoming:
        db.refresh(incoming)
        if incoming.state == 'complete':
            return  # 下载回传文件期间，其他进程可能已完成同一任务。
    task = db.get(OfficeSave, session.active_save_id) if session.active_save_id else None
    if task and task is not incoming:
        db.refresh(task)
    if incoming and task and incoming.revision != task.revision:
        return  # 编辑内容已经发生变化，旧快照不能覆盖本次保存。
    matches = task and task.state in ('pending', 'pending_snapshot') and incoming and incoming.id == task.id and status in (6, 7)
    if matches and status == 7:
        task.state, task.error, session.state = 'failed', 'Office 保存失败，请重试', 'open'
    elif data:
        require_access(db, session.owner_id, write=True)
        upload = stage_bytes(db, session, data)
        session.staged_upload_id = upload.id
        session.staged_revision = incoming.revision if incoming else None
        can_use_previous = task and task.state == 'pending_snapshot' and incoming and incoming.revision == task.revision
        if matches or can_use_previous:
            try:
                commit_staged(db, session, task, upload.id)
            except (HTTPException, ValueError) as exc:
                task.state, task.error, session.state = 'failed', str(getattr(exc, 'detail', exc))[:500], 'open'
    db.commit()
