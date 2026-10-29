"""个人任务和日报 API 数据结构。"""
from datetime import date, datetime, time
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas import ProjectAssignedTranslatorResponse, ProjectRoleAssignmentResponse


TaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]
SourceType = Literal["project", "non_project"]


class TranslatorExecutionEntityResponse(BaseModel):
    entity_type: Literal["project", "suborder"]
    entity_id: UUID
    order_no: str
    sub_project_name: Optional[str] = None
    status: Optional[str] = None
    needs_attention: bool = False
    assigned_translators: list[ProjectAssignedTranslatorResponse] = Field(default_factory=list)


class TranslatorExecutionResponse(BaseModel):
    attention_count: int = 0
    overdue_count: int = 0
    next_return_time: Optional[datetime] = None
    items: list[TranslatorExecutionEntityResponse] = Field(default_factory=list)


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
    project_responsibility_id: Optional[UUID] = None
    source_kind: Optional[str] = None
    project_type: Optional[str] = None
    project_type_label: Optional[str] = None
    project_id: Optional[UUID] = None
    detail_route_name: Optional[str] = None
    translation_project_id: Optional[UUID] = None
    sub_order_id: Optional[UUID] = None
    order_no: Optional[str] = None
    project_name: Optional[str] = None
    consultation_id: Optional[UUID] = None
    sub_project_name: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    current_stage_key: Optional[str] = None
    current_stage_role_code: Optional[str] = None
    current_stage_role_name: Optional[str] = None
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    group_assign_role: Optional[str] = None
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    assignment_type: Optional[str] = None
    difficulty: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    language_pair: Optional[str] = None
    entity_type: Optional[str] = None
    transfer_mode: Optional[Literal["permanent", "delegation"]] = None
    delegation_id: Optional[UUID] = None
    original_assignee_id: Optional[UUID] = None
    original_assignee_name: Optional[str] = None
    delegation_end_at: Optional[datetime] = None
    delegation_overdue: bool = False
    translator_execution: Optional[TranslatorExecutionResponse] = None


class TaskStatusChange(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class WorkEntryCreate(BaseModel):
    work_date: date
    workflow_instance_id: Optional[UUID] = None
    project_responsibility_id: Optional[UUID] = None
    non_project_task_id: Optional[UUID] = None
    progress_content: str = Field(min_length=1, max_length=10000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    result_content: Optional[str] = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_source(self):
        sources = [self.workflow_instance_id, self.project_responsibility_id, self.non_project_task_id]
        if sum(value is not None for value in sources) != 1:
            raise ValueError("项目责任、笔译工作流和非项目任务必须且只能选择一个")
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
    project_responsibility_id: Optional[UUID] = None
    non_project_task_id: Optional[UUID] = None
    progress_content: str
    duration_minutes: int
    result_content: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class DailyReportItemInput(BaseModel):
    source_type: Literal["project", "non_project", "manual", "system_event"]
    source_id: Optional[UUID] = None
    task_type: str = Field(min_length=1, max_length=50)
    task_name: str = Field(max_length=255)
    progress_content: str = Field(min_length=1, max_length=10000)
    result_content: Optional[str] = Field(default=None, max_length=10000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    display_metadata: Optional[dict[str, Any]] = None


    @model_validator(mode="after")
    def validate_report_form(self):
        import math
        metadata = self.display_metadata or {}
        from work_report_lunch import validate_item
        validate_item(metadata,self.duration_minutes,self.source_type)
        quantity = metadata.get("quantity")
        if quantity not in (None, ""):
            try:
                numeric = float(quantity)
            except (TypeError, ValueError):
                raise ValueError("工作量须为非负数字")
            if isinstance(quantity, bool) or not math.isfinite(numeric) or numeric < 0:
                raise ValueError("工作量须为非负数字")
            if not str(metadata.get("quantity_unit") or "").strip():
                raise ValueError("填写工作量后请选择单位")
            if metadata.get("quantity_unit") == "其他" and not str(metadata.get("quantity_unit_other") or "").strip():
                raise ValueError("请填写具体单位")
        if "report_types" in metadata:
            from work_report_categories import DEFAULT_CATEGORIES
            allowed = set(DEFAULT_CATEGORIES['项目工作']) | set(DEFAULT_CATEGORIES)
            types = metadata["report_types"]
            def valid_type(value):
                if not isinstance(value, str):
                    return False
                if value in allowed:
                    return True
                parent, separator, name = value.partition('::')
                return bool(separator and parent in DEFAULT_CATEGORIES and name.strip() and len(name) <= 80 and '::' not in name)
            if not isinstance(types, list) or not types or any(not valid_type(value) for value in types):
                raise ValueError("请选择有效的任务/项目类型")
            if "其他项目" in types and not str(metadata.get("custom_project_type") or "").strip():
                raise ValueError("其他项目须填写具体项目类型")
            if self.source_type != 'system_event':
                needs_identity = any(value != '非项目工作' and not value.startswith('非项目工作::') for value in types)
                if needs_identity and (not self.task_name.strip() or not str(metadata.get('order_no') or '').strip()):
                    raise ValueError('除非项目工作外，订单号和项目名称均为必填')
                if not self.progress_content.strip():
                    raise ValueError('请填写具体任务')
                if quantity in (None, '') or not str(metadata.get('quantity_unit') or '').strip() or self.duration_minutes <= 0:
                    raise ValueError('请填写工作量、单位和耗时')
        elif not self.task_name.strip():
            raise ValueError('请填写工作名称')
        return self


class DailyReportSaveRequest(BaseModel):
    supplemental_note: Optional[str] = Field(default=None, max_length=10000)
    items: Optional[list[DailyReportItemInput]] = None

    @model_validator(mode='after')
    def reject_screenshots(self):
        import json
        from work_report_lunch import validate_report
        validate_report(self.items)
        if 'screenshot://' in json.dumps(self.model_dump(mode='json'), ensure_ascii=False).lower() or 'data:image/' in json.dumps(self.model_dump(mode='json'), ensure_ascii=False).lower():
            raise ValueError('工作报告所有字段禁止粘贴截图，请填写文字或数字')
        return self


class DailyReportItemResponse(DailyReportItemInput):
    id: Optional[UUID] = None
    sort_order: int = 0

    @model_validator(mode='after')
    def validate_report_form(self):
        # 必填规则用于写入；历史草稿和系统汇总仍需正常返回以供补全。
        return self


class DailyReportResponse(BaseModel):
    amendment_used: bool = False
    can_amend: bool = False
    id: Optional[UUID] = None
    user_id: UUID
    user_name: str
    report_date: date
    status: Literal["draft", "finalized"]
    supplemental_note: Optional[str] = None
    generated_at: datetime
    finalized_at: Optional[datetime] = None
    items: list[DailyReportItemResponse] = Field(default_factory=list)
