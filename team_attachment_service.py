"""团队资料附件；沿用栏目附件的格式、容量与事务文件清理规则。"""
import os
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import joinedload

from business_time import BUSINESS_TIMEZONE, business_iso
from company_management_attachment_service import ALLOWED_EXTENSIONS, MAX_FILE_BYTES, MAX_FILES_PER_SECTION
from team_resource_models import TeamResourceAttachment as Attachment


def upload_dir():
    return Path(os.getenv("TEAM_UPLOAD_DIR", "data/team_uploads")).resolve()


def attachment_path(storage_name):
    root = upload_dir()
    path = (root / storage_name).resolve()
    if path.parent != root or Path(storage_name).name != storage_name:
        raise ValueError("附件路径无效")
    return path


def is_ready(db):
    return bool(db.execute(text("SELECT to_regclass('resource_team_attachment') IS NOT NULL")).scalar())


def require_ready(db):
    if not is_ready(db):
        raise HTTPException(503, "团队资料附件尚未启用，请联系管理员完成数据库升级")


def attachment_counts(db, team_ids):
    # 附件迁移前，既有团队列表继续可用；只批量查询当前页的数量。
    if not team_ids or not is_ready(db):
        return {}
    return dict(db.query(Attachment.team_id, func.count(Attachment.id)).filter(Attachment.team_id.in_(team_ids)).group_by(Attachment.team_id).all())


def serialize_attachment(row):
    return {"id": str(row.id), "team_id": str(row.team_id), "original_name": row.original_name, "file_size": row.file_size,
            "content_type": row.content_type, "uploaded_by": str(row.uploaded_by) if row.uploaded_by else None,
            "uploaded_by_name": (row.uploader.full_name or row.uploader.username) if row.uploader else None,
            "uploaded_at": business_iso(row.uploaded_at)}


def list_attachments(db, team_id):
    from team_resource_service import get_team
    require_ready(db)
    get_team(db, team_id)
    rows = db.query(Attachment).options(joinedload(Attachment.uploader)).filter(Attachment.team_id == team_id).order_by(Attachment.uploaded_at.desc(), Attachment.id).all()
    return [serialize_attachment(row) for row in rows]


async def save_attachment(db, team_id, upload, user):
    from team_resource_service import get_team, audit
    destination = None
    try:
        require_ready(db)
        team = get_team(db, team_id, lock=True)
        if db.query(Attachment).filter(Attachment.team_id == team_id).count() >= MAX_FILES_PER_SECTION:
            raise HTTPException(400, "每个团队最多上传50个附件")
        name = (upload.filename or "").replace(chr(92), "/").rsplit("/", 1)[-1]
        if not name or len(name) > 255 or any(ord(char) < 32 for char in name):
            raise HTTPException(400, "附件文件名无效或超过255字符")
        extension = Path(name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, "不支持的附件格式")
        storage_name = uuid4().hex + extension
        destination = attachment_path(storage_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with destination.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_FILE_BYTES:
                    raise HTTPException(413, "单个附件不能超过20MB")
                output.write(chunk)
        if not written:
            raise HTTPException(400, "不能上传空文件")
        row = Attachment(id=uuid4(), team_id=team_id, original_name=name, storage_name=storage_name,
                         file_size=written, content_type=(upload.content_type or "application/octet-stream")[:255],
                         uploaded_by=user.id, uploaded_at=datetime.now(BUSINESS_TIMEZONE))
        db.add(row); db.flush()
        result = serialize_attachment(row)
        audit(db, user, team, "attachment_upload", after=result)
        db.commit()
        return result
    except BaseException:
        db.rollback()
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def get_attachment(db, team_id, attachment_id, *, lock=False):
    from team_resource_service import get_team
    require_ready(db)
    get_team(db, team_id, lock=lock)
    row = db.query(Attachment).filter(Attachment.team_id == team_id, Attachment.id == attachment_id).first()
    if not row:
        raise HTTPException(404, "团队附件不存在")
    return row


@contextmanager
def quarantine_files(paths):
    """提交前暂存文件；删除事务失败时逐个恢复，成功后清理文件。"""
    moved = []
    try:
        for path in paths:
            if path.exists():
                quarantine = path.with_name(uuid4().hex + ".deleting")
                path.replace(quarantine)
                moved.append((path, quarantine))
        yield
    except BaseException:
        for path, quarantine in reversed(moved):
            quarantine.replace(path)
        raise
    else:
        for _, quarantine in moved:
            quarantine.unlink(missing_ok=True)


def delete_attachment(db, team_id, attachment_id, user):
    from team_resource_service import get_team, audit
    try:
        row = get_attachment(db, team_id, attachment_id, lock=True)
        before = serialize_attachment(row)
        with quarantine_files([attachment_path(row.storage_name)]):
            audit(db, user, get_team(db, team_id), "attachment_delete", before=before)
            db.delete(row); db.commit()
    except BaseException:
        db.rollback()
        raise


def delete_team_with_attachments(db, user, team_id, revision):
    from team_resource_service import get_team, check_revision, delete_team
    try:
        check_revision(get_team(db, team_id, lock=True), revision)
        rows = db.query(Attachment).filter(Attachment.team_id == team_id).all() if is_ready(db) else []
        with quarantine_files([attachment_path(row.storage_name) for row in rows]):
            delete_team(db, user, team_id, revision)
            db.commit()
    except BaseException:
        db.rollback()
        raise
