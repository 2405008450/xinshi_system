"""统一人才资源库接口模型。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CapabilityType = Literal["written_translation", "interpretation", "annotation"]
ResourceStatus = Literal["active", "standby", "inactive"]
InterpretationMode = Literal["simultaneous", "consecutive"]


def _clean_text(value):
    if isinstance(value, str):
        return value.strip() or None
    return value


def _blank_to_none(value):
    """把表单空字符串转成 None，避免可选 date/Literal 被 '' 打成 422。"""
    if isinstance(value, str) and not value.strip():
        return None
    return value


class CapabilityInput(BaseModel):
    capability_type: CapabilityType
    status: ResourceStatus = "active"
    review_required: bool = False
    remarks: Optional[str] = None

    _normalize_remarks = field_validator("remarks", mode="before")(_clean_text)


class CapabilityResponse(CapabilityInput):
    id: UUID
    source: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WrittenTranslationProfileInput(BaseModel):
    languages: Optional[str] = None
    direction: Optional[str] = None
    domain_skills: list = Field(default_factory=list)
    quality_score: Optional[str] = None
    default_priority: int = Field(default=0, ge=0)
    daily_accept_count: Optional[int] = Field(default=None, ge=0)
    hourly_speed: Optional[int] = Field(default=None, ge=0)
    daily_word_capacity: Optional[int] = Field(default=None, ge=0)
    can_cloud_edit: Optional[bool] = None
    can_revision: Optional[bool] = None
    available_time_slot: Optional[str] = None
    schedule_remarks: Optional[str] = None
    availability_updated_at: Optional[datetime] = None

    _normalize_text = field_validator(
        "languages", "direction", "quality_score", "available_time_slot",
        "schedule_remarks", mode="before",
    )(_clean_text)


class InterpretationProfileInput(BaseModel):
    languages: Optional[str] = None
    direction: Optional[str] = None
    interpretation_level: Optional[Literal["初级", "中级", "高级"]] = None
    interpretation_modes: list[InterpretationMode] = Field(default_factory=list)
    domain_skills: list = Field(default_factory=list)
    quality_score: Optional[str] = None
    evaluation_summary: Optional[str] = None

    _normalize_text = field_validator(
        "languages", "direction", "quality_score", "evaluation_summary", mode="before",
    )(_clean_text)
    _normalize_level = field_validator("interpretation_level", mode="before")(_blank_to_none)


class AnnotationProfileInput(BaseModel):
    task_types: list[str] = Field(default_factory=list)
    data_modalities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domain_skills: list = Field(default_factory=list)
    quality_score: Optional[str] = None
    daily_capacity: Optional[int] = Field(default=None, ge=0)
    remarks: Optional[str] = None

    _normalize_text = field_validator("quality_score", "remarks", mode="before")(_clean_text)


class AnnotationLanguageSkillInput(BaseModel):
    source_language_id: UUID
    target_language_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_distinct_languages(self):
        if self.target_language_id == self.source_language_id:
            raise ValueError("标注语言方向的源语种和目标语种不能相同")
        return self


class CareerProfileInput(BaseModel):
    industries: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    years_experience: Optional[Decimal] = Field(default=None, ge=0)
    preferred_locations: list[str] = Field(default_factory=list)
    expected_salary: Optional[str] = None
    summary: Optional[str] = None

    _normalize_text = field_validator("expected_salary", "summary", mode="before")(_clean_text)


class ResourcePersonWrite(BaseModel):
    resource_code: Optional[str] = None
    full_name: str = Field(min_length=1, max_length=255)
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    secondary_email: Optional[str] = None
    other_contact: Optional[str] = None
    resume_path: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    native_place: Optional[str] = None
    residence_address: Optional[str] = None
    dialects: list[str] = Field(default_factory=list)
    dialect_regions: list[str] = Field(default_factory=list)
    height: Optional[str] = None
    appearance: Optional[str] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None
    status: ResourceStatus = "standby"
    capabilities: list[CapabilityInput] = Field(default_factory=list)
    written_profile: Optional[WrittenTranslationProfileInput] = None
    interpretation_profile: Optional[InterpretationProfileInput] = None
    annotation_profile: Optional[AnnotationProfileInput] = None
    annotation_language_skills: list[AnnotationLanguageSkillInput] = Field(default_factory=list)
    career_profile: Optional[CareerProfileInput] = None
    allow_duplicate: bool = False

    @field_validator(
        "resource_code", "full_name", "cooperation_type", "contact_info",
        "primary_phone", "secondary_phone", "primary_email", "secondary_email",
        "other_contact", "resume_path", "gender", "native_place", "residence_address",
        "height", "appearance",
        "nationality", "ethnicity", "overall_rating", "remarks", mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        return _clean_text(value)

    @field_validator("birth_date", mode="before")
    @classmethod
    def normalize_birth_date(cls, value):
        return _blank_to_none(value)

    @field_validator("primary_email", "secondary_email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower() if value else value

    @model_validator(mode="after")
    def validate_profiles(self):
        capability_types = [item.capability_type for item in self.capabilities]
        if len(capability_types) != len(set(capability_types)):
            raise ValueError("同一种能力不能重复添加")
        profile_map = {
            "written_translation": self.written_profile,
            "interpretation": self.interpretation_profile,
            "annotation": self.annotation_profile,
        }
        for capability_type, profile in profile_map.items():
            if profile is not None and capability_type not in capability_types:
                raise ValueError("专业档案必须启用对应能力后才能保存")
        if self.annotation_language_skills and "annotation" not in capability_types:
            raise ValueError("设置标注语言方向前必须启用标注能力")
        language_keys = {
            (item.source_language_id, item.target_language_id)
            for item in self.annotation_language_skills
        }
        if len(language_keys) != len(self.annotation_language_skills):
            raise ValueError("标注语言方向不能重复")
        return self


class ResourcePersonCreate(ResourcePersonWrite):
    @model_validator(mode="after")
    def require_annotation_language_skills(self):
        if any(item.capability_type == "annotation" for item in self.capabilities):
            if not self.annotation_language_skills:
                raise ValueError("新增标注员时必须填写标注语言方向")
        return self


class ResourcePersonUpdate(ResourcePersonWrite):
    pass


class ResourcePersonNameUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return _clean_text(value)


class ResourcePersonStatusUpdate(BaseModel):
    status: ResourceStatus


class WrittenTranslationProfileResponse(WrittenTranslationProfileInput):
    person_id: UUID
    model_config = ConfigDict(from_attributes=True)


class InterpretationProfileResponse(InterpretationProfileInput):
    person_id: UUID
    model_config = ConfigDict(from_attributes=True)


class AnnotationProfileResponse(AnnotationProfileInput):
    person_id: UUID
    model_config = ConfigDict(from_attributes=True)


class AnnotationLanguageSkillResponse(AnnotationLanguageSkillInput):
    id: UUID
    source_language_label: str
    target_language_label: Optional[str] = None
    display: str
    model_config = ConfigDict(from_attributes=True)


class CareerProfileResponse(CareerProfileInput):
    person_id: UUID
    model_config = ConfigDict(from_attributes=True)


class ResourcePersonListResponse(BaseModel):
    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    cooperation_type: Optional[str] = None
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    status: ResourceStatus
    duplicate_review_required: bool = False
    capability_types: list[str] = Field(default_factory=list)
    language_directions: list[str] = Field(default_factory=list)
    annotation_language_directions: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    years_experience: Optional[Decimal] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    native_place: Optional[str] = None
    residence_address: Optional[str] = None
    dialects: list[str] = Field(default_factory=list)
    dialect_regions: list[str] = Field(default_factory=list)
    nationality: Optional[str] = None
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TalentOptionResponse(BaseModel):
    """项目人员选择器仅返回识别所需字段，不泄露联系方式等敏感信息。"""

    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    cooperation_type: Optional[str] = None
    status: ResourceStatus
    annotation_language_skills: list[AnnotationLanguageSkillResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ResourcePersonDetailResponse(ResourcePersonListResponse):
    contact_info: Optional[str] = None
    secondary_phone: Optional[str] = None
    secondary_email: Optional[str] = None
    other_contact: Optional[str] = None
    resume_path: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    appearance: Optional[str] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None
    capabilities: list[CapabilityResponse] = Field(default_factory=list)
    written_profile: Optional[WrittenTranslationProfileResponse] = None
    interpretation_profile: Optional[InterpretationProfileResponse] = None
    annotation_profile: Optional[AnnotationProfileResponse] = None
    annotation_language_skills: list[AnnotationLanguageSkillResponse] = Field(default_factory=list)
    career_profile: Optional[CareerProfileResponse] = None


class DuplicateCandidateResponse(BaseModel):
    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    match_fields: list[str] = Field(default_factory=list)


class DuplicateCheckResponse(BaseModel):
    duplicates: list[DuplicateCandidateResponse] = Field(default_factory=list)
