"""客户进度接口；版本值保留微秒和时区。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from annotation_progress_time import business_datetime, business_now


class CustomerProgressWrite(BaseModel):
    change_note: str = Field(min_length=1, max_length=10000)
    effective_on: datetime = Field(default_factory=business_now)

    @field_validator("change_note")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("请填写客户具体进度")
        return value

    @field_validator("effective_on")
    @classmethod
    def normalize_time(cls, value):
        return business_datetime(value)


class CustomerProgressUpdate(CustomerProgressWrite):
    expected_updated_at: datetime

    @field_validator("expected_updated_at")
    @classmethod
    def normalize_version(cls, value):
        return business_datetime(value)


class CustomerProgressDelete(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    expected_updated_at: datetime

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("请填写删除原因")
        return value

    @field_validator("expected_updated_at")
    @classmethod
    def normalize_version(cls, value):
        return business_datetime(value)


class CustomerProgressResponse(BaseModel):
    id: UUID
    project_id: UUID
    track: Literal["customer"] = "customer"
    change_note: str
    effective_on: datetime
    changed_at: datetime
    changed_by: UUID | None = None
    changed_by_name: str | None = None
    updated_at: datetime
    updated_by: UUID | None = None
    updated_by_name: str | None = None

    @field_validator("effective_on", "changed_at", "updated_at")
    @classmethod
    def normalize_response_time(cls, value):
        return business_datetime(value)
