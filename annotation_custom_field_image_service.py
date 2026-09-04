"""项目账号动态图片字段的文件存储、校验和分配关联。"""

from __future__ import annotations

import datetime as dt
import logging
import os
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from annotation_ops_models import (
    AnnotationAccountAssignmentImage,
    AnnotationCustomFieldDefinition,
    AnnotationCustomFieldImage,
)
from database import engine


MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_SIGNATURES = {
    "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
    "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/gif": lambda value: value.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP",
}
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


logger = logging.getLogger(__name__)


def get_custom_field_image_dir() -> Path:
    path = Path(os.getenv("ANNOTATION_CUSTOM_FIELD_IMAGE_DIR", "data/annotation_custom_field_images")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_image_content(content: bytes, content_type: str) -> str:
    normalized_type = (content_type or "").lower()
    validator = IMAGE_SIGNATURES.get(normalized_type)
    if validator is None:
        raise ValueError("仅支持 JPEG、PNG、GIF、WebP 图片")
    if not content:
        raise ValueError("图片内容为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("单张图片不能超过 10MB")
    if not validator(content):
        raise ValueError("图片格式与文件内容不匹配")
    return normalized_type


def create_custom_field_image(
    db: Session,
    *,
    project_id: UUID,
    field_id: UUID,
    uploaded_by: UUID,
    original_name: str,
    content_type: str,
    content: bytes,
) -> AnnotationCustomFieldImage:
    field = db.get(AnnotationCustomFieldDefinition, field_id)
    if not field or not field.is_active:
        raise ValueError("图片动态字段不存在或已停用")
    if field.table_code != "account_assignment" or field.data_type != "image":
        raise ValueError("所选字段不是项目账号图片字段")
    if field.project_id != project_id:
        raise ValueError("图片字段不属于当前项目")

    normalized_type = validate_image_content(content, content_type)
    storage_name = f"{uuid.uuid4().hex}{IMAGE_EXTENSIONS[normalized_type]}"
    destination = get_custom_field_image_dir() / storage_name
    destination.write_bytes(content)
    row = AnnotationCustomFieldImage(
        project_id=project_id,
        field_definition_id=field_id,
        uploaded_by=uploaded_by,
        original_name=(original_name or "image")[:255],
        storage_name=storage_name,
        content_type=normalized_type,
        file_size=len(content),
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return row


def get_accessible_custom_field_image(db: Session, image_id: UUID, user_id: UUID):
    row = db.get(AnnotationCustomFieldImage, image_id)
    if not row:
        return None
    linked = db.query(AnnotationAccountAssignmentImage.id).filter(
        AnnotationAccountAssignmentImage.image_id == image_id,
    ).first()
    if not linked and row.uploaded_by != user_id:
        return None
    return row


def delete_pending_custom_field_image(db: Session, image_id: UUID, user_id: UUID) -> bool:
    row = db.get(AnnotationCustomFieldImage, image_id)
    if not row or row.uploaded_by != user_id:
        return False
    if db.query(AnnotationAccountAssignmentImage.id).filter(
        AnnotationAccountAssignmentImage.image_id == image_id,
    ).first():
        raise ValueError("已保存的图片请通过清空图片字段后保存来删除")
    path = get_custom_field_image_dir() / row.storage_name
    db.delete(row)
    db.commit()
    path.unlink(missing_ok=True)
    return True


def delete_custom_field_image_files(storage_names) -> None:
    """数据库事务提交后，清理已经随业务记录删除的项目图片文件。"""
    upload_dir = get_custom_field_image_dir()
    for storage_name in set(storage_names or []):
        if not storage_name:
            continue
        path = (upload_dir / storage_name).resolve()
        if path.parent != upload_dir:
            logger.warning("跳过异常的标注动态字段图片路径：%s", storage_name)
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # 数据库删除已经成功，文件清理失败不能把接口伪装成业务删除失败；
            # 启动清理任务仍会再次处理未被数据库追踪的旧文件。
            logger.exception("清理标注动态字段图片文件失败：%s", path)


def normalize_image_value(
    db: Session,
    definition: AnnotationCustomFieldDefinition,
    project_id: UUID,
    value,
    *,
    user_id: UUID | None,
    existing_value=None,
) -> str | None:
    if value in {None, ""}:
        return None
    try:
        image_id = UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{definition.field_label} 图片标识无效") from exc
    image = db.get(AnnotationCustomFieldImage, image_id)
    if not image:
        raise ValueError(f"{definition.field_label} 图片不存在")
    if image.project_id != project_id or image.field_definition_id != definition.id:
        raise ValueError(f"{definition.field_label} 图片不属于当前项目或字段")
    existing_id = str(existing_value) if existing_value else None
    already_linked = db.query(AnnotationAccountAssignmentImage.id).filter(
        AnnotationAccountAssignmentImage.image_id == image.id,
    ).first()
    if user_id is not None and str(image.id) != existing_id and image.uploaded_by != user_id and not already_linked:
        raise ValueError(f"{definition.field_label} 图片不属于当前用户")
    return str(image.id)


def validate_image_value_ownership(
    db: Session,
    project_id: UUID,
    values: dict,
    user_id: UUID | None,
    existing_values: dict | None = None,
) -> None:
    if not values:
        return
    definitions = db.query(AnnotationCustomFieldDefinition).filter(
        AnnotationCustomFieldDefinition.table_code == "account_assignment",
        AnnotationCustomFieldDefinition.project_id == project_id,
        AnnotationCustomFieldDefinition.data_type == "image",
    ).all()
    existing_values = existing_values or {}
    for definition in definitions:
        key = str(definition.id)
        if key not in values:
            continue
        normalize_image_value(
            db,
            definition,
            project_id,
            values[key],
            user_id=user_id,
            existing_value=existing_values.get(key),
        )


def sync_assignment_image_links(db: Session, assignment_id: UUID, project_id: UUID, values: dict) -> None:
    definitions = db.query(AnnotationCustomFieldDefinition).filter(
        AnnotationCustomFieldDefinition.table_code == "account_assignment",
        AnnotationCustomFieldDefinition.project_id == project_id,
        AnnotationCustomFieldDefinition.data_type == "image",
    ).all()
    existing_links = {
        row.field_definition_id: row
        for row in db.query(AnnotationAccountAssignmentImage).filter(
            AnnotationAccountAssignmentImage.assignment_id == assignment_id,
        ).all()
    }
    for definition in definitions:
        desired = values.get(str(definition.id))
        link = existing_links.get(definition.id)
        if not desired:
            if link:
                db.delete(link)
            continue
        image_id = UUID(str(desired))
        if link:
            link.image_id = image_id
        else:
            db.add(AnnotationAccountAssignmentImage(
                assignment_id=assignment_id,
                field_definition_id=definition.id,
                image_id=image_id,
            ))


def cleanup_orphan_custom_field_images() -> None:
    now_utc = dt.datetime.now(dt.timezone.utc)
    cutoff = (now_utc - dt.timedelta(hours=24)).replace(tzinfo=None)
    upload_dir = get_custom_field_image_dir()
    with Session(engine) as db:
        orphans = (
            db.query(AnnotationCustomFieldImage)
            .outerjoin(
                AnnotationAccountAssignmentImage,
                AnnotationAccountAssignmentImage.image_id == AnnotationCustomFieldImage.id,
            )
            .filter(
                AnnotationAccountAssignmentImage.id.is_(None),
                AnnotationCustomFieldImage.created_at < cutoff,
            )
            .all()
        )
        for image in orphans:
            (upload_dir / image.storage_name).unlink(missing_ok=True)
            db.delete(image)
        if orphans:
            db.commit()

        known_names = {name for (name,) in db.query(AnnotationCustomFieldImage.storage_name).all()}
    cutoff_timestamp = (now_utc - dt.timedelta(hours=24)).timestamp()
    for path in upload_dir.iterdir():
        if path.is_file() and path.name not in known_names and path.stat().st_mtime < cutoff_timestamp:
            path.unlink(missing_ok=True)
