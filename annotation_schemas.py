"""标注项目 API 数据契约。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from path_security import validate_managed_path
from schemas import ProjectRoleAssignmentInput, ProjectRoleAssignmentResponse


ANNOTATION_PROJECT_TYPE_LABELS = {
    "audio_collection": "音频采集",
    "audio_annotation": "音频标注",
    "audio_evaluation": "音频评测",
    "text_evaluation": "文本评测",
    "text_annotation": "文本标注",
    "quality_inspection": "质检",
    "listening_test": "测听",
    "slot_deduction": "扣槽",
    "generalization": "泛化",
    "translation": "翻译",
}
ANNOTATION_PROJECT_STATUSES = {
    "initial_consultation",
    "consultation_no_result",
    "resource_sourcing",
    "resource_sourcing_cancelled",
    "trial_preparation",
    "trial_in_progress",
    "trial_passed",
    "trial_failed",
    "trial_partially_passed",
    "project_in_progress",
    "sent_to_client",
    "client_feedback",
    "cancelled",
    "partially_cancelled",
}
CURRENCY_SYMBOLS = {
    "CNY": "￥",
    "USD": "$",
    "HKD": "HK$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


def _nullable_text(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def currency_symbol(code=None) -> str:
    if not code or not str(code).strip():
        return CURRENCY_SYMBOLS["CNY"]
    normalized = str(code).strip().upper()
    return CURRENCY_SYMBOLS.get(normalized, normalized)


class AnnotationLanguageItemInput(BaseModel):
    id: Optional[UUID] = None
    source_language_id: UUID
    target_language_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_distinct(self):
        if self.target_language_id == self.source_language_id:
            raise ValueError("语言方向的两个语种不能相同")
        return self

    @property
    def key(self):
        return self.source_language_id, self.target_language_id


class AnnotationLanguageItemResponse(AnnotationLanguageItemInput):
    id: UUID
    sequence_no: int
    source_language_label: str
    target_language_label: Optional[str] = None
    display: str
    model_config = ConfigDict(from_attributes=True)


class AnnotationPriceItemInput(BaseModel):
    id: Optional[UUID] = None
    project_type: Optional[str] = None
    source_language_id: Optional[UUID] = None
    target_language_id: Optional[UUID] = None
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    unit: str = Field(min_length=1, max_length=50)
    remarks: Optional[str] = None

    @field_validator("project_type", "remarks", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return _nullable_text(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        value = _nullable_text(value)
        if value is None:
            return None
        value = value.upper()
        if len(value) != 3:
            raise ValueError("报价币种必须为三位代码")
        return value

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("计价单位不能为空")
        return value

    @model_validator(mode="after")
    def validate_language_scope(self):
        if self.target_language_id is not None and self.source_language_id is None:
            raise ValueError("价格语言范围缺少源语种")
        return self

    @property
    def language_key(self):
        if self.source_language_id is None:
            return None
        return self.source_language_id, self.target_language_id


class AnnotationPriceItemResponse(AnnotationPriceItemInput):
    id: UUID
    sequence_no: int
    source_language_label: Optional[str] = None
    target_language_label: Optional[str] = None
    language_display: Optional[str] = None
    display: str
    model_config = ConfigDict(from_attributes=True)


class AnnotationAssigneeInput(BaseModel):
    id: Optional[UUID] = None
    person_id: UUID
    assignment_role: str = "annotator"
    language_item_id: Optional[UUID] = None
    audio_duration_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    audio_duration_unit: Optional[str] = None
    custom_values: dict = Field(default_factory=dict)
    assignment_status: str = "assigned"
    quality_score: Optional[str] = None
    evaluation_note: Optional[str] = None

    @field_validator("assignment_status")
    @classmethod
    def validate_status(cls, value):
        if value not in {"assigned", "in_progress", "completed", "cancelled"}:
            raise ValueError("不支持的标注人员安排状态")
        return value

    @field_validator("assignment_role")
    @classmethod
    def validate_role(cls, value):
        if value not in {"annotator", "quality_inspector"}:
            raise ValueError("不支持的正式安排角色")
        return value

    @field_validator("audio_duration_unit")
    @classmethod
    def validate_duration_unit(cls, value):
        if value is not None and value not in {"second", "minute", "hour"}:
            raise ValueError("不支持的音频时长单位")
        return value

    @field_validator("quality_score", "evaluation_note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return _nullable_text(value)


class AnnotationAssigneeRateInline(BaseModel):
    id: UUID
    amount: Decimal
    currency: Optional[str] = None
    unit: str
    remarks: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AnnotationAssigneeResponse(AnnotationAssigneeInput):
    id: UUID
    sequence_no: int
    person_name: str
    resource_code: Optional[str] = None
    rate: Optional[AnnotationAssigneeRateInline] = None
    model_config = ConfigDict(from_attributes=True)


class AnnotationProjectWrite(BaseModel):
    project_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list, max_length=10)
    task_description: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    manager_contact: Optional[str] = None
    contact_name: Optional[str] = None
    customer_order_no: Optional[str] = None
    email_subject_preview: Optional[str] = Field(default=None, max_length=1000)
    project_status: str = "initial_consultation"
    language_region: Optional[str] = None
    status_effective_on: date = Field(default_factory=date.today)
    custom_values: dict = Field(default_factory=dict)
    potential_demand: Optional[str] = None
    project_path: Optional[str] = None
    quotation_path: Optional[str] = None
    contract_path: Optional[str] = None
    task_dispatched_at: Optional[datetime] = None
    task_submitted_at: Optional[datetime] = None
    client_manager_id: Optional[UUID] = None
    customer_consultation_time: Optional[datetime] = None
    customer_confirmation_time: Optional[datetime] = None
    language_items: list[AnnotationLanguageItemInput] = Field(default_factory=list)
    price_items: list[AnnotationPriceItemInput] = Field(default_factory=list)
    assignees: list[AnnotationAssigneeInput] = Field(default_factory=list)
    role_assignments: list[ProjectRoleAssignmentInput] = Field(default_factory=list)

    @field_validator("project_path", "quotation_path", "contract_path")
    @classmethod
    def validate_network_paths(cls, value):
        return validate_managed_path(value)

    @field_validator(
        "project_name", "task_description", "client_name", "client_short_name",
        "client_code", "manager_contact", "contact_name", "customer_order_no", "email_subject_preview", "potential_demand",
        "project_path", "quotation_path", "contract_path", "language_region",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        return _nullable_text(value)

    @field_validator("project_types")
    @classmethod
    def validate_project_types(cls, values):
        normalized = []
        for value in values:
            if value not in ANNOTATION_PROJECT_TYPE_LABELS:
                raise ValueError(f"不支持的项目类型：{value}")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @field_validator("project_status")
    @classmethod
    def validate_status(cls, value):
        if value not in ANNOTATION_PROJECT_STATUSES:
            raise ValueError("不支持的标注项目状态")
        return value

    @model_validator(mode="after")
    def validate_project(self):
        if (
            self.task_dispatched_at and self.task_submitted_at
            and self.task_submitted_at < self.task_dispatched_at
        ):
            raise ValueError("任务提交时间不能早于任务派发时间")

        language_keys = [item.key for item in self.language_items]
        if len(set(language_keys)) != len(language_keys):
            raise ValueError("同一语言或语言方向不能重复")

        project_types = set(self.project_types)
        language_key_set = set(language_keys)
        for item in self.price_items:
            if item.project_type and item.project_type not in project_types:
                raise ValueError("价格明细引用了当前项目未选择的项目类型")
            if item.language_key and item.language_key not in language_key_set:
                raise ValueError("价格明细引用了当前项目未选择的语言项")
        assignee_keys = [
            (item.person_id, item.language_item_id, item.assignment_role)
            for item in self.assignees
        ]
        if len(assignee_keys) != len(set(assignee_keys)):
            raise ValueError("同一人员、语种与角色不能重复安排")
        return self


class AnnotationProjectCreate(AnnotationProjectWrite):
    pass


class AnnotationProjectUpdate(AnnotationProjectWrite):
    expected_updated_at: Optional[datetime] = None


class AnnotationProjectStatusUpdate(BaseModel):
    project_status: str
    effective_on: date = Field(default_factory=date.today)
    change_note: Optional[str] = None

    @field_validator("project_status")
    @classmethod
    def validate_status(cls, value):
        if value not in ANNOTATION_PROJECT_STATUSES:
            raise ValueError("不支持的标注项目状态")
        return value

    @field_validator("change_note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return _nullable_text(value)


class AnnotationProjectListResponse(BaseModel):
    id: UUID
    order_no: str
    project_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list)
    task_description: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    contact_name: Optional[str] = None
    customer_order_no: Optional[str] = None
    email_subject_preview: Optional[str] = None
    project_status: str
    language_region: Optional[str] = None
    status_effective_on: date
    custom_values: dict = Field(default_factory=dict)
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    language_items: list[AnnotationLanguageItemResponse] = Field(default_factory=list)
    potential_demand: Optional[str] = None
    project_path: Optional[str] = None
    quotation_path: Optional[str] = None
    contract_path: Optional[str] = None
    task_dispatched_at: Optional[datetime] = None
    task_submitted_at: Optional[datetime] = None
    client_manager_id: Optional[UUID] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    client_full_name: Optional[str] = None
    client_manager_name: Optional[str] = None
    sub_client_contact: Optional[str] = None
    language_items_display: Optional[str] = None
    customer_price_summary: Optional[str] = None
    assignee_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnnotationProjectDetailResponse(AnnotationProjectListResponse):
    consultation_id: Optional[UUID] = None
    consultation_code: Optional[str] = None
    customer_consultation_time: Optional[datetime] = None
    customer_confirmation_time: Optional[datetime] = None
    created_by_name: Optional[str] = None
    legacy_order_no: Optional[str] = None
    legacy_status: Optional[str] = None
    language_items: list[AnnotationLanguageItemResponse] = Field(default_factory=list)
    price_items: list[AnnotationPriceItemResponse] = Field(default_factory=list)
    assignees: list[AnnotationAssigneeResponse] = Field(default_factory=list)


class AnnotationNamePreviewRequest(BaseModel):
    client_short_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list)
    language_items: list[AnnotationLanguageItemInput] = Field(default_factory=list)
    name_date: Optional[date] = None

    @field_validator("client_short_name", mode="before")
    @classmethod
    def normalize_client_name(cls, value):
        return _nullable_text(value)

    @field_validator("project_types")
    @classmethod
    def validate_types(cls, values):
        for value in values:
            if value not in ANNOTATION_PROJECT_TYPE_LABELS:
                raise ValueError(f"不支持的项目类型：{value}")
        return list(dict.fromkeys(values))


class AnnotationNamePreviewResponse(BaseModel):
    project_name: str
