"""项目资料接口，复用标注项目模块权限，不授予聊天访问者写资料权限。"""
import hashlib
import os
import uuid
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, Response, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from annotation_models import AnnotationProject
from routers.auth import get_current_user, require_module_access, require_permission, require_super_admin
from annotation_material_models import AnnotationMaterialUpload as Upload, AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialFolder as Folder
from annotation_material_schemas import OnlineVersionCreate, OnlineFileCreate
from annotation_material_service import MAX_BYTES, storage_path, serialize_upload, versions, folders, queue_upload_deletion, attach_upload
from annotation_material_storage import remote_origin, forward_upload, forward_delete, forward_download, forward_material_operation
from pydantic import BaseModel, ConfigDict
import annotation_material_trash_service as trash_service

router = APIRouter(prefix='/projects/annotation', tags=['annotation_materials'])
legacy_router = APIRouter(dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])


ONLINE_EDIT_EXTENSIONS = {'.docx', '.txt', '.md'}


def extension(name):
    return os.path.splitext(name or '')[1].lower()


def online_upload_extension(db, upload_id, user):
    # 只校验当前用户可用的暂存；其他情况交给 attach_upload 给出统一提示。
    upload = db.get(Upload, upload_id)
    if upload is None or upload.uploaded_by != user.id:
        return None
    suffix = extension(upload.original_name)
    if suffix not in ONLINE_EDIT_EXTENSIONS:
        raise HTTPException(400, '在线编辑仅支持 .docx、.txt、.md 文件')
    return suffix


def require_project(db, project_id):
    # 与标注项目详情接口保持同一可见性：模块权限 + 项目存在。
    if db.query(AnnotationProject.id).filter_by(id=project_id).first() is None:
        raise HTTPException(404, '标注项目不存在')


@legacy_router.post('/material-uploads', status_code=201, dependencies=[Depends(require_permission('projects:write'))])
async def upload_material(request: Request, file: UploadFile = File(...), original_name: str | None = Form(None),
                          db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    origin = remote_origin()
    if file.size is not None and (file.size == 0 or file.size > MAX_BYTES):
        raise HTTPException(413, '文件不能为空或超过100MB限制')
    if origin:
        result = await forward_upload(origin, request, file)
        # 转发双方必须使用相同的业务数据库；绝不复制另一套元数据。
        try:
            row = db.get(Upload, UUID(result['id']))
        except (ValueError, KeyError, TypeError):
            row = None
        if row is None or row.uploaded_by != user.id:
            raise HTTPException(502, '云端资料记录不可见，请检查两端是否使用同一业务数据库')
        return serialize_upload(row)
    name = (original_name or file.filename or 'file').replace('\\', '/').split('/')[-1]
    name = ''.join(char for char in name if ord(char) >= 32)[:255] or 'file'
    key = uuid.uuid4().hex
    path = storage_path(key)
    digest = hashlib.sha256()
    size = 0
    committed = False
    created = False
    try:
        # UploadFile 已由框架流式暂存；分块写入，100MB 不进入单个 bytes 对象。
        import anyio
        async with await anyio.open_file(path, 'xb') as destination:
            created = True
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, '单文件不能超过100MB')
                digest.update(chunk)
                await destination.write(chunk)
        if not size:
            raise HTTPException(413, '不能上传空文件')
        row = Upload(uploaded_by=user.id, uploader_name=getattr(user, 'full_name', None) or getattr(user, 'username', None) or str(user.id),
                     original_name=name, storage_key=key, file_size=size, content_type='application/octet-stream',
                     sha256=digest.hexdigest(), expires_at=datetime.utcnow() + timedelta(hours=24))
        db.add(row)
        db.commit()
        committed = True
        db.refresh(row)
        return serialize_upload(row)
    except BaseException:
        db.rollback()
        if created and not committed:
            path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@legacy_router.delete('/material-uploads/{upload_id}', status_code=204, dependencies=[Depends(require_permission('projects:write'))])
async def cancel_upload(upload_id: UUID, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    origin = remote_origin()
    if origin:
        await forward_delete(origin, request, upload_id)
        return Response(status_code=204)
    row = db.query(Upload).filter_by(id=upload_id).with_for_update().populate_existing().first()
    if row is None:
        return Response(status_code=204)
    if row.uploaded_by != user.id:
        raise HTTPException(403, '不能取消其他用户上传的资料')
    if row.consumed_at:
        # 保存与关闭弹窗相邻时，取消操作不能删除已保存的资料。
        return Response(status_code=204)
    queue_upload_deletion(db, row)
    db.commit()
    return Response(status_code=204)


@legacy_router.get('/{project_id}/materials')
def list_materials(project_id: UUID, db: Session = Depends(get_db)):
    require_project(db, project_id)
    latest = {}
    for row in versions(db, project_id):
        latest.setdefault(row['file_id'], row)
    return list(latest.values())


@legacy_router.get('/{project_id}/material-folders')
def list_material_folders(project_id: UUID, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return folders(db, project_id)


@legacy_router.get('/{project_id}/materials/{file_id}/versions')
def list_versions(project_id: UUID, file_id: UUID, db: Session = Depends(get_db)):
    require_project(db, project_id)
    material = db.query(Material).filter_by(id=file_id, project_id=project_id).first()
    if material is None:
        raise HTTPException(404, '资料不属于当前项目或已移除')
    if material.deleted_at is not None:
        raise HTTPException(410, '文件已进入回收站，请恢复后查看历史版本')
    return versions(db, project_id, file_id)


@legacy_router.get('/{project_id}/materials/{file_id}/versions/{version_id}/download')
async def download(project_id: UUID, file_id: UUID, version_id: UUID, request: Request, db: Session = Depends(get_db)):
    require_project(db, project_id)
    upload = db.query(Upload).join(Version, Version.upload_id == Upload.id).join(Material, Material.id == Version.file_id).filter(
        Material.project_id == project_id, Material.id == file_id, Material.deleted_at.is_(None), Version.id == version_id).first()
    if upload is None:
        raise HTTPException(404, '资料版本不存在或不属于当前项目')
    origin = remote_origin()
    if origin:
        return await forward_download(origin, request, project_id, file_id, version_id)
    path = storage_path(upload.storage_key)
    if not path.is_file():
        raise HTTPException(404, '资料文件缺失，请联系管理员')
    return FileResponse(path, filename=upload.original_name, media_type='application/octet-stream',
                        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@legacy_router.post('/{project_id}/materials/online-files', status_code=201, dependencies=[Depends(require_permission('projects:write'))])
def create_online_file(project_id: UUID, payload: OnlineFileCreate, db: Session = Depends(get_db),
                       user: AppUser = Depends(get_current_user)):
    # 在线新建只写资料表，不更新项目修改时间；remote 模式两端共用业务库，无需转发。
    require_project(db, project_id)
    if payload.folder_id is not None and db.query(Folder.id).filter_by(id=payload.folder_id, project_id=project_id).first() is None:
        raise HTTPException(400, '文件夹不属于当前项目或不存在')
    online_upload_extension(db, payload.upload_id, user)
    try:
        material, _version = attach_upload(db, project_id, payload.upload_id, user.id, 'project', folder_id=payload.folder_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return versions(db, project_id, material.id)[0]


@legacy_router.post('/{project_id}/materials/{file_id}/online-versions', status_code=201, dependencies=[Depends(require_permission('projects:write'))])
def create_online_version(project_id: UUID, file_id: UUID, payload: OnlineVersionCreate, db: Session = Depends(get_db),
                          user: AppUser = Depends(get_current_user)):
    require_project(db, project_id)
    # 锁住逻辑文件，串行化同一文件的并发在线保存，避免基于同一版本各自追加。
    material = db.query(Material).filter_by(id=file_id, project_id=project_id, deleted_at=None).with_for_update().populate_existing().first()
    if material is None:
        raise HTTPException(404, '资料不属于当前项目或已移除')
    latest = db.query(Version, Upload).join(Upload, Upload.id == Version.upload_id).filter(
        Version.file_id == file_id).order_by(Version.version_no.desc()).first()
    if latest is None or latest[0].id != payload.base_version_id:
        db.rollback()
        raise HTTPException(409, '文件已被他人更新，请刷新后重试')
    current = extension(latest[1].original_name)
    suffix = online_upload_extension(db, payload.upload_id, user)
    if current not in ONLINE_EDIT_EXTENSIONS or (suffix is not None and suffix != current):
        db.rollback()
        raise HTTPException(400, '在线编辑文件格式必须与当前版本一致，且仅支持 .docx、.txt、.md')
    try:
        attach_upload(db, project_id, payload.upload_id, user.id, material.category, file_id=file_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return versions(db, project_id, file_id)[0]


router.include_router(legacy_router)


class TrashToken(BaseModel):
    model_config = ConfigDict(extra='forbid')
    trash_token: UUID


@router.post('/{project_id}/materials/{file_id}/trash', dependencies=[Depends(require_permission('projects:write'))])
async def trash_material(project_id: UUID, file_id: UUID, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    origin = remote_origin()
    if origin:
        return await forward_material_operation(origin, request, f'{project_id}/materials/{file_id}/trash')
    try:
        material = trash_service.lock_file(db, project_id, file_id)
        trash_service.trash_file(db, material, user.id, user.full_name or user.username)
        db.commit()
        return dict(file_id=material.id, trash_token=material.trash_token, deleted_at=trash_service.business_iso(material.deleted_at))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.get('/{project_id}/material-trash', dependencies=[Depends(require_permission('projects:write'))])
async def list_trash(project_id: UUID, request: Request, keyword: str = Query('', max_length=200), page: int = Query(1, ge=1),
                     limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    origin = remote_origin()
    if origin:
        return await forward_material_operation(origin, request, f'{project_id}/material-trash', params=dict(keyword=keyword, page=page, limit=limit))
    require_project(db, project_id)
    return trash_service.catalog(db, project_id, keyword, page, limit)


@router.post('/{project_id}/materials/{file_id}/restore', dependencies=[Depends(require_permission('projects:write'))])
async def restore_material(project_id: UUID, file_id: UUID, payload: TrashToken, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    origin = remote_origin()
    if origin:
        return await forward_material_operation(origin, request, f'{project_id}/materials/{file_id}/restore', payload=payload.model_dump(mode='json'))
    material = trash_service.lock_file(db, project_id, file_id)
    trash_service.restore_file(db, material, payload.trash_token, user.id)
    db.commit()
    return dict(file_id=material.id, restored=True)


@router.delete('/{project_id}/material-trash/{file_id}', status_code=204)
async def purge_material(project_id: UUID, file_id: UUID, payload: TrashToken, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(require_super_admin)):
    origin = remote_origin()
    if origin:
        await forward_material_operation(origin, request, f'{project_id}/material-trash/{file_id}', payload=payload.model_dump(mode='json'))
        return Response(status_code=204)
    try:
        material = trash_service.lock_file(db, project_id, file_id, missing_ok=True)
        if material:
            trash_service.purge_file(db, material, payload.trash_token, user.id)
        db.commit()
        return Response(status_code=204)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
