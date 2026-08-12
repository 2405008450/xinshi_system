"""招聘项目接口数据结构。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PROJECT_STATUSES = {
    "pending_setup": "新建待立项",
    "sourcing": "立项启动（寻访阶段）",
    "recommending": "简历推荐中",
    "interviewing": "面试进行中",
    "offer_negotiation": "Offer谈判阶段",
    "pending_onboard": "候选人待入职",
    "probation": "已入职保用期",
    "closed": "项目结案",
}

CANDIDATE_STAGES = {
    "screening": "待筛选",
    "recommended": "已推荐",
    "interviewing": "面试中",
    "offer": "Offer阶段",
    "pending_onboard": "待入职",
    "onboarded": "已入职",
    "rejected": "已淘汰",
}


class RecruitmentLanguageDirectionInput(BaseModel):
    direction_type: Literal["single", "translation"] = "single"
    source_language_id: UUID
    target_language_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.direction_type == "translation" and not self.target_language_id:
            raise ValueError("翻译方向必须选择目标语种")
        if self.target_language_id and self.target_language_id == self.source_language_id:
            raise ValueError("源语种与目标语种不能相同")
        return self


class RecruitmentLanguageDirectionResponse(RecruitmentLanguageDirectionInput):
    id: UUID
    source_language_label: str
    target_language_label: Optional[str] = None
    label: str
    model_config = ConfigDict(from_attributes=True)


class RecruitmentProjectBase(BaseModel):
    project_name: Optional[str] = Field(default=None, max_length=500)
    job_description: Optional[str] = None
    position_title: Optional[str] = Field(default=None, max_length=255)
    headcount_min: Optional[int] = Field(default=None, ge=0)
    headcount_max: Optional[int] = Field(default=None, ge=0)
    project_status: str = "pending_setup"
    consultation_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    contact_name: Optional[str] = Field(default=None, max_length=255)
    customer_order_no: Optional[str] = Field(default=None, max_length=150)
    client_manager_id: Optional[UUID] = None
    target_onboard_type: Literal["date", "anytime"] = "date"
    target_onboard_date: Optional[date] = None
    employment_start: Optional[date] = None
    employment_end: Optional[date] = None
    work_location: Optional[str] = Field(default=None, max_length=500)
    service_fee_type: Optional[Literal["fixed", "annual_salary_rate", "other"]] = None
    service_fee_currency: Optional[str] = Field(default="CNY", max_length=10)
    service_fee_amount: Optional[Decimal] = Field(default=None, ge=0)
    service_fee_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    service_fee_note: Optional[str] = None
    customer_consultation_time: Optional[datetime] = None
    customer_confirmation_time: Optional[datetime] = None
    project_path: Optional[str] = None
    quotation_path: Optional[str] = None
    contract_path: Optional[str] = None
    remarks: Optional[str] = None
    email_subject_preview: Optional[str] = None
    social_post_request: Optional[str] = None
    resource_request: Optional[str] = None
    language_directions: list[RecruitmentLanguageDirectionInput] = Field(default_factory=list)

    @field_validator("project_status")
    @classmethod
    def validate_status(cls, value):
        if value not in PROJECT_STATUSES:
            raise ValueError("不支持的招聘项目状态")
        return value

    @field_validator(
        "project_name", "job_description", "position_title", "contact_name", "customer_order_no",
        "work_location", "service_fee_currency", "service_fee_note", "project_path", "quotation_path",
        "contract_path", "remarks", "email_subject_preview", "social_post_request", "resource_request",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_ranges_and_fee(self):
        if self.headcount_min is not None and self.headcount_max is not None and self.headcount_max < self.headcount_min:
            raise ValueError("招聘人数上限不能小于下限")
        if self.employment_start and self.employment_end and self.employment_end < self.employment_start:
            raise ValueError("拟履职结束日期不能早于开始日期")
        if self.target_onboard_type == "anytime":
            self.target_onboard_date = None
        elif self.target_onboard_date is None:
            # 新建咨询自动建项时允许暂缺；前端保存时也可先形成待完善项目。
            pass
        if self.service_fee_type == "fixed" and self.service_fee_amount is None:
            raise ValueError("固定金额服务费必须填写金额")
        if self.service_fee_type == "annual_salary_rate" and self.service_fee_rate is None:
            raise ValueError("年薪比例服务费必须填写比例")
        return self


class RecruitmentProjectCreate(RecruitmentProjectBase):
    pass


class RecruitmentProjectUpdate(RecruitmentProjectBase):
    pass


class RecruitmentProjectResponse(RecruitmentProjectBase):
    id: UUID
    order_no: str
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_domain: Optional[str] = None
    client_manager_name: Optional[str] = None
    client_manager_name_snapshot: Optional[str] = None
    candidate_count: int = 0
    language_directions: list[RecruitmentLanguageDirectionResponse] = Field(default_factory=list)
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecruitmentNamePreviewRequest(BaseModel):
    employment_start: date
    employment_end: date
    work_location: str = Field(min_length=1, max_length=500)
    position_title: str = Field(min_length=1, max_length=255)
    language_directions: list[RecruitmentLanguageDirectionInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_period(self):
        if self.employment_end < self.employment_start:
            raise ValueError("拟履职结束日期不能早于开始日期")
        return self


class RecruitmentNamePreviewResponse(BaseModel):
    project_name: str


class RecruitmentProgressCreate(BaseModel):
    note: str = Field(min_length=1)
    occurred_at: Optional[datetime] = None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("进度说明不能为空")
        return value


class RecruitmentProgressResponse(BaseModel):
    id: UUID
    project_id: UUID
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    note: Optional[str] = None
    is_system: bool
    operator_id: Optional[UUID] = None
    operator_name: Optional[str] = None
    occurred_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecruitmentCandidateBase(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=255)
    contact_info: Optional[str] = Field(default=None, max_length=500)
    resume_path: Optional[str] = None
    resume_source_id: Optional[UUID] = None
    stage: str = "screening"
    recommended_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None
    offer_at: Optional[datetime] = None
    planned_onboard_date: Optional[date] = None
    actual_onboard_date: Optional[date] = None
    first_interview_date: Optional[date] = None
    first_interview_details: Optional[str] = None
    second_interview_date: Optional[date] = None
    second_interview_details: Optional[str] = None
    owner_id: Optional[UUID] = None
    next_follow_up_at: Optional[datetime] = None
    remarks: Optional[str] = None

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value):
        if value not in CANDIDATE_STAGES:
            raise ValueError("不支持的候选人阶段")
        return value

    @field_validator(
        "candidate_name", "contact_info", "resume_path", "remarks",
        "first_interview_details", "second_interview_details", mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value


class RecruitmentCandidateCreate(RecruitmentCandidateBase):
    pass


class RecruitmentCandidateUpdate(RecruitmentCandidateBase):
    pass


class RecruitmentCandidatePatch(BaseModel):
    resume_source_id: Optional[UUID] = None
    first_interview_date: Optional[date] = None
    first_interview_details: Optional[str] = None
    second_interview_date: Optional[date] = None
    second_interview_details: Optional[str] = None
    actual_onboard_date: Optional[date] = None

    @field_validator("first_interview_details", "second_interview_details", mode="before")
    @classmethod
    def normalize_details(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value


class RecruitmentCandidateCommunicationBase(BaseModel):
    communication_date: date
    details: str = Field(min_length=1)

    @field_validator("details", mode="before")
    @classmethod
    def normalize_details(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class RecruitmentCandidateCommunicationCreate(RecruitmentCandidateCommunicationBase):
    pass


class RecruitmentCandidateCommunicationUpdate(RecruitmentCandidateCommunicationBase):
    pass


class RecruitmentCandidateCommunicationResponse(RecruitmentCandidateCommunicationBase):
    id: UUID
    candidate_id: UUID
    sequence_no: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecruitmentCandidateResponse(RecruitmentCandidateBase):
    id: UUID
    project_id: UUID
    owner_name: Optional[str] = None
    resume_source_label: Optional[str] = None
    communications: list[RecruitmentCandidateCommunicationResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RecruitmentResumeSourceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class RecruitmentResumeSourceResponse(BaseModel):
    id: UUID
    label: str
    is_custom: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
