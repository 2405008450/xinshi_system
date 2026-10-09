"""公司管理正文的受控图片节点校验。"""
import re
from uuid import UUID

from annotation_notice_schemas import AnnotationNoticeSectionUpdate, validate_tiptap_document
from pydantic import field_validator

IMAGE_PATH_PATTERN = re.compile(
    r"/api/company-management/sections/([0-9a-f-]{36})/images/([0-9a-f-]{36})"
)


def parse_image_path(value: str) -> tuple[UUID, UUID]:
    match = IMAGE_PATH_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError("正文图片地址无效，请重新粘贴图片")
    try:
        return UUID(match[1]), UUID(match[2])
    except ValueError as exc:
        raise ValueError("正文图片地址无效") from exc


def validate_image_node(node: dict) -> None:
    attrs = node.get("attrs")
    if not isinstance(attrs, dict) or set(attrs) - {"src", "alt", "title", "width", "height"}:
        raise ValueError("正文图片属性无效")
    parse_image_path(attrs.get("src"))
    for key in ("alt", "title"):
        value = attrs.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > 255):
            raise ValueError("正文图片说明不能超过255字符")
    # 尺寸由响应式样式决定，不接收来源文档中的任意布局属性。
    if attrs.get("width") is not None or attrs.get("height") is not None or node.get("content") or node.get("marks"):
        raise ValueError("正文图片包含不支持的属性")


class CompanyManagementSectionUpdate(AnnotationNoticeSectionUpdate):
    @field_validator("content_json")
    @classmethod
    def validate_content(cls, value: dict) -> dict:
        return validate_tiptap_document(value, image_validator=validate_image_node)


def document_images(document: dict | None) -> set[tuple[UUID, UUID]]:
    result = set()

    def visit(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "image":
            result.add(parse_image_path(node.get("attrs", {}).get("src")))
        for child in node.get("content", []):
            visit(child)

    visit(document)
    return result
