"""口译项目 API 数据契约。"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from schemas import ProjectRoleAssignmentInput, ProjectRoleAssignmentResponse


PROJECT_TYPE_LABELS = {
    "onsite": "现场口译",
    "booth": "展会摊位口译",
    "exhibition_escort": "展会陪同口译",
    "escort": "陪同口译",
    "small_business_meeting": "小型商务会议口译",
    "consecutive": "会议交传口译",
    "simultaneous": "会议同传口译",
    "online_meeting": "线上会议口译",
    "online_simultaneous": "线上同传口译",
}
PROJECT_STATUSES = {
    "initial_follow_up", "in_progress", "cancelled",
    "partially_cancelled", "ended", "settled",
}
RATING_VALUES = {
    "very_satisfied", "satisfied", "basically_satisfied",
    "dissatisfied", "very_dissatisfied",
}


def _nullable_text(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class InterpretationTimeRangeInput(BaseModel):
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.scheduled_end < self.scheduled_start:
            raise ValueError("预定结束时间不能早于预定开始时间")
        if self.actual_end is not None and self.actual_start is None:
            raise ValueError("填写实际结束时间前必须填写实际开始时间")
        if self.actual_start and self.actual_end and self.actual_end < self.actual_start:
            raise ValueError("实际结束时间不能早于实际开始时间")
        return self


class InterpretationTimeRangeResponse(InterpretationTimeRangeInput):
    id: UUID
    sequence_no: int
    model_config = ConfigDict(from_attributes=True)


class InterpretationLanguageDirectionInput(BaseModel):
    source_language_id: UUID
    target_language_id: UUID

    @model_validator(mode="after")
    def validate_distinct(self):
        if self.source_language_id == self.target_language_id:
            raise ValueError("口译方向的两个语种不能相同")
        return self


class InterpretationLanguageDirectionResponse(InterpretationLanguageDirectionInput):
    id: UUID
    sequence_no: int
    source_language_label: str
    target_language_label: str
    display: str
    model_config = ConfigDict(from_attributes=True)


class InterpretationInterpreterInput(BaseModel):
    translator_id: UUID
    customer_rating: Optional[str] = None
    evaluation_note: Optional[str] = None

    @field_validator("customer_rating")
    @classmethod
    def validate_rating(cls, value):
        value = _nullable_text(value)
        if value is not None and value not in RATING_VALUES:
            raise ValueError("不支持的客户评价")
        return value

    _normalize_note = field_validator("evaluation_note", mode="before")(_nullable_text)


class InterpretationInterpreterResponse(InterpretationInterpreterInput):
    id: UUID
    sequence_no: int
    translator_name: str
    translator_code: Optional[str] = None
    translator_gender: Optional[str] = None
    translator_height: Optional[str] = None
    translator_appearance: Optional[str] = None
    translator_interpretation_level: Optional[str] = None
    translator_languages: Optional[str] = None
    translator_translation_type: Optional[str] = None
    translator_direction: Optional[str] = None
    translator_resume_path: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class InterpretationProjectWrite(BaseModel):
    project_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list, max_length=9)
    task_description: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    contact_name: Optional[str] = None
    customer_order_no: Optional[str] = None
    project_status: str = "initial_follow_up"
    locations: list[str] = Field(default_factory=list, max_length=4)
    customer_budget: Optional[str] = None
    required_interpreter_count: Optional[int] = Field(default=None, ge=0)
    required_interpreter_gender: Optional[str] = None
    required_interpretation_level: Optional[str] = None
    interpreter_special_requirements: Optional[str] = None
    interpreter_height_requirement: Optional[str] = None
    interpreter_appearance_requirement: Optional[str] = None
    interpreter_dress_requirement: Optional[str] = None
    customer_consultation_time: Optional[datetime] = None
    customer_confirmation_time: Optional[datetime] = None
    interpretation_domain: Optional[str] = None
    interpretation_content: Optional[str] = None
    file_path: Optional[str] = None
    quotation_path: Optional[str] = None
    contract_path: Optional[str] = None
    role_assignments: list[ProjectRoleAssignmentInput] = Field(default_factory=list)
    client_rating: Optional[str] = None
    client_rating_note: Optional[str] = None
    remarks: Optional[str] = None
    email_subject_preview: Optional[str] = None
    social_post_request: Optional[str] = None
    resource_request: Optional[str] = None
    time_ranges: list[InterpretationTimeRangeInput] = Field(default_factory=list)
    language_directions: list[InterpretationLanguageDirectionInput] = Field(default_factory=list)
    interpreter_assignments: list[InterpretationInterpreterInput] = Field(default_factory=list)

    @field_validator(
        "project_name", "task_description", "client_name", "client_short_name",
        "client_code", "contact_name", "customer_order_no", "customer_budget",
        "interpretation_domain", "interpretation_content", "file_path",
        "quotation_path", "contract_path", "client_rating_note", "remarks",
        "email_subject_preview", "social_post_request", "resource_request",
        "required_interpreter_gender", "required_interpretation_level",
        "interpreter_special_requirements", "interpreter_height_requirement",
        "interpreter_appearance_requirement", "interpreter_dress_requirement",
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
            if value not in PROJECT_TYPE_LABELS:
                raise ValueError(f"不支持的项目类型：{value}")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @field_validator("locations")
    @classmethod
    def normalize_locations(cls, values):
        normalized = []
        for value in values:
            text_value = str(value or "").strip()
            if text_value and text_value not in normalized:
                normalized.append(text_value)
        return normalized

    @field_validator("project_status")
    @classmethod
    def validate_status(cls, value):
        if value not in PROJECT_STATUSES:
            raise ValueError("不支持的口译项目状态")
        return value

    @field_validator("client_rating")
    @classmethod
    def validate_client_rating(cls, value):
        value = _nullable_text(value)
        if value is not None and value not in RATING_VALUES:
            raise ValueError("不支持的客户评价")
        return value

    @field_validator("required_interpreter_gender")
    @classmethod
    def validate_required_gender(cls, value):
        value = _nullable_text(value)
        if value is not None and value not in {"男", "女", "不限"}:
            raise ValueError("译员性别要求仅支持男、女或不限")
        return value

    @field_validator("required_interpretation_level")
    @classmethod
    def validate_required_level(cls, value):
        value = _nullable_text(value)
        if value is not None and value not in {"初级", "中级", "高级"}:
            raise ValueError("口译水平要求仅支持初级、中级或高级")
        return value

    @model_validator(mode="after")
    def validate_nested_duplicates(self):
        direction_keys = []
        for item in self.language_directions:
            key = frozenset((item.source_language_id, item.target_language_id))
            if key in direction_keys:
                raise ValueError("同一双向口译方向不能重复")
            direction_keys.append(key)
        translator_ids = [item.translator_id for item in self.interpreter_assignments]
        if len(set(translator_ids)) != len(translator_ids):
            raise ValueError("同一译员不能重复安排")
        return self


class InterpretationProjectCreate(InterpretationProjectWrite):
    pass


class InterpretationProjectUpdate(InterpretationProjectWrite):
    expected_updated_at: Optional[datetime] = None


class InterpretationProjectStatusUpdate(BaseModel):
    project_status: str

    @field_validator("project_status")
    @classmethod
    def validate_status(cls, value):
        if value not in PROJECT_STATUSES:
            raise ValueError("不支持的口译项目状态")
        return value


class InterpretationProjectListResponse(BaseModel):
    id: UUID
    order_no: str
    project_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list)
    task_description: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    contact_name: Optional[str] = None
    customer_order_no: Optional[str] = None
    project_status: str
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    customer_budget: Optional[str] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    current_client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    sub_client_contact: Optional[str] = None
    language_directions_display: Optional[str] = None
    assigned_interpreters_display: Optional[str] = None
    translator_codes: Optional[str] = None
    locations: list[str] = Field(default_factory=list)
    client_full_name: Optional[str] = None
    client_domain: Optional[str] = None
    customer_consultation_time: Optional[datetime] = None
    customer_confirmation_time: Optional[datetime] = None
    interpretation_domain: Optional[str] = None
    interpretation_content: Optional[str] = None
    file_path: Optional[str] = None
    quotation_path: Optional[str] = None
    contract_path: Optional[str] = None
    client_rating: Optional[str] = None
    client_rating_note: Optional[str] = None
    remarks: Optional[str] = None
    email_subject_preview: Optional[str] = None
    social_post_request: Optional[str] = None
    resource_request: Optional[str] = None
    required_interpreter_count: Optional[int] = None
    required_interpreter_gender: Optional[str] = None
    required_interpretation_level: Optional[str] = None
    interpreter_special_requirements: Optional[str] = None
    interpreter_height_requirement: Optional[str] = None
    interpreter_appearance_requirement: Optional[str] = None
    interpreter_dress_requirement: Optional[str] = None
    time_ranges: list[InterpretationTimeRangeResponse] = Field(default_factory=list)
    interpreter_assignments: list[InterpretationInterpreterResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InterpretationProjectDetailResponse(InterpretationProjectListResponse):
    consultation_id: Optional[UUID] = None
    language_directions: list[InterpretationLanguageDirectionResponse] = Field(default_factory=list)


class InterpretationLanguageCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("语种名称不能为空")
        return normalized


class InterpretationLanguageUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_active: Optional[bool] = None

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value):
        if value is None:
            return value
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("语种名称不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_changes(self):
        if self.label is None and self.is_active is None:
            raise ValueError("至少需要修改一项语种信息")
        return self


class InterpretationLanguageResponse(BaseModel):
    id: UUID
    label: str
    is_custom: bool
    is_active: bool = True
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_by: Optional[UUID] = None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InterpretationNamePreviewRequest(BaseModel):
    project_types: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list, max_length=4)
    time_ranges: list[InterpretationTimeRangeInput] = Field(default_factory=list)
    language_directions: list[InterpretationLanguageDirectionInput] = Field(default_factory=list)

    @field_validator("project_types")
    @classmethod
    def validate_types(cls, values):
        for value in values:
            if value not in PROJECT_TYPE_LABELS:
                raise ValueError(f"不支持的项目类型：{value}")
        return list(dict.fromkeys(values))

    @field_validator("locations")
    @classmethod
    def normalize_preview_locations(cls, values):
        return list(dict.fromkeys(str(value or "").strip() for value in values if str(value or "").strip()))


class InterpretationNamePreviewResponse(BaseModel):
    project_name: str
