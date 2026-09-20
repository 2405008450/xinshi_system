"""人才联系方式访问控制与脱敏工具。"""

from __future__ import annotations

from typing import Any, Iterable, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from crud import get_user_roles_with_role_names
from permission_registry import SUPER_ROLE_NAMES


CONTACT_MASK = "******"

RESOURCE_CONTACT_FIELDS = (
    "contact_info",
    "primary_phone",
    "secondary_phone",
    "primary_email",
    "secondary_email",
    "other_contact",
    "wechat",
    "whatsapp",
    "skype",
    "line",
)

LEGACY_TRANSLATOR_CONTACT_FIELDS = (
    "contact_info",
    "phone",
    "phone2",
    "email1",
    "email2",
    "other_contact",
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def can_view_talent_contacts(db: Session, user: Any) -> bool:
    """只有系统定义的超级管理员角色可以查看人才联系方式明文。"""
    roles = set(get_user_roles_with_role_names(db, user.id))
    return not SUPER_ROLE_NAMES.isdisjoint(roles)


def has_contact_values(payload: BaseModel, fields: Iterable[str]) -> bool:
    """判断写入对象是否携带了任一非空联系方式。"""
    return any(getattr(payload, field, None) not in (None, "") for field in fields)


def preserve_contact_fields(
    payload: ModelT,
    existing: Any,
    fields: Iterable[str],
) -> ModelT:
    """用数据库现值覆盖客户端提交值，防止受限用户改写联系方式。"""
    return payload.model_copy(update={
        field: getattr(existing, field, None)
        for field in fields
    })


def serialize_with_contact_access(
    value: Any,
    schema: type[ModelT],
    fields: Iterable[str],
    *,
    contacts_visible: bool,
) -> dict[str, Any]:
    """按当前用户权限序列化对象，并在受限响应中移除联系方式明文。"""
    data = schema.model_validate(value).model_dump()
    data["contact_restricted"] = not contacts_visible
    if not contacts_visible:
        for field in fields:
            if field in data:
                data[field] = CONTACT_MASK if data[field] not in (None, "") else None
    return data


def redact_contact_mapping(
    value: dict[str, Any],
    fields: Iterable[str],
    *,
    contacts_visible: bool,
) -> dict[str, Any]:
    """脱敏普通字典，主要用于核重结果。"""
    data = dict(value)
    data["contact_restricted"] = not contacts_visible
    if not contacts_visible:
        for field in fields:
            if field in data:
                data[field] = CONTACT_MASK if data[field] not in (None, "") else None
    return data
