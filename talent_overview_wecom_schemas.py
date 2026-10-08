"""企微大群写入契约；操作人和操作时间仅由后端生成。"""

from datetime import date
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class ManagementWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: str = Field(default="", max_length=10000)
    remarks: str = Field(default="", max_length=10000)


class LanguageManagementWrite(ManagementWrite):
    expected_revision: int = Field(ge=0)


class WecomGroupCreate(ManagementWrite):
    name: str = Field(min_length=1, max_length=200)
    is_built: StrictBool
    built_date: date | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("群名不能为空")
        return value.strip()

    @model_validator(mode="after")
    def check_built_date(self):
        if not self.is_built and self.built_date is not None:
            raise ValueError("未建群不能填写建群日期")
        return self


class WecomGroupWrite(WecomGroupCreate):
    expected_revision: int = Field(ge=1)


class RevisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class WecomCountWrite(RevisionWrite):
    statistics_date: date
    people_count: int = Field(strict=True, ge=0, le=2147483647)


class WecomCountVoid(RevisionWrite):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        if not value.strip():
            raise ValueError("请填写作废原因")
        return value.strip()


class WecomArchiveWrite(RevisionWrite):
    archived: StrictBool
