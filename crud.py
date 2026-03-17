from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import String, and_

from models import AppUser, Role, TranslationProject, TranslationSubOrder, UserRole, ProjectFile, Client, ClientContact, SubClient, Translator, Consultation, FinanceRecord, AppNotification
from schemas import (
    AppUserCreate, AppUserUpdate,
    RoleCreate, RoleUpdate,
    TranslationProjectCreate, TranslationProjectUpdate,
    TranslationSubOrderCreate, TranslationSubOrderUpdate,
    UserRoleCreate,
    ProjectFileCreate, ProjectFileUpdate,
    ClientCreate, ClientUpdate,
    ClientContactCreate, ClientContactUpdate,
    SubClientCreate, SubClientUpdate,
    TranslatorCreate, TranslatorUpdate,
    ConsultationCreate, ConsultationUpdate
)
from passlib.context import CryptContext
import hashlib
from utils import generate_order_no


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_password_for_bcrypt(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        return hashlib.sha256(password_bytes).hexdigest()
    return plain_password


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(normalize_password_for_bcrypt(plain_password))


# AppUser CRUD
def get_user(db: Session, user_id: UUID) -> Optional[AppUser]:
    return db.query(AppUser).filter(AppUser.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[AppUser]:
    return db.query(AppUser).filter(AppUser.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[AppUser]:
    return db.query(AppUser).offset(skip).limit(limit).all()


def create_user(db: Session, user: AppUserCreate) -> AppUser:
    hashed = hash_password(user.password)
    db_user = AppUser(
        username=user.username,
        password_hash=hashed,
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
        update_data["password_hash"] = hash_password(update_data.pop("password"))
    
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
import datetime as dt

def generate_client_code(db: Session) -> str:
    today = dt.datetime.now()
    yy = today.strftime("%y")
    mmdd = today.strftime("%m%d")
    prefix = f"CL-{yy}-{mmdd}-"

    last_record = (
        db.query(Client)
        .filter(Client.client_code.like(f"{prefix}%"))
        .order_by(Client.client_code.desc())
        .first()
    )

    if last_record and last_record.client_code:
        try:
            seq_str = last_record.client_code.split("-")[-1]
            new_seq = int(seq_str) + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1

    return f"{prefix}{new_seq:04d}"


def get_client(db: Session, client_id: UUID) -> Optional[Client]:
    return db.query(Client).options(selectinload(Client.sub_clients)).filter(Client.id == client_id).first()

def get_clients(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    client_code: Optional[str] = None,
    client_name: Optional[str] = None
) -> List[Client]:
    query = db.query(Client).options(selectinload(Client.sub_clients))
    if client_code:
        query = query.filter(Client.client_code.ilike(f"%{client_code}%"))
    if client_name:
        query = query.filter(Client.client_name.ilike(f"%{client_name}%"))
    return query.offset(skip).limit(limit).all()

def create_client(db: Session, client: ClientCreate) -> Client:
    data = client.model_dump()
    if not data.get('client_code'):
        data['client_code'] = generate_client_code(db)
    db_client = Client(**data)
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


def _fill_client_contact_fields(db: Session, data: dict) -> dict:
    client = None
    client_id = data.get('client_id')
    client_code = data.get('client_code')

    if client_id:
        client = db.query(Client).filter(Client.id == client_id).first()
    elif client_code:
        client = db.query(Client).filter(Client.client_code == client_code).first()

    if client:
        data['client_id'] = client.id
        data['client_code'] = client.client_code
        data['client_name'] = client.client_name
        data['client_short_name'] = client.client_short_name
        data['client_manager'] = client.client_manager
        data['manager_contact'] = client.manager_contact

    return data


def get_client_contact(db: Session, contact_id: UUID) -> Optional[ClientContact]:
    return db.query(ClientContact).filter(ClientContact.id == contact_id).first()


def get_client_contacts(db: Session, skip: int = 0, limit: int = 100) -> List[ClientContact]:
    return (
        db.query(ClientContact)
        .order_by(ClientContact.visit_date.desc(), ClientContact.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_client_contacts(db: Session) -> int:
    return db.query(ClientContact.id).count()


def create_client_contact(db: Session, contact: ClientContactCreate) -> ClientContact:
    data = _fill_client_contact_fields(db, contact.model_dump())
    db_contact = ClientContact(**data)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


def update_client_contact(db: Session, contact_id: UUID, contact_update: ClientContactUpdate) -> Optional[ClientContact]:
    db_contact = get_client_contact(db, contact_id)
    if not db_contact:
        return None

    update_data = _fill_client_contact_fields(db, contact_update.model_dump(exclude_unset=True))
    for field, value in update_data.items():
        setattr(db_contact, field, value)

    db.commit()
    db.refresh(db_contact)
    return db_contact


def delete_client_contact(db: Session, contact_id: UUID) -> bool:
    db_contact = get_client_contact(db, contact_id)
    if not db_contact:
        return False
    db.delete(db_contact)
    db.commit()
    return True


# SubClient CRUD
def generate_sub_client_code(db: Session, parent_id: UUID) -> str:
    """生成子客户流水号, 格式 CL-YY-MMDD-NNNN.MMMM"""
    parent = get_client(db, parent_id)
    if not parent:
        raise ValueError("母客户不存在")
    base_no = parent.client_code

    last = (
        db.query(SubClient)
        .filter(SubClient.parent_client_id == parent_id)
        .filter(SubClient.sub_client_code.like(f"{base_no}.%"))
        .order_by(SubClient.sub_client_code.desc())
        .first()
    )
    if last and last.sub_client_code:
        try:
            seq_str = last.sub_client_code.rsplit(".", 1)[-1]
            new_seq = int(seq_str) + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1

    return f"{base_no}.{new_seq:04d}"

def get_sub_client(db: Session, sub_client_id: UUID) -> Optional[SubClient]:
    return db.query(SubClient).filter(SubClient.id == sub_client_id).first()

def create_sub_client(db: Session, sub_client: SubClientCreate) -> SubClient:
    sub_code = sub_client.sub_client_code or generate_sub_client_code(db, sub_client.parent_client_id)
    data = sub_client.model_dump(exclude={'sub_client_code'})
    db_sub = SubClient(sub_client_code=sub_code, **data)
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

def update_sub_client(db: Session, sub_id: UUID, sub_update: SubClientUpdate) -> Optional[SubClient]:
    db_sub = get_sub_client(db, sub_id)
    if not db_sub:
        return None
    for field, value in sub_update.model_dump(exclude_unset=True).items():
        setattr(db_sub, field, value)
    db.commit()
    db.refresh(db_sub)
    return db_sub

def delete_sub_client(db: Session, sub_id: UUID) -> bool:
    db_sub = get_sub_client(db, sub_id)
    if not db_sub:
        return False
    db.delete(db_sub)
    db.commit()
    return True

# Translator CRUD
def get_translator(db: Session, translator_id: UUID) -> Optional[Translator]:
    return db.query(Translator).filter(Translator.id == translator_id).first()

def _apply_translator_filters(
    query,
    translator_code: Optional[str] = None,
    translator_name: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    languages: Optional[str] = None,
    translation_type: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    available_time_slot: Optional[str] = None,
    domain_keyword: Optional[str] = None,
    stale_only: bool = False,
    stale_days: int = 4,
):
    if translator_code:
        query = query.filter(Translator.translator_code.ilike(f"%{translator_code}%"))
    if translator_name:
        query = query.filter(Translator.translator_name.ilike(f"%{translator_name}%"))
    if cooperation_type:
        query = query.filter(Translator.cooperation_type == cooperation_type)
    if languages:
        query = query.filter(Translator.languages.ilike(f"%{languages}%"))
    if translation_type:
        query = query.filter(Translator.translation_type == translation_type)
    if direction:
        query = query.filter(Translator.direction == direction)
    if status:
        query = query.filter(Translator.status == status)
    if available_time_slot:
        query = query.filter(Translator.available_time_slot.ilike(f"%{available_time_slot}%"))
    if domain_keyword:
        query = query.filter(Translator.domain_skills.cast(String).ilike(f"%{domain_keyword}%"))
    if stale_only:
        stale_before = dt.datetime.utcnow() - dt.timedelta(days=max(stale_days, 1))
        query = query.filter(
            (Translator.availability_updated_at.is_(None)) |
            (Translator.availability_updated_at < stale_before)
        )
    return query

def get_translators(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    translator_code: Optional[str] = None,
    translator_name: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    languages: Optional[str] = None,
    translation_type: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    available_time_slot: Optional[str] = None,
    domain_keyword: Optional[str] = None,
    stale_only: bool = False,
    stale_days: int = 4,
) -> List[Translator]:
    query = db.query(Translator)
    query = _apply_translator_filters(
        query,
        translator_code=translator_code,
        translator_name=translator_name,
        cooperation_type=cooperation_type,
        languages=languages,
        translation_type=translation_type,
        direction=direction,
        status=status,
        available_time_slot=available_time_slot,
        domain_keyword=domain_keyword,
        stale_only=stale_only,
        stale_days=stale_days,
    )
    return (
        query
        .order_by(Translator.default_priority.asc(), Translator.translator_name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def count_translators(
    db: Session,
    translator_code: Optional[str] = None,
    translator_name: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    languages: Optional[str] = None,
    translation_type: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    available_time_slot: Optional[str] = None,
    domain_keyword: Optional[str] = None,
    stale_only: bool = False,
    stale_days: int = 4,
) -> int:
    query = db.query(Translator.id)
    query = _apply_translator_filters(
        query,
        translator_code=translator_code,
        translator_name=translator_name,
        cooperation_type=cooperation_type,
        languages=languages,
        translation_type=translation_type,
        direction=direction,
        status=status,
        available_time_slot=available_time_slot,
        domain_keyword=domain_keyword,
        stale_only=stale_only,
        stale_days=stale_days,
    )
    return query.count()

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
from models import Client

def get_translation_project(db: Session, project_id: UUID) -> Optional[TranslationProject]:
    result = (
        db.query(TranslationProject, Client.client_short_name, Client.client_code)
        .options(selectinload(TranslationProject.sub_orders))
        .outerjoin(Client, TranslationProject.client_id == Client.id)
        .filter(TranslationProject.id == project_id)
        .first()
    )
    if not result:
        return None
    project, short_name, code = result
    project.client_short_name = short_name
    project.client_code = code
    return project

def get_translation_project_by_no(db: Session, order_no: str) -> Optional[TranslationProject]:
    result = (
        db.query(TranslationProject, Client.client_short_name, Client.client_code)
        .options(selectinload(TranslationProject.sub_orders))
        .outerjoin(Client, TranslationProject.client_id == Client.id)
        .filter(TranslationProject.order_no == order_no)
        .first()
    )
    if not result:
        return None
    project, short_name, code = result
    project.client_short_name = short_name
    project.client_code = code
    return project

def get_translation_projects(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None
) -> List[TranslationProject]:
    query = (
        db.query(TranslationProject, Client.client_short_name, Client.client_code)
        .options(selectinload(TranslationProject.sub_orders))
        .outerjoin(Client, TranslationProject.client_id == Client.id)
    )
    if created_by:
        query = query.filter(TranslationProject.created_by == created_by)
    if project_name:
        query = query.filter(TranslationProject.project_name.ilike(f"%{project_name}%"))
    if order_no:
        query = query.filter(TranslationProject.order_no.ilike(f"%{order_no}%"))
    if project_status:
        query = query.filter(TranslationProject.project_status == project_status)
    if client_short_name:
        query = query.filter(Client.client_short_name.ilike(f"%{client_short_name}%"))
    results = query.offset(skip).limit(limit).all()
    projects = []
    for project, short_name, code in results:
        project.client_short_name = short_name
        project.client_code = code
        projects.append(project)
    return projects


def count_translation_projects(
    db: Session,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None
) -> int:
    query = db.query(TranslationProject.id).outerjoin(Client, TranslationProject.client_id == Client.id)
    if created_by:
        query = query.filter(TranslationProject.created_by == created_by)
    if project_name:
        query = query.filter(TranslationProject.project_name.ilike(f"%{project_name}%"))
    if order_no:
        query = query.filter(TranslationProject.order_no.ilike(f"%{order_no}%"))
    if project_status:
        query = query.filter(TranslationProject.project_status == project_status)
    if client_short_name:
        query = query.filter(Client.client_short_name.ilike(f"%{client_short_name}%"))
    return query.count()


def create_translation_project(db: Session, project: TranslationProjectCreate) -> TranslationProject:
    order_no = generate_order_no(db)
    
    project_data = project.model_dump(exclude={'client_short_name', 'client_code'})
    
    # Try looking up client_id by client_short_name if provided and client_id is missing
    if project.client_short_name and not project.client_id:
        client = db.query(Client).filter(Client.client_short_name == project.client_short_name).first()
        if client:
            project_data['client_id'] = client.id
    elif project.client_code and not project.client_id:
        client = db.query(Client).filter(Client.client_code == project.client_code).first()
        if client:
            project_data['client_id'] = client.id

    db_project = TranslationProject(
        order_no=order_no,
        **project_data
    )
    db.add(db_project)
    db.flush()

    from workflow_crud import init_workflow

    init_workflow(db, db_project.id)
    db.refresh(db_project)
    return db_project


def update_translation_project(db: Session, project_id: UUID, project_update: TranslationProjectUpdate) -> Optional[TranslationProject]:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return None
    
    update_data = project_update.model_dump(exclude_unset=True, exclude={'client_short_name', 'client_code'})
    
    # Try looking up client_id by client_short_name if provided and client_id is not specifically being updated
    if project_update.client_short_name and 'client_id' not in update_data:
        client = db.query(Client).filter(Client.client_short_name == project_update.client_short_name).first()
        if client:
            update_data['client_id'] = client.id
    elif project_update.client_code and 'client_id' not in update_data:
        client = db.query(Client).filter(Client.client_code == project_update.client_code).first()
        if client:
            update_data['client_id'] = client.id

    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db.commit()
    db.refresh(db_project)
    
    # Reload with client_short_name
    return get_translation_project(db, project_id)


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



def get_users_by_role_names(db: Session, role_names: List[str]) -> List[AppUser]:
    normalized = [name for name in role_names if name]
    if not normalized:
        return []
    return (
        db.query(AppUser)
        .join(UserRole, UserRole.user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.role_name.in_(normalized), AppUser.is_active == True)
        .distinct(AppUser.id)
        .all()
    )


def get_notification(db: Session, notification_id: UUID) -> Optional[AppNotification]:
    return db.query(AppNotification).filter(AppNotification.id == notification_id).first()


def get_notifications(
    db: Session,
    recipient_user_id: UUID,
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
) -> List[AppNotification]:
    query = db.query(AppNotification).filter(AppNotification.recipient_user_id == recipient_user_id)
    if unread_only:
        query = query.filter(AppNotification.is_read == False)
    return query.order_by(AppNotification.created_at.desc()).offset(skip).limit(limit).all()


def count_unread_notifications(db: Session, recipient_user_id: UUID) -> int:
    return (
        db.query(AppNotification.id)
        .filter(
            AppNotification.recipient_user_id == recipient_user_id,
            AppNotification.is_read == False,
        )
        .count()
    )


def create_notification(
    db: Session,
    recipient_user_id: UUID,
    title: str,
    content: str,
    notification_type: str = 'workflow',
    related_project_id: Optional[UUID] = None,
    commit: bool = True,
) -> AppNotification:
    notification = AppNotification(
        recipient_user_id=recipient_user_id,
        title=title,
        content=content,
        notification_type=notification_type,
        related_project_id=related_project_id,
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    else:
        db.flush()
    return notification


def create_notifications_for_users(
    db: Session,
    recipient_user_ids: List[UUID],
    title: str,
    content: str,
    notification_type: str = 'workflow',
    related_project_id: Optional[UUID] = None,
    commit: bool = True,
) -> List[AppNotification]:
    unique_user_ids = []
    seen = set()
    for user_id in recipient_user_ids:
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        unique_user_ids.append(user_id)

    notifications = [
        AppNotification(
            recipient_user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            related_project_id=related_project_id,
        )
        for user_id in unique_user_ids
    ]
    if notifications:
        db.add_all(notifications)
        if commit:
            db.commit()
            for notification in notifications:
                db.refresh(notification)
        else:
            db.flush()
    return notifications


def mark_notification_read(db: Session, notification_id: UUID, recipient_user_id: UUID) -> Optional[AppNotification]:
    notification = (
        db.query(AppNotification)
        .filter(
            AppNotification.id == notification_id,
            AppNotification.recipient_user_id == recipient_user_id,
        )
        .first()
    )
    if not notification:
        return None
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = dt.datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, recipient_user_id: UUID) -> int:
    notifications = (
        db.query(AppNotification)
        .filter(
            AppNotification.recipient_user_id == recipient_user_id,
            AppNotification.is_read == False,
        )
        .all()
    )
    if not notifications:
        return 0
    now = dt.datetime.utcnow()
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
    db.commit()
    return len(notifications)


# ProjectFile CRUD
def get_project_file(db: Session, file_id: UUID) -> Optional[ProjectFile]:
    return db.query(ProjectFile).filter(ProjectFile.id == file_id).first()


def get_project_files_by_project(db: Session, translation_project_id: UUID, skip: int = 0, limit: int = 100) -> List[ProjectFile]:
    return (
        db.query(ProjectFile)
        .options(joinedload(ProjectFile.translation_project))
        .filter(ProjectFile.translation_project_id == translation_project_id)
        .offset(skip).limit(limit).all()
    )


def count_project_files_by_project(db: Session, translation_project_id: UUID) -> int:
    return db.query(ProjectFile.id).filter(ProjectFile.translation_project_id == translation_project_id).count()


def get_project_files(db: Session, skip: int = 0, limit: int = 100, order_no: Optional[str] = None) -> List[ProjectFile]:
    q = db.query(ProjectFile).options(joinedload(ProjectFile.translation_project))
    if order_no:
        q = q.join(ProjectFile.translation_project).filter(
            TranslationProject.order_no.ilike(f'%{order_no}%')
        )
    return q.offset(skip).limit(limit).all()


def count_project_files(db: Session, order_no: Optional[str] = None) -> int:
    q = db.query(ProjectFile.id)
    if order_no:
        q = q.join(ProjectFile.translation_project).filter(
            TranslationProject.order_no.ilike(f'%{order_no}%')
        )
    return q.count()


def create_project_file(db: Session, project_file: ProjectFileCreate) -> ProjectFile:
    db_file = ProjectFile(
        translation_project_id=project_file.translation_project_id,
        file_name=project_file.file_name,
        storage_path=project_file.storage_path,
        dispatch_path=project_file.dispatch_path,
        translation_path=project_file.translation_path,
        client_delivery_path=project_file.client_delivery_path,
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


def ensure_finance_record_for_project(db: Session, project_id: UUID, edited_by: Optional[UUID] = None) -> FinanceRecord:
    existing = db.query(FinanceRecord).filter(FinanceRecord.project_id == project_id).first()
    if existing:
        return existing

    record = FinanceRecord(project_id=project_id, edited_by=edited_by)
    db.add(record)
    db.flush()
    return record


# Consultation CRUD
import datetime as dt

def generate_consultation_code(db: Session) -> str:
    """
    生成咨询流水号
    格式: EQ-YYMMDD-NNNN (如 EQ-260309-0001)
    """
    today_str = dt.datetime.now().strftime("%y%m%d")
    prefix = f"EQ-{today_str}-"

    last_consultation = (
        db.query(Consultation)
        .filter(Consultation.consultation_code.like(f"EQ-{today_str}-%"))
        .order_by(Consultation.consultation_code.desc())
        .first()
    )

    if last_consultation and last_consultation.consultation_code:
        try:
            seq_str = last_consultation.consultation_code.split("-")[-1]
            last_seq = int(seq_str)
            new_seq = last_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1

    return f"{prefix}{new_seq:04d}"


def get_consultation(db: Session, consultation_id: UUID) -> Optional[Consultation]:
    result = db.query(Consultation, Client.client_code, Client.client_name, Client.client_short_name).outerjoin(Client, Consultation.client_id == Client.id).filter(Consultation.id == consultation_id).first()
    if not result:
        return None
    consultation, client_code, client_name, client_short_name = result
    consultation.client_code = client_code
    consultation.client_name = client_name
    consultation.client_short_name = client_short_name
    return consultation


def get_consultations(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None
) -> List[Consultation]:
    query = db.query(Consultation, Client.client_code, Client.client_name, Client.client_short_name).outerjoin(Client, Consultation.client_id == Client.id)
    
    if consultation_code:
        query = query.filter(Consultation.consultation_code.ilike(f"%{consultation_code}%"))
    if client_name:
        query = query.filter(Client.client_name.ilike(f"%{client_name}%"))
    if status:
        query = query.filter(Consultation.status == status)
        
    results = query.order_by(Consultation.created_at.desc()).offset(skip).limit(limit).all()
    
    consultations = []
    for consultation, client_code, db_client_name, client_short_name in results:
        consultation.client_code = client_code
        consultation.client_name = db_client_name
        consultation.client_short_name = client_short_name
        consultations.append(consultation)
    return consultations


def count_consultations(
    db: Session,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    query = db.query(Consultation.id).outerjoin(Client, Consultation.client_id == Client.id)
    if consultation_code:
        query = query.filter(Consultation.consultation_code.ilike(f"%{consultation_code}%"))
    if client_name:
        query = query.filter(Client.client_name.ilike(f"%{client_name}%"))
    if status:
        query = query.filter(Consultation.status == status)
    return query.count()


def create_consultation(db: Session, consultation: ConsultationCreate) -> Consultation:
    consultation_code = generate_consultation_code(db)

    db_consultation = Consultation(
        consultation_code=consultation_code,
        **consultation.model_dump(exclude={'consultation_code'})
    )
    db.add(db_consultation)
    db.commit()
    db.refresh(db_consultation)
    return db_consultation


def update_consultation(db: Session, consultation_id: UUID, consultation_update: ConsultationUpdate) -> Optional[Consultation]:
    db_consultation = get_consultation(db, consultation_id)
    if not db_consultation:
        return None
    for field, value in consultation_update.model_dump(exclude_unset=True).items():
        setattr(db_consultation, field, value)
    db.commit()
    db.refresh(db_consultation)
    return db_consultation


def delete_consultation(db: Session, consultation_id: UUID) -> bool:
    db_consultation = get_consultation(db, consultation_id)
    if not db_consultation:
        return False
    db.delete(db_consultation)
    db.commit()
    return True


# ============================================================
# TranslationSubOrder CRUD
# ============================================================

def generate_sub_order_no(db: Session, parent_project_id: UUID) -> str:
    """根据母订单的 order_no 自动生成子订单号，如 TP-20260302-0014.0001"""
    parent = db.query(TranslationProject).filter(TranslationProject.id == parent_project_id).first()
    if not parent:
        raise ValueError("母订单不存在")
    base_no = parent.order_no  # e.g. TP-20260302-0014

    # 查找当前最大子序号
    last = (
        db.query(TranslationSubOrder)
        .filter(TranslationSubOrder.parent_project_id == parent_project_id)
        .filter(TranslationSubOrder.sub_order_no.like(f"{base_no}.%"))
        .order_by(TranslationSubOrder.sub_order_no.desc())
        .first()
    )
    if last and last.sub_order_no:
        try:
            seq_str = last.sub_order_no.rsplit(".", 1)[-1]
            new_seq = int(seq_str) + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1

    return f"{base_no}.{new_seq:04d}"


def get_sub_order(db: Session, sub_order_id: UUID) -> Optional[TranslationSubOrder]:
    return db.query(TranslationSubOrder).filter(TranslationSubOrder.id == sub_order_id).first()


def get_sub_orders_by_project(db: Session, parent_project_id: UUID) -> List[TranslationSubOrder]:
    return (
        db.query(TranslationSubOrder)
        .filter(TranslationSubOrder.parent_project_id == parent_project_id)
        .order_by(TranslationSubOrder.sub_order_no)
        .all()
    )


def get_all_sub_orders(db: Session, skip: int = 0, limit: int = 200, sub_order_no: Optional[str] = None, project_name: Optional[str] = None) -> List[TranslationSubOrder]:
    q = db.query(TranslationSubOrder)
    if sub_order_no:
        q = q.filter(TranslationSubOrder.sub_order_no.ilike(f'%{sub_order_no}%'))
    if project_name:
        q = q.filter(TranslationSubOrder.sub_project_name.ilike(f'%{project_name}%'))
    return q.offset(skip).limit(limit).all()


def create_sub_order(db: Session, sub_order: TranslationSubOrderCreate) -> TranslationSubOrder:
    sub_order_no = sub_order.sub_order_no or generate_sub_order_no(db, sub_order.parent_project_id)
    data = sub_order.model_dump(exclude={'sub_order_no'})
    db_sub = TranslationSubOrder(sub_order_no=sub_order_no, **data)
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub


def update_sub_order(db: Session, sub_order_id: UUID, sub_order_update: TranslationSubOrderUpdate) -> Optional[TranslationSubOrder]:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return None
    for field, value in sub_order_update.model_dump(exclude_unset=True).items():
        setattr(db_sub, field, value)
    db.commit()
    db.refresh(db_sub)
    return db_sub


def delete_sub_order(db: Session, sub_order_id: UUID) -> bool:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return False
    db.delete(db_sub)
    db.commit()
    return True
