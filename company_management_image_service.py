"""公司管理正文图片：鉴权归属、文件验证及草稿生命周期。"""
import io
import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from company_management_attachment_service import attachment_path, require_section, serialize_attachment
from company_management_models import CompanyManagementAttachment
from company_management_schemas import document_images

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGES_PER_SECTION = 50
MAX_IMAGE_PIXELS = 40_000_000
IMAGE_TYPES = {"PNG": ("image/png", ".png"), "JPEG": ("image/jpeg", ".jpg"), "WEBP": ("image/webp", ".webp")}
logger = logging.getLogger(__name__)


def image_rows(db: Session, section_id: UUID):
    return db.query(CompanyManagementAttachment).filter(
        CompanyManagementAttachment.section_id == section_id,
        CompanyManagementAttachment.is_inline_image.is_(True),
    )


def normalize_image(content: bytes, content_type: str) -> tuple[bytes, str, str]:
    if not content:
        raise HTTPException(status_code=400, detail="不能粘贴空图片")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="单张正文图片不能超过20MB")
    try:
        with Image.open(io.BytesIO(content)) as source:
            detected = source.format
            if detected not in IMAGE_TYPES or content_type != IMAGE_TYPES[detected][0]:
                raise ValueError("仅支持内容与格式一致的 PNG、JPEG、WebP 图片")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("图片像素尺寸过大，请缩小后重新粘贴")
            source.verify()
        with Image.open(io.BytesIO(content)) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            if detected == "JPEG" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format=detected)
            normalized = output.getvalue()
        if len(normalized) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="处理后的正文图片超过20MB，请缩小后重新粘贴")
        return normalized, *IMAGE_TYPES[detected]
    except HTTPException:
        raise
    except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) if isinstance(exc, ValueError) else "图片损坏或无法识别，请重新截图粘贴") from exc


def commit_removed_images(db: Session, rows: list) -> None:
    """提交前暂存被删除文件，失败时恢复；必须已取得栏目锁。"""
    moved = []
    try:
        for row in rows:
            path = attachment_path(row.storage_name)
            if path.exists():
                quarantine = path.with_name(uuid4().hex + ".deleting")
                path.replace(quarantine)
                moved.append((path, quarantine))
            db.delete(row)
        db.commit()
    except BaseException:
        db.rollback()
        for path, quarantine in moved:
            quarantine.replace(path)
        raise
    for _, quarantine in moved:
        try:
            quarantine.unlink(missing_ok=True)
        except OSError:
            logger.exception("正文图片暂存文件清理失败")


def expired_drafts(db: Session, section) -> list:
    used = {image_id for _, image_id in document_images(section.content_json)}
    rows = image_rows(db, section.id).filter(
        CompanyManagementAttachment.uploaded_at < datetime.now() - timedelta(hours=24)
    ).all()
    return [row for row in rows if row.id not in used]


async def save_image(db: Session, section_id: UUID, upload: UploadFile, user_id: UUID) -> dict:
    destination = None
    try:
        section = require_section(db, section_id, lock=True)
        if not section.has_content:
            raise HTTPException(status_code=400, detail="分组栏目不能上传正文图片")
        expired = expired_drafts(db, section)
        if image_rows(db, section_id).count() - len(expired) >= MAX_IMAGES_PER_SECTION:
            raise HTTPException(status_code=400, detail="每个栏目最多保存50张正文图片，请先移除不需要的图片并保存")
        content = bytearray()
        while chunk := await upload.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="单张正文图片不能超过20MB")
        normalized, mime, extension = normalize_image(bytes(content), upload.content_type or "")
        name = (upload.filename or "粘贴图片").replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(c for c in name if ord(c) >= 32 and ord(c) != 127)[:240] or "粘贴图片"
        name = name.rsplit(".", 1)[0] + extension
        storage_name = uuid4().hex + extension
        destination = attachment_path(storage_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(normalized)
        row = CompanyManagementAttachment(
            section_id=section_id, original_name=name, storage_name=storage_name,
            content_type=mime, file_size=len(normalized), uploaded_by=user_id, is_inline_image=True,
        )
        db.add(row)
        db.flush()
        result = serialize_attachment(row)
        result["src"] = f"/api/company-management/sections/{section_id}/images/{row.id}"
        commit_removed_images(db, expired)
        return result
    except BaseException:
        db.rollback()
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def get_image(db: Session, section_id: UUID, image_id: UUID):
    require_section(db, section_id)
    row = image_rows(db, section_id).filter(CompanyManagementAttachment.id == image_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="正文图片不存在")
    return row


def delete_draft(db: Session, section_id: UUID, image_id: UUID, user_id: UUID) -> None:
    section = require_section(db, section_id, lock=True)
    row = get_image(db, section_id, image_id)
    if any(used_id == image_id for _, used_id in document_images(section.content_json)):
        raise HTTPException(status_code=409, detail="图片正在被正文引用，不能直接删除")
    if row.uploaded_by != user_id:
        raise HTTPException(status_code=403, detail="只能清理自己上传的未保存图片")
    commit_removed_images(db, [row, *[item for item in expired_drafts(db, section) if item.id != row.id]])


def validate_content_images(db: Session, section, document: dict) -> list:
    references = document_images(document)
    if any(section_id != section.id for section_id, _ in references):
        raise ValueError("正文图片不属于当前栏目")
    used_ids = {image_id for _, image_id in references}
    existing = {row.id: row for row in image_rows(db, section.id).all()}
    if not used_ids.issubset(existing):
        raise ValueError("正文图片已失效，请重新粘贴图片")
    if any(not attachment_path(existing[image_id].storage_name).is_file() for image_id in used_ids):
        raise ValueError("正文图片文件不存在，请重新粘贴图片")
    previous_ids = {image_id for _, image_id in document_images(section.content_json)}
    removed_ids = previous_ids - used_ids
    removed_ids.update(row.id for row in expired_drafts(db, section) if row.id not in used_ids)
    return [row for image_id, row in existing.items() if image_id in removed_ids]
