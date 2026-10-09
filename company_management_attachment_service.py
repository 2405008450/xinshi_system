"""公司管理附件的鉴权归属、容量校验和文件存储。"""
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from company_management_models import CompanyManagementAttachment, CompanyManagementSection

ALLOWED_EXTENSIONS = {
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".csv",
    ".jpg", ".jpeg", ".png", ".webp", ".zip", ".rar", ".7z",
}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_SECTION = 50


def upload_dir() -> Path:
    return Path(os.getenv("COMPANY_MANAGEMENT_UPLOAD_DIR", "data/company_management_uploads")).resolve()


def attachment_path(storage_name: str) -> Path:
    root = upload_dir()
    path = (root / storage_name).resolve()
    if path.parent != root or Path(storage_name).name != storage_name:
        raise ValueError("附件路径无效")
    return path


def require_section(db: Session, section_id: UUID, *, lock: bool = False):
    query = db.query(CompanyManagementSection).filter(
        CompanyManagementSection.id == section_id, CompanyManagementSection.is_active.is_(True)
    )
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(status_code=404, detail="公司管理栏目不存在")
    return row


def serialize_attachment(row) -> dict:
    return {
        "id": row.id, "section_id": row.section_id,
        "original_name": row.original_name, "file_size": row.file_size,
        "content_type": row.content_type, "uploaded_by": row.uploaded_by,
        "uploaded_by_name": (row.uploader.full_name or row.uploader.username) if row.uploader else None,
        "uploaded_at": row.uploaded_at,
    }


def list_attachments(db: Session, section_id: UUID) -> list[dict]:
    require_section(db, section_id)
    rows = db.query(CompanyManagementAttachment).options(
        joinedload(CompanyManagementAttachment.uploader)
    ).filter(CompanyManagementAttachment.section_id == section_id,
             CompanyManagementAttachment.is_inline_image.is_(False)).order_by(
        CompanyManagementAttachment.uploaded_at.desc(), CompanyManagementAttachment.id
    ).all()
    return [serialize_attachment(row) for row in rows]


async def save_attachment(db: Session, section_id: UUID, upload: UploadFile, user_id: UUID) -> dict:
    destination = None
    try:
        # 所有栏目附件写操作先锁父记录，串行检查容量并防止与软删除竞态。
        require_section(db, section_id, lock=True)
        count = db.query(CompanyManagementAttachment).filter(
            CompanyManagementAttachment.section_id == section_id,
            CompanyManagementAttachment.is_inline_image.is_(False),
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
        destination = attachment_path(storage_name)
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
        row = CompanyManagementAttachment(
            section_id=section_id, original_name=original_name, storage_name=storage_name,
            content_type=(upload.content_type or "application/octet-stream")[:255],
            file_size=written, uploaded_by=user_id,
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


def get_attachment(db: Session, section_id: UUID, attachment_id: UUID, *, lock: bool = False):
    require_section(db, section_id, lock=lock)
    row = db.query(CompanyManagementAttachment).filter(
        CompanyManagementAttachment.id == attachment_id,
        CompanyManagementAttachment.section_id == section_id,
        CompanyManagementAttachment.is_inline_image.is_(False),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="附件不存在")
    return row


def delete_attachment(db: Session, section_id: UUID, attachment_id: UUID) -> None:
    row = get_attachment(db, section_id, attachment_id, lock=True)
    path = attachment_path(row.storage_name)
    quarantine = path.with_name(uuid4().hex + ".deleting")
    moved = False
    try:
        # 提交前暂存文件；数据库删除失败时恢复原文件，保持可下载和可重试。
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
