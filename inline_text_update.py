"""详情小窗单字段文本更新的公共校验。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from concurrency import assert_fresh
from path_security import validate_managed_path


class TextFieldUpdate(BaseModel):
    """一次只允许提交一个自由文本字段。"""

    field: str = Field(min_length=1, max_length=100)
    value: Optional[str] = None
    expected_updated_at: Optional[datetime] = None


class TextValueUpdate(BaseModel):
    """字段由 URL 确定时使用的单值更新结构。"""

    value: Optional[str] = None
    expected_updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class TextFieldRule:
    max_length: Optional[int] = None
    required: bool = False
    managed_path: bool = False
    empty_as_null: bool = True


def normalize_text_value(value: Optional[str], rule: TextFieldRule) -> Optional[str]:
    normalized = value.strip() if isinstance(value, str) else value
    if normalized == "" and rule.empty_as_null:
        normalized = None
    if rule.required and normalized is None:
        raise ValueError("该字段不能为空")
    if normalized is not None and rule.max_length is not None and len(normalized) > rule.max_length:
        raise ValueError(f"该字段不能超过 {rule.max_length} 个字符")
    if rule.managed_path:
        normalized = validate_managed_path(normalized)
    return normalized


def apply_text_field_update(row, payload: TextFieldUpdate, rules: dict[str, TextFieldRule]) -> bool:
    """校验白名单并修改 ORM 行；提交事务由调用方负责。"""

    rule = rules.get(payload.field)
    if rule is None:
        raise ValueError("该字段不支持快捷编辑")
    assert_fresh(row, payload.expected_updated_at)
    value = normalize_text_value(payload.value, rule)
    if getattr(row, payload.field) == value:
        return False
    setattr(row, payload.field, value)
    row.updated_at = datetime.now()
    return True
