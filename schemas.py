from typing import Optional
from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, EmailStr


# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    roles: Optional[list[str]] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# AppUser Schemas
class AppUserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True


class AppUserCreate(AppUserBase):
    password: str


class AppUserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class AppUserResponse(AppUserBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


# Client Schemas
class ClientBase(BaseModel):
    client_code: str
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

class ClientResponse(ClientBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Consultation Schemas
class ConsultationBase(BaseModel):
    consultation_code: Optional[str] = None
    client_id: Optional[UUID] = None
    consultation_time: Optional[datetime] = None
    consultation_method: Optional[str] = None
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
    pass

class ConsultationUpdate(BaseModel):
    consultation_code: Optional[str] = None
    client_id: Optional[UUID] = None
    consultation_time: Optional[datetime] = None
    consultation_method: Optional[str] = None
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

class ConsultationResponse(ConsultationBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Translator Schemas
class TranslatorBase(BaseModel):
    translator_code: Optional[str] = None
    translator_name: str
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None
    translation_type: Optional[str] = None
    quality_score: Optional[str] = None
    cloud_revision: Optional[str] = None
    daily_rate: Optional[str] = None
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
    first_contact_date: Optional[date] = None
    remarks: Optional[str] = None

class TranslatorCreate(TranslatorBase):
    pass

class TranslatorUpdate(BaseModel):
    translator_code: Optional[str] = None
    translator_name: Optional[str] = None
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None
    translation_type: Optional[str] = None
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
    first_contact_date: Optional[date] = None
    remarks: Optional[str] = None

class TranslatorResponse(TranslatorBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Translation Project Schemas
class TranslationProjectBase(BaseModel):
    project_name: str
    file_type_secondary: Optional[str] = None
    client_id: Optional[UUID] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    customer_reception_time: Optional[datetime] = None
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count: Optional[int] = None
    project_status: Optional[str] = None
    pm_confirmed_by: Optional[UUID] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    expected_translator_stats_method: Optional[str] = None
    expected_translator_word_count: Optional[int] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None

class TranslationProjectCreate(TranslationProjectBase):
    created_by: Optional[UUID] = None

class TranslationProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    file_type_secondary: Optional[str] = None
    client_id: Optional[UUID] = None
    client_short_name: Optional[str] = None
    client_code: Optional[str] = None
    customer_reception_time: Optional[datetime] = None
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count: Optional[int] = None
    project_status: Optional[str] = None
    pm_confirmed_by: Optional[UUID] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    expected_translator_stats_method: Optional[str] = None
    expected_translator_word_count: Optional[int] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None

class TranslationProjectResponse(TranslationProjectBase):
    id: UUID
    order_no: str
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True



# UserRole Schemas
class UserRoleBase(BaseModel):
    user_id: UUID
    role_id: UUID


class UserRoleCreate(UserRoleBase):
    pass


class UserRoleResponse(UserRoleBase):
    id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ProjectFile Schemas
class ProjectFileBase(BaseModel):
    translation_project_id: UUID
    file_name: str
    storage_path: str
    file_type: Optional[str] = None
    file_ext: Optional[str] = None
    file_size: Optional[int] = None
    storage_type: Optional[str] = None


class ProjectFileCreate(ProjectFileBase):
    uploaded_by: Optional[UUID] = None


class ProjectFileUpdate(BaseModel):
    file_name: Optional[str] = None
    storage_path: Optional[str] = None
    file_type: Optional[str] = None
    file_ext: Optional[str] = None
    file_size: Optional[int] = None
    storage_type: Optional[str] = None


class ProjectFileResponse(ProjectFileBase):
    id: UUID
    uploaded_by: Optional[UUID] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


# ========== 请假 Schemas ==========

class EmployeeLeaveCreate(BaseModel):
    employee_id: UUID
    employee_name: str
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
    start_date: datetime
    end_date: datetime
    leave_type: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 财务 Schemas ==========

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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class FinanceEntryPayload(BaseModel):
    """4步综合表单一次性提交的联合 payload"""
    # 第1步：咨询基本情况（可选，若已有咨询则传 consultation_id）
    consultation_id: Optional[UUID] = None
    consultation: Optional[ConsultationCreate] = None

    # 第2步：项目详情（可选，若已有项目则传 project_id）
    project_id: Optional[UUID] = None
    project: Optional[TranslationProjectCreate] = None

    # 第3步：原文路径（文本路径，存入项目备注或单独字段）
    source_file_path: Optional[str] = None

    # 第4步：财务信息
    finance: Optional[FinanceRecordCreate] = None


class FinanceEntryResponse(BaseModel):
    """综合录入接口的返回"""
    consultation_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    finance_id: Optional[UUID] = None
    detail: str = "操作成功"


class FinanceRecordDisplayResponse(BaseModel):
    """视图 v_finance_record_display 的响应模型"""
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
    # 嵌套款项明细
    payments: list[FinancePaymentResponse] = []
    # 人员 ID（编辑回填用）
    sales_person_id: Optional[UUID] = None
    follow_up_person_id: Optional[UUID] = None
    # 人员名称（前端展示用）
    sales_person_name: Optional[str] = None
    follow_up_person_name: Optional[str] = None

    class Config:
        from_attributes = True
