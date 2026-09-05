"""列表接口共享分页与轻量选项响应类型。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field


T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)


def resolve_page_total(
    items: list[Any], skip: int, fallback: Callable[[], int]
) -> int:
    """Read the window total attached by list queries; only recount an empty later page."""
    if items:
        first = items[0]
        value = first.get("_page_total") if isinstance(first, dict) else getattr(first, "_page_total", None)
        if value is not None:
            return int(value)
    return int(fallback()) if skip > 0 else 0


class ClientOptionResponse(BaseModel):
    id: UUID
    client_code: str
    client_name: str
    client_short_name: str


class UserOptionResponse(BaseModel):
    id: UUID
    display_name: str
    username: str
    department: str | None = None
    is_active: bool


class ProjectSourceOptionResponse(BaseModel):
    id: UUID
    order_no: str
    project_name: str | None = None
    project_status: str | None = None
    client_short_name: str | None = None
