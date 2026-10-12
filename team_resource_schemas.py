"""团队表单契约；枚举及条件必填由服务端统一校验。"""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TeamType = Literal["small_team", "medium_large_company", "small_medium_company"]
ResourceType = Literal["annotation", "interpretation", "written_translation", "full_time", "other"]


class TeamWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)
    short_name: str = Field(min_length=1, max_length=100)
    full_name: str = Field(default="", max_length=255)
    team_type: TeamType
    introduction: str = Field(default="", max_length=5000)
    resource_types: list[ResourceType] = Field(min_length=1, max_length=5)
    other_resource_description: str = Field(default="", max_length=500)
    resource_situation: str = Field(default="", max_length=5000)
    remarks: str = Field(default="", max_length=2000)
    contact_user_id: UUID | None = None
    contact_date: date | None = None
    follow_up_user_id: UUID | None = None
    revision: int = Field(default=0, ge=0)
    allow_duplicate: bool = False

    @field_validator("resource_types")
    @classmethod
    def unique_types(cls, values):
        return list(dict.fromkeys(values))

    @field_validator("other_resource_description")
    @classmethod
    def validate_other(cls, value, info):
        if "other" in info.data.get("resource_types", []):
            if not value.strip():
                raise ValueError("请填写其他资源说明")
            return value
        return ""

