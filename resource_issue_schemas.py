"""开拓问题写入白名单；来源与人员快照只由后端生成。"""
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IssueCategory = Literal['arrangement','request','idea','decision','execution','problem','risk','standard']
IssueTaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]


class SummaryFields(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    specific_classification: str = Field(default='',max_length=200)
    planned_completion_at: datetime | None = None
    follower_user_ids: list[UUID] = Field(default_factory=list,max_length=2000)
    actual_progress: str = Field(default='',max_length=10000)
    notify_user_ids: list[UUID] = Field(default_factory=list,max_length=2000)
    notify_department_ids: list[UUID] = Field(default_factory=list,max_length=500)
    view_all: bool | None = None
    view_user_ids: list[UUID] = Field(default_factory=list,max_length=2000)
    view_department_ids: list[UUID] = Field(default_factory=list,max_length=500)

    @field_validator('planned_completion_at')
    @classmethod
    def explicit_timezone(cls,value):
        if value is not None:
            if value.utcoffset() is None:raise ValueError('预定完成时间必须带时区')
            from business_time import BUSINESS_TIMEZONE
            return value.astimezone(BUSINESS_TIMEZONE)
        return value


class IssueWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=20000)
    remarks: str = Field(default="", max_length=10000)
    summary: SummaryFields | None = None


class IssueProgressWrite(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    revision: int = Field(ge=1)
    actual_progress: str = Field(max_length=10000)


class IssueCreate(IssueWrite):
    source_message_id: UUID | None = None
    source_discussion_room_id: UUID | None = None
    source_discussion_message_id: int | None = Field(default=None,ge=1)
    client_request_id: UUID | None = None
    topic_id: UUID | None = None
    category: IssueCategory

    @model_validator(mode='after')
    def manual_request_id(self):
        if bool(self.source_discussion_room_id) != bool(self.source_discussion_message_id):
            raise ValueError('讨论来源必须同时提供会话与消息编号')
        if self.source_message_id and self.source_discussion_room_id:
            raise ValueError('只能指定一种聊天来源')
        if not self.source_message_id and not self.source_discussion_room_id and not self.client_request_id:
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
