from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


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


# Project Schemas
class ProjectBase(BaseModel):
    project_no: str
    client_name: Optional[str] = None
    project_type: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    word_count: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None
    sales_owner: Optional[str] = None
    remarks: Optional[str] = None


class ProjectCreate(ProjectBase):
    created_by: Optional[UUID] = None


class ProjectUpdate(BaseModel):
    project_no: Optional[str] = None
    client_name: Optional[str] = None
    project_type: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    word_count: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None
    sales_owner: Optional[str] = None
    remarks: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: UUID
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
    project_id: UUID
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
