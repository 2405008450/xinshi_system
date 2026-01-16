from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import AppUser, Role, Project, UserRole, ProjectFile
from schemas import (
    AppUserCreate, AppUserUpdate,
    RoleCreate, RoleUpdate,
    ProjectCreate, ProjectUpdate,
    UserRoleCreate,
    ProjectFileCreate, ProjectFileUpdate
)
import hashlib


# AppUser CRUD
def get_user(db: Session, user_id: UUID) -> Optional[AppUser]:
    return db.query(AppUser).filter(AppUser.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[AppUser]:
    return db.query(AppUser).filter(AppUser.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[AppUser]:
    return db.query(AppUser).offset(skip).limit(limit).all()


def create_user(db: Session, user: AppUserCreate) -> AppUser:
    # 简单的密码哈希（实际项目中应使用 bcrypt 等）
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    db_user = AppUser(
        username=user.username,
        password_hash=password_hash,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: UUID, user_update: AppUserUpdate) -> Optional[AppUser]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = hashlib.sha256(update_data.pop("password").encode()).hexdigest()
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: UUID) -> bool:
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    db.delete(db_user)
    db.commit()
    return True


# Role CRUD
def get_role(db: Session, role_id: UUID) -> Optional[Role]:
    return db.query(Role).filter(Role.id == role_id).first()


def get_role_by_name(db: Session, role_name: str) -> Optional[Role]:
    return db.query(Role).filter(Role.role_name == role_name).first()


def get_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
    return db.query(Role).offset(skip).limit(limit).all()


def create_role(db: Session, role: RoleCreate) -> Role:
    db_role = Role(
        role_name=role.role_name,
        description=role.description
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role


def update_role(db: Session, role_id: UUID, role_update: RoleUpdate) -> Optional[Role]:
    db_role = get_role(db, role_id)
    if not db_role:
        return None
    
    update_data = role_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_role, field, value)
    
    db.commit()
    db.refresh(db_role)
    return db_role


def delete_role(db: Session, role_id: UUID) -> bool:
    db_role = get_role(db, role_id)
    if not db_role:
        return False
    db.delete(db_role)
    db.commit()
    return True


# Project CRUD
def get_project(db: Session, project_id: UUID) -> Optional[Project]:
    return db.query(Project).filter(Project.id == project_id).first()


def get_project_by_no(db: Session, project_no: str) -> Optional[Project]:
    return db.query(Project).filter(Project.project_no == project_no).first()


def get_projects(db: Session, skip: int = 0, limit: int = 100, created_by: Optional[UUID] = None) -> List[Project]:
    query = db.query(Project)
    if created_by:
        query = query.filter(Project.created_by == created_by)
    return query.offset(skip).limit(limit).all()


def create_project(db: Session, project: ProjectCreate) -> Project:
    db_project = Project(
        project_no=project.project_no,
        client_name=project.client_name,
        project_type=project.project_type,
        source_language=project.source_language,
        target_language=project.target_language,
        word_count=project.word_count,
        deadline=project.deadline,
        status=project.status,
        sales_owner=project.sales_owner,
        remarks=project.remarks,
        created_by=project.created_by
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def update_project(db: Session, project_id: UUID, project_update: ProjectUpdate) -> Optional[Project]:
    db_project = get_project(db, project_id)
    if not db_project:
        return None
    
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, project_id: UUID) -> bool:
    db_project = get_project(db, project_id)
    if not db_project:
        return False
    db.delete(db_project)
    db.commit()
    return True


# UserRole CRUD
def get_user_role(db: Session, user_role_id: UUID) -> Optional[UserRole]:
    return db.query(UserRole).filter(UserRole.id == user_role_id).first()


def get_user_roles_by_user(db: Session, user_id: UUID) -> List[UserRole]:
    return db.query(UserRole).filter(UserRole.user_id == user_id).all()


def get_user_roles_by_role(db: Session, role_id: UUID) -> List[UserRole]:
    return db.query(UserRole).filter(UserRole.role_id == role_id).all()


def get_user_role_by_user_and_role(db: Session, user_id: UUID, role_id: UUID) -> Optional[UserRole]:
    return db.query(UserRole).filter(
        and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
    ).first()


def create_user_role(db: Session, user_role: UserRoleCreate) -> UserRole:
    db_user_role = UserRole(
        user_id=user_role.user_id,
        role_id=user_role.role_id
    )
    db.add(db_user_role)
    db.commit()
    db.refresh(db_user_role)
    return db_user_role


def delete_user_role(db: Session, user_role_id: UUID) -> bool:
    db_user_role = get_user_role(db, user_role_id)
    if not db_user_role:
        return False
    db.delete(db_user_role)
    db.commit()
    return True


def delete_user_role_by_user_and_role(db: Session, user_id: UUID, role_id: UUID) -> bool:
    db_user_role = get_user_role_by_user_and_role(db, user_id, role_id)
    if not db_user_role:
        return False
    db.delete(db_user_role)
    db.commit()
    return True


# ProjectFile CRUD
def get_project_file(db: Session, file_id: UUID) -> Optional[ProjectFile]:
    return db.query(ProjectFile).filter(ProjectFile.id == file_id).first()


def get_project_files_by_project(db: Session, project_id: UUID, skip: int = 0, limit: int = 100) -> List[ProjectFile]:
    return db.query(ProjectFile).filter(ProjectFile.project_id == project_id).offset(skip).limit(limit).all()


def get_project_files(db: Session, skip: int = 0, limit: int = 100) -> List[ProjectFile]:
    return db.query(ProjectFile).offset(skip).limit(limit).all()


def create_project_file(db: Session, project_file: ProjectFileCreate) -> ProjectFile:
    db_file = ProjectFile(
        project_id=project_file.project_id,
        file_name=project_file.file_name,
        storage_path=project_file.storage_path,
        file_type=project_file.file_type,
        file_ext=project_file.file_ext,
        file_size=project_file.file_size,
        storage_type=project_file.storage_type,
        uploaded_by=project_file.uploaded_by
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


def update_project_file(db: Session, file_id: UUID, file_update: ProjectFileUpdate) -> Optional[ProjectFile]:
    db_file = get_project_file(db, file_id)
    if not db_file:
        return None
    
    update_data = file_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_file, field, value)
    
    db.commit()
    db.refresh(db_file)
    return db_file


def delete_project_file(db: Session, file_id: UUID) -> bool:
    db_file = get_project_file(db, file_id)
    if not db_file:
        return False
    db.delete(db_file)
    db.commit()
    return True
