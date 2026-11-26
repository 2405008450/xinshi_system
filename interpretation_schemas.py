"""口译项目 API 数据契约。"""

from annotation_progress_time import business_now, project_progress_datetime
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from path_security import validate_managed_path
from language_catalog import normalize_language_label
from schemas import ProjectRoleAssignmentInput, ProjectRoleAssignmentResponse
from interpretation_finance_schemas import InterpretationProjectFinanceDraft


PROJECT_TYPE_LABELS = {
    "onsite": "现场口译",
    "booth": "展会摊位口译",
    "exhibition_escort": "展会陪同口译",
    "escort": "陪同口译",
    "tourism_escort": "旅游陪同口译",
    "business_escort": "商务陪同口译",
    "other_escort": "其他陪同口译",
    "small_business_meeting": "小型商务会议口译",
    "small_non_business_meeting": "小型（非商务）会议口译",
    "consecutive": "会议交传口译",
    "simultaneous": "会议同传口译",
    "online_meeting": "线上会议口译",
    "online_simultaneous": "线上同传口译",
}
PROJECT_STATUSES = {
    "initial_follow_up", "deal_pending_execution", "in_progress", "cancelled",
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


class InterpretationLocationInput(BaseModel):
    country_province: str = Field(default='', max_length=200)
    city: str = Field(default='', max_length=200)
    address: str = Field(default='', max_length=2000)

    @field_validator('country_province', 'city', 'address', mode='before')
    @classmethod
    def trim_location(cls, value):
        return str(value or '').strip()

    def display_text(self):
        return ' '.join(value for value in (self.country_province, self.city, self.address) if value)


class InterpretationTimeRangeInput(BaseModel):
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    locations: Optional[list[str]] = None
    location_details: Optional[list[InterpretationLocationInput]] = None
    language_directions: Optional[list['InterpretationLanguageDirectionInput']] = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.scheduled_end < self.scheduled_start:
            raise ValueError("预定结束时间不能早于预定开始时间")
        if self.actual_end is not None and self.actual_start is None:
            raise ValueError("填写实际结束时间前必须填写实际开始时间")
        if self.actual_start and self.actual_end and self.actual_end < self.actual_start:
            raise ValueError("实际结束时间不能早于实际开始时间")
        if self.location_details is not None:
            self.location_details = [item for item in self.location_details if item.display_text()]
            self.locations = [item.display_text() for item in self.location_details]
        if self.locations is not None or self.language_directions is not None:
            self.locations = list(dict.fromkeys(str(value or '').strip() for value in (self.locations or []) if str(value or '').strip()))
            if not self.locations:raise ValueError('每个时间段请至少填写一个项目地点')
            if not self.language_directions:raise ValueError('每个时间段请至少填写一个口译方向')
            keys = [frozenset(item.language_ids) for item in self.language_directions]
            if len(set(keys)) != len(keys):raise ValueError('同一时间段内的双向口译方向不能重复')
            if any(item.required_count is None for item in self.language_directions):raise ValueError('每个时间段的口译方向都必须填写需求人数')
        return self


class InterpretationTimeRangeResponse(InterpretationTimeRangeInput):
    id: UUID
    sequence_no: int
    model_config = ConfigDict(from_attributes=True)


class InterpretationLanguageDirectionInput(BaseModel):
    source_language_id: UUID
    target_language_id: UUID
    language_ids: list[UUID] = Field(min_length=2, max_length=5)
    required_count: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_language_ids(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        language_ids = list(data.get("language_ids") or [])
        source_id = data.get("source_language_id")
        target_id = data.get("target_language_id")
        if language_ids:
            if len(language_ids) >= 2:
                if source_id and str(source_id) != str(language_ids[0]):
                    raise ValueError("口译方向的首个语种与源语种不一致")
                if target_id and str(target_id) != str(language_ids[1]):
                    raise ValueError("口译方向的第二个语种与目标语种不一致")
                data["source_language_id"] = language_ids[0]
                data["target_language_id"] = language_ids[1]
        elif source_id and target_id:
            data["language_ids"] = [source_id, target_id]
        return data

    @model_validator(mode="after")
    def validate_distinct(self):
        if len(set(self.language_ids)) != len(self.language_ids):
            raise ValueError("同一口译方向内的语种不能重复")
        return self


def schedule_summary(ranges):
    if not any(item.locations is not None or item.language_directions is not None for item in ranges):return None
    if any(item.locations is None or item.language_directions is None for item in ranges):
        raise ValueError('每个时间段都必须配置自己的项目地点和口译方向')
    locations = list(dict.fromkeys(value for item in ranges for value in item.locations))
    directions = {}
    for group in ranges:
        for item in group.language_directions:
            key = frozenset(item.language_ids)
            if key not in directions or item.required_count > directions[key].required_count:
                directions[key] = item
    return locations, list(directions.values())


class InterpretationLanguageDirectionResponse(InterpretationLanguageDirectionInput):
    id: UUID
    sequence_no: int
    source_language_label: str
    target_language_label: str
    language_labels: list[str]
    display: str
    model_config = ConfigDict(from_attributes=True)


class InterpretationInterpreterInput(BaseModel):
    client_selected: Optional[bool] = None
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
    client_selected: bool = False
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


class InterpreterRequirementsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bring_vehicle: str = Field(default='', max_length=5000)
    driving: str = Field(default='', max_length=5000)
    driving_license: str = Field(default='', max_length=5000)
    certificates: str = Field(default='', max_length=5000)
    photos: str = Field(default='', max_length=5000)
    audio: str = Field(default='', max_length=5000)
    video: str = Field(default='', max_length=5000)
    interview: str = Field(default='', max_length=5000)
    guide_licenses: str = Field(default='', max_length=5000)
    passport: str = Field(default='', max_length=5000)
    visa: str = Field(default='', max_length=5000)
    hong_kong_macau_permit: str = Field(default='', max_length=5000)

    @field_validator('*', mode='before')
    @classmethod
    def trim_requirement(cls,value):
        return str(value or '').strip()


class InterpretationProjectWrite(BaseModel):
    interpreter_requirements: Optional[InterpreterRequirementsInput] = None
    client_source: Optional[str] = Field(default=None, max_length=500)
    finance_draft: InterpretationProjectFinanceDraft | None = None
    client_manager_id: Optional[UUID] = None
    client_manager_change_reason: Optional[str] = Field(default=None, max_length=500)
    project_name: Optional[str] = None
    project_types: list[str] = Field(default_factory=list, max_length=9)
    task_description: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    current_client_manager: Optional[str] = Field(default=None, max_length=100)
    manager_contact: Optional[str] = Field(default=None, max_length=100)
    client_contact_method: Optional[str] = Field(default=None,max_length=5000)
    client_contact_description: Optional[str] = Field(default=None,max_length=5000)
    client_contact_job_title: Optional[str] = Field(default=None, max_length=100)
    client_contact_department: Optional[str] = Field(default=None, max_length=100)
    client_contact_company: Optional[str] = Field(default=None, max_length=200)
    client_contact_version: Optional[str] = Field(default=None,max_length=64)
    contact_name: Optional[str] = None
    customer_order_no: Optional[str] = None
    project_status: str = "initial_follow_up"
    locations: list[str] = Field(default_factory=list)
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

    @field_validator("file_path", "quotation_path", "contract_path")
    @classmethod
    def validate_network_paths(cls, value):
        return validate_managed_path(value)

    @field_validator(
        "project_name", "task_description", "client_name", "client_short_name",
        "client_code", "manager_contact", "contact_name", "customer_order_no", "customer_budget",
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
        grouped = schedule_summary(self.time_ranges)
        if grouped:self.locations, self.language_directions = grouped
        direction_keys = []
        for item in self.language_directions:
            key = frozenset(item.language_ids)
            if key in direction_keys:
                raise ValueError("同一双向口译方向不能重复")
            direction_keys.append(key)
        if any(item.required_count is None for item in self.language_directions):
            raise ValueError("每个口译方向都必须填写需求人数")
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
    effective_on: datetime = Field(default_factory=lambda:project_progress_datetime(business_now()))
    change_note: Optional[str] = Field(default=None, max_length=10000)
    progress_only: bool = False

    @field_validator('effective_on')
    @classmethod
    def normalize_progress_time(cls,value):return project_progress_datetime(value)

    @field_validator("project_status")
    @classmethod
    def validate_status(cls, value):
        if value not in PROJECT_STATUSES:
            raise ValueError("不支持的口译项目状态")
        return value

    @field_validator("change_note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return _nullable_text(value)

    @model_validator(mode="after")
    def validate_note(self):
        if self.progress_only and not self.change_note:
            raise ValueError("请填写具体进度")
        return self


class InterpretationProjectStatusHistoryResponse(BaseModel):
    id: UUID
    project_id: UUID
    from_status: Optional[str] = None
    to_status: str
    effective_on: datetime
    changed_at: datetime
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None
    change_note: Optional[str] = None


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
    client_manager_id: Optional[UUID] = None
    manager_contact: Optional[str] = None
    sub_client_contact: Optional[str] = None
    parent_client_short_name: Optional[str] = None
    sub_client_name: Optional[str] = None
    language_directions_display: Optional[str] = None
    language_direction_counts_complete: bool = False
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
    interpreter_requirements: InterpreterRequirementsInput = Field(default_factory=InterpreterRequirementsInput)
    client_source: Optional[str] = Field(default=None, max_length=500)
    consultation_id: Optional[UUID] = None
    language_directions: list[InterpretationLanguageDirectionResponse] = Field(default_factory=list)


class InterpretationLanguageCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=30)
    name_zh: Optional[str] = Field(default=None, max_length=100)
    name_en: Optional[str] = Field(default=None, max_length=100)
    short_name_zh: Optional[str] = Field(default=None, max_length=50)
    short_name_en: Optional[str] = Field(default=None, max_length=50)
    language_type: Literal["language", "dialect", "ethnic_language"] = "language"

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value):
        return normalize_language_label(value)


class InterpretationLanguageUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_active: Optional[bool] = None

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value):
        if value is None:
            return value
        return normalize_language_label(value)

    @model_validator(mode="after")
    def validate_changes(self):
        if self.label is None and self.is_active is None:
            raise ValueError("至少需要修改一项语种信息")
        return self


class InterpretationLanguageResponse(BaseModel):
    id: UUID
    label: str
    code: Optional[str] = None
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    short_name_zh: Optional[str] = None
    short_name_en: Optional[str] = None
    language_type: str = "language"
    talent_overview_key: Optional[str] = None
    is_custom: bool
    is_active: bool = True
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_by: Optional[UUID] = None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InterpretationNamePreviewRequest(BaseModel):
    project_types: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
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

    @model_validator(mode='after')
    def summarize_schedule(self):
        grouped = schedule_summary(self.time_ranges)
        if grouped:self.locations, self.language_directions = grouped
        return self


class InterpretationNamePreviewResponse(BaseModel):
    project_name: str
