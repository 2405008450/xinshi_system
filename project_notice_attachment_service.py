"""项目须知附件的权限归属、容量限制和事务文件清理。"""
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from project_notice_models import ProjectNoticeAttachment
from project_notice_service import require_section, MODULES
from business_time import BUSINESS_TIMEZONE, business_iso
from company_management_attachment_service import ALLOWED_EXTENSIONS, MAX_FILE_BYTES, MAX_FILES_PER_SECTION


def upload_dir(module: str) -> Path:
    if module not in MODULES:
        raise HTTPException(404, "项目须知板块不存在")
    return Path(os.getenv("PROJECT_NOTICE_UPLOAD_DIR", "data/project_notice_uploads")).resolve() / module


def attachment_path(module: str, storage_name: str) -> Path:
    root = upload_dir(module)
    path = (root / storage_name).resolve()
    if path.parent != root or Path(storage_name).name != storage_name:
        raise ValueError("附件路径无效")
    return path



def serialize_attachment(row) -> dict:
    return {
        "id": row.id, "section_id": row.section_id,
        "original_name": row.original_name, "file_size": row.file_size,
        "content_type": row.content_type, "uploaded_by": row.uploaded_by,
        "uploaded_by_name": (row.uploader.full_name or row.uploader.username) if row.uploader else None,
        "uploaded_at": business_iso(row.uploaded_at),
    }


def list_attachments(db: Session, module: str, section_id: UUID) -> list[dict]:
    require_section(db, module, section_id)
    rows = db.query(ProjectNoticeAttachment).options(
        joinedload(ProjectNoticeAttachment.uploader)
    ).filter(ProjectNoticeAttachment.section_id == section_id).order_by(
        ProjectNoticeAttachment.uploaded_at.desc(), ProjectNoticeAttachment.id
    ).all()
    return [serialize_attachment(row) for row in rows]


async def save_attachment(db: Session, module: str, section_id: UUID, upload: UploadFile, user_id: UUID) -> dict:
    destination = None
    try:
        require_section(db, module, section_id, lock=True)
        count = db.query(ProjectNoticeAttachment).filter(
            ProjectNoticeAttachment.section_id == section_id
        ).count()
        if count >= MAX_FILES_PER_SECTION:
            raise HTTPException(status_code=400, detail="每个栏目最多上传50个附件")
        original_name = (upload.filename or "").replace(chr(92), "/").rsplit("/", 1)[-1]
        if not original_name or len(original_name) > 255 or any(ord(c) < 32 for c in original_name):
            raise HTTPException(status_code=400, detail="附件文件名无效或超过255字符")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="不支持的附件格式")
        storage_name = uuid4().hex + extension
        destination = attachment_path(module, storage_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with destination.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_FILE_BYTES:
                    raise HTTPException(status_code=413, detail="单个附件不能超过20MB")
                output.write(chunk)
        if not written:
            raise HTTPException(status_code=400, detail="不能上传空文件")
        row = ProjectNoticeAttachment(
            section_id=section_id, original_name=original_name, storage_name=storage_name,
            content_type=(upload.content_type or "application/octet-stream")[:255],
            file_size=written, uploaded_by=user_id, uploaded_at=datetime.now(BUSINESS_TIMEZONE),
        )
        db.add(row)
        db.flush()
        result = serialize_attachment(row)
        db.commit()
        return result
    except BaseException:
        db.rollback()
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def get_attachment(db: Session, module: str, section_id: UUID, attachment_id: UUID, *, lock: bool = False):
    require_section(db, module, section_id, lock=lock)
    row = db.query(ProjectNoticeAttachment).filter(
        ProjectNoticeAttachment.id == attachment_id,
        ProjectNoticeAttachment.section_id == section_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="附件不存在")
    return row


def delete_attachment(db: Session, module: str, section_id: UUID, attachment_id: UUID) -> None:
    row = get_attachment(db, module, section_id, attachment_id, lock=True)
    path = attachment_path(module, row.storage_name)
    quarantine = path.with_name(uuid4().hex + ".deleting")
    moved = False
    try:
        if path.exists():
            path.replace(quarantine)
            moved = True
        db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
        if moved:
            quarantine.replace(path)
        raise
    if moved:
        quarantine.unlink(missing_ok=True)
