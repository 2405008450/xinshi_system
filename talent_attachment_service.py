"""人才照片、音频和证书附件的受控存储。"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from resource_models import ResourceCertificate, ResourcePerson, ResourcePersonAttachment


UPLOAD_RULES = {
    "photo": ({".jpg", ".jpeg", ".png", ".webp"}, 10 * 1024 * 1024),
    "audio": ({".mp3", ".wav", ".m4a", ".aac", ".ogg"}, 100 * 1024 * 1024),
    "certificate": ({".pdf", ".jpg", ".jpeg", ".png"}, 20 * 1024 * 1024),
}
MAX_FILES_PER_CATEGORY = 10


def talent_upload_dir() -> Path:
    path = Path(os.getenv("TALENT_UPLOAD_DIR", "data/talent_uploads")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def attachment_path(storage_name: str) -> Path:
    path = (talent_upload_dir() / Path(storage_name).name).resolve()
    if path.parent != talent_upload_dir():
        raise ValueError("附件路径无效")
    return path


async def save_talent_attachment(
    db: Session,
    person_id: UUID,
    category: str,
    upload: UploadFile,
    *,
    uploaded_by: UUID | None,
    certificate_id: UUID | None = None,
) -> ResourcePersonAttachment:
    if category not in UPLOAD_RULES:
        raise ValueError("不支持的附件分类")
    person = db.query(ResourcePerson.id).filter(ResourcePerson.id == person_id).first()
    if not person:
        raise LookupError("人才档案不存在")
    if db.query(ResourcePersonAttachment.id).filter(
        ResourcePersonAttachment.person_id == person_id,
        ResourcePersonAttachment.category == category,
    ).count() >= MAX_FILES_PER_CATEGORY:
        raise ValueError(f"每类附件最多上传{MAX_FILES_PER_CATEGORY}个")
    if category == "certificate":
        if certificate_id is None:
            raise ValueError("证书附件必须关联证书")
        belongs = db.query(ResourceCertificate.id).filter(
            ResourceCertificate.id == certificate_id,
            ResourceCertificate.person_id == person_id,
        ).first()
        if not belongs:
            raise ValueError("关联证书不属于当前人才")
    elif certificate_id is not None:
        raise ValueError("照片和音频不能关联证书")

    original_name = Path(upload.filename or "未命名文件").name
    extension = Path(original_name).suffix.lower()
    allowed_extensions, max_bytes = UPLOAD_RULES[category]
    if extension not in allowed_extensions:
        raise ValueError(f"不支持的文件格式：{extension or '无扩展名'}")
    storage_name = f"{uuid4().hex}{extension}"
    destination = attachment_path(storage_name)
    written = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError("文件大小超过限制")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    row = ResourcePersonAttachment(
        person_id=person_id,
        certificate_id=certificate_id,
        category=category,
        original_name=original_name,
        storage_name=storage_name,
        content_type=upload.content_type or "application/octet-stream",
        file_size=written,
        uploaded_by=uploaded_by,
    )
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    db.refresh(row)
    return row


def delete_talent_attachment(db: Session, person_id: UUID, attachment_id: UUID) -> bool:
    row = db.query(ResourcePersonAttachment).filter(
        ResourcePersonAttachment.id == attachment_id,
        ResourcePersonAttachment.person_id == person_id,
    ).first()
    if not row:
        return False
    path = attachment_path(row.storage_name)
    db.delete(row)
    db.commit()
    path.unlink(missing_ok=True)
    return True
