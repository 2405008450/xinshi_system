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
EducationLevel = Literal["associate", "bachelor", "second_degree", "master", "doctor"]
HighestEducation = Literal[
    "high_school_or_below", "secondary_vocational", "associate", "bachelor",
    "master", "doctor", "other",
]
EmploymentStatus = Literal["student", "employed", "freelance", "seeking", "retired", "other"]
LanguageRole = Literal["native", "foreign", "dialect_ethnic"]
LanguageProficiency = Literal["very_familiar", "familiar", "basic", "listening_mainly", "listening_only"]
CertificateType = Literal["language", "other"]
PerformanceLevel = Literal["high", "medium", "low"]


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


class EducationExperienceInput(BaseModel):
    id: Optional[UUID] = None
    education_level: EducationLevel
    institution: Optional[str] = None
    institution_category: Optional[str] = None
    major: Optional[str] = None
    major_category: Optional[str] = None
    graduation_year: Optional[int] = Field(default=None, ge=1900, le=2200)
    minor_major: Optional[str] = None
    degree_name: Optional[str] = None
    remarks: Optional[str] = None
    sort_order: int = Field(default=0, ge=0)

    _normalize_text = field_validator(
        "institution", "institution_category", "major", "major_category",
        "minor_major", "degree_name", "remarks", mode="before",
    )(_clean_text)


class LanguageSkillInput(BaseModel):
    id: Optional[UUID] = None
    language_id: UUID
    role: LanguageRole
    priority: int = Field(default=0, ge=0, le=9)
    proficiency: Optional[LanguageProficiency] = None
    remarks: Optional[str] = None
    sort_order: int = Field(default=0, ge=0)

    _normalize_remarks = field_validator("remarks", mode="before")(_clean_text)


class CertificateInput(BaseModel):
    id: Optional[UUID] = None
    certificate_type: CertificateType
    name: str = Field(min_length=1, max_length=255)
    language_id: Optional[UUID] = None
    issuer: Optional[str] = None
    certificate_no: Optional[str] = None
    issued_on: Optional[date] = None
    material_received: bool = False
    remarks: Optional[str] = None
    sort_order: int = Field(default=0, ge=0)

    _normalize_text = field_validator(
        "name", "issuer", "certificate_no", "remarks", mode="before",
    )(_clean_text)


class ResourcePersonWrite(BaseModel):
    resource_code: Optional[str] = None
    full_name: str = Field(min_length=1, max_length=255)
    chinese_name: Optional[str] = None
    english_name: Optional[str] = None
    nickname: Optional[str] = None
    other_names: list[str] = Field(default_factory=list)
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    secondary_email: Optional[str] = None
    other_contact: Optional[str] = None
    wechat: Optional[str] = None
    whatsapp: Optional[str] = None
    skype: Optional[str] = None
    line: Optional[str] = None
    resume_path: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    birth_year_month: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    native_place: Optional[str] = None
    residence_address: Optional[str] = None
    dialects: list[str] = Field(default_factory=list)
    dialect_regions: list[str] = Field(default_factory=list)
    height: Optional[str] = None
    appearance: Optional[str] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    employment_status: Optional[EmploymentStatus] = None
    employment_detail: Optional[str] = None
    student_stage: Optional[str] = None
    enrollment_year: Optional[int] = Field(default=None, ge=1900, le=2200)
    program_duration_years: Optional[int] = Field(default=None, ge=1, le=15)
    student_grade_override: Optional[str] = None
    highest_education: Optional[HighestEducation] = None
    annotation_experience: Optional[str] = None
    interpretation_experience: Optional[str] = None
    translation_experience: Optional[str] = None
    other_experience: Optional[str] = None
    annotation_willingness: Optional[PerformanceLevel] = None
    overall_score: Optional[int] = Field(default=None, ge=1, le=10)
    overall_rating: Optional[str] = None
    cooperation_level: Optional[PerformanceLevel] = None
    cooperation_note: Optional[str] = None
    punctuality_level: Optional[PerformanceLevel] = None
    punctuality_note: Optional[str] = None
    audio_annotation_score: Optional[int] = Field(default=None, ge=1, le=10)
    audio_annotation_evaluation: Optional[str] = None
    non_audio_annotation_score: Optional[int] = Field(default=None, ge=1, le=10)
    non_audio_annotation_evaluation: Optional[str] = None
    collection_score: Optional[int] = Field(default=None, ge=1, le=10)
    collection_evaluation: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None
    status: ResourceStatus = "standby"
    capabilities: list[CapabilityInput] = Field(default_factory=list)
    written_profile: Optional[WrittenTranslationProfileInput] = None
    interpretation_profile: Optional[InterpretationProfileInput] = None
    annotation_profile: Optional[AnnotationProfileInput] = None
    annotation_language_skills: list[AnnotationLanguageSkillInput] = Field(default_factory=list)
    career_profile: Optional[CareerProfileInput] = None
    education_experiences: list[EducationExperienceInput] = Field(default_factory=list)
    language_skills: list[LanguageSkillInput] = Field(default_factory=list)
    certificates: list[CertificateInput] = Field(default_factory=list)
    allow_duplicate: bool = False

    @field_validator(
        "resource_code", "full_name", "chinese_name", "english_name", "nickname",
        "cooperation_type", "contact_info",
        "primary_phone", "secondary_phone", "primary_email", "secondary_email",
        "other_contact", "wechat", "whatsapp", "skype", "line", "resume_path", "gender",
        "native_place", "residence_address", "height", "appearance", "nationality", "ethnicity",
        "employment_detail", "student_stage", "student_grade_override", "annotation_experience",
        "interpretation_experience", "translation_experience", "other_experience", "overall_rating",
        "cooperation_note", "punctuality_note", "audio_annotation_evaluation",
        "non_audio_annotation_evaluation", "collection_evaluation", "remarks", mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        return _clean_text(value)

    @field_validator("birth_date", "birth_year_month", mode="before")
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
        skill_keys = {(item.language_id, item.role, item.priority) for item in self.language_skills}
        if len(skill_keys) != len(self.language_skills):
            raise ValueError("人才语言能力不能重复")
        if self.employment_status == "student" and self.enrollment_year and not self.program_duration_years:
            raise ValueError("填写入学年份后必须填写学制")
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


class EducationExperienceResponse(EducationExperienceInput):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class LanguageSkillResponse(LanguageSkillInput):
    id: UUID
    language_label: str
    model_config = ConfigDict(from_attributes=True)


class CertificateResponse(CertificateInput):
    id: UUID
    language_label: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TalentAttachmentResponse(BaseModel):
    id: UUID
    certificate_id: Optional[UUID] = None
    category: str
    original_name: str
    content_type: str
    file_size: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TalentProjectHistoryResponse(BaseModel):
    project_type: str
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None
    order_no: Optional[str] = None
    role: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    participation_sources: list[str] = Field(default_factory=list)
    status: Optional[str] = None
    participated_at: Optional[datetime] = None
    trial_count: int = 0
    performance_available: bool = False


class TalentProjectSituationResponse(BaseModel):
    total: int = 0
    primary: Optional[TalentProjectHistoryResponse] = None


class TalentProjectCustomFieldResponse(BaseModel):
    id: UUID
    field_label: str
    data_type: str
    sequence_no: int


class TalentAnnotationTrialPerformanceResponse(BaseModel):
    id: UUID
    round_no: int
    trial_status: str
    trial_result: Optional[str] = None
    willingness_text: Optional[str] = None
    result_note: Optional[str] = None
    custom_values: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TalentAnnotationAssignmentPerformanceResponse(BaseModel):
    id: UUID
    assignment_role: str
    assignment_status: str
    language_label: Optional[str] = None
    quality_score: Optional[str] = None
    evaluation_note: Optional[str] = None
    custom_values: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TalentAnnotationProjectPerformanceResponse(BaseModel):
    person_id: UUID
    project: TalentProjectHistoryResponse
    trial_fields: list[TalentProjectCustomFieldResponse] = Field(default_factory=list)
    assignment_fields: list[TalentProjectCustomFieldResponse] = Field(default_factory=list)
    trials: list[TalentAnnotationTrialPerformanceResponse] = Field(default_factory=list)
    assignments: list[TalentAnnotationAssignmentPerformanceResponse] = Field(default_factory=list)


class ResourcePersonListResponse(BaseModel):
    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    chinese_name: Optional[str] = None
    english_name: Optional[str] = None
    nickname: Optional[str] = None
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
    birth_year_month: Optional[str] = None
    current_age: Optional[int] = None
    employment_status: Optional[str] = None
    current_student_grade: Optional[str] = None
    highest_education: Optional[str] = None
    education_summary: Optional[str] = None
    language_summary: Optional[str] = None
    native_place: Optional[str] = None
    residence_address: Optional[str] = None
    dialects: list[str] = Field(default_factory=list)
    dialect_regions: list[str] = Field(default_factory=list)
    nationality: Optional[str] = None
    annotation_willingness: Optional[PerformanceLevel] = None
    overall_score: Optional[int] = None
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    contact_restricted: bool = False
    project_situation: TalentProjectSituationResponse = Field(default_factory=TalentProjectSituationResponse)
    model_config = ConfigDict(from_attributes=True)


class TalentOptionResponse(BaseModel):
    """项目人员选择器仅返回识别所需字段，不泄露联系方式等敏感信息。"""

    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    cooperation_type: Optional[str] = None
    status: ResourceStatus
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    annotation_language_skills: list[AnnotationLanguageSkillResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ResourcePersonDetailResponse(ResourcePersonListResponse):
    other_names: list[str] = Field(default_factory=list)
    contact_info: Optional[str] = None
    secondary_phone: Optional[str] = None
    secondary_email: Optional[str] = None
    other_contact: Optional[str] = None
    wechat: Optional[str] = None
    whatsapp: Optional[str] = None
    skype: Optional[str] = None
    line: Optional[str] = None
    resume_path: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    appearance: Optional[str] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    employment_detail: Optional[str] = None
    student_stage: Optional[str] = None
    enrollment_year: Optional[int] = None
    program_duration_years: Optional[int] = None
    student_grade_override: Optional[str] = None
    annotation_experience: Optional[str] = None
    interpretation_experience: Optional[str] = None
    translation_experience: Optional[str] = None
    other_experience: Optional[str] = None
    cooperation_level: Optional[PerformanceLevel] = None
    cooperation_note: Optional[str] = None
    punctuality_level: Optional[PerformanceLevel] = None
    punctuality_note: Optional[str] = None
    audio_annotation_score: Optional[int] = None
    audio_annotation_evaluation: Optional[str] = None
    non_audio_annotation_score: Optional[int] = None
    non_audio_annotation_evaluation: Optional[str] = None
    collection_score: Optional[int] = None
    collection_evaluation: Optional[str] = None
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None
    capabilities: list[CapabilityResponse] = Field(default_factory=list)
    written_profile: Optional[WrittenTranslationProfileResponse] = None
    interpretation_profile: Optional[InterpretationProfileResponse] = None
    annotation_profile: Optional[AnnotationProfileResponse] = None
    annotation_language_skills: list[AnnotationLanguageSkillResponse] = Field(default_factory=list)
    career_profile: Optional[CareerProfileResponse] = None
    education_experiences: list[EducationExperienceResponse] = Field(default_factory=list)
    language_skills: list[LanguageSkillResponse] = Field(default_factory=list)
    certificates: list[CertificateResponse] = Field(default_factory=list)
    attachments: list[TalentAttachmentResponse] = Field(default_factory=list)


class DuplicateCandidateResponse(BaseModel):
    id: UUID
    resource_code: Optional[str] = None
    full_name: str
    primary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    match_fields: list[str] = Field(default_factory=list)
    contact_restricted: bool = False


class DuplicateCheckResponse(BaseModel):
    duplicates: list[DuplicateCandidateResponse] = Field(default_factory=list)
