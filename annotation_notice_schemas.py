"""标注须知接口 Schema。"""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


ALLOWED_NODE_TYPES = {
    "doc", "paragraph", "text", "heading", "bulletList", "orderedList",
    "listItem", "blockquote", "hardBreak", "horizontalRule", "codeBlock",
}
ALLOWED_MARK_TYPES = {"bold", "italic", "strike", "code", "textColor", "highlight"}
MAX_DOCUMENT_BYTES = 512 * 1024


def validate_tiptap_document(value: Any) -> dict:
    """仅允许标注须知编辑器支持的结构和格式，拒绝任意 HTML/未知节点。"""
    if not isinstance(value, dict) or value.get("type") != "doc":
        raise ValueError("须知内容格式无效")

    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("须知内容不能超过 512KB")

    def visit(node: Any) -> None:
        if not isinstance(node, dict) or node.get("type") not in ALLOWED_NODE_TYPES:
            raise ValueError("须知内容包含不支持的节点")
        if node.get("type") == "text" and not isinstance(node.get("text"), str):
            raise ValueError("须知文本格式无效")
        attrs = node.get("attrs")
        if attrs is not None:
            if node.get("type") == "heading":
                if not isinstance(attrs, dict) or attrs.get("level") not in {1, 2, 3}:
                    raise ValueError("须知标题级别无效")
            elif node.get("type") == "orderedList":
                if not isinstance(attrs, dict) or set(attrs) - {"start", "type"}:
                    raise ValueError("须知编号列表属性无效")
            elif attrs:
                raise ValueError("须知内容包含不支持的属性")
        marks = node.get("marks", [])
        if not isinstance(marks, list):
            raise ValueError("须知文字格式无效")
        for mark in marks:
            if not isinstance(mark, dict) or mark.get("type") not in ALLOWED_MARK_TYPES:
                raise ValueError("须知内容包含不支持的文字格式")
            mark_attrs = mark.get("attrs") or {}
            if mark.get("type") == "textColor":
                color = mark_attrs.get("color")
                if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                    raise ValueError("字体颜色格式无效")
            elif mark.get("type") == "highlight":
                if mark_attrs and mark_attrs != {"color": "#fff59d"}:
                    raise ValueError("高亮颜色无效")
            elif mark_attrs:
                raise ValueError("须知文字格式属性无效")
        children = node.get("content", [])
        if not isinstance(children, list):
            raise ValueError("须知内容层级无效")
        for child in children:
            visit(child)

    visit(value)
    return value


class AnnotationNoticeSectionResponse(BaseModel):
    id: UUID
    section_key: str
    title: str
    display_title: str
    parent_id: Optional[UUID] = None
    sort_order: int
    has_content: bool = True
    is_active: bool = True
    content_json: Optional[dict] = None
    updated_by: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    updated_at: Optional[datetime] = None
    structure_updated_at: Optional[datetime] = None


class AnnotationNoticeTreeNodeResponse(AnnotationNoticeSectionResponse):
    content_json: None = None
    children: list["AnnotationNoticeTreeNodeResponse"] = Field(default_factory=list)


class AnnotationNoticeSectionUpdate(BaseModel):
    content_json: dict
    expected_updated_at: Optional[datetime] = None

    @field_validator("content_json")
    @classmethod
    def validate_content(cls, value: dict) -> dict:
        return validate_tiptap_document(value)


class AnnotationNoticeSectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    parent_id: Optional[UUID] = None
    has_content: bool = True

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("栏目名称不能为空")
        return normalized


class AnnotationNoticeSectionEdit(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    has_content: bool
    expected_structure_updated_at: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("栏目名称不能为空")
        return normalized


class AnnotationNoticePlacement(BaseModel):
    id: UUID
    parent_id: Optional[UUID] = None
    sort_order: int = Field(ge=1)
    expected_structure_updated_at: Optional[datetime] = None


class AnnotationNoticeReorder(BaseModel):
    placements: list[AnnotationNoticePlacement] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        ids = [item.id for item in self.placements]
        if len(ids) != len(set(ids)):
            raise ValueError("栏目排序中存在重复记录")
        return self


class AnnotationNoticeSearchItemResponse(BaseModel):
    id: UUID
    section_key: str
    display_title: str
    parent_title: Optional[str] = None
    breadcrumb: str
    snippet: str
    matched_title: bool
    matched_content: bool


class AnnotationNoticeSearchResponse(BaseModel):
    items: list[AnnotationNoticeSearchItemResponse]
    total: int = Field(ge=0)
