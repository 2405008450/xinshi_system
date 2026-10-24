"""双人采标写入契约；价格及进度文本不参与金额推算。"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Write(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int | None = Field(None, ge=1)


class WorkspaceWrite(Write):
    allow_multiple_groups: bool = False
    archived: bool = False
    notes: dict[str, str] = Field(default_factory=dict)


class ContactWrite(Write):
    person_id: UUID
    willingness: Literal["pending", "available", "collection_only", "annotation_only", "no_time", "declined", "this_time_declined", "no_pair", "price_low"] = "pending"
    data: dict = Field(default_factory=dict)

    @field_validator("data")
    @classmethod
    def validate_data(cls, value):
        import json
        if len(json.dumps(value, ensure_ascii=False)) > 100000:
            raise ValueError("联系资料过长")
        for key in ("sources", "channel_states", "availability", "follow_ups", "attachments"):
            if key in value and not isinstance(value[key], list):
                raise ValueError("联系资料明细必须为列表")
        if any(not isinstance(item, str) or len(item) > 1000 for item in value.get("sources", [])):
            raise ValueError("来源必须为文本")
        for entry in value.get("availability", []):
            if not isinstance(entry, dict) or entry.get("type") not in {"date", "weekday", "weekend", "exception"} or not isinstance(entry.get("time", ""), str):
                raise ValueError("请填写有效的可工作时间安排")
            if entry["type"] in {"date", "exception"}:
                from datetime import date
                date.fromisoformat(entry.get("date", ""))
        for entry in value.get("channel_states", []):
            if not isinstance(entry, dict) or entry.get("channel") not in {"small_group", "project_group", "wecom", "wechat"} or not isinstance(entry.get("target"), str) or not entry["target"].strip() or entry.get("status") not in {"正常", "已删好友", "已退群"}:
                raise ValueError("渠道状态必须填写具体公司账号或群名")
        for key in ("quote", "reason", "remarks"):
            if key in value and not isinstance(value[key], str):
                raise ValueError("报价、原因与备注必须为文本")
        if value.get("response_status", "not_contacted") not in {"not_contacted", "no_response", "responded"}:
            raise ValueError("联系回复状态无效")
        return value


class FollowUpWrite(Write):
    channel: Literal["message", "wechat_call", "phone", "other"] = "message"
    contact_date: str
    content: str = Field(min_length=1, max_length=10000)
    response_status: Literal["no_response", "responded"] = "no_response"

    @field_validator("contact_date")
    @classmethod
    def valid_date(cls, value):
        from datetime import date
        return date.fromisoformat(value).isoformat()


class GroupWrite(Write):
    request_key: UUID
    name: str = Field(min_length=1, max_length=150)
    person1_id: UUID
    person2_id: UUID
    reason: str = Field(default="", max_length=4000)
    archived: bool = False

    @model_validator(mode="after")
    def distinct(self):
        if self.person1_id == self.person2_id:
            raise ValueError("同一分组必须选择两名不同人才")
        return self


class TaskWrite(Write):
    request_key: UUID
    group_id: UUID
    name: str = Field(min_length=1, max_length=200)
    status: Literal["pending", "in_progress", "withdrawn", "completed", "inspected", "submitted", "accepted", "archived"] = "pending"
    person_ids: list[UUID] = Field(default_factory=list, max_length=100)
    data: dict[str, str] = Field(default_factory=dict)

    @field_validator("data")
    @classmethod
    def bound_text(cls, value):
        if any(len(item) > 20000 for item in value.values()):
            raise ValueError("任务文本不能超过20000字")
        return value


class TransferWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_ids: list[UUID] = Field(min_length=1, max_length=100)
    person_ids: list[UUID] = Field(min_length=1, max_length=100)


class RecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field("", max_length=20000)
    price: str = Field("", max_length=4000)
    planned_progress: str = Field("", max_length=4000)
    actual_progress: str = Field("", max_length=4000)
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    duration_adjustment_minutes: float = Field(0, allow_inf_nan=False)
    adjustment_reason: str = Field("", max_length=4000)
    trainer: str = Field("", max_length=255)
    actual_trainer: str = Field("", max_length=255)
    actual_content: str = Field("", max_length=20000)
    skipped: bool = False
    reason: str = Field("", max_length=4000)
    result: str = Field("", max_length=4000)
    client_feedback: str = Field("", max_length=20000)
    communicated: bool = False
    inserted: bool = False
    postponed: bool = False

    @field_validator("planned_start", "planned_end", "actual_start", "actual_end")
    @classmethod
    def business_time(cls, value):
        if value is None:
            return value
        from business_time import BUSINESS_TIMEZONE
        return value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)

    @model_validator(mode="after")
    def times(self):
        for start, end in [(self.planned_start, self.planned_end), (self.actual_start, self.actual_end)]:
            if start and end and end < start:
                raise ValueError("结束时间不能早于开始时间")
        if self.duration_adjustment_minutes and not self.adjustment_reason.strip():
            raise ValueError("人工调整耗时必须填写原因")
        if self.actual_start and self.actual_end and (self.actual_end - self.actual_start).total_seconds() / 60 + self.duration_adjustment_minutes < 0:
            raise ValueError("调整后的实际耗时不能为负数")
        if self.skipped and not self.reason.strip():
            raise ValueError("未进行培训必须填写原因")
        return self


class RecordWrite(Write):
    request_key: UUID
    kind: Literal["price", "training", "trial", "progress", "inspection", "repair", "performance", "account"]
    title: str = Field(min_length=1, max_length=200)
    insert_after_id: UUID | None = None
    person_ids: list[UUID] = Field(default_factory=list, max_length=100)
    data: RecordData = Field(default_factory=RecordData)
    account_ids: list[UUID] = Field(default_factory=list, max_length=100)
