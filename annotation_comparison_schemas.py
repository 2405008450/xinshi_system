"""标注项目比较组 API 数据契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


def _required_text(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label}不能为空")
    return normalized


class AnnotationComparisonGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=5000)
    project_ids: list[UUID] = Field(min_length=2, max_length=10)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required_text(value, "比较组名称")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return _required_text(value, "比较说明")

    @model_validator(mode="after")
    def validate_unique_projects(self):
        if len(self.project_ids) != len(set(self.project_ids)):
            raise ValueError("同一比较组内不能重复选择项目")
        return self


class AnnotationComparisonGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    project_ids: Optional[list[UUID]] = Field(default=None, min_length=2, max_length=10)
    expected_updated_at: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _required_text(value, "比较组名称")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _required_text(value, "比较说明")

    @model_validator(mode="after")
    def validate_unique_projects(self):
        if self.project_ids is not None and len(self.project_ids) != len(set(self.project_ids)):
            raise ValueError("同一比较组内不能重复选择项目")
        return self


class AnnotationComparisonMemberPreview(BaseModel):
    project_id: UUID
    sequence_no: int
    order_no: str
    project_name: Optional[str] = None


class AnnotationComparisonProjectResponse(AnnotationComparisonMemberPreview):
    client_short_name: Optional[str] = None
    client_full_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list)
    language_items_display: Optional[str] = None
    customer_price_summary: Optional[str] = None
    client_manager_name: Optional[str] = None
    project_manager_name: Optional[str] = None
    project_status: str
    potential_demand: Optional[str] = None


class AnnotationComparisonGroupListResponse(BaseModel):
    id: UUID
    name: str
    description: str
    created_by: Optional[UUID] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    member_count: int
    members: list[AnnotationComparisonMemberPreview] = Field(default_factory=list)


class AnnotationComparisonGroupDetailResponse(AnnotationComparisonGroupListResponse):
    projects: list[AnnotationComparisonProjectResponse] = Field(default_factory=list)
