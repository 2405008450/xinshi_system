"""邮件正文图片的校验、持久化、清理与 HTML/CID 转换。"""

from __future__ import annotations

import datetime
import html
import io
import os
import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from mail_inline_image_models import MailInlineImage, MailInlineImageBinding
from mail_service import MailInlineImagePart
from mail_html_security import safe_css_color, safe_mail_href


MAX_INLINE_IMAGE_BYTES = 2 * 1024 * 1024
MAX_INLINE_IMAGE_COUNT = 5
MAX_INLINE_IMAGE_TOTAL_BYTES = 8 * 1024 * 1024
MAX_IMAGE_EDGE = 1920
MAX_SOURCE_PIXELS = 40_000_000
ALLOWED_INPUT_TYPES = {"image/jpeg", "image/png", "image/webp"}
SCOPE_TYPES = {"business_mail", "daily_report_delivery", "manuscript_arrangement"}
IMAGE_ID_PATTERN = re.compile(r'data-mail-image-id=["\']([0-9a-fA-F-]{36})["\']')


def get_mail_inline_image_dir() -> Path:
    path = Path(os.getenv("MAIL_INLINE_IMAGE_DIR", "data/mail_inline_images")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def inline_image_path(storage_name: str) -> Path:
    root = get_mail_inline_image_dir()
    candidate = (root / storage_name).resolve()
    if candidate.parent != root:
        raise ValueError("正文图片存储路径不合法")
    return candidate


def _safe_name(value: Optional[str]) -> str:
    name = (value or "正文图片").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name).strip()
    return (name or "正文图片")[:255]


def normalize_uploaded_image(content: bytes, content_type: str) -> tuple[bytes, str, int, int, str]:
    if not content:
        raise ValueError("图片内容为空")
    if len(content) > MAX_INLINE_IMAGE_BYTES:
        raise ValueError("单张正文图片不能超过 2MB")
    if content_type not in ALLOWED_INPUT_TYPES:
        raise ValueError("仅支持 JPEG、PNG、WebP 图片")
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.verify()
        with Image.open(io.BytesIO(content)) as source:
            source_format = (source.format or "").upper()
            if source_format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("图片格式与文件内容不匹配")
            expected_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[source_format]
            if content_type != expected_type:
                raise ValueError("图片格式与文件内容不匹配")
            if source.width <= 0 or source.height <= 0 or source.width * source.height > MAX_SOURCE_PIXELS:
                raise ValueError("图片像素尺寸过大")
            image = ImageOps.exif_transpose(source)
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            has_alpha = image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
            output = io.BytesIO()
            if has_alpha:
                image.convert("RGBA").save(output, format="PNG", optimize=True)
                normalized_type, extension = "image/png", ".png"
            else:
                image.convert("RGB").save(output, format="JPEG", quality=85, optimize=True, progressive=True)
                normalized_type, extension = "image/jpeg", ".jpg"
            normalized = output.getvalue()
            if len(normalized) > MAX_INLINE_IMAGE_BYTES:
                raise ValueError("图片压缩后仍超过 2MB，请降低分辨率后重试")
            return normalized, normalized_type, image.width, image.height, extension
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("无法识别图片内容") from exc


def save_uploaded_image(db: Session, *, uploaded_by: UUID, filename: Optional[str], content_type: str, content: bytes) -> MailInlineImage:
    normalized, normalized_type, width, height, extension = normalize_uploaded_image(content, content_type)
    storage_name = f"{uuid.uuid4().hex}{extension}"
    destination = inline_image_path(storage_name)
    destination.write_bytes(normalized)
    record = MailInlineImage(
        uploaded_by=uploaded_by,
        original_name=_safe_name(filename),
        storage_name=storage_name,
        content_type=normalized_type,
        file_size=len(normalized),
        width=width,
        height=height,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return record


def serialize_inline_image(image: MailInlineImage) -> dict:
    return {
        "id": image.id,
        "original_name": image.original_name,
        "content_type": image.content_type,
        "file_size": image.file_size,
        "width": image.width,
        "height": image.height,
    }


def load_owned_images(db: Session, image_ids: Iterable[UUID], uploaded_by: UUID) -> list[MailInlineImage]:
    ids = list(image_ids or [])
    if len(ids) > MAX_INLINE_IMAGE_COUNT or len(set(ids)) != len(ids):
        raise ValueError("每封邮件最多插入 5 张且不能重复")
    if not ids:
        return []
    images = db.query(MailInlineImage).filter(MailInlineImage.id.in_(ids)).all()
    found = {item.id: item for item in images}
    if len(found) != len(ids):
        raise ValueError("部分正文图片不存在或已过期")
    ordered = [found[item_id] for item_id in ids]
    if any(item.uploaded_by != uploaded_by for item in ordered):
        raise PermissionError("无权使用其他用户上传的正文图片")
    if sum(item.file_size for item in ordered) > MAX_INLINE_IMAGE_TOTAL_BYTES:
        raise ValueError("正文图片合计不能超过 8MB")
    return ordered


def load_owned_or_bound_images(
    db: Session,
    image_ids: Iterable[UUID],
    uploaded_by: UUID,
    *,
    scope_type: str,
    scope_id: UUID,
) -> list[MailInlineImage]:
    ids = list(image_ids or [])
    if len(ids) > MAX_INLINE_IMAGE_COUNT or len(set(ids)) != len(ids):
        raise ValueError("每封邮件最多插入 5 张且不能重复")
    if not ids:
        return []
    images = db.query(MailInlineImage).filter(MailInlineImage.id.in_(ids)).all()
    found = {item.id: item for item in images}
    if len(found) != len(ids):
        raise ValueError("部分正文图片不存在或已过期")
    ordered = [found[item_id] for item_id in ids]
    bound_ids = {
        item.image_id for item in db.query(MailInlineImageBinding).filter(
            MailInlineImageBinding.image_id.in_(ids),
            MailInlineImageBinding.scope_type == scope_type,
            MailInlineImageBinding.scope_id == scope_id,
        ).all()
    }
    if any(item.uploaded_by != uploaded_by and item.id not in bound_ids for item in ordered):
        raise PermissionError("无权使用其他用户上传的正文图片")
    if sum(item.file_size for item in ordered) > MAX_INLINE_IMAGE_TOTAL_BYTES:
        raise ValueError("正文图片合计不能超过 8MB")
    return ordered


def bind_images(db: Session, images: Iterable[MailInlineImage], scope_type: str, scope_id: UUID) -> None:
    if scope_type not in SCOPE_TYPES:
        raise ValueError("不支持的邮件图片绑定类型")
    existing = {
        item.image_id for item in db.query(MailInlineImageBinding).filter(
            MailInlineImageBinding.scope_type == scope_type,
            MailInlineImageBinding.scope_id == scope_id,
        ).all()
    }
    for image in images:
        if image.id not in existing:
            db.add(MailInlineImageBinding(image_id=image.id, scope_type=scope_type, scope_id=scope_id))


def bound_images(db: Session, scope_type: str, scope_id: UUID) -> list[MailInlineImage]:
    return (
        db.query(MailInlineImage)
        .join(MailInlineImageBinding, MailInlineImageBinding.image_id == MailInlineImage.id)
        .filter(MailInlineImageBinding.scope_type == scope_type, MailInlineImageBinding.scope_id == scope_id)
        .all()
    )


def delete_draft_image(db: Session, image_id: UUID, uploaded_by: UUID) -> bool:
    image = db.query(MailInlineImage).filter(MailInlineImage.id == image_id).first()
    if not image:
        return False
    if image.uploaded_by != uploaded_by:
        raise PermissionError("无权删除该正文图片")
    bound = db.query(MailInlineImageBinding.id).filter(MailInlineImageBinding.image_id == image_id).first()
    if bound:
        raise ValueError("已随邮件保存的图片不能删除")
    path = inline_image_path(image.storage_name)
    db.delete(image)
    db.commit()
    path.unlink(missing_ok=True)
    return True


def cleanup_orphan_inline_images(
    db: Session,
    *,
    older_than_hours: int = 24,
    prune_missing_scopes: bool = False,
) -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=older_than_hours)
    bindings_removed = False
    if prune_missing_scopes:
        # 该检查仅在显式维护/迁移时执行，避免普通上传请求遍历全部历史绑定。
        from business_mail_models import BusinessMail
        from daily_report_mail_models import DailyReportMailDelivery
        from manuscript_models import ManuscriptArrangement

        scope_models = {
            "business_mail": BusinessMail,
            "daily_report_delivery": DailyReportMailDelivery,
            "manuscript_arrangement": ManuscriptArrangement,
        }
        for binding in db.query(MailInlineImageBinding).filter(
            MailInlineImageBinding.created_at < cutoff
        ).all():
            model = scope_models.get(binding.scope_type)
            if model is None or not db.query(model.id).filter(model.id == binding.scope_id).first():
                db.delete(binding)
                bindings_removed = True
        db.flush()
    rows = (
        db.query(MailInlineImage)
        .outerjoin(MailInlineImageBinding, MailInlineImageBinding.image_id == MailInlineImage.id)
        .filter(MailInlineImageBinding.id == None, MailInlineImage.created_at < cutoff)
        .all()
    )
    for image in rows:
        inline_image_path(image.storage_name).unlink(missing_ok=True)
        db.delete(image)
    if rows or bindings_removed:
        db.commit()
    return len(rows)


class _SafeMailHtmlParser(HTMLParser):
    allowed = {"p", "br", "div", "strong", "b", "em", "i", "u", "span", "a", "ul", "ol", "li", "blockquote"}

    def __init__(self, allowed_image_ids: set[UUID]):
        super().__init__(convert_charrefs=True)
        self.allowed_image_ids = allowed_image_ids
        self.output: list[str] = []
        self.referenced: list[UUID] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        values = dict(attrs)
        if tag == "img":
            try:
                image_id = UUID(values.get("data-mail-image-id", ""))
            except ValueError:
                return
            if image_id not in self.allowed_image_ids:
                raise ValueError("邮件正文引用了未授权图片")
            if image_id in self.referenced:
                raise ValueError("同一张正文图片不能重复插入")
            self.referenced.append(image_id)
            alt = html.escape((values.get("alt") or "正文图片")[:255], quote=True)
            self.output.append(f'<img data-mail-image-id="{image_id}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:8px 0;">')
        elif tag in self.allowed:
            if tag == "br":
                self.output.append("<br>")
                return
            attributes = ""
            if tag == "a":
                href = safe_mail_href(values.get("href", ""))
                if href:
                    attributes = f' href="{html.escape(href, quote=True)}" rel="noopener noreferrer"'
            elif tag in {"span", "p", "div"}:
                style_values = {}
                for item in (values.get("style") or "").split(";"):
                    key, separator, value = item.partition(":")
                    if separator:
                        style_values[key.strip().lower()] = value.strip()
                color = safe_css_color(style_values.get("color", "") or values.get("color", ""))
                if color:
                    attributes = f' style="color:{color};"'
                if tag == "div" and values.get("data-mail-signature") == "true":
                    attributes = (
                        ' data-mail-signature="true" '
                        'style="margin-top:20px;padding-top:12px;border-top:1px solid #e5e7eb;"'
                    )
            self.output.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.allowed and tag != "br":
            self.output.append(f"</{tag}>")

    def handle_data(self, data: str):
        self.output.append(html.escape(data))


def plain_text_to_html(body: str) -> str:
    lines = (body or "").splitlines() or [""]
    return "".join(f"<p>{html.escape(line) or '<br>'}</p>" for line in lines)


def previewable_body_html(body_html: Optional[str]) -> Optional[str]:
    """为编辑器返回可解析的占位 src；不会写入数据库或实际邮件。"""
    if not body_html:
        return body_html
    return re.sub(r"<img(?![^>]*\ssrc=)", '<img src="about:blank"', body_html)


def sanitize_body_html(body_html: Optional[str], body: str, images: Iterable[MailInlineImage]) -> str:
    image_list = list(images)
    if not body_html:
        if image_list:
            raise ValueError("邮件正文缺少图片位置数据")
        return plain_text_to_html(body)
    parser = _SafeMailHtmlParser({item.id for item in image_list})
    parser.feed(body_html)
    parser.close()
    if set(parser.referenced) != {item.id for item in image_list}:
        raise ValueError("邮件正文图片与上传列表不一致")
    return "".join(parser.output)


def prepare_inline_mail(body_html: Optional[str], body: str, images: Iterable[MailInlineImage]) -> tuple[str, list[MailInlineImagePart]]:
    image_list = list(images)
    safe_html = sanitize_body_html(body_html, body, image_list)
    parts: list[MailInlineImagePart] = []
    for image in image_list:
        cid = f"mail-image-{image.id}@xinshi-system.local"
        safe_html = safe_html.replace(
            f'data-mail-image-id="{image.id}"',
            f'src="cid:{cid}"',
        )
        path = inline_image_path(image.storage_name)
        if not path.is_file():
            raise ValueError(f"正文图片文件不存在：{image.original_name}")
        parts.append(MailInlineImagePart(
            cid=cid,
            filename=image.original_name,
            content=path.read_bytes(),
            content_type=image.content_type,
        ))
    return safe_html, parts


def prepare_trusted_mail_html(body_html: str, images: Iterable[MailInlineImage]) -> tuple[str, list[MailInlineImagePart]]:
    """处理由服务端模板生成、仅图片片段经过清洗的完整 HTML。"""
    image_list = list(images)
    referenced = [UUID(value) for value in IMAGE_ID_PATTERN.findall(body_html or "")]
    if len(referenced) != len(set(referenced)) or set(referenced) != {item.id for item in image_list}:
        raise ValueError("邮件正文图片与上传列表不一致")
    rendered = body_html
    parts: list[MailInlineImagePart] = []
    for image in image_list:
        cid = f"mail-image-{image.id}@xinshi-system.local"
        rendered = re.sub(
            rf'data-mail-image-id=["\']{re.escape(str(image.id))}["\']',
            f'src="cid:{cid}"',
            rendered,
            count=1,
        )
        path = inline_image_path(image.storage_name)
        if not path.is_file():
            raise ValueError(f"正文图片文件不存在：{image.original_name}")
        parts.append(MailInlineImagePart(
            cid=cid,
            filename=image.original_name,
            content=path.read_bytes(),
            content_type=image.content_type,
        ))
    return rendered, parts
