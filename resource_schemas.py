"""统一人才资源库接口模型。"""

from __future__ import annotations

from datetime import datetime
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


class AnnotationProfileInput(BaseModel):
    task_types: list[str] = Field(default_factory=list)
    data_modalities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domain_skills: list = Field(default_factory=list)
    quality_score: Optional[str] = None
    daily_capacity: Optional[int] = Field(default=None, ge=0)
    remarks: Optional[str] = None

    _normalize_text = field_validator("quality_score", "remarks", mode="before")(_clean_text)


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
    career_profile: Optional[CareerProfileInput] = None
    allow_duplicate: bool = False

    @field_validator(
        "resource_code", "full_name", "cooperation_type", "contact_info",
        "primary_phone", "secondary_phone", "primary_email", "secondary_email",
        "other_contact", "resume_path", "gender", "height", "appearance",
        "nationality", "ethnicity", "overall_rating", "remarks", mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        return _clean_text(value)

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
        return self


class ResourcePersonCreate(ResourcePersonWrite):
    pass


class ResourcePersonUpdate(ResourcePersonWrite):
    pass


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
    industries: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    years_experience: Optional[Decimal] = None
    gender: Optional[str] = None
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
