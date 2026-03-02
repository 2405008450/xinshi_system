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


# Translator Schemas
class TranslatorBase(BaseModel):
    translator_code: Optional[str] = None
    translator_name: str
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None

class TranslatorCreate(TranslatorBase):
    pass

class TranslatorUpdate(BaseModel):
    translator_code: Optional[str] = None
    translator_name: Optional[str] = None
    cooperation_type: Optional[str] = None
    contact_info: Optional[str] = None

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
    start_date: date
    end_date: date
    leave_type: Optional[str] = None
    reason: Optional[str] = None


class EmployeeLeaveResponse(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str
    start_date: date
    end_date: date
    leave_type: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
