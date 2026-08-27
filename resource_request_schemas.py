"""资源需求接口数据契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResourceRequestItemWrite(BaseModel):
    id: Optional[UUID] = None
    source_language_id: Optional[UUID] = None
    target_language_id: Optional[UUID] = None
    required_count: Optional[int] = Field(default=None, gt=0)
    requirement_detail: Optional[str] = None

    @model_validator(mode="after")
    def validate_languages(self):
        if self.target_language_id and not self.source_language_id:
            raise ValueError("目标语种存在时必须填写源语种")
        if self.target_language_id == self.source_language_id and self.target_language_id:
            raise ValueError("源语种与目标语种不能相同")
        return self


class ResourceRequestItemResponse(ResourceRequestItemWrite):
    id: UUID
    sequence_no: int
    model_config = ConfigDict(from_attributes=True)


class ResourceRequestWrite(BaseModel):
    source_type: str
    request_category: str
    annotation_project_id: Optional[UUID] = None
    recruitment_project_id: Optional[UUID] = None
    interpretation_project_id: Optional[UUID] = None
    translation_project_id: Optional[UUID] = None
    other_source_name: Optional[str] = Field(default=None, max_length=500)
    request_detail: str = ""
    priority: str = "medium"
    request_status: str = "submitted"
    owner_id: Optional[UUID] = None
    items: list[ResourceRequestItemWrite] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source(self):
        allowed_categories = {
            "annotation": {"annotation_trial", "annotation_formal"},
            "recruitment": {"recruitment"}, "interpretation": {"interpretation"},
            "translation": {"translation"}, "other": {"other"},
        }
        if self.source_type not in allowed_categories or self.request_category not in allowed_categories[self.source_type]:
            raise ValueError("来源类型与请求类别不一致")
        fields = {
            "annotation": self.annotation_project_id, "recruitment": self.recruitment_project_id,
            "interpretation": self.interpretation_project_id, "translation": self.translation_project_id,
        }
        if self.source_type == "other":
            if any(fields.values()) or not (self.other_source_name or "").strip():
                raise ValueError("其他来源必须填写来源名称且不能关联项目")
        elif not fields[self.source_type] or sum(value is not None for value in fields.values()) != 1:
            raise ValueError("资源请求必须且只能关联一个与来源类型一致的项目")
        if self.priority not in {"high", "medium", "low"}:
            raise ValueError("不支持的优先级")
        if self.request_status not in {"draft", "submitted", "in_progress", "fulfilled", "cancelled"}:
            raise ValueError("不支持的请求状态")
        return self


class ResourceRequestSourcePrefillResponse(BaseModel):
    """从来源项目生成资源需求时的统一预填数据。"""

    source_type: str
    request_category: str
    source_project_types: list[str] = Field(default_factory=list)
    order_no: Optional[str] = None
    project_name: str
    project_status: Optional[str] = None
    client_code: Optional[str] = None
    client_short_name: Optional[str] = None
    request_detail: str = ""
    items: list[ResourceRequestItemWrite] = Field(default_factory=list)


class ResourceRequestResponse(ResourceRequestWrite):
    id: UUID
    request_no: str
    source_project_types_snapshot: list = Field(default_factory=list)
    source_order_no_snapshot: Optional[str] = None
    source_project_name_snapshot: str
    source_status_snapshot: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    client_code_snapshot: Optional[str] = None
    client_short_name_snapshot: Optional[str] = None
    progress_percent: int
    requested_by: Optional[UUID] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    current_project_status: Optional[str] = None
    current_order_no: Optional[str] = None
    current_project_name: Optional[str] = None
    items: list[ResourceRequestItemResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ResourceProgressUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)
    progress_note: Optional[str] = None
    request_status: Optional[str] = None

    @model_validator(mode="after")
    def validate_status(self):
        if self.request_status is not None and self.request_status not in {"draft", "submitted", "in_progress", "fulfilled", "cancelled"}:
            raise ValueError("不支持的请求状态")
        return self


class ResourceProgressLogResponse(BaseModel):
    id: UUID
    request_id: UUID
    progress_percent: int
    progress_note: Optional[str] = None
    changed_by: Optional[UUID] = None
    changed_at: datetime
    model_config = ConfigDict(from_attributes=True)
