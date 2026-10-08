"""开拓表单及工时校验。"""
from datetime import date, time
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CleanModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ActionWrite(CleanModel):
    id: UUID
    channel: Literal["wechat", "enterprise", "group", "group_large", "communication", "project"]
    status: str = Field(min_length=1, max_length=100)
    action_date: date
    operator_id: UUID
    account_id: UUID | None = None


class FollowUpWrite(CleanModel):
    id: UUID
    content: str = Field(min_length=1, max_length=20000)


class RecordWrite(CleanModel):
    id: UUID
    revision: int = Field(default=0, ge=0)
    platform_id: UUID
    work_date: date
    owner_id: UUID
    full_name: str = Field(min_length=1, max_length=255)
    account_id: UUID | None = None
    friend_accounts: list[str] = Field(default_factory=list, max_length=100)
    phone: str = Field(default="", max_length=100)
    wechat: str = Field(default="", max_length=100)
    xiaohongshu: str = Field(default="", max_length=100)
    language_ids: list[UUID] = Field(default_factory=list, max_length=100)
    follow_up: str = Field(default="", max_length=20000)
    remarks: str = Field(default="", max_length=20000)
    actions: list[ActionWrite] = Field(default_factory=list, max_length=500)
    follow_ups: list[FollowUpWrite] = Field(default_factory=list, max_length=500)
    capabilities: list[Literal["written_translation", "interpretation", "annotation", "recruitment"]] = Field(default_factory=list)
    link_person_id: UUID | None = None
    duplicate_note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def unique_items(self):
        self.friend_accounts = list(dict.fromkeys(value.strip() for value in self.friend_accounts if value.strip()))
        if any(len(value) > 100 for value in self.friend_accounts):
            raise ValueError("每个加微账号最多100个字符")
        if any(value in {"已删微信", "已删企微"} for value in self.friend_accounts):
            raise ValueError("加微账号不能填写删除状态，请使用跟进状态")
        if len({a.id for a in self.actions}) != len(self.actions):
            raise ValueError("操作历史不能重复")
        if len({a.id for a in self.follow_ups}) != len(self.follow_ups):
            raise ValueError("文字跟进不能重复")
        if len(set(self.language_ids)) != len(self.language_ids):
            raise ValueError("语种不能重复")
        return self


class GroupActionWrite(CleanModel):
    id: UUID
    revision: int = Field(ge=1)
    channel: Literal["group", "group_large"]
    status: Literal["未处理", "已拉群", "已发码", "已进群", "已退群"]


class Period(CleanModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class WorkWrite(CleanModel):
    work_date: date
    owner_id: UUID
    revision: int = Field(default=0, ge=0)
    periods: list[Period] = Field(default_factory=list, max_length=30)
    deduction: int = Field(default=0, ge=0)
    completed: bool | None = None
    explanation: str = Field(default="", max_length=5000)

    @property
    def duration_minutes(self):
        return sum((time.fromisoformat(p.end).hour * 60 + time.fromisoformat(p.end).minute)
                   - (time.fromisoformat(p.start).hour * 60 + time.fromisoformat(p.start).minute)
                   for p in self.periods) - self.deduction

    @model_validator(mode="after")
    def validate_work(self):
        previous = None
        for p in sorted(self.periods, key=lambda item: item.start):
            start, end = time.fromisoformat(p.start), time.fromisoformat(p.end)
            if end <= start:
                raise ValueError("结束时间必须晚于开始时间")
            if previous and start < previous:
                raise ValueError("工作时间段不能重叠")
            previous = end
        if self.duration_minutes < 0:
            raise ValueError("扣减分钟不能超过工作时长")
        if self.completed is False and not self.explanation:
            raise ValueError("未完成时必须填写说明")
        return self


class OptionWrite(CleanModel):
    kind: Literal["platform", "account"]
    category: Literal["national", "local", "international", ""] = ""
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    revision: int = Field(default=0, ge=0)


class LanguageWrite(CleanModel):
    label: str = Field(min_length=1, max_length=100)
    language_type: Literal["language", "dialect"] = "language"


class ArrangementTargetWrite(CleanModel):
    kind: Literal["request", "manual", "internal"]
    request_id: UUID | None = None
    language_id: UUID | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if self.kind == "request" and (not self.request_id or not self.language_id):
            raise ValueError("需求开拓方向必须包含需求和语种")
        if self.kind == "manual" and (not self.language_id or self.request_id):
            raise ValueError("自选开拓方向必须且只能包含语种")
        if self.kind == "internal" and (self.language_id or self.request_id):
            raise ValueError("内部招聘不关联语种或需求")
        return self


class ArrangementProjectWrite(CleanModel):
    source_type: Literal["annotation", "recruitment", "interpretation", "translation"]
    project_id: UUID


class ArrangementCellWrite(CleanModel):
    platform_id: UUID
    owner_id: UUID | None = None
    targets: list[ArrangementTargetWrite] = Field(default_factory=list, max_length=100)
    projects: list[ArrangementProjectWrite] = Field(default_factory=list, max_length=100)
    remarks: str = Field(default="", max_length=20000)

    @model_validator(mode="after")
    def unique_sources(self):
        targets = [(t.kind, t.request_id, t.language_id) for t in self.targets]
        projects = [(p.source_type, p.project_id) for p in self.projects]
        if len(set(targets)) != len(targets) or len(set(projects)) != len(projects):
            raise ValueError("开拓方向和关联项目不能重复")
        return self


class ArrangementWrite(CleanModel):
    revision: int = Field(ge=0)
    cells: list[ArrangementCellWrite] = Field(default_factory=list, max_length=200)
    remarks: str | None = Field(default=None, max_length=20000)
    carried_from: date | None = None

    @model_validator(mode="after")
    def unique_platforms(self):
        if len({c.platform_id for c in self.cells}) != len(self.cells):
            raise ValueError("同一天的平台账号不能重复")
        return self


class ArrangementCompletionWrite(CleanModel):
    revision: int = Field(ge=1)
    completed: bool
