from typing import Optional
from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


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

class ClientResponse(ClientBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sub_clients: list['SubClientResponse'] = Field(default_factory=list)

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

class SubClientResponse(SubClientBase):
    id: UUID
    parent_client_id: UUID
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
    client_code: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
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
    status: Optional[str] = "standby"
    available_time_slot: Optional[str] = None
    daily_accept_count: Optional[int] = None
    hourly_speed: Optional[int] = None
    daily_word_capacity: Optional[int] = None
    can_cloud_edit: Optional[bool] = None
    can_revision: Optional[bool] = None
    domain_skills: Optional[list] = []
    availability_updated_at: Optional[datetime] = None

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
    status: Optional[str] = None
    available_time_slot: Optional[str] = None
    daily_accept_count: Optional[int] = None
    hourly_speed: Optional[int] = None
    daily_word_capacity: Optional[int] = None
    can_cloud_edit: Optional[bool] = None
    can_revision: Optional[bool] = None
    domain_skills: Optional[list] = None
    availability_updated_at: Optional[datetime] = None

class TranslatorResponse(TranslatorBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TranslatorScheduleBase(BaseModel):
    translator_id: UUID
    schedule_date: date
    available_time_slot: Optional[str] = None
    remaining_capacity: Optional[int] = None
    source_type: Optional[str] = "manual"
    source_ref: Optional[str] = None
    last_confirmed_at: Optional[datetime] = None
    remarks: Optional[str] = None


class TranslatorScheduleCreate(TranslatorScheduleBase):
    pass


class TranslatorScheduleUpdate(BaseModel):
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
    network_file_path: Optional[str] = None

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
    network_file_path: Optional[str] = None

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
    word_count: Optional[int] = None
    # 鏃堕棿鑺傜偣
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    # 璇戝憳
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    expected_translator_stats_method: Optional[str] = None
    expected_translator_word_count: Optional[int] = None
    # 杩涘害
    status: Optional[str] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
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

    class Config:
        from_attributes = True


class TranslationProjectResponse(TranslationProjectBase):
    id: UUID
    order_no: str
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sub_orders: list['TranslationSubOrderResponse'] = Field(default_factory=list)

    class Config:
        from_attributes = True


# TranslationSubOrder Schemas
class TranslationSubOrderCreate(BaseModel):
    parent_project_id: UUID
    sub_order_no: Optional[str] = None  # 若不传则由后端自动生成
    sub_project_name: Optional[str] = None
    # 鏂囦欢/璇█/瀛楁暟
    file_type_secondary: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count: Optional[int] = None
    # 鏃堕棿鑺傜偣
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    # 璇戝憳
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    expected_translator_stats_method: Optional[str] = None
    expected_translator_word_count: Optional[int] = None
    # 杩涘害
    status: Optional[str] = 'pending'
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    # 鍏朵粬
    network_file_path: Optional[str] = None
    remarks: Optional[str] = None
    created_by: Optional[UUID] = None


class TranslationSubOrderUpdate(BaseModel):
    sub_project_name: Optional[str] = None
    file_type_secondary: Optional[str] = None
    language_pair: Optional[str] = None
    priority: Optional[str] = None
    word_count: Optional[int] = None
    customer_deadline_time: Optional[datetime] = None
    sent_to_client_time: Optional[datetime] = None
    client_feedback: Optional[str] = None
    translator_id: Optional[UUID] = None
    translator_assignment_time: Optional[datetime] = None
    expected_translator_stats_method: Optional[str] = None
    expected_translator_word_count: Optional[int] = None
    status: Optional[str] = None
    translator_delivery_progress: Optional[str] = None
    pre_review_qc_progress: Optional[str] = None
    review1_progress: Optional[str] = None
    review2_progress: Optional[str] = None
    post_review_qc_progress: Optional[str] = None
    layout_progress: Optional[str] = None
    consolidation_progress: Optional[str] = None
    network_file_path: Optional[str] = None
    remarks: Optional[str] = None


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
    dispatch_path: Optional[str] = None
    translation_path: Optional[str] = None
    client_delivery_path: Optional[str] = None
    file_type: Optional[str] = None
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
    client_delivery_path: Optional[str] = None
    file_type: Optional[str] = None
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


# ========== 璇峰亣 Schemas ==========

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

    class Config:
        from_attributes = True




class NotificationResponse(BaseModel):
    id: UUID
    recipient_user_id: UUID
    title: str
    content: str
    notification_type: str
    is_read: bool
    read_at: Optional[datetime] = None
    related_project_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

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
    content: str = Field(min_length=1, max_length=2000)
    mentioned_user_id: Optional[UUID] = None


class ProjectChatMessageResponse(BaseModel):
    id: UUID
    project_id: UUID
    sender_user_id: Optional[UUID] = None
    sender_name: str
    content: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    mentioned_user_id: Optional[UUID] = None
    mentioned_user_name: Optional[str] = None


class ProjectChatMessageQueryResponse(BaseModel):
    items: list[ProjectChatMessageResponse] = Field(default_factory=list)
    total: int = 0
    enabled: bool = False
    can_manage: bool = False
