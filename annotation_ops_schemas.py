"""标注运营接口数据契约。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from annotation_schemas import AnnotationProjectListResponse


class PlatformWrite(BaseModel):
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    origin_project_id: Optional[UUID] = None
    platform_name: Optional[str] = Field(default=None, max_length=150)
    platform_url: str = Field(min_length=1)
    login_notes: Optional[str] = None
    sequence_no: Optional[int] = Field(default=None, gt=0)
    is_active: bool = True


class PlatformResponse(PlatformWrite):
    id: UUID
    platform_url_normalized: str
    sequence_no: int
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AccountWrite(BaseModel):
    platform_id: UUID
    parent_account_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    nickname: Optional[str] = Field(default=None, max_length=255)
    login_account: Optional[str] = None
    password: Optional[str] = None
    account_status: str = "available"
    registration_status: str = "unregistered"
    account_source: str = "client_provided"
    expires_on: Optional[date] = None
    remarks: Optional[str] = None
    sequence_no: Optional[int] = Field(default=None, gt=0)
    custom_values: dict[str, Any] = Field(default_factory=dict)

    @field_validator("login_account", "password")
    @classmethod
    def normalize_optional_secret(cls, value):
        return value if value not in {""} else None

    @field_validator("account_status")
    @classmethod
    def validate_account_status(cls, value):
        if value not in {"available", "assigned", "suspended", "banned", "retired"}:
            raise ValueError("不支持的账号状态")
        return value

    @field_validator("registration_status")
    @classmethod
    def validate_registration_status(cls, value):
        if value not in {"unregistered", "registering", "registered", "registration_failed", "disabled", "not_required"}:
            raise ValueError("不支持的平台注册状态")
        return value

    @field_validator("account_source")
    @classmethod
    def validate_account_source(cls, value):
        if value not in {"client_provided", "self_registered", "annotator_owned"}:
            raise ValueError("不支持的账号来源")
        return value

class AccountResponse(BaseModel):
    id: UUID
    platform_id: UUID
    parent_account_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    owner_name: Optional[str] = None
    nickname: Optional[str] = None
    masked_login_account: Optional[str] = None
    login_account: Optional[str] = None
    password: Optional[str] = None
    account_status: str
    registration_status: str
    account_source: str
    expires_on: Optional[date] = None
    remarks: Optional[str] = None
    sequence_no: int
    custom_values: dict[str, Any] = Field(default_factory=dict)
    has_login_account: bool
    has_password: bool
    password_updated_at: Optional[datetime] = None
    platform_name: Optional[str] = None
    platform_url: str
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    current_assignment_id: Optional[UUID] = None
    person_id: Optional[UUID] = None
    person_name: Optional[str] = None
    resource_code: Optional[str] = None
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    assigned_on: Optional[date] = None
    person_gender: Optional[str] = None
    assignment_custom_values: dict[str, Any] = Field(default_factory=dict)
    language_item_ids: list[UUID] = Field(default_factory=list)
    language_labels: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AccountPersonProfileResponse(BaseModel):
    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    age: Optional[int] = None
    native_place: Optional[str] = None
    residence_address: Optional[str] = None
    dialects: list[str] = Field(default_factory=list)
    dialect_regions: list[str] = Field(default_factory=list)
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    cooperation_type: Optional[str] = None
    status: str
    annotation_task_types: list[str] = Field(default_factory=list)
    annotation_data_modalities: list[str] = Field(default_factory=list)
    annotation_tools: list[str] = Field(default_factory=list)
    annotation_quality_score: Optional[str] = None
    annotation_remarks: Optional[str] = None


class CredentialRevealResponse(BaseModel):
    login_account: str
    password: str


class CredentialRevealRequest(BaseModel):
    access_reason: Optional[str] = Field(default=None, max_length=500)


class CredentialBatchRevealRequest(BaseModel):
    account_ids: list[UUID] = Field(min_length=1, max_length=100)
    access_reason: Optional[str] = Field(default=None, max_length=500)


class CredentialBatchRevealItem(BaseModel):
    id: UUID
    login_account: Optional[str] = None
    password: Optional[str] = None


class AccountAssignmentWrite(BaseModel):
    person_id: UUID
    project_id: Optional[UUID] = None
    assigned_on: date = Field(default_factory=date.today)
    assignment_note: Optional[str] = None
    language_item_ids: list[UUID] = Field(default_factory=list)
    custom_values: dict[str, Any] = Field(default_factory=dict)


class AccountReleaseWrite(BaseModel):
    released_on: date = Field(default_factory=date.today)
    release_reason: str = "other"
    assignment_note: Optional[str] = None

    @field_validator("release_reason")
    @classmethod
    def validate_release_reason(cls, value):
        if value not in {"project_completed", "person_left", "account_banned", "reassigned", "other"}:
            raise ValueError("不支持的释放原因")
        return value


class AccountBatchRow(BaseModel):
    row_key: str = Field(min_length=1, max_length=100)
    id: Optional[UUID] = None
    account: AccountWrite
    person_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    language_item_ids: list[UUID] = Field(default_factory=list)
    assignment_custom_values: dict[str, Any] = Field(default_factory=dict)


class AccountBatchWrite(BaseModel):
    client_id: UUID
    rows: list[AccountBatchRow] = Field(min_length=1, max_length=500)


class AccountBatchResultItem(BaseModel):
    row_key: str
    success: bool
    account: Optional[AccountResponse] = None
    error: Optional[str] = None


class AccountBatchResult(BaseModel):
    results: list[AccountBatchResultItem]


class AccountAnnotatorOccupancyResponse(BaseModel):
    person_id: UUID
    account_id: UUID
    project_id: Optional[UUID] = None
    language_item_id: Optional[UUID] = None


class AccountAssignmentResponse(BaseModel):
    id: UUID
    account_id: UUID
    person_id: Optional[UUID] = None
    person_name: Optional[str] = None
    resource_code: Optional[str] = None
    person_gender: Optional[str] = None
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    assigned_on: date
    released_on: Optional[date] = None
    release_reason: Optional[str] = None
    assignment_note: Optional[str] = None
    assigned_by: Optional[UUID] = None
    language_item_ids: list[UUID] = Field(default_factory=list)
    language_labels: list[str] = Field(default_factory=list)
    custom_values: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AccountStatsResponse(BaseModel):
    platform_id: UUID
    platform_name: Optional[str] = None
    platform_url: str
    total: int
    available: int
    assigned: int
    suspended: int
    banned: int
    retired: int
    expiring_soon: int


class ReleaseAllResponse(BaseModel):
    released_count: int


class TrialWrite(BaseModel):
    project_id: UUID
    person_id: UUID
    platform_account_id: Optional[UUID] = None
    round_no: int = Field(default=1, gt=0)
    sequence_no: Optional[int] = Field(default=None, gt=0)
    willingness_text: Optional[str] = None
    trial_status: str = "pending"
    trial_result: Optional[str] = None
    result_note: Optional[str] = None
    custom_values: dict[str, Any] = Field(default_factory=dict)

    @field_validator("trial_status")
    @classmethod
    def validate_status(cls, value):
        if value not in {"pending", "in_progress", "submitted", "reviewing", "completed", "cancelled"}:
            raise ValueError("不支持的试标状态")
        return value

    @field_validator("trial_result")
    @classmethod
    def validate_result(cls, value):
        if value is not None and value not in {"passed", "failed", "partially_passed", "withdrawn"}:
            raise ValueError("不支持的试标结果")
        return value


class TrialResponse(TrialWrite):
    id: UUID
    sequence_no: int
    person_name: Optional[str] = None
    resource_code: Optional[str] = None
    project_order_no: Optional[str] = None
    project_name: Optional[str] = None
    project_status: Optional[str] = None
    client_short_name: Optional[str] = None
    platform_name: Optional[str] = None
    platform_account_nickname: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class AssigneeRateWrite(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    unit: str
    remarks: Optional[str] = None

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value):
        if value not in {"item", "second", "minute", "hour"}:
            raise ValueError("不支持的计价单位")
        return value


class AssigneeRateResponse(AssigneeRateWrite):
    id: UUID
    assignee_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnnotationWorkflowWrite(BaseModel):
    person_id: UUID
    assignment_role: str = "annotator"
    language_item_id: Optional[UUID] = None
    audio_duration_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    audio_duration_unit: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    unit: Optional[str] = None
    currency: Optional[str] = Field(default="CNY", min_length=3, max_length=3)
    custom_values: dict[str, Any] = Field(default_factory=dict)
    assignment_status: str = "assigned"
    quality_score: Optional[str] = None
    evaluation_note: Optional[str] = None

    @field_validator("assignment_role")
    @classmethod
    def validate_role(cls, value):
        if value not in {"annotator", "quality_inspector"}:
            raise ValueError("不支持的正式安排角色")
        return value

    @field_validator("assignment_status")
    @classmethod
    def validate_assignment_status(cls, value):
        if value not in {"assigned", "in_progress", "completed", "cancelled"}:
            raise ValueError("不支持的安排状态")
        return value

    @field_validator("audio_duration_unit")
    @classmethod
    def validate_audio_unit(cls, value):
        if value is not None and value not in {"second", "minute", "hour"}:
            raise ValueError("不支持的音频时长单位")
        return value

    @field_validator("unit")
    @classmethod
    def validate_workflow_rate_unit(cls, value):
        if value is not None and value not in {"item", "second", "minute", "hour"}:
            raise ValueError("不支持的计价单位")
        return value

    @model_validator(mode="after")
    def validate_workflow_pairs(self):
        if (self.audio_duration_value is None) != (self.audio_duration_unit is None):
            raise ValueError("音频长度和单位必须同时填写")
        if (self.amount is None) != (self.unit is None):
            raise ValueError("人员价格和单位必须同时填写")
        return self


class AnnotationWorkflowResponse(AnnotationWorkflowWrite):
    id: UUID
    project_id: UUID
    sequence_no: int
    resource_code: Optional[str] = None
    person_name: str
    language_display: Optional[str] = None
    project_order_no: Optional[str] = None
    project_name: Optional[str] = None
    project_status: Optional[str] = None
    client_short_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StatusHistoryResponse(BaseModel):
    id: UUID
    project_id: UUID
    from_status: Optional[str] = None
    to_status: str
    effective_on: datetime
    changed_at: datetime
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None
    change_note: Optional[str] = None
    entry_kind: str = "status"
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None


class StatusHistoryProgressUpdate(BaseModel):
    effective_on: datetime
    change_note: str = Field(min_length=1, max_length=10000)
    expected_updated_at: Optional[datetime] = None

    @field_validator("change_note")
    @classmethod
    def normalize_change_note(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请填写具体进度")
        return normalized


class StatusHistorySearchItemResponse(StatusHistoryResponse):
    project_order_no: str
    project_name: Optional[str] = None
    project_current_status: str
    client_manager_name: Optional[str] = None
    project_manager_name: Optional[str] = None
    record_type: str


class ArrangementTaskTypeWrite(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    expected_updated_at: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("请填写任务类型")
        return normalized


class ArrangementTaskTypeStateWrite(BaseModel):
    is_active: bool
    expected_updated_at: Optional[datetime] = None


class ArrangementTaskTypeResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ArrangementTaskWrite(BaseModel):
    id: Optional[UUID] = None
    project_id: UUID
    execution_date: date
    task_type_id: UUID
    assignee_id: UUID
    task_content: str = Field(min_length=1, max_length=10000)
    expected_updated_at: Optional[datetime] = None

    @field_validator("task_content")
    @classmethod
    def normalize_task_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请填写任务内容")
        return normalized


class ArrangementTaskDelete(BaseModel):
    id: UUID
    expected_updated_at: Optional[datetime] = None


class ArrangementBatchWrite(BaseModel):
    items: list[ArrangementTaskWrite] = Field(default_factory=list, max_length=1000)
    deleted_items: list[ArrangementTaskDelete] = Field(default_factory=list, max_length=1000)


class ArrangementMembershipWrite(BaseModel):
    included: bool
    membership_note: Optional[str] = Field(default=None, max_length=1000)
    expected_updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_membership_note(self):
        self.membership_note = (self.membership_note or "").strip() or None
        if self.included and not self.membership_note:
            raise ValueError("加入项目安排时请填写备注")
        return self


class ArrangementMembershipResponse(BaseModel):
    project_id: UUID
    included: bool
    membership_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ArrangementTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    execution_date: date
    task_type_id: UUID
    task_type_name: str
    assignee_id: UUID
    assignee_name: str
    task_content: str
    created_at: datetime
    updated_at: datetime


class ArrangementProjectResponse(BaseModel):
    id: UUID
    order_no: str
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    task_description: Optional[str] = None
    project_status: str
    tasks: list[ArrangementTaskResponse] = Field(default_factory=list)


class ArrangementAssigneeResponse(BaseModel):
    id: UUID
    display_name: str
    department: Optional[str] = None
    priority_group: str


class ArrangementContextResponse(BaseModel):
    projects: list[ArrangementProjectResponse]
    task_types: list[ArrangementTaskTypeResponse]
    assignees: list[ArrangementAssigneeResponse]


class ArrangementOverviewSummary(BaseModel):
    project_total: int = 0
    arranged_project_count: int = 0
    unarranged_project_count: int = 0
    task_count: int = 0
    assignee_count: int = 0


class ArrangementOverviewProjectResponse(AnnotationProjectListResponse):
    client_name: Optional[str] = None
    project_manager_id: Optional[UUID] = None
    project_manager_name: Optional[str] = None
    arrangement_scope_state: str
    arrangement_status: str
    task_count: int = 0
    assignee_names: list[str] = Field(default_factory=list)
    tasks: list[ArrangementTaskResponse] = Field(default_factory=list)


class ArrangementOverviewResponse(BaseModel):
    items: list[ArrangementOverviewProjectResponse]
    total: int = 0
    summary: ArrangementOverviewSummary
    task_types: list[ArrangementTaskTypeResponse] = Field(default_factory=list)
    assignees: list[ArrangementAssigneeResponse] = Field(default_factory=list)


class ArrangementWorkloadTaskResponse(ArrangementTaskResponse):
    order_no: str
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    project_status: str


class ArrangementWorkloadItemResponse(BaseModel):
    assignee_id: UUID
    assignee_name: str
    department: Optional[str] = None
    priority_group: str
    task_count: int = 0
    project_count: int = 0
    project_names: list[str] = Field(default_factory=list)
    tasks: list[ArrangementWorkloadTaskResponse] = Field(default_factory=list)


class ArrangementWorkloadResponse(BaseModel):
    items: list[ArrangementWorkloadItemResponse]
    total: int = 0


class CustomFieldWrite(BaseModel):
    project_id: Optional[UUID] = None
    table_code: str
    field_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    field_label: str = Field(min_length=1, max_length=150)
    data_type: str
    options: list[Any] = Field(default_factory=list)
    sequence_no: Optional[int] = Field(default=None, gt=0)
    is_required: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_definition(self):
        if self.table_code not in {"project", "account", "trial", "assignment", "account_assignment"}:
            raise ValueError("不支持的动态字段业务表")
        if self.data_type not in {"text", "number", "date", "datetime", "boolean", "single_select", "multi_select", "url", "image"}:
            raise ValueError("不支持的动态字段类型")
        if self.data_type == "image" and self.table_code != "account_assignment":
            raise ValueError("图片字段仅支持项目账号表")
        if self.data_type in {"single_select", "multi_select"} and not self.options:
            raise ValueError("选择型字段必须配置选项")
        return self


class CustomFieldResponse(CustomFieldWrite):
    id: UUID
    sequence_no: int
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CustomFieldImageResponse(BaseModel):
    id: UUID
    project_id: UUID
    field_definition_id: UUID
    original_name: str
    content_type: str
    file_size: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
