"""资料回收站：项目、文件、Office 会话按固定顺序加锁，永不自动清理。"""
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, inspect
from annotation_models import AnnotationProject
from annotation_material_models import AnnotationMaterialFile as Material, AnnotationMaterialFolder as Folder
from annotation_material_models import AnnotationMaterialVersion as Version, AnnotationMaterialUpload as Upload
from annotation_material_service import remove_material
from business_time import BUSINESS_TIMEZONE, business_iso
from search_matching import keyword_any

logger = logging.getLogger(__name__)
LABELS = {'project': '项目资料', 'quotation': '报价单', 'contract': '合同'}


def lock_file(db, project_id, file_id, missing_ok=False):
    if not db.query(AnnotationProject.id).filter_by(id=project_id).with_for_update().first():
        raise HTTPException(404, '标注项目不存在')
    row = db.query(Material).filter_by(id=file_id, project_id=project_id).with_for_update().populate_existing().first()
    if row is None and not missing_ok:
        raise HTTPException(404, '资料不属于当前项目或已彻底删除')
    return row


def folder_path(db, material):
    parts, seen, folder_id = [], set(), material.folder_id
    while folder_id and folder_id not in seen:
        seen.add(folder_id)
        folder = db.query(Folder).filter_by(id=folder_id, project_id=material.project_id).first()
        if folder is None:
            break
        parts.insert(0, folder.name)
        folder_id = folder.parent_id
    return ' / '.join([LABELS[material.category], *parts])


def log_action(action, material, actor_id):
    logger.info('%s material_%s project=%s file=%s actor=%s token=%s',
                business_iso(datetime.now(BUSINESS_TIMEZONE)), action, material.project_id,
                material.id, actor_id, material.trash_token)


def trash_file(db, material, actor_id, actor_name=None):
    material = lock_file(db, material.project_id, material.id)
    if material.deleted_at is not None:
        return material
    from annotation_office_service import assert_file_unlocked
    assert_file_unlocked(db, material.id)
    if actor_name is None:
        from models import AppUser
        actor = db.query(AppUser.username, AppUser.full_name).filter(AppUser.id == actor_id).first()
        actor_name = (actor.full_name or actor.username) if actor else str(actor_id)
    material.deleted_at = datetime.now(BUSINESS_TIMEZONE)
    material.deleted_by, material.deleted_by_name = actor_id, actor_name
    material.deleted_folder_path = folder_path(db, material)
    material.trash_token = uuid4()
    # 旧只读和已过期会话不能在恢复文件后重新取得访问或提交能力。
    if inspect(db.connection()).has_table('annotation_office_session'):
        from annotation_office_models import AnnotationOfficeSession as OfficeSession
        sessions = db.query(OfficeSession).filter_by(file_id=material.id).with_for_update().all()
        for session in sessions:
            if session.state in ('open', 'saving', 'expired'):
                session.state = 'discarded'
    db.flush()
    log_action('trash', material, actor_id)
    return material


def check_token(material, token):
    if material.trash_token != token:
        raise HTTPException(409, '回收站记录已变化，请刷新后重试')


def restore_file(db, material, token, actor_id):
    check_token(material, token)
    if material.deleted_at is None:
        return material
    if material.folder_id and not db.query(Folder.id).filter_by(id=material.folder_id, project_id=material.project_id).first():
        material.folder_id = None
    material.deleted_at = None
    log_action('restore', material, actor_id)
    db.flush()
    return material


def purge_file(db, material, token, actor_id):
    check_token(material, token)
    if material.deleted_at is None:
        raise HTTPException(409, '文件已恢复，不能彻底删除')
    log_action('purge', material, actor_id)
    remove_material(db, material)
    db.flush()


def catalog(db, project_id, keyword='', page=1, limit=20):
    latest = db.query(Version.file_id, func.max(Version.version_no).label('number'),
                      func.count(Version.id).label('version_count')).group_by(Version.file_id).subquery()
    query = db.query(Material, Version, Upload, latest.c.version_count).join(latest, latest.c.file_id == Material.id).join(
        Version, (Version.file_id == Material.id) & (Version.version_no == latest.c.number)).join(Upload, Upload.id == Version.upload_id).filter(
        Material.project_id == project_id, Material.deleted_at.is_not(None))
    if keyword.strip():
        query = query.filter(keyword_any([Upload.original_name, Material.deleted_folder_path, Material.deleted_by_name], keyword))
    total = query.count()
    items = []
    for material, version, upload, count in query.order_by(Material.deleted_at.desc(), Material.id).offset((page - 1) * limit).limit(limit):
        items.append(dict(file_id=material.id, original_name=upload.original_name, category=material.category,
            folder_id=material.folder_id, original_folder_path=material.deleted_folder_path, version_count=count,
            version_no=version.version_no, deleted_at=business_iso(material.deleted_at),
            deleted_by_name=material.deleted_by_name, trash_token=material.trash_token))
    return dict(items=items, total=total, page=page, limit=limit)
