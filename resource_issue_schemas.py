"""开拓问题写入白名单；来源与人员快照只由后端生成。"""
from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IssueCategory = Literal["arrangement", "execution", "problem", "idea"]
IssueTaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]


class IssueWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=20000)
    remarks: str = Field(default="", max_length=10000)


class IssueCreate(IssueWrite):
    source_message_id: UUID | None = None
    client_request_id: UUID | None = None
    topic_id: UUID | None = None
    category: IssueCategory

    @model_validator(mode='after')
    def manual_request_id(self):
        if not self.source_message_id and not self.client_request_id:
            raise ValueError('手工新增必须提供请求标识')
        return self


class IssueUpdate(IssueWrite):
    revision: int = Field(ge=1)
    topic_id: UUID | None = None


class IssueTaskWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # 所有任务写入以主体修订号为条件，避免任务分配与主体编辑相互覆盖。
    revision: int = Field(ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    executor_id: UUID | None = None
    planned_date: date | None = None
    status: IssueTaskStatus | None = None
    progress: str | None = Field(default=None, max_length=10000)
    completed_date: date | None = None
    remarks: str | None = Field(default=None, max_length=10000)

    @field_validator("content", "status", "progress", "remarks", "executor_id")
    @classmethod
    def no_explicit_null(cls, value):
        if value is None:
            raise ValueError("字段不能为 null")
        return value
