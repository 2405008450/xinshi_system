"""项目资料接口，复用标注项目模块权限，不授予聊天访问者写资料权限。"""
import hashlib
import uuid
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from annotation_models import AnnotationProject
from routers.auth import get_current_user, require_module_access, require_permission
from annotation_material_models import AnnotationMaterialUpload as Upload, AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version
from annotation_material_service import MAX_BYTES, storage_path, serialize_upload, versions, queue_upload_deletion
from annotation_material_storage import remote_origin, forward_upload, forward_delete, forward_download

router = APIRouter(prefix='/projects/annotation', tags=['annotation_materials'],
                   dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])


def require_project(db, project_id):
    # 与标注项目详情接口保持同一可见性：模块权限 + 项目存在。
    if db.get(AnnotationProject, project_id) is None:
        raise HTTPException(404, '标注项目不存在')


@router.post('/material-uploads', status_code=201, dependencies=[Depends(require_permission('projects:write'))])
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


@router.delete('/material-uploads/{upload_id}', status_code=204, dependencies=[Depends(require_permission('projects:write'))])
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


@router.get('/{project_id}/materials')
def list_materials(project_id: UUID, db: Session = Depends(get_db)):
    require_project(db, project_id)
    latest = {}
    for row in versions(db, project_id):
        latest.setdefault(row['file_id'], row)
    return list(latest.values())


@router.get('/{project_id}/materials/{file_id}/versions')
def list_versions(project_id: UUID, file_id: UUID, db: Session = Depends(get_db)):
    require_project(db, project_id)
    if db.query(Material).filter_by(id=file_id, project_id=project_id).first() is None:
        raise HTTPException(404, '资料不属于当前项目或已移除')
    return versions(db, project_id, file_id)


@router.get('/{project_id}/materials/{file_id}/versions/{version_id}/download')
async def download(project_id: UUID, file_id: UUID, version_id: UUID, request: Request, db: Session = Depends(get_db)):
    require_project(db, project_id)
    upload = db.query(Upload).join(Version, Version.upload_id == Upload.id).join(Material, Material.id == Version.file_id).filter(
        Material.project_id == project_id, Material.id == file_id, Version.id == version_id).first()
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
