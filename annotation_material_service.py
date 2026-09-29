"""项目事务管理资料关联；只有存储主机执行文件清理。"""
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import func
from annotation_material_models import (
    AnnotationMaterialUpload as Upload, AnnotationMaterialFile as Material,
    AnnotationMaterialVersion as Version, AnnotationMaterialDeletion as Deletion,
)

logger = logging.getLogger(__name__)
MAX_BYTES = 100 * 1024 * 1024


def storage_mode():
    # 未配置时关闭，防止局域网意外把正式文件写到本地。
    mode = os.getenv('ANNOTATION_MATERIAL_STORAGE_MODE', 'disabled').strip().lower()
    if mode not in {'local', 'remote', 'disabled'}:
        raise ValueError('项目资料存储模式配置错误')
    return mode


def storage_path(key):
    if not re.fullmatch(r'[0-9a-f]{32}', key):
        raise ValueError('项目资料存储键无效')
    root = Path(os.getenv('ANNOTATION_MATERIAL_DIR', 'data/annotation_materials')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = (root / key).resolve()
    if path.parent != root:
        raise ValueError('项目资料路径无效')
    return path


def serialize_upload(row):
    return {name: getattr(row, name) for name in (
        'id', 'original_name', 'file_size', 'content_type', 'sha256',
        'uploader_name', 'created_at', 'expires_at',
    )}


def versions(db, project_id, file_id=None):
    query = db.query(Material, Version, Upload).join(Version, Version.file_id == Material.id).join(
        Upload, Upload.id == Version.upload_id).filter(Material.project_id == project_id)
    if file_id:
        query = query.filter(Material.id == file_id)
    result = []
    for material, version, upload in query.order_by(Material.created_at, Version.version_no.desc()).all():
        result.append({**serialize_upload(upload), 'id': version.id, 'file_id': material.id,
                       'category': material.category, 'version_no': version.version_no})
    return result


def queue_upload_deletion(db, upload):
    if db.get(Deletion, upload.storage_key) is None:
        db.add(Deletion(storage_key=upload.storage_key))
    db.delete(upload)


def remove_material(db, material):
    rows = db.query(Version, Upload).join(Upload, Upload.id == Version.upload_id).filter(
        Version.file_id == material.id).all()
    for version, _upload in rows:
        db.delete(version)
    db.flush()
    for _version, upload in rows:
        queue_upload_deletion(db, upload)
    db.delete(material)


def remove_project_materials(db, project_id):
    for material in db.query(Material).filter(Material.project_id == project_id).all():
        remove_material(db, material)


def apply_changes(db, project_id, changes, user_id):
    if changes is None:
        return
    # 调用者先锁项目，再锁暂存行；清理也锁暂存行，避免保存和清理竞争。
    for file_id in set(changes.removed_file_ids):
        material = db.query(Material).filter_by(id=file_id, project_id=project_id).first()
        if material is None:
            raise ValueError('待移除文件不属于当前项目或已被移除')
        remove_material(db, material)
    for item in sorted(changes.additions, key=lambda item: str(item.upload_id)):
        upload = db.query(Upload).filter_by(id=item.upload_id).with_for_update().populate_existing().first()
        if (upload is None or upload.uploaded_by != user_id or upload.consumed_at is not None
                or upload.expires_at <= datetime.utcnow()):
            raise ValueError('暂存文件已过期、已使用或不属于当前用户，请重新上传')
        if item.file_id:
            material = db.query(Material).filter_by(id=item.file_id, project_id=project_id).first()
            if material is None or material.category != item.category:
                raise ValueError('新版文件不属于当前项目或资料分类不匹配')
        else:
            material = Material(project_id=project_id, category=item.category)
            db.add(material)
            db.flush()
        last = db.query(func.max(Version.version_no)).filter_by(file_id=material.id).scalar() or 0
        db.add(Version(file_id=material.id, upload_id=upload.id, version_no=last + 1))
        upload.consumed_at = datetime.utcnow()
    db.flush()


def cleanup(db):
    if storage_mode() != 'local':
        return
    expired = db.query(Upload).filter(Upload.consumed_at.is_(None), Upload.expires_at < datetime.utcnow()).with_for_update(skip_locked=True).limit(200).all()
    for upload in expired:
        queue_upload_deletion(db, upload)
    # 进程在文件写完、元数据提交前退出时也可能留下孤立文件。
    # 仅处理超过24小时且没有任何元数据的随机存储键，绝不触碰正在上传的文件。
    root = storage_path('0' * 32).parent
    cutoff = time.time() - 24 * 60 * 60
    for path in root.iterdir():
        if not re.fullmatch(r'[0-9a-f]{32}', path.name) or path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            if db.query(Upload.id).filter(Upload.storage_key == path.name).first() is None and db.get(Deletion, path.name) is None:
                db.add(Deletion(storage_key=path.name))
        except OSError:
            logger.warning('项目资料孤立文件检查失败，下一轮重试：%s', path.name)
    db.commit()
    # 独立提交删除队列后再删除文件；失败保留任务供下一轮重试。
    pending = db.query(Deletion).with_for_update(skip_locked=True).limit(200).all()
    for task in pending:
        try:
            storage_path(task.storage_key).unlink(missing_ok=True)
            db.delete(task)
        except OSError as exc:
            task.attempts += 1
            task.last_error = str(exc)[:500]
            logger.warning('项目资料清理失败，将重试：%s', task.storage_key)
    db.commit()
