"""团队表单契约；枚举及条件必填由服务端统一校验。"""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TeamType = Literal["small_team", "medium_large_company", "small_medium_company"]
ResourceType = Literal["annotation", "interpretation", "written_translation", "full_time", "other"]


class TeamContactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: UUID | None = None
    name: str = Field(default="", max_length=100)
    nickname: str = Field(default="", max_length=100)
    contact_info: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_identity(self):
        if not (self.name or self.nickname):
            raise ValueError("请填写对接人姓名或昵称")
        return self


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
    # 未提交时保留原联系人，兼容旧客户端保存其他团队资料。
    contacts: list[TeamContactWrite] | None = Field(default=None, max_length=3)
    contact_user_id: UUID | None = None
    contact_date: date | None = None
    follow_up_user_id: UUID | None = None
    revision: int = Field(default=0, ge=0)
    allow_duplicate: bool = False

    @field_validator("contacts")
    @classmethod
    def unique_contact_ids(cls, values):
        ids = [item.id for item in values or [] if item.id]
        if len(ids) != len(set(ids)):
            raise ValueError("对接人标识不能重复")
        return values

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

