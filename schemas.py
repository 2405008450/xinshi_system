from typing import Optional
from datetime import datetime, date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from path_security import validate_managed_path

from language_catalog import normalize_language_pairs
from department_utils import normalize_department
from word_count_schemas import WordCountCreateMatrix, WordCountValues
import re

_PROGRESS_PERCENT_RE = re.compile(r"^(?:100|[0-9]|[1-9][0-9])%$")


def normalize_progress_percent(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        number = int(text)
        if 0 <= number <= 100:
            return f"{number}%"
        raise ValueError("进度必须是 0% 到 100%")
    if not _PROGRESS_PERCENT_RE.fullmatch(text):
        raise ValueError("进度必须是 0% 到 100% 的百分比")
    return text


# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    roles: Optional[list[str]] = None
    permissions: Optional[list[str]] = None


class AuthSession(BaseModel):
    user_id: str
    username: str
    full_name: str
    roles: list[str]
    permissions: list[str]


class LoginRequest(BaseModel):
    username: str
    password: str
    # 仅在账号或来源 IP 已连续失败若干次时才由前端回传。
    captcha_id: Optional[str] = None
    captcha_code: Optional[str] = None


class CaptchaRequirement(BaseModel):
    required: bool


class CaptchaChallenge(BaseModel):
    captcha_id: str
    image: str
    expires_in: int


# AppUser Schemas
class AppUserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    department: Optional[str] = None

    @field_validator('email', mode='before')
    @classmethod
    def normalize_optional_email(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator('department', mode='before')
    @classmethod
    def normalize_department_name(cls, value):
        return normalize_department(value)


class AppUserCreate(AppUserBase):
    password: str


class AppUserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    department: Optional[str] = None

    @field_validator('email', mode='before')
    @classmethod
    def normalize_optional_email(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator('department', mode='before')
    @classmethod
    def normalize_department_name(cls, value):
        return normalize_department(value)


class AppUserPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class AppUserResponse(AppUserBase):
    id: UUID
    mail_profile_configured: bool = False
    mail_display_name: Optional[str] = None
    mail_signature_enabled: bool = False
    mail_account_bound: bool = False
    mail_account_verified: bool = False
    mail_account_verified_at: Optional[datetime] = None
    is_on_leave: bool = False
    leave_start: Optional[datetime] = None
    leave_end: Optional[datetime] = None
    assignment_disabled_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Role Schemas
class RoleBase(BaseModel):
    role_name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    role_name: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(RoleBase):
    id: UUID
    permissions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RolePermissionsUpdate(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class PermissionItem(BaseModel):
    code: str
    name: str


class PermissionGroup(BaseModel):
    group: str
    permissions: list[PermissionItem]


# Client Schemas
class ClientBase(BaseModel):
    client_code: Optional[str] = None
    client_name: str
    client_short_name: str
    english_name: Optional[str] = None
    english_short_name: Optional[str] = None
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    field_level1: Optional[str] = None
    field_level2: Optional[str] = None
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    client_status: Optional[str] = "pending"
    cooperation_start_date: Optional[datetime] = None
    remarks: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    english_name: Optional[str] = None
    english_short_name: Optional[str] = None
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    field_level1: Optional[str] = None
    field_level2: Optional[str] = None
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    client_status: Optional[str] = None
    cooperation_start_date: Optional[datetime] = None
    remarks: Optional[str] = None
    expected_updated_at: Optional[datetime] = None

class ClientResponse(ClientBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sub_clients: list['SubClientResponse'] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ClientContactBase(BaseModel):
    client_id: Optional[UUID] = None
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    visit_count: Optional[int] = 0
    visit_date: Optional[date] = None
    visit_type: Optional[str] = None
    client_attitude: Optional[str] = None
    description: Optional[str] = None
    follow_up_count: Optional[int] = 0
    follow_up_date: Optional[date] = None
    follow_up_status: Optional[str] = None
    remarks: Optional[str] = None


class ClientContactCreate(ClientContactBase):
    pass


class ClientContactUpdate(BaseModel):
    client_id: Optional[UUID] = None
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    visit_count: Optional[int] = None
    visit_date: Optional[date] = None
    visit_type: Optional[str] = None
    client_attitude: Optional[str] = None
    description: Optional[str] = None
    follow_up_count: Optional[int] = None
    follow_up_date: Optional[date] = None
    follow_up_status: Optional[str] = None
    remarks: Optional[str] = None


class ClientContactResponse(ClientContactBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# SubClient Schemas
class SubClientBase(BaseModel):
    sub_client_code: Optional[str] = None
    client_name: str
    client_short_name: str
    english_name: Optional[str] = None
    english_short_name: Optional[str] = None
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    field_level1: Optional[str] = None
    field_level2: Optional[str] = None
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    client_status: Optional[str] = "pending"
    cooperation_start_date: Optional[datetime] = None
    remarks: Optional[str] = None

class SubClientCreate(SubClientBase):
    parent_client_id: UUID

class SubClientUpdate(BaseModel):
    sub_client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    english_name: Optional[str] = None
    english_short_name: Optional[str] = None
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    field_level1: Optional[str] = None
    field_level2: Optional[str] = None
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    client_status: Optional[str] = None
    cooperation_start_date: Optional[datetime] = None
    remarks: Optional[str] = None
    expected_updated_at: Optional[datetime] = None

class SubClientResponse(SubClientBase):
    id: UUID
    parent_client_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Consultation Schemas
class ConsultationBase(BaseModel):
    consultation_code: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    contact_name: Optional[str] = Field(default=None, max_length=255)
    customer_order_no: Optional[str] = Field(default=None, max_length=150)
    project_name: Optional[str] = Field(default=None, max_length=500)
    project_intake: dict = Field(default_factory=dict)
    project_intake_version: int = 2
    consultation_time: Optional[datetime] = None
    consultation_method: Optional[str] = Field(default=None, max_length=50)
    consultation_method_detail: Optional[str] = Field(default=None, max_length=255)
    client_source: Optional[str] = None
    source_keyword: Optional[str] = None
    consultation_description: Optional[str] = None
    remarks: Optional[str] = None
    customer_service_id: Optional[UUID] = None
    sales_person_id: Optional[UUID] = None
    status: Optional[str] = "pending"
    consultation_type: Optional[str] = None
    handling_method: Optional[str] = None
    editor_id: Optional[UUID] = None
    follow_up_count: Optional[int] = 0
    follow_up_time: Optional[datetime] = None
    follow_up_status: Optional[str] = None
    follow_up_remarks: Optional[str] = None
    follow_up_person_id: Optional[UUID] = None

class ConsultationCreate(ConsultationBase):
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    manager_contact: Optional[str] = None

class ConsultationUpdate(BaseModel):
    consultation_code: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    contact_name: Optional[str] = Field(default=None, max_length=255)
    customer_order_no: Optional[str] = Field(default=None, max_length=150)
    project_name: Optional[str] = Field(default=None, max_length=500)
    project_intake: Optional[dict] = None
    project_intake_version: Optional[int] = None
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    manager_contact: Optional[str] = None
    consultation_time: Optional[datetime] = None
    consultation_method: Optional[str] = Field(default=None, max_length=50)
    consultation_method_detail: Optional[str] = Field(default=None, max_length=255)
    client_source: Optional[str] = None
    source_keyword: Optional[str] = None
    consultation_description: Optional[str] = None
    remarks: Optional[str] = None
    customer_service_id: Optional[UUID] = None
    sales_person_id: Optional[UUID] = None
    status: Optional[str] = None
    consultation_type: Optional[str] = None
    handling_method: Optional[str] = None
    editor_id: Optional[UUID] = None
    follow_up_count: Optional[int] = None
    follow_up_time: Optional[datetime] = None
    follow_up_status: Optional[str] = None
    follow_up_remarks: Optional[str] = None
    follow_up_person_id: Optional[UUID] = None
    expected_updated_at: Optional[datetime] = None

class ConsultationResponse(ConsultationBase):
    id: UUID
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    manager_contact: Optional[str] = None
    translation_project_id: Optional[UUID] = None
    interpretation_project_id: Optional[UUID] = None
    annotation_project_id: Optional[UUID] = None
    recruitment_project_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sub_client_code: Optional[str] = None
    sub_client_name: Optional[str] = None
    sub_client_short_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Translator Schemas
class TranslatorFieldsBase(BaseModel):
    translator_code: Optional[str] = None
    translator_name: str
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None
    translation_type: Optional[str] = None
    interpretation_level: Optional[Literal['初级', '中级', '高级']] = None
    quality_score: Optional[str] = None
    direction: Optional[str] = None
    default_priority: Optional[int] = 0
    schedule_remarks: Optional[str] = None
    languages: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    appearance: Optional[str] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    email1: Optional[str] = None
    email2: Optional[str] = None
    resume_path: Optional[str] = None
    other_contact: Optional[str] = None
    overdue_count: Optional[int] = 0
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None
    status: Optional[str] = "standby"
    available_time_slot: Optional[str] = None
    daily_accept_count: Optional[int] = None
    hourly_speed: Optional[int] = None
    daily_word_capacity: Optional[int] = None
    can_cloud_edit: Optional[bool] = None
    can_revision: Optional[bool] = None
    domain_skills: Optional[list] = []
    availability_updated_at: Optional[datetime] = None

    @field_validator('first_contact_date', 'availability_updated_at', mode='before')
    @classmethod
    def normalize_optional_datetime(cls, value):
        """兼容旧客户端将空日期字段提交为空字符串的情况。"""
        if isinstance(value, str) and not value.strip():
            return None
        return value

class TranslatorCreate(TranslatorFieldsBase):
    cloud_revision: Optional[str] = None
    daily_rate: Optional[str] = None
    pass

class TranslatorUpdate(BaseModel):
    translator_code: Optional[str] = None
    translator_name: Optional[str] = None
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None
    translation_type: Optional[str] = None
    interpretation_level: Optional[Literal['初级', '中级', '高级']] = None
    quality_score: Optional[str] = None
    cloud_revision: Optional[str] = None
    daily_rate: Optional[str] = None
    direction: Optional[str] = None
    default_priority: Optional[int] = None
    schedule_remarks: Optional[str] = None
    languages: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    appearance: Optional[str] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    email1: Optional[str] = None
    email2: Optional[str] = None
    resume_path: Optional[str] = None
    other_contact: Optional[str] = None
    overdue_count: Optional[int] = None
    overall_rating: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None
    status: Optional[str] = None
    available_time_slot: Optional[str] = None
    daily_accept_count: Optional[int] = None
    hourly_speed: Optional[int] = None
    daily_word_capacity: Optional[int] = None
    can_cloud_edit: Optional[bool] = None
    can_revision: Optional[bool] = None
    domain_skills: Optional[list] = None
    availability_updated_at: Optional[datetime] = None

    @field_validator('first_contact_date', 'availability_updated_at', mode='before')
    @classmethod
    def normalize_optional_datetime(cls, value):
        """兼容旧客户端将空日期字段提交为空字符串的情况。"""
        if isinstance(value, str) and not value.strip():
            return None
        return value

class TranslatorResponse(TranslatorFieldsBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TranslatorScheduleBase(BaseModel):
    translator_id: UUID
    schedule_date: date
    availability_status: Literal['available', 'unavailable', 'cycle_blocked'] = 'available'
    available_time_slot: Optional[str] = None
    remaining_capacity: Optional[int] = None
    source_type: Optional[str] = "manual"
    source_ref: Optional[str] = None
    last_confirmed_at: Optional[datetime] = None
    remarks: Optional[str] = None


class TranslatorScheduleCreate(TranslatorScheduleBase):
    pass


class TranslatorScheduleUpdate(BaseModel):
    availability_status: Optional[Literal['available', 'unavailable', 'cycle_blocked']] = None
    available_time_slot: Optional[str] = None
    remaining_capacity: Optional[int] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    last_confirmed_at: Optional[datetime] = None
    remarks: Optional[str] = None


class TranslatorScheduleResponse(TranslatorScheduleBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


SHIFT_CODES = {
    'early_early', 'early', 'late', 'late_late',
    'weekend_duty', 'custom', 'off', 'unassigned',
}


class EmployeeShiftValue(BaseModel):
    shift_code: str
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode='after')
    def validate_shift_value(self):
        if self.shift_code not in SHIFT_CODES:
            raise ValueError('不支持的班次编码')
        if self.shift_code == 'custom':
            if not self.start_time or not self.end_time:
                raise ValueError('自定义班次必须填写开始和结束时间')
            if self.end_time <= self.start_time:
                raise ValueError('结束时间必须晚于开始时间，暂不支持跨午夜班次')
        return self


class EmployeeShiftTemplateDay(EmployeeShiftValue):
    weekday: int = Field(ge=1, le=7)

    @model_validator(mode='after')
    def validate_weekend_duty(self):
        if self.shift_code == 'weekend_duty' and self.weekday not in (6, 7):
            raise ValueError('周末值班只能设置在周六或周日')
        return self


class EmployeeShiftTemplateUpdate(BaseModel):
    effective_from: date
    days: list[EmployeeShiftTemplateDay]

    @model_validator(mode='after')
    def validate_template(self):
        if self.effective_from.weekday() != 0:
            raise ValueError('周模板生效日期必须是周一')
        if sorted(day.weekday for day in self.days) != list(range(1, 8)):
            raise ValueError('周模板必须完整包含周一至周日且不能重复')
        return self


class EmployeeShiftOverrideItem(EmployeeShiftValue):
    user_id: UUID
    schedule_date: date
    action: Literal['set', 'clear'] = 'set'
    note: Optional[str] = None
    override_locked: bool = False

    @model_validator(mode='after')
    def validate_override(self):
        if self.action == 'set' and self.shift_code == 'weekend_duty' and self.schedule_date.weekday() < 5:
            raise ValueError('周末值班只能设置在周六或周日')
        return self


class EmployeeShiftOverrideBatchUpdate(BaseModel):
    items: list[EmployeeShiftOverrideItem]


class EmployeeShiftLockUpdate(BaseModel):
    effective_from: date
    is_locked: bool
    reason: str = Field(min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, value: str):
        normalized = value.strip()
        if not normalized:
            raise ValueError('锁定或解锁原因不能为空')
        return normalized

    @model_validator(mode='after')
    def validate_effective_week(self):
        if self.effective_from.weekday() != 0:
            raise ValueError('锁定状态生效日期必须是周一')
        return self


# Translation Project Schemas
class ProjectRoleAssignmentInput(BaseModel):
    role_code: Literal[
        'project_manager',
        'project_specialist',
        'project_assistant',
        'layout_specialist',
    ]
    assignee_id: Optional[UUID] = None


class ProjectRoleAssignmentResponse(ProjectRoleAssignmentInput):
    role_name: str
    assignee_name: Optional[str] = None
    assignment_type: Literal['direct', 'role_pool']


class TranslationProjectBase(BaseModel):
    project_name: str
    task_type: Optional[str] = None
    consultation_id: Optional[UUID] = None
    file_type_secondary: Optional[str] = None
    project_contract_type: Optional[str] = None
    project_contract_status: Optional[str] = None
    quotation_required: bool = False
    quotation_status: Optional[str] = None
    quotation_path: Optional[str] = None
    customer_requirement_professional: Optional[str] = None
    customer_requirement_special: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    manager_contact: Optional[str] = Field(default=None, max_length=100)
    customer_order_no: Optional[str] = None
    email_subject_preview: Optional[str] = None
    service_content: Optional[str] = None
    customer_reception_time: Optional[datetime] = None
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: WordCountCreateMatrix = Field(default_factory=WordCountCreateMatrix)
    project_status: Optional[str] = None
    project_manager_id: Optional[UUID] = None
    pm_confirmed_by: Optional[UUID] = None
    major_project_manager_confirmation: Optional[str] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    network_file_path: Optional[str] = None
    reference_file_path_one: Optional[str] = None

    @field_validator('language_pair')
    @classmethod
    def validate_language_pair(cls, value: Optional[str]) -> Optional[str]:
        return normalize_language_pairs(value)

    @field_validator(
        'translator_delivery_progress', 'pre_review_qc_progress', 'review1_progress',
        'review2_progress', 'post_review_qc_progress', 'layout_progress', 'consolidation_progress',
    )
    @classmethod
    def validate_progress(cls, value: Optional[str]) -> Optional[str]:
        return normalize_progress_percent(value)

class TranslationProjectCreate(TranslationProjectBase):
    created_by: Optional[UUID] = None
    role_assignments: list[ProjectRoleAssignmentInput] = Field(default_factory=list)

    @field_validator('quotation_path', 'network_file_path', 'reference_file_path_one')
    @classmethod
    def validate_network_paths(cls, value):
        return validate_managed_path(value)

class AssignedTranslatorCompletionUpdate(BaseModel):
    """笔译项目编辑页回写稿件安排中的单个译员任务完成情况。"""

    arrangement_id: UUID
    completion_remarks: Optional[str] = Field(default=None, max_length=255)


class TranslationProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    task_type: Optional[str] = None
    consultation_id: Optional[UUID] = None
    file_type_secondary: Optional[str] = None
    project_contract_type: Optional[str] = None
    project_contract_status: Optional[str] = None
    quotation_required: bool = False
    quotation_status: Optional[str] = None
    quotation_path: Optional[str] = None
    customer_requirement_professional: Optional[str] = None
    customer_requirement_special: Optional[str] = None
    client_id: Optional[UUID] = None
    sub_client_id: Optional[UUID] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    manager_contact: Optional[str] = Field(default=None, max_length=100)
    customer_order_no: Optional[str] = None
    email_subject_preview: Optional[str] = None
    service_content: Optional[str] = None
    customer_reception_time: Optional[datetime] = None
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: Optional[WordCountCreateMatrix] = None
    project_status: Optional[str] = None
    project_manager_id: Optional[UUID] = None
    pm_confirmed_by: Optional[UUID] = None
    major_project_manager_confirmation: Optional[str] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    network_file_path: Optional[str] = None
    reference_file_path_one: Optional[str] = None
    role_assignments: Optional[list[ProjectRoleAssignmentInput]] = None
    assigned_translator_completions: Optional[list[AssignedTranslatorCompletionUpdate]] = None
    expected_updated_at: Optional[datetime] = None

    @field_validator('quotation_path', 'network_file_path', 'reference_file_path_one')
    @classmethod
    def validate_network_paths(cls, value):
        return validate_managed_path(value)

    @field_validator('language_pair')
    @classmethod
    def validate_language_pair(cls, value: Optional[str]) -> Optional[str]:
        return normalize_language_pairs(value)

    @field_validator(
        'translator_delivery_progress', 'pre_review_qc_progress', 'review1_progress',
        'review2_progress', 'post_review_qc_progress', 'layout_progress', 'consolidation_progress',
    )
    @classmethod
    def validate_progress(cls, value: Optional[str]) -> Optional[str]:
        return normalize_progress_percent(value)

class ProjectAssignedTranslatorResponse(BaseModel):
    arrangement_id: UUID
    dispatch_id: Optional[UUID] = None
    translator_id: UUID
    translator_name: str
    cooperation_type: Optional[str] = None
    status: Optional[str] = None
    planned: WordCountValues = Field(default_factory=WordCountValues)
    actual: WordCountValues = Field(default_factory=WordCountValues)
    translation_scope: Optional[str] = None
    # 与稿件安排的“译员交稿全稿预定时间”共用同一数据源。
    translator_return_time: Optional[datetime] = None
    # 译员回稿后的本次任务完成情况，由稿件安排模块维护。
    completion_remarks: Optional[str] = None


# TranslationSubOrderResponse 鍓嶇疆澹版槑锛圱ranslationProjectResponse 渚濊禆瀹冿級
class TranslationSubOrderResponse(BaseModel):
    id: UUID
    parent_project_id: UUID
    sub_order_no: str
    sub_project_name: Optional[str] = None
    # 鏂囦欢/璇█/瀛楁暟
    file_type_secondary: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: WordCountCreateMatrix = Field(default_factory=WordCountCreateMatrix)
    # 鏃堕棿鑺傜偣
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    # 璇戝憳
    translator_id: Optional[UUID] = None
    translator_name: Optional[str] = None
    translator_assignment_time: Optional[datetime] = None
    assigned_translators: list[ProjectAssignedTranslatorResponse] = Field(default_factory=list)
    # 杩涘害
    status: Optional[str] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    # 鍏朵粬
    network_file_path: Optional[str] = None
    remarks: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TranslationProjectResponse(TranslationProjectBase):
    id: UUID
    order_no: str
    client_manager: Optional[str] = None
    manager_contact: Optional[str] = None
    project_manager_name: Optional[str] = None
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    translator_name: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sub_orders: list['TranslationSubOrderResponse'] = Field(default_factory=list)
    assigned_translators: list[ProjectAssignedTranslatorResponse] = Field(default_factory=list)
    project_file_name: Optional[str] = None
    project_file_translation_domain_level1: Optional[str] = None
    project_file_translation_domain_level2: Optional[str] = None
    project_file_type_level1: Optional[str] = None
    project_file_type_level2: Optional[str] = None
    project_file_format: Optional[str] = None
    project_file_attribute_level1: Optional[str] = None
    project_file_attribute_level2: Optional[str] = None
    project_file_attribute_level3: Optional[str] = None
    project_file_difficulty: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# TranslationSubOrder Schemas
class TranslationSubOrderCreate(BaseModel):
    parent_project_id: UUID
    sub_order_no: Optional[str] = None  # 若不传则由后端自动生成
    sub_project_name: Optional[str] = None
    # 鏂囦欢/璇█/瀛楁暟
    file_type_secondary: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: WordCountCreateMatrix = Field(default_factory=WordCountCreateMatrix)
    # 鏃堕棿鑺傜偣
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    # 璇戝憳
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    # 杩涘害
    status: Optional[str] = 'pending'
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    # 鍏朵粬
    network_file_path: Optional[str] = None
    remarks: Optional[str] = None
    created_by: Optional[UUID] = None

    @field_validator('language_pair')
    @classmethod
    def validate_language_pair(cls, value: Optional[str]) -> Optional[str]:
        return normalize_language_pairs(value)

    @field_validator(
        'translator_delivery_progress', 'pre_review_qc_progress', 'review_progress', 'review1_progress',
        'review2_progress', 'post_review_qc_progress', 'layout_progress', 'consolidation_progress',
    )
    @classmethod
    def validate_progress(cls, value: Optional[str]) -> Optional[str]:
        return normalize_progress_percent(value)


class TranslationSubOrderUpdate(BaseModel):
    sub_project_name: Optional[str] = None
    file_type_secondary: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: Optional[WordCountCreateMatrix] = None
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    status: Optional[str] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    network_file_path: Optional[str] = None
    remarks: Optional[str] = None
    assigned_translator_completions: Optional[list[AssignedTranslatorCompletionUpdate]] = None

    @field_validator('language_pair')
    @classmethod
    def validate_language_pair(cls, value: Optional[str]) -> Optional[str]:
        return normalize_language_pairs(value)

    @field_validator(
        'translator_delivery_progress', 'pre_review_qc_progress', 'review_progress', 'review1_progress',
        'review2_progress', 'post_review_qc_progress', 'layout_progress', 'consolidation_progress',
    )
    @classmethod
    def validate_progress(cls, value: Optional[str]) -> Optional[str]:
        return normalize_progress_percent(value)


class TranslationSubOrderBulkDefaults(BaseModel):
    file_type_secondary: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: WordCountCreateMatrix = Field(default_factory=WordCountCreateMatrix)
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    status: Optional[str] = 'pending'
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    network_file_path: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator('language_pair')
    @classmethod
    def validate_language_pair(cls, value: Optional[str]) -> Optional[str]:
        return normalize_language_pairs(value)

    @field_validator(
        'translator_delivery_progress', 'pre_review_qc_progress', 'review_progress', 'review1_progress',
        'review2_progress', 'post_review_qc_progress', 'layout_progress', 'consolidation_progress',
    )
    @classmethod
    def validate_progress(cls, value: Optional[str]) -> Optional[str]:
        return normalize_progress_percent(value)


class TranslationSubOrderBulkCreate(BaseModel):
    parent_project_id: UUID
    sub_project_names: list[str] = Field(min_length=1, max_length=500)
    defaults: TranslationSubOrderBulkDefaults = Field(default_factory=TranslationSubOrderBulkDefaults)

    @field_validator('sub_project_names')
    @classmethod
    def validate_sub_project_names(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for index, value in enumerate(values, start=1):
            name = str(value or '').lstrip('\ufeff').strip()
            if not name:
                raise ValueError(f'第 {index} 条子项目名称不能为空')
            if len(name) > 255:
                raise ValueError(f'第 {index} 条子项目名称不能超过 255 个字符')
            cleaned.append(name)
        return cleaned


class TranslationSubOrderBulkSkipped(BaseModel):
    name: str
    reason: str


class TranslationSubOrderBulkResponse(BaseModel):
    created_count: int
    skipped_count: int
    created: list[TranslationSubOrderResponse] = Field(default_factory=list)
    skipped: list[TranslationSubOrderBulkSkipped] = Field(default_factory=list)


# UserRole Schemas
class UserRoleBase(BaseModel):
    user_id: UUID
    role_id: UUID


class UserRoleCreate(UserRoleBase):
    pass


class UserRoleResponse(UserRoleBase):
    id: UUID
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserRoleDetailResponse(UserRoleResponse):
    username: str
    user_full_name: Optional[str] = None
    role_name: str


# ProjectFile Schemas
class ProjectFileBase(BaseModel):
    translation_project_id: UUID
    file_name: str
    storage_path: str
    dispatch_path: Optional[str] = None
    translation_path: Optional[str] = None
    translator_return_path: Optional[str] = None
    client_delivery_path: Optional[str] = None
    project_feedback_path: Optional[str] = None
    feedback_delivery_path: Optional[str] = None
    translation_domain_level1: Optional[str] = None
    translation_domain_level2: Optional[str] = None
    file_type: Optional[str] = None
    file_type_secondary: Optional[str] = None
    file_format: Optional[str] = None
    file_attribute_level1: Optional[str] = None
    file_attribute_level2: Optional[str] = None
    file_attribute_level3: Optional[str] = None
    file_difficulty: Optional[str] = None
    file_ext: Optional[str] = None
    file_size: Optional[int] = None
    storage_type: Optional[str] = None


class ProjectFileCreate(ProjectFileBase):
    uploaded_by: Optional[UUID] = None


class ProjectFileUpdate(BaseModel):
    file_name: Optional[str] = None
    storage_path: Optional[str] = None
    dispatch_path: Optional[str] = None
    translation_path: Optional[str] = None
    translator_return_path: Optional[str] = None
    client_delivery_path: Optional[str] = None
    project_feedback_path: Optional[str] = None
    feedback_delivery_path: Optional[str] = None
    translation_domain_level1: Optional[str] = None
    translation_domain_level2: Optional[str] = None
    file_type: Optional[str] = None
    file_type_secondary: Optional[str] = None
    file_format: Optional[str] = None
    file_attribute_level1: Optional[str] = None
    file_attribute_level2: Optional[str] = None
    file_attribute_level3: Optional[str] = None
    file_difficulty: Optional[str] = None
    file_ext: Optional[str] = None
    file_size: Optional[int] = None
    storage_type: Optional[str] = None


class ProjectFileResponse(ProjectFileBase):
    id: UUID
    uploaded_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    order_no: Optional[str] = None
    project_name: Optional[str] = None
    project_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# WorkSchedule Schemas
from datetime import date as date_type
from typing import Any

class WorkScheduleBase(BaseModel):
    schedule_date: date_type
    shift_table: Optional[Any] = None
    leave_notes: Optional[Any] = None
    urgent_table_zh_en: Optional[Any] = None
    urgent_table_en_zh: Optional[Any] = None
    dept_person_data: Optional[Any] = None
    not_scheduled_tasks: Optional[Any] = None
    pm_rotation_order: Optional[str] = None


class WorkScheduleCreate(WorkScheduleBase):
    updated_by: Optional[UUID] = None


class WorkScheduleUpdate(BaseModel):
    shift_table: Optional[Any] = None
    leave_notes: Optional[Any] = None
    urgent_table_zh_en: Optional[Any] = None
    urgent_table_en_zh: Optional[Any] = None
    dept_person_data: Optional[Any] = None
    not_scheduled_tasks: Optional[Any] = None
    pm_rotation_order: Optional[str] = None
    updated_by: Optional[UUID] = None


class WorkScheduleResponse(WorkScheduleBase):
    id: UUID
    updated_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ========== 璇峰亣 Schemas ==========

class EmployeeLeaveCreate(BaseModel):
    employee_id: UUID
    employee_name: Optional[str] = None
    start_date: datetime
    end_date: datetime
    leave_type: Optional[str] = None
    reason: Optional[str] = None


class EmployeeLeaveUpdate(BaseModel):
    employee_id: Optional[UUID] = None
    employee_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    leave_type: Optional[str] = None
    reason: Optional[str] = None


class EmployeeLeaveResponse(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str
    department: Optional[str] = None
    start_date: datetime
    end_date: datetime
    leave_type: Optional[str] = None
    reason: Optional[str] = None
    status: Literal['active', 'upcoming', 'past'] = 'upcoming'
    is_current_user: bool = False
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ========== 璐㈠姟 Schemas ==========

class FinancePaymentBase(BaseModel):
    stage_type: str  # deposit, mid, final
    stage_no: int = 1
    planned_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    payment_time: Optional[datetime] = None
    payment_method: Optional[str] = None
    confirmed_by: Optional[UUID] = None
    confirmed_at: Optional[datetime] = None


class FinancePaymentCreate(FinancePaymentBase):
    pass


class FinancePaymentUpdate(BaseModel):
    stage_type: Optional[str] = None
    stage_no: Optional[int] = None
    planned_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    payment_time: Optional[datetime] = None
    payment_method: Optional[str] = None
    confirmed_by: Optional[UUID] = None
    confirmed_at: Optional[datetime] = None


class FinancePaymentResponse(FinancePaymentBase):
    id: UUID
    finance_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FinanceRecordBase(BaseModel):
    project_id: UUID
    sales_person_id: Optional[UUID] = None
    follow_up_person_id: Optional[UUID] = None
    settlement_method: Optional[str] = None
    unit_price_excl_tax: Optional[float] = None
    unit_price_incl_tax: Optional[float] = None
    total_excl_tax: Optional[float] = None
    total_incl_tax: Optional[float] = None
    invoice_status: Optional[str] = 'unissued'
    remarks: Optional[str] = None
    edited_by: Optional[UUID] = None


class FinanceRecordCreate(FinanceRecordBase):
    payments: Optional[list[FinancePaymentCreate]] = []


class FinanceRecordUpdate(BaseModel):
    sales_person_id: Optional[UUID] = None
    follow_up_person_id: Optional[UUID] = None
    settlement_method: Optional[str] = None
    unit_price_excl_tax: Optional[float] = None
    unit_price_incl_tax: Optional[float] = None
    total_excl_tax: Optional[float] = None
    total_incl_tax: Optional[float] = None
    invoice_status: Optional[str] = None
    remarks: Optional[str] = None
    edited_by: Optional[UUID] = None
    payments: Optional[list[FinancePaymentCreate]] = None


class FinanceRecordResponse(FinanceRecordBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    payments: list[FinancePaymentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class FinanceEntryPayload(BaseModel):
    """4姝ョ患鍚堣〃鍗曚竴娆℃€ф彁浜ょ殑鑱斿悎 payload"""
    # 绗?姝ワ細鍜ㄨ鍩烘湰鎯呭喌锛堝彲閫夛紝鑻ュ凡鏈夊挩璇㈠垯浼?consultation_id锛?    consultation_id: Optional[UUID] = None
    consultation: Optional[ConsultationCreate] = None

    # 绗?姝ワ細椤圭洰璇︽儏锛堝彲閫夛紝鑻ュ凡鏈夐」鐩垯浼?project_id锛?    project_id: Optional[UUID] = None
    project: Optional[TranslationProjectCreate] = None

    # 绗?姝ワ細鍘熸枃璺緞锛堟枃鏈矾寰勶紝瀛樺叆椤圭洰澶囨敞鎴栧崟鐙瓧娈碉級
    source_file_path: Optional[str] = None

    # 绗?姝ワ細璐㈠姟淇℃伅
    finance: Optional[FinanceRecordCreate] = None


class FinanceEntryResponse(BaseModel):
    """Combined entry response."""
    consultation_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    finance_id: Optional[UUID] = None
    detail: str = "鎿嶄綔鎴愬姛"


class FinanceRecordDisplayResponse(BaseModel):
    """Response model for view v_finance_record_display."""
    finance_id: UUID
    project_id: UUID
    order_no: Optional[str] = None
    client_short_name: Optional[str] = None
    project_name: Optional[str] = None
    project_status: Optional[str] = None
    customer_reception_time: Optional[datetime] = None
    settlement_method: Optional[str] = None
    unit_price_excl_tax: Optional[float] = None
    unit_price_incl_tax: Optional[float] = None
    total_excl_tax: Optional[float] = None
    total_incl_tax: Optional[float] = None
    invoice_status: Optional[str] = None
    remarks: Optional[str] = None
    edited_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 宓屽娆鹃」鏄庣粏
    payments: list[FinancePaymentResponse] = []
    # 浜哄憳 ID锛堢紪杈戝洖濉敤锛?    sales_person_id: Optional[UUID] = None
    follow_up_person_id: Optional[UUID] = None
    # 浜哄憳鍚嶇О锛堝墠绔睍绀虹敤锛?    sales_person_name: Optional[str] = None
    follow_up_person_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)




class NotificationResponse(BaseModel):
    id: UUID
    recipient_user_id: UUID
    title: str
    content: str
    notification_type: str
    is_read: bool
    read_at: Optional[datetime] = None
    related_project_id: Optional[UUID] = None
    related_project_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ProjectChatSettingsUpdateRequest(BaseModel):
    enabled: bool


class ProjectChatSettingsResponse(BaseModel):
    project_id: UUID
    enabled: bool
    enabled_by: Optional[UUID] = None
    enabled_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    can_manage: bool = False


class ProjectChatMessageCreate(BaseModel):
    content: str = Field(default='', max_length=10000)
    content_json: Optional[dict] = None
    mentioned_user_id: Optional[UUID] = None
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=9)


class ProjectChatAttachmentResponse(BaseModel):
    id: UUID
    original_name: str
    content_type: str
    file_size: int
    created_at: Optional[datetime] = None


class ProjectChatMessageResponse(BaseModel):
    id: UUID
    project_id: UUID
    sender_user_id: Optional[UUID] = None
    sender_name: str
    content: str
    content_json: Optional[dict] = None
    message_type: str = 'user'
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    mentioned_user_id: Optional[UUID] = None
    mentioned_user_name: Optional[str] = None
    attachments: list[ProjectChatAttachmentResponse] = Field(default_factory=list)


class ProjectChatMessageQueryResponse(BaseModel):
    items: list[ProjectChatMessageResponse] = Field(default_factory=list)
    total: int = 0
    enabled: bool = False
    can_manage: bool = False
