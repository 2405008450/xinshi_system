from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import AppUser, Role, TranslationProject, UserRole, ProjectFile, Client, Translator
from schemas import (
    AppUserCreate, AppUserUpdate,
    RoleCreate, RoleUpdate,
    TranslationProjectCreate, TranslationProjectUpdate,
    UserRoleCreate,
    ProjectFileCreate, ProjectFileUpdate,
    ClientCreate, ClientUpdate,
    TranslatorCreate, TranslatorUpdate
)
import hashlib
from utils import generate_order_no


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


# Client CRUD
def get_client(db: Session, client_id: UUID) -> Optional[Client]:
    return db.query(Client).filter(Client.id == client_id).first()

def get_clients(db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
    return db.query(Client).offset(skip).limit(limit).all()

def create_client(db: Session, client: ClientCreate) -> Client:
    db_client = Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

def update_client(db: Session, client_id: UUID, client_update: ClientUpdate) -> Optional[Client]:
    db_client = get_client(db, client_id)
    if not db_client:
        return None
    for field, value in client_update.model_dump(exclude_unset=True).items():
        setattr(db_client, field, value)
    db.commit()
    db.refresh(db_client)
    return db_client

def delete_client(db: Session, client_id: UUID) -> bool:
    db_client = get_client(db, client_id)
    if not db_client:
        return False
    db.delete(db_client)
    db.commit()
    return True


# Translator CRUD
def get_translator(db: Session, translator_id: UUID) -> Optional[Translator]:
    return db.query(Translator).filter(Translator.id == translator_id).first()

def get_translators(db: Session, skip: int = 0, limit: int = 100) -> List[Translator]:
    return db.query(Translator).offset(skip).limit(limit).all()

def create_translator(db: Session, translator: TranslatorCreate) -> Translator:
    db_translator = Translator(**translator.model_dump())
    db.add(db_translator)
    db.commit()
    db.refresh(db_translator)
    return db_translator

def update_translator(db: Session, translator_id: UUID, translator_update: TranslatorUpdate) -> Optional[Translator]:
    db_translator = get_translator(db, translator_id)
    if not db_translator:
        return None
    for field, value in translator_update.model_dump(exclude_unset=True).items():
        setattr(db_translator, field, value)
    db.commit()
    db.refresh(db_translator)
    return db_translator

def delete_translator(db: Session, translator_id: UUID) -> bool:
    db_translator = get_translator(db, translator_id)
    if not db_translator:
        return False
    db.delete(db_translator)
    db.commit()
    return True


# Translation Project CRUD
def get_translation_project(db: Session, project_id: UUID) -> Optional[TranslationProject]:
    return db.query(TranslationProject).filter(TranslationProject.id == project_id).first()


def get_translation_project_by_no(db: Session, order_no: str) -> Optional[TranslationProject]:
    return db.query(TranslationProject).filter(TranslationProject.order_no == order_no).first()


def get_translation_projects(db: Session, skip: int = 0, limit: int = 100, created_by: Optional[UUID] = None) -> List[TranslationProject]:
    query = db.query(TranslationProject)
    if created_by:
        query = query.filter(TranslationProject.created_by == created_by)
    return query.offset(skip).limit(limit).all()


def create_translation_project(db: Session, project: TranslationProjectCreate) -> TranslationProject:
    order_no = generate_order_no(db)
    db_project = TranslationProject(
        order_no=order_no,
        **project.model_dump()
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def update_translation_project(db: Session, project_id: UUID, project_update: TranslationProjectUpdate) -> Optional[TranslationProject]:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return None
    
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db.commit()
    db.refresh(db_project)
    return db_project


def delete_translation_project(db: Session, project_id: UUID) -> bool:
    db_project = get_translation_project(db, project_id)
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


def get_user_role_names(db: Session, user_id: UUID) -> List[str]:
    """获取用户的所有角色名称"""
    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    role_names = []
    for user_role in user_roles:
        role = get_role(db, user_role.role_id)
        if role:
            role_names.append(role.role_name)
    return role_names


def get_user_roles_by_role(db: Session, role_id: UUID) -> List[UserRole]:
    return db.query(UserRole).filter(UserRole.role_id == role_id).all()


def get_user_roles_with_role_names(db: Session, user_id: UUID) -> List[str]:
    """获取用户的所有角色名称列表"""
    user_roles = (
        db.query(Role.role_name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .all()
    )
    return [r.role_name for r in user_roles]


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


def get_project_files_by_project(db: Session, translation_project_id: UUID, skip: int = 0, limit: int = 100) -> List[ProjectFile]:
    return db.query(ProjectFile).filter(ProjectFile.translation_project_id == translation_project_id).offset(skip).limit(limit).all()


def get_project_files(db: Session, skip: int = 0, limit: int = 100) -> List[ProjectFile]:
    return db.query(ProjectFile).offset(skip).limit(limit).all()


def create_project_file(db: Session, project_file: ProjectFileCreate) -> ProjectFile:
    db_file = ProjectFile(
        translation_project_id=project_file.translation_project_id,
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
