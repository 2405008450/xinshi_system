"""个人任务和日报 API 数据结构。"""
from datetime import date, datetime, time
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


TaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]
SourceType = Literal["project", "non_project"]


class NonProjectTaskCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=50)
    task_name: str = Field(min_length=1, max_length=255)
    assignee_id: Optional[UUID] = None
    planned_completion_at: Optional[datetime] = None
    remark: Optional[str] = Field(default=None, max_length=5000)


class NonProjectTaskUpdate(BaseModel):
    task_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    task_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    assignee_id: Optional[UUID] = None
    planned_completion_at: Optional[datetime] = None
    remark: Optional[str] = Field(default=None, max_length=5000)


class NonProjectTaskResponse(BaseModel):
    id: UUID
    task_type: str
    task_name: str
    assigner_id: UUID
    assigner_name: str
    assignee_id: UUID
    assignee_name: str
    assigned_at: datetime
    planned_completion_at: Optional[datetime] = None
    actual_completion_at: Optional[datetime] = None
    status: TaskStatus
    remark: Optional[str] = None
    recurrence_template_id: Optional[UUID] = None
    occurrence_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class WorkItemResponse(BaseModel):
    source_type: SourceType
    source_id: UUID
    task_type: str
    task_name: str
    assigner_name: Optional[str] = None
    assigner_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    planned_completion_at: Optional[datetime] = None
    actual_completion_at: Optional[datetime] = None
    status: str
    remark: Optional[str] = None
    available_actions: list[str] = Field(default_factory=list)
    workflow_instance_id: Optional[UUID] = None
    translation_project_id: Optional[UUID] = None
    sub_order_id: Optional[UUID] = None
    order_no: Optional[str] = None
    project_name: Optional[str] = None
    consultation_id: Optional[UUID] = None
    sub_project_name: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    current_stage_key: Optional[str] = None
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    assignment_type: Optional[str] = None
    difficulty: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    language_pair: Optional[str] = None
    entity_type: Optional[str] = None


class TaskStatusChange(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class WorkEntryCreate(BaseModel):
    work_date: date
    workflow_instance_id: Optional[UUID] = None
    non_project_task_id: Optional[UUID] = None
    progress_content: str = Field(min_length=1, max_length=10000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    result_content: Optional[str] = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_source(self):
        if (self.workflow_instance_id is None) == (self.non_project_task_id is None):
            raise ValueError("项目任务和非项目任务必须且只能选择一个")
        return self


class WorkEntryUpdate(BaseModel):
    work_date: Optional[date] = None
    progress_content: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    result_content: Optional[str] = Field(default=None, max_length=10000)


class WorkEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    work_date: date
    workflow_instance_id: Optional[UUID] = None
    non_project_task_id: Optional[UUID] = None
    progress_content: str
    duration_minutes: int
    result_content: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecurrenceCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=50)
    task_name: str = Field(min_length=1, max_length=255)
    assignee_id: Optional[UUID] = None
    frequency: Literal["daily", "workday", "weekly", "monthly"]
    weekdays: Optional[list[int]] = None
    month_day: Optional[int] = Field(default=None, ge=1, le=31)
    default_due_time: Optional[time] = None
    start_date: date
    end_date: Optional[date] = None
    remark: Optional[str] = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_rule(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if self.weekdays and any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("星期值必须在 0 到 6 之间")
        return self


class RecurrenceResponse(BaseModel):
    id: UUID
    task_type: str
    task_name: str
    assigner_id: UUID
    assignee_id: UUID
    frequency: str
    weekdays: Optional[list[int]] = None
    month_day: Optional[int] = None
    default_due_time: Optional[time] = None
    start_date: date
    end_date: Optional[date] = None
    remark: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DailyReportItemInput(BaseModel):
    source_type: Literal["project", "non_project", "manual"]
    source_id: Optional[UUID] = None
    task_type: str = Field(min_length=1, max_length=50)
    task_name: str = Field(min_length=1, max_length=255)
    progress_content: str = Field(min_length=1, max_length=10000)
    result_content: Optional[str] = Field(default=None, max_length=10000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    display_metadata: Optional[dict[str, Any]] = None


class DailyReportSaveRequest(BaseModel):
    supplemental_note: Optional[str] = Field(default=None, max_length=10000)
    items: Optional[list[DailyReportItemInput]] = None


class DailyReportItemResponse(DailyReportItemInput):
    id: Optional[UUID] = None
    sort_order: int = 0


class DailyReportResponse(BaseModel):
    id: Optional[UUID] = None
    user_id: UUID
    user_name: str
    report_date: date
    status: Literal["draft", "finalized"]
    supplemental_note: Optional[str] = None
    generated_at: datetime
    finalized_at: Optional[datetime] = None
    items: list[DailyReportItemResponse] = Field(default_factory=list)
