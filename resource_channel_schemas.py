"""渠道资料和独立说明更新契约。"""
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from resource_development_schemas import CleanModel


class ChannelWrite(CleanModel):
    name: str = Field(min_length=1, max_length=100)
    category: Literal["national", "local", "international"]
    description: str = Field(default="", max_length=5000)
    purpose: str = Field(default="", max_length=2000)
    maintainer_ids: list[UUID] = Field(default_factory=list, max_length=500)
    user_ids: list[UUID] = Field(default_factory=list, max_length=500)
    revision: int = Field(default=0, ge=0)

    @field_validator("maintainer_ids", "user_ids")
    @classmethod
    def unique_members(cls, values):
        return list(dict.fromkeys(values))


class ChannelDescriptionWrite(CleanModel):
    description: str = Field(default="", max_length=5000)
    revision: int = Field(ge=1)
