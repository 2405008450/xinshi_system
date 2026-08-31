from typing import List, Optional
from uuid import UUID
from datetime import date, datetime, time, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import Integer, String, and_, case, cast, exists as db_exists, func, or_

from models import AppUser, Role, TranslationProject, TranslationSubOrder, UserRole, ProjectFile, Client, ClientContact, SubClient, Translator, Consultation, FinanceRecord, AppNotification, ProjectRoleAssignment
from project_roles import (
    PROJECT_ROLE_BY_CODE,
    PROJECT_ROLE_NAME_BY_CODE,
    RELATION_ROLE_CODES,
)
from schemas import (
    AppUserCreate, AppUserUpdate,
    RoleCreate, RoleUpdate,
    TranslationProjectCreate, TranslationProjectUpdate,
    TranslationSubOrderCreate, TranslationSubOrderUpdate, TranslationSubOrderBulkCreate,
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
import re
from utils import generate_order_no
from department_utils import department_filter_values
from field_filtering import apply_scalar_specs
from concurrency import VERSION_FIELD, assert_fresh


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


def normalize_user_email(email: Optional[str]) -> Optional[str]:
    normalized = str(email or "").strip().casefold()
    return normalized or None


def get_user_by_email(
    db: Session,
    email: Optional[str],
    *,
    exclude_user_id: Optional[UUID] = None,
) -> Optional[AppUser]:
    normalized = normalize_user_email(email)
    if not normalized:
        return None
    query = db.query(AppUser).filter(
        func.lower(func.btrim(AppUser.email)) == normalized
    )
    if exclude_user_id is not None:
        query = query.filter(AppUser.id != exclude_user_id)
    return query.first()


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    department: Optional[str] = None,
) -> List[AppUser]:
    query = db.query(AppUser)
    if username:
        query = query.filter(AppUser.username.ilike(f"%{username}%"))
    if full_name:
        query = query.filter(AppUser.full_name.ilike(f"%{full_name}%"))
    if department:
        query = query.filter(AppUser.department.in_(department_filter_values(department)))
    return (
        query
        .order_by(AppUser.created_at.desc(), AppUser.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_users(
    db: Session,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    department: Optional[str] = None,
) -> int:
    query = db.query(AppUser.id)
    if username:
        query = query.filter(AppUser.username.ilike(f"%{username}%"))
    if full_name:
        query = query.filter(AppUser.full_name.ilike(f"%{full_name}%"))
    if department:
        query = query.filter(AppUser.department.in_(department_filter_values(department)))
    return query.count()


def create_user(db: Session, user: AppUserCreate) -> AppUser:
    hashed = hash_password(user.password)
    db_user = AppUser(
        username=user.username,
        password_hash=hashed,
        full_name=user.full_name,
        email=normalize_user_email(user.email),
        is_active=user.is_active,
        department=user.department,
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
    if "email" in update_data:
        update_data["email"] = normalize_user_email(update_data["email"])

    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user


def reset_user_password(db: Session, user_id: UUID, new_password: str) -> Optional[AppUser]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    db_user.password_hash = hash_password(new_password)
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
    return db.query(Role).options(selectinload(Role.role_permissions)).filter(Role.id == role_id).first()


def get_role_by_name(db: Session, role_name: str) -> Optional[Role]:
    return db.query(Role).filter(Role.role_name == role_name).first()


def get_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
    return db.query(Role).options(selectinload(Role.role_permissions)).offset(skip).limit(limit).all()


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
    date_text = today.strftime("%y%m%d")
    prefix = f"CL-{date_text}-"
    legacy_prefix = f"CL-{today.strftime('%y-%m%d')}-"
    last_records = [
        (
            db.query(Client)
            .filter(Client.client_code.like(f"{current_prefix}%"))
            .order_by(Client.client_code.desc())
            .first()
        )
        for current_prefix in (prefix, legacy_prefix)
    ]

    sequences = []
    for record in last_records:
        if not record or not record.client_code:
            continue
        try:
            sequences.append(int(record.client_code.rsplit("-", 1)[-1]))
        except ValueError:
            continue

    new_seq = max(sequences, default=0) + 1

    return f"{prefix}{new_seq:03d}"


def get_client(db: Session, client_id: UUID) -> Optional[Client]:
    return db.query(Client).options(selectinload(Client.sub_clients)).filter(Client.id == client_id).first()


def _apply_client_filters(
    query,
    *,
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    client_short_name: Optional[str] = None,
    english_name: Optional[str] = None,
    client_manager: Optional[str] = None,
    manager_contact: Optional[str] = None,
    field_level1: Optional[str] = None,
    field_level2: Optional[str] = None,
    country: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    client_status: Optional[str] = None,
    cooperation_start_date_from: Optional[date] = None,
    cooperation_start_date_to: Optional[date] = None,
    field_filters: Optional[dict] = None,
):
    """为客户列表和总数查询复用完全一致的筛选条件。"""
    text_filters = (
        (client_code, Client.client_code, SubClient.sub_client_code),
        (client_short_name, Client.client_short_name, SubClient.client_short_name),
        (client_manager, Client.client_manager, SubClient.client_manager),
        (manager_contact, Client.manager_contact, SubClient.manager_contact),
        (field_level1, Client.field_level1, SubClient.field_level1),
        (field_level2, Client.field_level2, SubClient.field_level2),
        (country, Client.country, SubClient.country),
        (province, Client.province, SubClient.province),
        (city, Client.city, SubClient.city),
        (district, Client.district, SubClient.district),
    )
    for value, client_column, sub_client_column in text_filters:
        if value and value.strip():
            pattern = f"%{value.strip()}%"
            query = query.filter(or_(
                client_column.ilike(pattern),
                Client.sub_clients.any(sub_client_column.ilike(pattern)),
            ))

    if client_name and client_name.strip():
        pattern = f"%{client_name.strip()}%"
        query = query.filter(or_(
            Client.client_name.ilike(pattern),
            Client.client_short_name.ilike(pattern),
            Client.sub_clients.any(or_(
                SubClient.client_name.ilike(pattern),
                SubClient.client_short_name.ilike(pattern),
            )),
        ))
    if english_name and english_name.strip():
        pattern = f"%{english_name.strip()}%"
        query = query.filter(or_(
            Client.english_name.ilike(pattern),
            Client.english_short_name.ilike(pattern),
            Client.sub_clients.any(or_(
                SubClient.english_name.ilike(pattern),
                SubClient.english_short_name.ilike(pattern),
            )),
        ))
    if client_status:
        query = query.filter(or_(
            Client.client_status == client_status,
            Client.sub_clients.any(SubClient.client_status == client_status),
        ))
    if cooperation_start_date_from:
        start_at = datetime.combine(cooperation_start_date_from, time.min)
        query = query.filter(or_(
            Client.cooperation_start_date >= start_at,
            Client.sub_clients.any(SubClient.cooperation_start_date >= start_at),
        ))
    if cooperation_start_date_to:
        end_at = datetime.combine(cooperation_start_date_to, time.max)
        query = query.filter(or_(
            Client.cooperation_start_date <= end_at,
            Client.sub_clients.any(SubClient.cooperation_start_date <= end_at),
        ))
    for field, descriptor in (field_filters or {}).items():
        if field == "cooperation_start_date":
            start_value, end_value = descriptor.get("from"), descriptor.get("to")
            if start_value:
                start_at = datetime.combine(date.fromisoformat(str(start_value)), time.min)
                query = query.filter(or_(Client.cooperation_start_date >= start_at, Client.sub_clients.any(SubClient.cooperation_start_date >= start_at)))
            if end_value:
                end_at = datetime.combine(date.fromisoformat(str(end_value)), time.max)
                query = query.filter(or_(Client.cooperation_start_date <= end_at, Client.sub_clients.any(SubClient.cooperation_start_date <= end_at)))
            continue
        if field == "client_status":
            values = descriptor.get("value") or []
            query = query.filter(or_(Client.client_status.in_(values), Client.sub_clients.any(SubClient.client_status.in_(values))))
            continue
        if field == "client_name" and descriptor.get("op") == "contains":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(
                Client.client_name.ilike(pattern), Client.client_short_name.ilike(pattern),
                Client.sub_clients.any(or_(SubClient.client_name.ilike(pattern), SubClient.client_short_name.ilike(pattern))),
            ))
            continue
        if field == "english_name" and descriptor.get("op") == "contains":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(
                Client.english_name.ilike(pattern), Client.english_short_name.ilike(pattern),
                Client.sub_clients.any(or_(SubClient.english_name.ilike(pattern), SubClient.english_short_name.ilike(pattern))),
            ))
            continue
        columns = {
            "client_code": (Client.client_code, SubClient.sub_client_code),
            "client_short_name": (Client.client_short_name, SubClient.client_short_name),
            "english_short_name": (Client.english_short_name, SubClient.english_short_name),
            "client_manager": (Client.client_manager, SubClient.client_manager),
            "manager_contact": (Client.manager_contact, SubClient.manager_contact),
            "field_level1": (Client.field_level1, SubClient.field_level1),
            "field_level2": (Client.field_level2, SubClient.field_level2),
            "country": (Client.country, SubClient.country),
            "province": (Client.province, SubClient.province),
            "city": (Client.city, SubClient.city),
            "district": (Client.district, SubClient.district),
            "remarks": (Client.remarks, SubClient.remarks),
        }.get(field)
        if columns and descriptor.get("op") == "contains":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(columns[0].ilike(pattern), Client.sub_clients.any(columns[1].ilike(pattern))))
    return query

def get_clients(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    client_short_name: Optional[str] = None,
    english_name: Optional[str] = None,
    client_manager: Optional[str] = None,
    manager_contact: Optional[str] = None,
    field_level1: Optional[str] = None,
    field_level2: Optional[str] = None,
    country: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    client_status: Optional[str] = None,
    cooperation_start_date_from: Optional[date] = None,
    cooperation_start_date_to: Optional[date] = None,
    frequent_first: bool = False,
    field_filters: Optional[dict] = None,
) -> List[Client]:
    query = db.query(Client).options(selectinload(Client.sub_clients))
    query = _apply_client_filters(
        query,
        client_code=client_code,
        client_name=client_name,
        client_short_name=client_short_name,
        english_name=english_name,
        client_manager=client_manager,
        manager_contact=manager_contact,
        field_level1=field_level1,
        field_level2=field_level2,
        country=country,
        province=province,
        city=city,
        district=district,
        client_status=client_status,
        cooperation_start_date_from=cooperation_start_date_from,
        cooperation_start_date_to=cooperation_start_date_to,
        field_filters=field_filters,
    )
    if frequent_first:
        cooperation_stats = (
            db.query(
                TranslationProject.client_id.label('client_id'),
                func.count(TranslationProject.id).label('project_count'),
            )
            .filter(TranslationProject.client_id.isnot(None))
            .group_by(TranslationProject.client_id)
            .subquery()
        )
        query = (
            query
            .outerjoin(cooperation_stats, cooperation_stats.c.client_id == Client.id)
            .order_by(
                func.coalesce(cooperation_stats.c.project_count, 0).desc(),
                Client.client_short_name.asc(),
            )
        )
    else:
        # 客户列表默认按创建时间倒序，确保新建客户出现在第一页顶部。
        query = query.order_by(Client.created_at.desc(), Client.id.desc())
    return query.offset(skip).limit(limit).all()


def count_clients(
    db: Session,
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    client_short_name: Optional[str] = None,
    english_name: Optional[str] = None,
    client_manager: Optional[str] = None,
    manager_contact: Optional[str] = None,
    field_level1: Optional[str] = None,
    field_level2: Optional[str] = None,
    country: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    client_status: Optional[str] = None,
    cooperation_start_date_from: Optional[date] = None,
    cooperation_start_date_to: Optional[date] = None,
    field_filters: Optional[dict] = None,
) -> int:
    query = db.query(Client.id)
    query = _apply_client_filters(
        query,
        client_code=client_code,
        client_name=client_name,
        client_short_name=client_short_name,
        english_name=english_name,
        client_manager=client_manager,
        manager_contact=manager_contact,
        field_level1=field_level1,
        field_level2=field_level2,
        country=country,
        province=province,
        city=city,
        district=district,
        client_status=client_status,
        cooperation_start_date_from=cooperation_start_date_from,
        cooperation_start_date_to=cooperation_start_date_to,
        field_filters=field_filters,
    )
    return query.count()


def create_client(
    db: Session, client: ClientCreate, idempotency_key: Optional[str] = None,
) -> Client:
    data = client.model_dump()
    if not data.get('client_code'):
        data['client_code'] = generate_client_code(db)
    db_client = Client(idempotency_key=idempotency_key, **data)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

def update_client(db: Session, client_id: UUID, client_update: ClientUpdate) -> Optional[Client]:
    db_client = get_client(db, client_id)
    if not db_client:
        return None
    update_data = client_update.model_dump(exclude_unset=True, exclude={VERSION_FIELD})
    assert_fresh(db_client, client_update.expected_updated_at)
    if "client_code" in update_data:
        next_code = (update_data["client_code"] or "").strip()
        if not next_code:
            raise ValueError("客户编号不能为空")
        update_data["client_code"] = next_code
    for field, value in update_data.items():
        setattr(db_client, field, value)
    db_client.updated_at = datetime.now()
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


def create_client_contact(
    db: Session, contact: ClientContactCreate, idempotency_key: Optional[str] = None,
) -> ClientContact:
    data = _fill_client_contact_fields(db, contact.model_dump())
    db_contact = ClientContact(idempotency_key=idempotency_key, **data)
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
    """生成子客户流水号，格式 CL-YY-MMDD-NNN.NNN"""
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

    return f"{base_no}.{new_seq:03d}"

def get_sub_client(db: Session, sub_client_id: UUID) -> Optional[SubClient]:
    return db.query(SubClient).filter(SubClient.id == sub_client_id).first()

def create_sub_client(
    db: Session, sub_client: SubClientCreate, idempotency_key: Optional[str] = None,
) -> SubClient:
    sub_code = sub_client.sub_client_code or generate_sub_client_code(db, sub_client.parent_client_id)
    data = sub_client.model_dump(exclude={'sub_client_code'})
    db_sub = SubClient(
        sub_client_code=sub_code, idempotency_key=idempotency_key, **data,
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

def update_sub_client(db: Session, sub_id: UUID, sub_update: SubClientUpdate) -> Optional[SubClient]:
    db_sub = get_sub_client(db, sub_id)
    if not db_sub:
        return None
    update_data = sub_update.model_dump(exclude_unset=True, exclude={VERSION_FIELD})
    assert_fresh(db_sub, sub_update.expected_updated_at)
    if "sub_client_code" in update_data:
        next_code = (update_data["sub_client_code"] or "").strip()
        if not next_code:
            raise ValueError("子客户编号不能为空")
        update_data["sub_client_code"] = next_code
    for field, value in update_data.items():
        setattr(db_sub, field, value)
    db_sub.updated_at = datetime.now()
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
    capability_type: Optional[str] = None,
    translator_code: Optional[str] = None,
    translator_name: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    languages: Optional[str] = None,
    translation_type: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    available_time_slot: Optional[str] = None,
    domain_keyword: Optional[str] = None,
    contact_keyword: Optional[str] = None,
    quality_score: Optional[str] = None,
    gender: Optional[str] = None,
    nationality: Optional[str] = None,
    can_cloud_edit: Optional[bool] = None,
    can_revision: Optional[bool] = None,
    default_priority_min: Optional[int] = None,
    default_priority_max: Optional[int] = None,
    daily_word_capacity_min: Optional[int] = None,
    daily_word_capacity_max: Optional[int] = None,
    stale_only: bool = False,
    stale_days: int = 4,
):
    if capability_type:
        from resource_models import ResourceCapability
        query = query.join(
            ResourceCapability,
            ResourceCapability.person_id == Translator.resource_person_id,
        ).filter(
            ResourceCapability.capability_type == capability_type,
            ResourceCapability.status == "active",
        )
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
    if contact_keyword and contact_keyword.strip():
        pattern = f"%{contact_keyword.strip()}%"
        query = query.filter(or_(
            Translator.contact_info.ilike(pattern),
            Translator.phone.ilike(pattern),
            Translator.phone2.ilike(pattern),
            Translator.email1.ilike(pattern),
            Translator.email2.ilike(pattern),
            Translator.other_contact.ilike(pattern),
        ))
    if quality_score and quality_score.strip():
        query = query.filter(Translator.quality_score.ilike(f"%{quality_score.strip()}%"))
    if gender and gender.strip():
        query = query.filter(Translator.gender.ilike(f"%{gender.strip()}%"))
    if nationality and nationality.strip():
        query = query.filter(Translator.nationality.ilike(f"%{nationality.strip()}%"))
    if can_cloud_edit is not None:
        query = query.filter(Translator.can_cloud_edit == can_cloud_edit)
    if can_revision is not None:
        query = query.filter(Translator.can_revision == can_revision)
    if default_priority_min is not None:
        query = query.filter(Translator.default_priority >= default_priority_min)
    if default_priority_max is not None:
        query = query.filter(Translator.default_priority <= default_priority_max)
    if daily_word_capacity_min is not None:
        query = query.filter(Translator.daily_word_capacity >= daily_word_capacity_min)
    if daily_word_capacity_max is not None:
        query = query.filter(Translator.daily_word_capacity <= daily_word_capacity_max)
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
    capability_type: Optional[str] = None,
    translator_code: Optional[str] = None,
    translator_name: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    languages: Optional[str] = None,
    translation_type: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    available_time_slot: Optional[str] = None,
    domain_keyword: Optional[str] = None,
    contact_keyword: Optional[str] = None,
    quality_score: Optional[str] = None,
    gender: Optional[str] = None,
    nationality: Optional[str] = None,
    can_cloud_edit: Optional[bool] = None,
    can_revision: Optional[bool] = None,
    default_priority_min: Optional[int] = None,
    default_priority_max: Optional[int] = None,
    daily_word_capacity_min: Optional[int] = None,
    daily_word_capacity_max: Optional[int] = None,
    stale_only: bool = False,
    stale_days: int = 4,
) -> List[Translator]:
    query = db.query(Translator)
    query = _apply_translator_filters(
        query,
        capability_type=capability_type,
        translator_code=translator_code,
        translator_name=translator_name,
        cooperation_type=cooperation_type,
        languages=languages,
        translation_type=translation_type,
        direction=direction,
        status=status,
        available_time_slot=available_time_slot,
        domain_keyword=domain_keyword,
        contact_keyword=contact_keyword,
        quality_score=quality_score,
        gender=gender,
        nationality=nationality,
        can_cloud_edit=can_cloud_edit,
        can_revision=can_revision,
        default_priority_min=default_priority_min,
        default_priority_max=default_priority_max,
        daily_word_capacity_min=daily_word_capacity_min,
        daily_word_capacity_max=daily_word_capacity_max,
        stale_only=stale_only,
        stale_days=stale_days,
    )
    return (
        query
        .order_by(
            Translator.availability_updated_at.desc().nullslast(),
            Translator.default_priority.asc(),
            Translator.translator_name.asc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

def count_translators(
    db: Session,
    capability_type: Optional[str] = None,
    translator_code: Optional[str] = None,
    translator_name: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    languages: Optional[str] = None,
    translation_type: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    available_time_slot: Optional[str] = None,
    domain_keyword: Optional[str] = None,
    contact_keyword: Optional[str] = None,
    quality_score: Optional[str] = None,
    gender: Optional[str] = None,
    nationality: Optional[str] = None,
    can_cloud_edit: Optional[bool] = None,
    can_revision: Optional[bool] = None,
    default_priority_min: Optional[int] = None,
    default_priority_max: Optional[int] = None,
    daily_word_capacity_min: Optional[int] = None,
    daily_word_capacity_max: Optional[int] = None,
    stale_only: bool = False,
    stale_days: int = 4,
) -> int:
    query = db.query(Translator.id)
    query = _apply_translator_filters(
        query,
        capability_type=capability_type,
        translator_code=translator_code,
        translator_name=translator_name,
        cooperation_type=cooperation_type,
        languages=languages,
        translation_type=translation_type,
        direction=direction,
        status=status,
        available_time_slot=available_time_slot,
        domain_keyword=domain_keyword,
        contact_keyword=contact_keyword,
        quality_score=quality_score,
        gender=gender,
        nationality=nationality,
        can_cloud_edit=can_cloud_edit,
        can_revision=can_revision,
        default_priority_min=default_priority_min,
        default_priority_max=default_priority_max,
        daily_word_capacity_min=daily_word_capacity_min,
        daily_word_capacity_max=daily_word_capacity_max,
        stale_only=stale_only,
        stale_days=stale_days,
    )
    return query.count()


def _parse_legacy_cloud_revision(value: Optional[str]) -> tuple[Optional[bool], Optional[bool]]:
    text = (value or "").strip()
    if not text:
        return None, None
    parts = [part.strip() for part in text.split("/")]
    while len(parts) < 2:
        parts.append("")

    def parse_bool(part: str) -> Optional[bool]:
        if part in {"可", "是", "true", "True", "1"}:
            return True
        if part in {"否", "不可", "不可以", "false", "False", "0"}:
            return False
        return None

    return parse_bool(parts[0]), parse_bool(parts[1])


def _parse_legacy_daily_rate(value: Optional[str]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    text = (value or "").strip()
    if not text:
        return None, None, None
    parts = [part.strip() for part in text.split("/")]
    while len(parts) < 3:
        parts.append("")

    def parse_int(part: str) -> Optional[int]:
        if not part:
            return None
        try:
            return int(float(part))
        except (TypeError, ValueError):
            return None

    return parse_int(parts[0]), parse_int(parts[1]), parse_int(parts[2])


def _normalize_translator_payload(payload: dict, current: Optional[Translator] = None) -> dict:
    data = dict(payload)

    if "cloud_revision" in data and "can_cloud_edit" not in data and "can_revision" not in data:
        parsed_cloud_edit, parsed_revision = _parse_legacy_cloud_revision(data.get("cloud_revision"))
        if parsed_cloud_edit is not None:
            data["can_cloud_edit"] = parsed_cloud_edit
        if parsed_revision is not None:
            data["can_revision"] = parsed_revision
    data.pop("cloud_revision", None)

    if "daily_rate" in data and not {"daily_accept_count", "hourly_speed", "daily_word_capacity"} & data.keys():
        parsed_accept_count, parsed_hourly_speed, parsed_daily_capacity = _parse_legacy_daily_rate(data.get("daily_rate"))
        if parsed_accept_count is not None:
            data["daily_accept_count"] = parsed_accept_count
        if parsed_hourly_speed is not None:
            data["hourly_speed"] = parsed_hourly_speed
        if parsed_daily_capacity is not None:
            data["daily_word_capacity"] = parsed_daily_capacity
    data.pop("daily_rate", None)

    return data


def create_translator(db: Session, translator: TranslatorCreate) -> Translator:
    payload = _normalize_translator_payload(translator.model_dump())
    availability_fields = {
        "available_time_slot", "schedule_remarks", "overdue_count",
        "daily_accept_count", "hourly_speed", "daily_word_capacity",
        "can_cloud_edit", "can_revision",
    }
    if any(payload.get(field) not in (None, "") for field in availability_fields):
        payload["availability_updated_at"] = dt.datetime.utcnow()
    db_translator = Translator(**payload)
    db.add(db_translator)
    db.flush()
    from resource_service import sync_legacy_translator_to_talent
    sync_legacy_translator_to_talent(db, db_translator)
    db.commit()
    db.refresh(db_translator)
    return db_translator

def update_translator(db: Session, translator_id: UUID, translator_update: TranslatorUpdate) -> Optional[Translator]:
    db_translator = get_translator(db, translator_id)
    if not db_translator:
        return None
    payload = _normalize_translator_payload(translator_update.model_dump(exclude_unset=True), current=db_translator)
    availability_fields = {
        "available_time_slot", "schedule_remarks", "overdue_count",
        "daily_accept_count", "hourly_speed", "daily_word_capacity",
        "can_cloud_edit", "can_revision",
    }
    if any(field in payload and payload[field] != getattr(db_translator, field) for field in availability_fields):
        payload["availability_updated_at"] = dt.datetime.utcnow()
    for field, value in payload.items():
        setattr(db_translator, field, value)
    from resource_service import sync_legacy_translator_to_talent
    sync_legacy_translator_to_talent(db, db_translator)
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


def _attach_manuscript_assignees(
    db: Session,
    *,
    projects: Optional[List[TranslationProject]] = None,
    sub_orders: Optional[List[TranslationSubOrder]] = None,
) -> None:
    """把有效派稿明细汇总到项目响应，不再依赖单一 translator_id。"""
    projects = projects or []
    sub_orders = sub_orders or []
    project_ids = {project.id for project in projects}
    project_ids.update(sub_order.parent_project_id for sub_order in sub_orders)
    if not project_ids:
        return

    from manuscript_models import ManuscriptArrangement, ManuscriptDispatch

    rows = (
        db.query(ManuscriptArrangement)
        .join(
            ManuscriptDispatch,
            ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
        )
        .filter(
            ManuscriptArrangement.translation_project_id.in_(project_ids),
            ManuscriptArrangement.status != "cancelled",
            ManuscriptDispatch.status != "cancelled",
            ManuscriptDispatch.confirmed_at.is_not(None),
        )
        .order_by(ManuscriptArrangement.created_at.asc())
        .all()
    )
    grouped = {}
    for row in rows:
        key = (row.translation_project_id, row.sub_order_id)
        grouped.setdefault(key, {})[row.translator_id] = {
            "arrangement_id": row.id,
            "dispatch_id": row.dispatch_id,
            "translator_id": row.translator_id,
            "translator_name": row.translator_name_snapshot,
            "cooperation_type": row.cooperation_type_snapshot,
            "status": row.status,
            "planned": {},
            "actual": {},
            "translation_scope": row.translation_scope,
        }

    for project in projects:
        project.assigned_translators = list(
            grouped.get((project.id, None), {}).values()
        )
        for sub_order in project.sub_orders:
            sub_order.assigned_translators = list(
                grouped.get((project.id, sub_order.id), {}).values()
            )
    for sub_order in sub_orders:
        sub_order.assigned_translators = list(
            grouped.get((sub_order.parent_project_id, sub_order.id), {}).values()
        )
    _attach_word_count_matrices(db, projects=projects, sub_orders=sub_orders)


def _attach_word_count_matrices(
    db: Session,
    *,
    projects: Optional[List[TranslationProject]] = None,
    sub_orders: Optional[List[TranslationSubOrder]] = None,
) -> None:
    """为项目响应批量挂载矩阵数据，并补齐每位译员的预定/实际矩阵。"""
    from word_count_models import WordCountMetric

    metric_types = ("words", "characters_no_spaces", "cjk_chars_korean_words", "foreign_words", "documents", "pages")
    dimensions = ("company", "customer", "translator_estimate")

    def empty_values():
        return {metric_type: None for metric_type in metric_types}

    def empty_matrix():
        return {dimension: empty_values() for dimension in dimensions}

    projects = projects or []
    explicit_sub_orders = sub_orders or []
    all_sub_orders = list(explicit_sub_orders)
    for project in projects:
        all_sub_orders.extend(list(getattr(project, "sub_orders", []) or []))

    project_map = {project.id: project for project in projects}
    sub_order_map = {sub_order.id: sub_order for sub_order in all_sub_orders}
    for project in project_map.values():
        project.word_count_matrix = empty_matrix()
    for sub_order in sub_order_map.values():
        sub_order.word_count_matrix = empty_matrix()

    arrangement_map = {}
    for owner in [*project_map.values(), *sub_order_map.values()]:
        for assignment in getattr(owner, "assigned_translators", []) or []:
            assignment["planned"] = empty_values()
            assignment["actual"] = empty_values()
            arrangement_id = assignment.get("arrangement_id")
            if arrangement_id:
                arrangement_map[arrangement_id] = assignment

    filters = []
    if project_map:
        filters.append(WordCountMetric.project_id.in_(project_map))
    if sub_order_map:
        filters.append(WordCountMetric.sub_order_id.in_(sub_order_map))
    if arrangement_map:
        filters.append(WordCountMetric.arrangement_id.in_(arrangement_map))
    if not filters:
        return

    for metric in db.query(WordCountMetric).filter(or_(*filters)).all():
        if metric.project_id in project_map and metric.dimension in dimensions:
            project_map[metric.project_id].word_count_matrix[metric.dimension][metric.metric_type] = metric.count_value
        elif metric.sub_order_id in sub_order_map and metric.dimension in dimensions:
            sub_order_map[metric.sub_order_id].word_count_matrix[metric.dimension][metric.metric_type] = metric.count_value
        elif metric.arrangement_id in arrangement_map and metric.dimension in {"planned", "actual"}:
            arrangement_map[metric.arrangement_id][metric.dimension][metric.metric_type] = metric.count_value


def _attach_project_client_fields(project: TranslationProject) -> None:
    """返回项目实际关联客户的信息；子客户缺失的负责人信息回退到母客户。"""
    parent_client = project.client
    sub_client = project.sub_client
    selected_client = sub_client or parent_client

    project.client_short_name = selected_client.client_short_name if selected_client else None
    project.client_code = (
        sub_client.sub_client_code
        if sub_client
        else (parent_client.client_code if parent_client else None)
    )
    project.client_manager = (
        (sub_client.client_manager if sub_client else None)
        or (parent_client.client_manager if parent_client else None)
    )
    project.manager_contact = (
        (sub_client.manager_contact if sub_client else None)
        or (parent_client.manager_contact if parent_client else None)
    )


def _attach_project_file_detail_fields(project: TranslationProject) -> None:
    """将唯一项目文件的分类字段挂载到项目响应，供“查看详情”统一展示。"""
    project_file = project.project_file[0] if project.project_file else None
    field_mapping = {
        'project_file_name': 'file_name',
        'project_file_translation_domain_level1': 'translation_domain_level1',
        'project_file_translation_domain_level2': 'translation_domain_level2',
        'project_file_type_level1': 'file_type',
        'project_file_type_level2': 'file_type_secondary',
        'project_file_format': 'file_format',
        'project_file_attribute_level1': 'file_attribute_level1',
        'project_file_attribute_level2': 'file_attribute_level2',
        'project_file_attribute_level3': 'file_attribute_level3',
        'project_file_difficulty': 'file_difficulty',
    }
    for response_field, file_field in field_mapping.items():
        setattr(
            project,
            response_field,
            getattr(project_file, file_field, None) if project_file else None,
        )


def _normalize_project_business_details(
    data: dict,
    existing: Optional[TranslationProject] = None,
) -> None:
    """清理项目合同、报价单和客户要求字段，保持报价单布尔状态一致。"""
    text_fields = (
        'project_contract_type',
        'project_contract_status',
        'quotation_status',
        'quotation_path',
        'customer_requirement_professional',
        'customer_requirement_special',
    )
    for field in text_fields:
        if field in data and isinstance(data[field], str):
            data[field] = data[field].strip() or None

    quotation_required = data.get(
        'quotation_required',
        existing.quotation_required if existing else False,
    )
    if not quotation_required:
        data['quotation_status'] = None
        data['quotation_path'] = None


def _resolve_project_client_link(
    db: Session,
    client_id: Optional[UUID],
    sub_client_id: Optional[UUID],
) -> Optional[UUID]:
    """校验子客户归属，并返回应写入项目的母客户 ID。"""
    if not sub_client_id:
        return client_id

    sub_client = db.query(SubClient).filter(SubClient.id == sub_client_id).first()
    if not sub_client:
        raise ValueError("所选子客户不存在")
    if client_id and sub_client.parent_client_id != client_id:
        raise ValueError("所选子客户不属于当前母客户")
    return sub_client.parent_client_id


def _resolve_or_create_project_client(
    db: Session,
    client_short_name: Optional[str],
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    manager_contact: Optional[str] = None,
) -> tuple[Optional[UUID], Optional[UUID], bool]:
    """按简称/编号关联已有客户；简称不存在时创建一条待完善的母客户记录。"""
    normalized_short_name = (client_short_name or "").strip()
    normalized_client_code = (client_code or "").strip()
    normalized_client_name = (client_name or "").strip()
    normalized_manager_contact = (manager_contact or "").strip()

    if normalized_short_name:
        short_name_key = normalized_short_name.lower()
        client = (
            db.query(Client)
            .filter(func.lower(func.trim(Client.client_short_name)) == short_name_key)
            .order_by(Client.created_at.asc(), Client.id.asc())
            .first()
        )
        if client:
            return client.id, None, False

        sub_client = (
            db.query(SubClient)
            .filter(func.lower(func.trim(SubClient.client_short_name)) == short_name_key)
            .order_by(SubClient.created_at.asc(), SubClient.id.asc())
            .first()
        )
        if sub_client:
            return sub_client.parent_client_id, sub_client.id, False

    if normalized_client_code:
        client_code_key = normalized_client_code.lower()
        client = (
            db.query(Client)
            .filter(func.lower(func.trim(Client.client_code)) == client_code_key)
            .first()
        )
        if client:
            return client.id, None, False

        sub_client = (
            db.query(SubClient)
            .filter(func.lower(func.trim(SubClient.sub_client_code)) == client_code_key)
            .first()
        )
        if sub_client:
            return sub_client.parent_client_id, sub_client.id, False

    if not normalized_short_name:
        return None, None, False

    client = Client(
        client_code=generate_client_code(db),
        client_name=normalized_client_name or normalized_short_name,
        client_short_name=normalized_short_name,
        manager_contact=normalized_manager_contact or None,
        client_status="pending",
    )
    db.add(client)
    db.flush()
    return client.id, None, True


def _validate_project_manager(db: Session, project_manager_id: Optional[UUID]) -> None:
    """项目管理主负责人必须是启用中的“项目经理”角色用户。"""
    if not project_manager_id:
        return
    manager = db.query(AppUser).filter(
        AppUser.id == project_manager_id,
        AppUser.is_active == True,
    ).first()
    if not manager:
        raise ValueError("所选项目经理不存在或已停用")
    if "项目经理" not in get_user_roles_with_role_names(db, manager.id):
        raise ValueError("管理主负责人必须绑定“项目经理”角色用户")


def _validate_project_manager_assignable(db: Session, project_manager_id: Optional[UUID]) -> None:
    """项目经理新获分配时还必须处于可接收任务状态。"""
    _validate_project_manager(db, project_manager_id)
    if project_manager_id:
        from leave_service import ensure_user_assignable
        ensure_user_assignable(db, project_manager_id)


def _normalize_project_role_assignments(role_assignments) -> dict[str, Optional[UUID]]:
    """校验并规范项目角色请求；同一角色只能出现一次。"""
    normalized: dict[str, Optional[UUID]] = {}
    for item in role_assignments or []:
        data = item.model_dump() if hasattr(item, 'model_dump') else dict(item)
        role_code = data.get('role_code')
        if role_code not in PROJECT_ROLE_BY_CODE:
            raise ValueError(f"不支持的项目角色：{role_code or '-'}")
        if role_code in normalized:
            raise ValueError(f"项目角色不能重复：{PROJECT_ROLE_NAME_BY_CODE[role_code]}")
        normalized[role_code] = data.get('assignee_id')
    return normalized


def _validate_project_role_assignee(
    db: Session,
    role_code: str,
    assignee_id: Optional[UUID],
    *,
    require_assignable: bool,
) -> None:
    if not assignee_id:
        return
    role_name = PROJECT_ROLE_NAME_BY_CODE[role_code]
    user = db.query(AppUser).filter(
        AppUser.id == assignee_id,
        AppUser.is_active == True,
    ).first()
    if not user:
        raise ValueError(f"所选{role_name}不存在或已停用")
    if role_name not in get_user_roles_with_role_names(db, user.id):
        raise ValueError(f"{role_name}负责人必须拥有“{role_name}”系统角色")
    if require_assignable:
        from leave_service import ensure_user_assignable
        ensure_user_assignable(db, user.id)


def _sync_project_role_assignments(
    db: Session,
    project: TranslationProject,
    role_assignments,
) -> None:
    """以提交列表替换三类关系角色；项目经理仅在列表明确出现时同步。"""
    normalized = _normalize_project_role_assignments(role_assignments)

    if 'project_manager' in normalized:
        manager_id = normalized['project_manager']
        if manager_id != project.project_manager_id:
            _validate_project_manager_assignable(db, manager_id)
        else:
            _validate_project_manager(db, manager_id)
        project.project_manager_id = manager_id

    current = {
        item.role_code: item for item in (project.project_role_assignments or [])
    }
    for role_code in RELATION_ROLE_CODES:
        target_id = normalized.get(role_code)
        existing = current.get(role_code)
        existing_id = existing.assignee_id if existing else None
        if target_id == existing_id:
            _validate_project_role_assignee(
                db, role_code, target_id, require_assignable=False
            )
            continue
        _validate_project_role_assignee(
            db, role_code, target_id, require_assignable=bool(target_id)
        )
        if target_id is None:
            if existing:
                db.delete(existing)
            continue
        if existing:
            existing.assignee_id = target_id
            existing.updated_at = datetime.now()
        else:
            db.add(ProjectRoleAssignment(
                translation_project_id=project.id,
                role_code=role_code,
                assignee_id=target_id,
            ))


def build_auto_project_name(
    client_short_name: Optional[str],
    sub_order_count: int = 0,
    current_time: Optional[datetime] = None,
    language_pair: Optional[str] = None,
    customer_deadline_time: Optional[datetime | str] = None,
) -> str:
    """按客户、建项日期、翻译方向和客户交稿时间生成项目名称。"""
    normalized_short_name = (client_short_name or "").strip()
    if not normalized_short_name:
        return ""

    date_text = (current_time or datetime.now()).strftime("%y%m%d")
    parts = [normalized_short_name, date_text]
    normalized_language_pair = (language_pair or "").strip()
    if normalized_language_pair:
        parts.append(normalized_language_pair)
    deadline = customer_deadline_time
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError:
            deadline = None
    if deadline:
        parts.append(f'{deadline:%Y%m%d-%H:%M}回稿')
    base_name = "-".join(parts)
    return f"{base_name}-{sub_order_count}批" if sub_order_count > 0 else base_name


def _is_auto_project_name(
    project_name: Optional[str],
    client_short_name: Optional[str],
) -> bool:
    """判断当前名称是否仍遵循自动命名格式，避免覆盖人工修改。"""
    normalized_project_name = (project_name or "").strip()
    normalized_short_name = (client_short_name or "").strip()
    prefix = f"{normalized_short_name}-"
    if not normalized_short_name or not normalized_project_name.startswith(prefix):
        return False

    suffix = normalized_project_name[len(prefix):]
    if len(suffix) == 6 and suffix.isdigit():
        return True
    # 翻译方向本身可能包含连接符，因此只固定首尾结构。
    if re.fullmatch(r"\d{6}-.+-\d{8}-\d{2}:?\d{2}回稿(?:-\d+批)?", suffix):
        return True
    if not suffix.endswith("批"):
        return False

    date_text, separator, batch_text = suffix[:-1].partition("-")
    return (
        separator == "-"
        and len(date_text) == 6
        and date_text.isdigit()
        and batch_text.isdigit()
        and int(batch_text) > 0
    )


def _sync_project_name_with_sub_order_count(
    db: Session,
    project_id: UUID,
    current_time: Optional[datetime] = None,
) -> None:
    """子订单数量变化后，同步母项目名称中的批次。"""
    project = (
        db.query(TranslationProject)
        .options(
            joinedload(TranslationProject.client),
            joinedload(TranslationProject.sub_client),
        )
        .filter(
            TranslationProject.id == project_id,
            TranslationProject.annotation_migrated_at.is_(None),
        )
        .first()
    )
    if not project:
        return

    selected_client = project.sub_client or project.client
    client_short_name = selected_client.client_short_name if selected_client else None
    sub_order_count = (
        db.query(func.count(TranslationSubOrder.id))
        .filter(TranslationSubOrder.parent_project_id == project_id)
        .scalar()
        or 0
    )
    generated_name = build_auto_project_name(
        client_short_name,
        sub_order_count,
        current_time,
        project.language_pair,
        project.customer_deadline_time,
    )
    if generated_name and (
        not project.project_name
        or _is_auto_project_name(project.project_name, client_short_name)
    ):
        project.project_name = generated_name


def get_translation_project(db: Session, project_id: UUID) -> Optional[TranslationProject]:
    project = (
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.client),
            selectinload(TranslationProject.sub_client),
            selectinload(TranslationProject.translator),
            selectinload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .selectinload(ProjectRoleAssignment.assignee),
            selectinload(TranslationProject.project_file),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
        )
        .filter(
            TranslationProject.id == project_id,
            TranslationProject.annotation_migrated_at.is_(None),
        )
        .first()
    )
    if not project:
        return None
    _attach_project_client_fields(project)
    _attach_project_file_detail_fields(project)
    _attach_manuscript_assignees(db, projects=[project])
    return project


def get_translation_project_by_no(db: Session, order_no: str) -> Optional[TranslationProject]:
    project = (
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.client),
            selectinload(TranslationProject.sub_client),
            selectinload(TranslationProject.translator),
            selectinload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .selectinload(ProjectRoleAssignment.assignee),
            selectinload(TranslationProject.project_file),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
        )
        .filter(
            TranslationProject.order_no == order_no,
            TranslationProject.annotation_migrated_at.is_(None),
        )
        .first()
    )
    if not project:
        return None
    _attach_project_client_fields(project)
    _attach_project_file_detail_fields(project)
    _attach_manuscript_assignees(db, projects=[project])
    return project


def _apply_translation_project_filters(
    query,
    *,
    keyword: Optional[str] = None,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None,
    task_type: Optional[str] = None,
    service_content: Optional[str] = None,
    priority: Optional[str] = None,
    project_manager_id: Optional[UUID] = None,
    customer_deadline_date_start: Optional[date] = None,
    customer_deadline_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    field_filters: Optional[dict] = None,
):
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            TranslationProject.order_no.ilike(pattern),
            TranslationProject.project_name.ilike(pattern),
            TranslationProject.customer_order_no.ilike(pattern),
            Client.client_name.ilike(pattern),
            Client.client_short_name.ilike(pattern),
            SubClient.client_name.ilike(pattern),
            SubClient.client_short_name.ilike(pattern),
        ))
    if created_by:
        query = query.filter(TranslationProject.created_by == created_by)
    if project_name:
        query = query.filter(TranslationProject.project_name.ilike(f"%{project_name}%"))
    if order_no:
        query = query.filter(TranslationProject.order_no.ilike(f"%{order_no}%"))
    if project_status:
        query = query.filter(TranslationProject.project_status == project_status)
    if client_short_name:
        pattern = f"%{client_short_name}%"
        query = query.filter(or_(
            Client.client_short_name.ilike(pattern),
            SubClient.client_short_name.ilike(pattern),
        ))
    if task_type:
        query = query.filter(TranslationProject.task_type == task_type)
    if service_content:
        query = query.filter(TranslationProject.service_content == service_content)
    if priority:
        query = query.filter(TranslationProject.priority == priority)
    if project_manager_id:
        query = query.filter(TranslationProject.project_manager_id == project_manager_id)
    for field, start_value, end_value in (
        (TranslationProject.customer_deadline_time, customer_deadline_date_start, customer_deadline_date_end),
        (TranslationProject.created_at, created_date_start, created_date_end),
    ):
        if start_value:
            query = query.filter(field >= datetime.combine(start_value, time.min))
        if end_value:
            query = query.filter(field <= datetime.combine(end_value, time.max))
    field_filters = field_filters or {}
    query = apply_scalar_specs(query, field_filters, {
        "order_no": (TranslationProject.order_no, "string"),
        "project_name": (TranslationProject.project_name, "string"),
        "service_content": (TranslationProject.service_content, "string"),
        "task_type": (TranslationProject.task_type, "string"),
        "customer_order_no": (TranslationProject.customer_order_no, "string"),
        "project_manager_id": (TranslationProject.project_manager_id, "uuid"),
        "project_status": (TranslationProject.project_status, "string"),
        "file_type_secondary": (TranslationProject.file_type_secondary, "string"),
        "project_contract_type": (TranslationProject.project_contract_type, "string"),
        "project_contract_status": (TranslationProject.project_contract_status, "string"),
        "quotation_required": (TranslationProject.quotation_required, "boolean"),
        "quotation_status": (TranslationProject.quotation_status, "string"),
        "customer_requirement_professional": (TranslationProject.customer_requirement_professional, "string"),
        "customer_requirement_special": (TranslationProject.customer_requirement_special, "string"),
        "language_pair": (TranslationProject.language_pair, "string"),
        "priority": (TranslationProject.priority, "string"),
        "customer_reception_time": (TranslationProject.customer_reception_time, "datetime"),
        "customer_deadline_time": (TranslationProject.customer_deadline_time, "datetime"),
        "sent_to_client_time": (TranslationProject.sent_to_client_time, "datetime"),
        "major_project_manager_confirmation": (TranslationProject.major_project_manager_confirmation, "string"),
        "translator_id": (TranslationProject.translator_id, "uuid"),
        "translator_assignment_time": (TranslationProject.translator_assignment_time, "datetime"),
        "client_feedback": (TranslationProject.client_feedback, "string"),
        "created_at": (TranslationProject.created_at, "datetime"),
        "updated_at": (TranslationProject.updated_at, "datetime"),
        "pm_confirmed_by": (TranslationProject.pm_confirmed_by, "uuid"),
    })
    word_count_descriptor = field_filters.get("word_count", {})
    word_count_dimension = field_filters.get("word_count_dimension", {})
    word_count_metric_type = field_filters.get("word_count_metric_type", {})
    if word_count_descriptor or word_count_dimension or word_count_metric_type:
        from word_count_models import WordCountMetric
        conditions = [WordCountMetric.project_id == TranslationProject.id]
        if word_count_dimension:
            conditions.append(WordCountMetric.dimension.in_(word_count_dimension.get("value") or []))
        if word_count_metric_type:
            conditions.append(WordCountMetric.metric_type.in_(word_count_metric_type.get("value") or []))
        if word_count_descriptor.get("min") not in (None, ""):
            conditions.append(WordCountMetric.count_value >= int(word_count_descriptor["min"]))
        if word_count_descriptor.get("max") not in (None, ""):
            conditions.append(WordCountMetric.count_value <= int(word_count_descriptor["max"]))
        query = query.filter(db_exists().where(and_(*conditions)))

    for field, descriptor in field_filters.items():
        if field in {"client_short_name", "client_code", "client_manager", "manager_contact"}:
            parent_column, sub_column = {
                "client_short_name": (Client.client_short_name, SubClient.client_short_name),
                "client_code": (Client.client_code, SubClient.sub_client_code),
                "client_manager": (Client.client_manager, SubClient.client_manager),
                "manager_contact": (Client.manager_contact, SubClient.manager_contact),
            }[field]
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(parent_column.ilike(pattern), sub_column.ilike(pattern)))
        elif field in {"word_count", "word_count_dimension", "word_count_metric_type"}:
            continue
        elif field == "translator_name":
            if descriptor.get("op") != "contains":
                raise HTTPException(status_code=422, detail="译员姓名只支持包含筛选")
            keyword = str(descriptor.get("value") or "").strip()
            if keyword:
                from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
                pattern = f"%{keyword}%"
                confirmed_arrangement = db_exists().where(and_(
                    ManuscriptArrangement.translation_project_id == TranslationProject.id,
                    ManuscriptArrangement.sub_order_id.is_(None),
                    ManuscriptArrangement.status != "cancelled",
                    ManuscriptArrangement.translator_name_snapshot.ilike(pattern),
                    ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
                    ManuscriptDispatch.status != "cancelled",
                    ManuscriptDispatch.confirmed_at.is_not(None),
                ))
                query = query.filter(or_(
                    TranslationProject.translator.has(Translator.translator_name.ilike(pattern)),
                    confirmed_arrangement,
                ))
        elif field in {"project_specialist_name", "project_assistant_name", "layout_specialist_name"}:
            role_code = {
                "project_specialist_name": "project_specialist",
                "project_assistant_name": "project_assistant",
                "layout_specialist_name": "layout_specialist",
            }[field]
            keyword = str(descriptor.get("value") or "").strip()
            query = query.filter(TranslationProject.project_role_assignments.any(and_(
                ProjectRoleAssignment.role_code == role_code,
                ProjectRoleAssignment.assignee.has(or_(
                    AppUser.full_name.ilike(f"%{keyword}%"), AppUser.username.ilike(f"%{keyword}%")
                )),
            )))
        elif field.startswith("project_file_"):
            file_column = {
                "project_file_translation_domain_level1": ProjectFile.translation_domain_level1,
                "project_file_translation_domain_level2": ProjectFile.translation_domain_level2,
                "project_file_type_level1": ProjectFile.file_type,
                "project_file_type_level2": ProjectFile.file_type_secondary,
                "project_file_format": ProjectFile.file_format,
                "project_file_attribute_level1": ProjectFile.file_attribute_level1,
                "project_file_attribute_level2": ProjectFile.file_attribute_level2,
                "project_file_attribute_level3": ProjectFile.file_attribute_level3,
                "project_file_difficulty": ProjectFile.file_difficulty,
            }[field]
            keyword = str(descriptor.get("value") or "").strip()
            query = query.filter(TranslationProject.project_file.any(file_column.ilike(f"%{keyword}%")))
        elif field in {"translator_delivery_progress", "pre_review_qc_progress", "review1_progress", "review2_progress", "post_review_qc_progress", "layout_progress", "consolidation_progress"}:
            expression = getattr(TranslationProject, field)
            numeric = cast(func.nullif(func.replace(expression, "%", ""), ""), Integer)
            if descriptor.get("min") not in (None, ""):
                query = query.filter(numeric >= int(descriptor["min"]))
            if descriptor.get("max") not in (None, ""):
                query = query.filter(numeric <= int(descriptor["max"]))
    return query


def get_translation_projects(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None,
    task_type: Optional[str] = None,
    service_content: Optional[str] = None,
    priority: Optional[str] = None,
    project_manager_id: Optional[UUID] = None,
    customer_deadline_date_start: Optional[date] = None,
    customer_deadline_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    sort: Optional[str] = None,
    field_filters: Optional[dict] = None,
) -> List[TranslationProject]:
    query = (
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.client),
            selectinload(TranslationProject.sub_client),
            selectinload(TranslationProject.translator),
            selectinload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .selectinload(ProjectRoleAssignment.assignee),
            selectinload(TranslationProject.project_file),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
        )
        .outerjoin(Client, TranslationProject.client_id == Client.id)
        .outerjoin(SubClient, TranslationProject.sub_client_id == SubClient.id)
        .filter(TranslationProject.annotation_migrated_at.is_(None))
    )
    query = _apply_translation_project_filters(
        query,
        keyword=keyword,
        created_by=created_by,
        project_name=project_name,
        order_no=order_no,
        project_status=project_status,
        client_short_name=client_short_name,
        task_type=task_type,
        service_content=service_content,
        priority=priority,
        project_manager_id=project_manager_id,
        customer_deadline_date_start=customer_deadline_date_start,
        customer_deadline_date_end=customer_deadline_date_end,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        field_filters=field_filters,
    )
    if sort in {"order_no_desc", "unfinished_first_order_no_desc"}:
        # 兼容 TP-YYMMDD-NNN 与历史 TP-YYYYMMDD-NNN；异常订单号回退到创建时间。
        order_date_part = func.substring(
            TranslationProject.order_no,
            r"^TP-([0-9]{6}|[0-9]{8})-",
        )
        normalized_order_date = case(
            (func.length(order_date_part) == 6, func.concat("20", order_date_part)),
            else_=order_date_part,
        )
        order_date_key = case(
            (order_date_part.isnot(None), normalized_order_date),
            else_=func.to_char(TranslationProject.created_at, "YYYYMMDD"),
        )
        order_sequence = case(
            (
                order_date_part.isnot(None),
                cast(
                    func.substring(
                        TranslationProject.order_no,
                        r"^TP-[0-9]{6,8}-([0-9]+)",
                    ),
                    Integer,
                ),
            ),
            else_=None,
        )
        order_no_ordering = (
            order_date_key.desc(),
            order_sequence.desc().nullslast(),
            TranslationProject.created_at.desc(),
            TranslationProject.id.desc(),
        )
        if sort == "unfinished_first_order_no_desc":
            ended_rank = case(
                (
                    TranslationProject.project_status.in_(
                        ("completed", "cancelled", "partially_cancelled", "terminated")
                    ),
                    1,
                ),
                else_=0,
            )
            ordering = (ended_rank.asc(), *order_no_ordering)
        else:
            ordering = order_no_ordering
    else:
        ordering = (
            TranslationProject.created_at.desc(),
            TranslationProject.id.desc(),
        )
    projects = (
        query
        .order_by(*ordering)
        .offset(skip)
        .limit(limit)
        .all()
    )
    for project in projects:
        _attach_project_client_fields(project)
        _attach_project_file_detail_fields(project)
    _attach_manuscript_assignees(db, projects=projects)
    return projects


def count_translation_projects(
    db: Session,
    keyword: Optional[str] = None,
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None,
    task_type: Optional[str] = None,
    service_content: Optional[str] = None,
    priority: Optional[str] = None,
    project_manager_id: Optional[UUID] = None,
    customer_deadline_date_start: Optional[date] = None,
    customer_deadline_date_end: Optional[date] = None,
    created_date_start: Optional[date] = None,
    created_date_end: Optional[date] = None,
    field_filters: Optional[dict] = None,
) -> int:
    query = (
        db.query(TranslationProject.id)
        .outerjoin(Client, TranslationProject.client_id == Client.id)
        .outerjoin(SubClient, TranslationProject.sub_client_id == SubClient.id)
        .filter(TranslationProject.annotation_migrated_at.is_(None))
    )
    return _apply_translation_project_filters(
        query,
        keyword=keyword,
        created_by=created_by,
        project_name=project_name,
        order_no=order_no,
        project_status=project_status,
        client_short_name=client_short_name,
        task_type=task_type,
        service_content=service_content,
        priority=priority,
        project_manager_id=project_manager_id,
        customer_deadline_date_start=customer_deadline_date_start,
        customer_deadline_date_end=customer_deadline_date_end,
        created_date_start=created_date_start,
        created_date_end=created_date_end,
        field_filters=field_filters,
    ).count()


def _validate_written_translator(db: Session, translator_id: Optional[UUID]) -> None:
    if not translator_id:
        return
    from resource_service import translator_has_capability
    if not translator_has_capability(db, translator_id, "written_translation"):
        raise ValueError("所选人员已停用或不具备有效的笔译能力")


def create_translation_project(
    db: Session,
    project: TranslationProjectCreate,
    *,
    commit: bool = True,
    order_no: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> TranslationProject:
    order_no = order_no or generate_order_no(db)
    role_assignments = project.role_assignments
    project_data = project.model_dump(exclude={
        'client_short_name', 'client_code', 'manager_contact', 'word_count_matrix', 'role_assignments'
    })
    normalized_roles = _normalize_project_role_assignments(role_assignments)
    role_manager_id = normalized_roles.get('project_manager')
    if (
        'project_manager' in normalized_roles
        and project_data.get('project_manager_id') is not None
        and role_manager_id != project_data.get('project_manager_id')
    ):
        raise ValueError('项目经理字段与角色负责人配置不一致')
    
    if not project_data.get('client_id') and not project_data.get('sub_client_id'):
        client_id, sub_client_id, _created = _resolve_or_create_project_client(
            db,
            project.client_short_name,
            project.client_code,
            manager_contact=project.manager_contact,
        )
        if client_id:
            project_data['client_id'] = client_id
        if sub_client_id:
            project_data['sub_client_id'] = sub_client_id

    project_data['client_id'] = _resolve_project_client_link(
        db,
        project_data.get('client_id'),
        project_data.get('sub_client_id'),
    )
    _validate_project_manager_assignable(db, project_data.get('project_manager_id'))
    _validate_written_translator(db, project_data.get('translator_id'))
    _normalize_project_business_details(project_data)

    db_project = TranslationProject(
        order_no=order_no,
        idempotency_key=idempotency_key,
        **project_data
    )
    db.add(db_project)
    db.flush()
    _sync_project_role_assignments(db, db_project, role_assignments)

    from word_count_service import save_created_entity_matrix
    save_created_entity_matrix(
        db,
        "project",
        db_project.id,
        project.word_count_matrix,
        updated_by=project.created_by,
    )

    from workflow_crud import init_workflow

    # 项目与初始工作流必须处于同一个事务中，避免接口失败但项目已单独落库。
    init_workflow(db, db_project.id, commit=False)
    if commit:
        db.commit()
    else:
        db.flush()
    return get_translation_project(db, db_project.id)


def update_translation_project(db: Session, project_id: UUID, project_update: TranslationProjectUpdate) -> Optional[TranslationProject]:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return None
    
    role_assignments_provided = (
        'role_assignments' in project_update.model_fields_set
        and project_update.role_assignments is not None
    )
    role_assignments = project_update.role_assignments if role_assignments_provided else None
    update_data = project_update.model_dump(
        exclude_unset=True,
        exclude={'client_short_name', 'client_code', 'manager_contact', 'word_count_matrix', 'role_assignments', VERSION_FIELD},
    )
    assert_fresh(db_project, project_update.expected_updated_at)
    if 'translator_id' in update_data:
        _validate_written_translator(db, update_data.get('translator_id'))
    if role_assignments_provided:
        normalized_roles = _normalize_project_role_assignments(role_assignments)
        role_manager_id = normalized_roles.get('project_manager')
        if (
            'project_manager' in normalized_roles
            and 'project_manager_id' in update_data
            and role_manager_id != update_data.get('project_manager_id')
        ):
            raise ValueError('项目经理字段与角色负责人配置不一致')
    
    # 编辑时手工输入简称与新增项目保持一致：优先复用已有客户，确实不存在则自动创建。
    has_client_input = bool(
        (project_update.client_short_name or '').strip()
        or (project_update.client_code or '').strip()
    )
    if has_client_input and not update_data.get('client_id') and not update_data.get('sub_client_id'):
        client_id, sub_client_id, _created = _resolve_or_create_project_client(
            db,
            project_update.client_short_name,
            project_update.client_code,
            manager_contact=project_update.manager_contact,
        )
        if client_id:
            update_data['client_id'] = client_id
            # 从原客户（尤其是子客户）切换到手工输入客户时，同步清除旧子客户关联。
            update_data['sub_client_id'] = sub_client_id

    # 只切换母客户时，自动清除已不匹配的子客户；显式提交子客户时则严格校验归属。
    if 'client_id' in update_data and 'sub_client_id' not in update_data and db_project.sub_client_id:
        current_sub_client = db.query(SubClient).filter(SubClient.id == db_project.sub_client_id).first()
        if not current_sub_client or current_sub_client.parent_client_id != update_data.get('client_id'):
            update_data['sub_client_id'] = None

    update_data['client_id'] = _resolve_project_client_link(
        db,
        update_data.get('client_id', db_project.client_id),
        update_data.get('sub_client_id', db_project.sub_client_id),
    )
    if 'project_manager_id' in update_data:
        manager_id = update_data.get('project_manager_id')
        if manager_id != db_project.project_manager_id:
            _validate_project_manager_assignable(db, manager_id)
        else:
            _validate_project_manager(db, manager_id)
    _normalize_project_business_details(update_data, db_project)

    for field, value in update_data.items():
        setattr(db_project, field, value)
    if role_assignments_provided:
        _sync_project_role_assignments(db, db_project, role_assignments)
    db_project.updated_at = datetime.now()
    
    db.commit()
    db.refresh(db_project)
    
    # Reload with client_short_name
    return get_translation_project(db, project_id)


def delete_translation_project(db: Session, project_id: UUID) -> bool:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return False
    from project_workbench_service import cancel_pending_project_handovers
    cancel_pending_project_handovers(db, 'translation', project_id)
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


def get_user_roles(db: Session, skip: int = 0, limit: int = 100) -> List[UserRole]:
    return (
        db.query(UserRole)
        .options(joinedload(UserRole.user), joinedload(UserRole.role))
        .order_by(UserRole.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


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
    related_project_type: Optional[str] = None,
    related_entity_id: Optional[UUID] = None,
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
            related_project_type=related_project_type or ('translation' if related_project_id else None),
            related_entity_id=related_entity_id or related_project_id,
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
PROJECT_FILE_STATUS_SEQUENCE = {
    'pending': 0,
    'pending_confirmation': 0,
    'in_progress': 1,
    'confirmed': 1,
    'organized': 2,
    'translator_assigned': 3,
    'sent_to_translator': 4,
    'translator_returned': 5,
    'special_checked': 6,
    'typeset': 7,
    'special_checked_typeset': 8,
    'reviewed': 9,
    'sent_to_client': 10,
    'completed': 10,
    'client_feedback': 11,
    'feedback_sent_to_client': 12,
}
PROJECT_FILE_STATUS_LOCKED = {
    'cancelled',
    'partially_cancelled',
    'terminated',
    'paused',
}


def _has_project_file_path(value: Optional[str]) -> bool:
    return bool((value or '').strip())


def _normalize_optional_project_file_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_project_file_details(db_file: ProjectFile) -> None:
    """规范化文件详情扩展字段，并校验各分级字段的父子依赖。"""
    detail_text_fields = (
        'translation_domain_level1',
        'translation_domain_level2',
        'file_type',
        'file_type_secondary',
        'file_format',
        'file_attribute_level1',
        'file_attribute_level2',
        'file_attribute_level3',
        'file_difficulty',
    )
    for field in detail_text_fields:
        setattr(
            db_file,
            field,
            _normalize_optional_project_file_text(getattr(db_file, field, None)),
        )

    if db_file.translation_domain_level2 and not db_file.translation_domain_level1:
        raise ValueError("翻译文本领域二级必须先选择一级")
    if db_file.file_type_secondary and not db_file.file_type:
        raise ValueError("文件类型二级必须先选择一级")
    if db_file.file_attribute_level2 and not db_file.file_attribute_level1:
        raise ValueError("文件属性二级必须先选择一级")
    if db_file.file_attribute_level3 and not db_file.file_attribute_level2:
        raise ValueError("文件属性三级必须先选择二级")

def _sync_project_status_from_file_paths(
    db: Session,
    db_file: ProjectFile,
    changed_paths: Optional[set[str]] = None,
) -> Optional[str]:
    """按本次填写的文件路径推进状态，并支持客户反馈与再次交付循环。"""
    path_statuses = (
        ('feedback_delivery_path', 'feedback_sent_to_client'),
        ('project_feedback_path', 'client_feedback'),
        ('client_delivery_path', 'sent_to_client'),
        ('translator_return_path', 'translator_returned'),
    )
    target_status = next(
        (
            status
            for field, status in path_statuses
            if (changed_paths is None or field in changed_paths)
            and _has_project_file_path(getattr(db_file, field))
        ),
        None,
    )
    if not target_status:
        return None

    project = (
        db.query(TranslationProject)
        .filter(TranslationProject.id == db_file.translation_project_id)
        .first()
    )
    if not project or project.project_status in PROJECT_FILE_STATUS_LOCKED:
        return project.project_status if project else None

    current_rank = PROJECT_FILE_STATUS_SEQUENCE.get(project.project_status, -1)
    target_rank = PROJECT_FILE_STATUS_SEQUENCE[target_status]
    feedback_cycle_transition = (
        project.project_status == 'feedback_sent_to_client'
        and target_status == 'client_feedback'
    )
    if target_rank > current_rank or feedback_cycle_transition:
        project.project_status = target_status
        project.updated_at = dt.datetime.now()
    return project.project_status


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
        translator_return_path=project_file.translator_return_path,
        client_delivery_path=project_file.client_delivery_path,
        project_feedback_path=project_file.project_feedback_path,
        feedback_delivery_path=project_file.feedback_delivery_path,
        translation_domain_level1=project_file.translation_domain_level1,
        translation_domain_level2=project_file.translation_domain_level2,
        file_type=project_file.file_type,
        file_type_secondary=project_file.file_type_secondary,
        file_format=project_file.file_format,
        file_attribute_level1=project_file.file_attribute_level1,
        file_attribute_level2=project_file.file_attribute_level2,
        file_attribute_level3=project_file.file_attribute_level3,
        file_difficulty=project_file.file_difficulty,
        file_ext=project_file.file_ext,
        file_size=project_file.file_size,
        storage_type=project_file.storage_type,
        uploaded_by=project_file.uploaded_by
    )
    db.add(db_file)
    _validate_project_file_details(db_file)
    _sync_project_status_from_file_paths(db, db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


def update_project_file(db: Session, file_id: UUID, file_update: ProjectFileUpdate) -> Optional[ProjectFile]:
    db_file = get_project_file(db, file_id)
    if not db_file:
        return None
    
    update_data = file_update.model_dump(exclude_unset=True)
    path_fields = {
        'translator_return_path',
        'client_delivery_path',
        'project_feedback_path',
        'feedback_delivery_path',
    }
    changed_paths = {
        field
        for field in path_fields.intersection(update_data)
        if (getattr(db_file, field) or '').strip()
        != (update_data.get(field) or '').strip()
    }
    for field, value in update_data.items():
        setattr(db_file, field, value)

    _validate_project_file_details(db_file)
    _sync_project_status_from_file_paths(db, db_file, changed_paths)
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
    格式：EQ-YYMMDD-NNN（如 EQ-260309-001）
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

    return f"{prefix}{new_seq:03d}"


def _attach_consultation_client_fields(
    consultation: Consultation,
    client_code,
    client_name,
    client_short_name,
    manager_contact,
    sub_client: Optional[SubClient] = None,
) -> Consultation:
    consultation.client_code = client_code
    consultation.client_name = client_name
    consultation.client_short_name = client_short_name
    consultation.manager_contact = manager_contact
    consultation.sub_client_code = sub_client.sub_client_code if sub_client else None
    consultation.sub_client_name = sub_client.client_name if sub_client else None
    consultation.sub_client_short_name = sub_client.client_short_name if sub_client else None
    if sub_client and sub_client.manager_contact:
        consultation.manager_contact = sub_client.manager_contact
    return consultation


def get_consultation(db: Session, consultation_id: UUID) -> Optional[Consultation]:
    result = db.query(
        Consultation,
        Client.client_code,
        Client.client_name,
        Client.client_short_name,
        Client.manager_contact,
        SubClient,
    ).outerjoin(Client, Consultation.client_id == Client.id).outerjoin(
        SubClient, Consultation.sub_client_id == SubClient.id
    ).filter(Consultation.id == consultation_id).first()
    if not result:
        return None
    consultation, client_code, client_name, client_short_name, manager_contact, sub_client = result
    return _attach_consultation_client_fields(
        consultation, client_code, client_name, client_short_name, manager_contact, sub_client,
    )


CONSULTATION_TYPE_FILTER_ALIASES = {
    '简单咨询': ('简单咨询', 'simple'),
    '笔译项目': ('笔译项目', 'translation', '笔译'),
    '口译项目': ('口译项目', 'interpretation', '口译'),
    '招聘项目': ('招聘项目', 'recruitment', '招聘'),
    '标注项目': ('标注项目', 'annotation'),
    '配音项目': ('配音项目', 'dubbing'),
    '字幕项目': ('字幕项目', 'subtitle'),
    '公证项目': ('公证项目', 'notarization'),
    '认证项目': ('认证项目', 'certification'),
    '其他项目': ('其他项目', 'equipment_rental', 'other', '其他'),
    '非项目工作': ('非项目工作',),
}


def _apply_consultation_filters(
    query,
    keyword: Optional[str] = None,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
):
    if keyword and keyword.strip():
        keyword_pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            Consultation.consultation_code.ilike(keyword_pattern),
            Consultation.project_name.ilike(keyword_pattern),
            Consultation.customer_order_no.ilike(keyword_pattern),
            Client.client_name.ilike(keyword_pattern),
            Client.client_short_name.ilike(keyword_pattern),
            SubClient.client_name.ilike(keyword_pattern),
            SubClient.client_short_name.ilike(keyword_pattern),
        ))
    if consultation_code:
        query = query.filter(Consultation.consultation_code.ilike(f"%{consultation_code}%"))
    if client_name:
        client_keyword = client_name.strip()
        if client_keyword:
            keyword_pattern = f"%{client_keyword}%"
            query = query.filter(or_(
                Client.client_name.ilike(keyword_pattern),
                Client.client_short_name.ilike(keyword_pattern),
                SubClient.client_name.ilike(keyword_pattern),
                SubClient.client_short_name.ilike(keyword_pattern),
            ))
    if status:
        query = query.filter(Consultation.status == status)
    if consultation_date_start:
        query = query.filter(Consultation.consultation_time >= datetime.combine(consultation_date_start, time.min))
    if consultation_date_end:
        end_exclusive = datetime.combine(consultation_date_end + timedelta(days=1), time.min)
        query = query.filter(Consultation.consultation_time < end_exclusive)
    if consultation_method:
        if consultation_method == 'other':
            query = query.filter(Consultation.consultation_method.notin_(['phone', 'email', 'online', 'onsite']))
        else:
            query = query.filter(Consultation.consultation_method == consultation_method)
    if consultation_type:
        type_values = CONSULTATION_TYPE_FILTER_ALIASES.get(consultation_type, (consultation_type,))
        query = query.filter(Consultation.consultation_type.in_(type_values))
    if client_source and client_source.strip():
        query = query.filter(Consultation.client_source.ilike(f"%{client_source.strip()}%"))
    if customer_service_id:
        query = query.filter(Consultation.customer_service_id == customer_service_id)
    if sales_person_id:
        query = query.filter(Consultation.sales_person_id == sales_person_id)
    if follow_up_person_id:
        query = query.filter(Consultation.follow_up_person_id == follow_up_person_id)
    if follow_up_status and follow_up_status.strip():
        query = query.filter(Consultation.follow_up_status.ilike(f"%{follow_up_status.strip()}%"))
    return query


def get_consultations(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
) -> List[Consultation]:
    query = db.query(
        Consultation,
        Client.client_code,
        Client.client_name,
        Client.client_short_name,
        Client.manager_contact,
        SubClient,
    ).outerjoin(Client, Consultation.client_id == Client.id).outerjoin(
        SubClient, Consultation.sub_client_id == SubClient.id
    )
    query = _apply_consultation_filters(
        query,
        keyword=keyword,
        consultation_code=consultation_code,
        client_name=client_name,
        status=status,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        consultation_method=consultation_method,
        consultation_type=consultation_type,
        client_source=client_source,
        customer_service_id=customer_service_id,
        sales_person_id=sales_person_id,
        follow_up_person_id=follow_up_person_id,
        follow_up_status=follow_up_status,
    )

    results = query.order_by(Consultation.created_at.desc()).offset(skip).limit(limit).all()
    
    consultations = []
    for consultation, client_code, db_client_name, client_short_name, manager_contact, sub_client in results:
        consultations.append(_attach_consultation_client_fields(
            consultation, client_code, db_client_name, client_short_name, manager_contact, sub_client,
        ))
    return consultations


def count_consultations(
    db: Session,
    keyword: Optional[str] = None,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
) -> int:
    query = db.query(Consultation.id).outerjoin(Client, Consultation.client_id == Client.id).outerjoin(
        SubClient, Consultation.sub_client_id == SubClient.id
    )
    query = _apply_consultation_filters(
        query,
        keyword=keyword,
        consultation_code=consultation_code,
        client_name=client_name,
        status=status,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        consultation_method=consultation_method,
        consultation_type=consultation_type,
        client_source=client_source,
        customer_service_id=customer_service_id,
        sales_person_id=sales_person_id,
        follow_up_person_id=follow_up_person_id,
        follow_up_status=follow_up_status,
    )
    return query.count()


def create_consultation(
    db: Session,
    consultation: ConsultationCreate,
    *,
    idempotency_key: Optional[str] = None,
    commit: bool = True,
) -> Consultation:
    consultation_code = generate_consultation_code(db)

    consultation_data = consultation.model_dump(exclude={
        'consultation_code',
        'client_code',
        'client_name',
        'client_short_name',
        'manager_contact',
    })
    if not consultation_data.get('client_id') and (consultation.client_short_name or '').strip():
        client_id, _sub_client_id, _created = _resolve_or_create_project_client(
            db,
            consultation.client_short_name,
            consultation.client_code,
            consultation.client_name,
        )
        consultation_data['client_id'] = client_id

    # 客户经理联系方式属于关联客户资料；咨询表单仅提供就地编辑入口，不重复落库。
    if 'manager_contact' in consultation.model_fields_set and consultation_data.get('client_id'):
        client = db.query(Client).filter(Client.id == consultation_data['client_id']).first()
        if client:
            client.manager_contact = (consultation.manager_contact or '').strip() or None

    db_consultation = Consultation(
        consultation_code=consultation_code,
        idempotency_key=idempotency_key,
        **consultation_data,
    )
    db.add(db_consultation)
    if commit:
        db.commit()
    else:
        db.flush()
    return get_consultation(db, db_consultation.id)


def update_consultation(
    db: Session,
    consultation_id: UUID,
    consultation_update: ConsultationUpdate,
    *,
    commit: bool = True,
) -> Optional[Consultation]:
    db_consultation = get_consultation(db, consultation_id)
    if not db_consultation:
        return None
    update_data = consultation_update.model_dump(
        exclude_unset=True,
        exclude={'client_code', 'client_name', 'client_short_name', 'manager_contact', VERSION_FIELD},
    )
    assert_fresh(db_consultation, consultation_update.expected_updated_at)
    has_client_input = bool(
        (consultation_update.client_short_name or '').strip()
        or (consultation_update.client_code or '').strip()
    )
    if has_client_input and not update_data.get('client_id'):
        client_id, _sub_client_id, _created = _resolve_or_create_project_client(
            db,
            consultation_update.client_short_name,
            consultation_update.client_code,
            consultation_update.client_name,
        )
        if client_id:
            update_data['client_id'] = client_id

    # 只在请求明确携带该字段时同步客户资料，避免列表内联更新状态时误清空联系方式。
    if 'manager_contact' in consultation_update.model_fields_set:
        target_client_id = update_data.get('client_id', db_consultation.client_id)
        if target_client_id:
            client = db.query(Client).filter(Client.id == target_client_id).first()
            if client:
                client.manager_contact = (consultation_update.manager_contact or '').strip() or None

    for field, value in update_data.items():
        setattr(db_consultation, field, value)
    # updated_at 的数据库默认值只在新增时生效，编辑时使用服务器时间主动刷新。
    db_consultation.updated_at = datetime.now()
    if commit:
        db.commit()
    else:
        db.flush()
    return get_consultation(db, consultation_id)


def delete_consultation(db: Session, consultation_id: UUID) -> bool:
    db_consultation = get_consultation(db, consultation_id)
    if not db_consultation:
        return False
    if (db_consultation.status or "").strip() == "success":
        raise ValueError("已确认的咨询不能删除，请保留与项目、邮件的审计链路")
    from annotation_models import AnnotationProject
    from interpretation_models import InterpretationProject
    from recruitment_models import RecruitmentProject
    linked = (
        db.query(TranslationProject.id).filter(TranslationProject.consultation_id == consultation_id).first()
        or db.query(InterpretationProject.id).filter(InterpretationProject.consultation_id == consultation_id).first()
        or db.query(AnnotationProject.id).filter(AnnotationProject.consultation_id == consultation_id).first()
        or db.query(RecruitmentProject.id).filter(RecruitmentProject.consultation_id == consultation_id).first()
    )
    if linked:
        raise ValueError("该咨询已生成项目，不能删除")
    db.delete(db_consultation)
    db.commit()
    return True


# ============================================================
# TranslationSubOrder CRUD
# ============================================================

def generate_sub_order_no(db: Session, parent_project_id: UUID) -> str:
    """根据母订单号生成三位子单流水号，如 TP-260302-014.001。"""
    parent = (
        db.query(TranslationProject)
        .filter(TranslationProject.id == parent_project_id)
        .with_for_update()
        .first()
    )
    if not parent:
        raise ValueError("母订单不存在")
    base_no = parent.order_no  # 例如 TP-260302-014

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

    return f"{base_no}.{new_seq:03d}"


def get_sub_order(db: Session, sub_order_id: UUID) -> Optional[TranslationSubOrder]:
    sub_order = (
        db.query(TranslationSubOrder)
        .options(selectinload(TranslationSubOrder.translator))
        .filter(TranslationSubOrder.id == sub_order_id)
        .first()
    )
    if sub_order:
        _attach_manuscript_assignees(db, sub_orders=[sub_order])
    return sub_order


def get_sub_orders_by_project(db: Session, parent_project_id: UUID) -> List[TranslationSubOrder]:
    sub_orders = (
        db.query(TranslationSubOrder)
        .options(selectinload(TranslationSubOrder.translator))
        .filter(TranslationSubOrder.parent_project_id == parent_project_id)
        .order_by(TranslationSubOrder.sub_order_no)
        .all()
    )
    _attach_manuscript_assignees(db, sub_orders=sub_orders)
    return sub_orders


def get_all_sub_orders(db: Session, skip: int = 0, limit: int = 200, sub_order_no: Optional[str] = None, project_name: Optional[str] = None) -> List[TranslationSubOrder]:
    q = db.query(TranslationSubOrder).options(selectinload(TranslationSubOrder.translator))
    if sub_order_no:
        q = q.filter(TranslationSubOrder.sub_order_no.ilike(f'%{sub_order_no}%'))
    if project_name:
        q = q.filter(TranslationSubOrder.sub_project_name.ilike(f'%{project_name}%'))
    sub_orders = q.offset(skip).limit(limit).all()
    _attach_manuscript_assignees(db, sub_orders=sub_orders)
    return sub_orders


def _create_sub_order_in_transaction(
    db: Session, sub_order: TranslationSubOrderCreate,
    idempotency_key: Optional[str] = None,
) -> TranslationSubOrder:
    sub_order_no = sub_order.sub_order_no or generate_sub_order_no(db, sub_order.parent_project_id)
    data = sub_order.model_dump(exclude={'sub_order_no', 'word_count_matrix'})
    _validate_written_translator(db, data.get('translator_id'))
    db_sub = TranslationSubOrder(
        sub_order_no=sub_order_no, idempotency_key=idempotency_key, **data,
    )
    db.add(db_sub)
    db.flush()
    from word_count_service import save_created_entity_matrix
    save_created_entity_matrix(
        db,
        "suborder",
        db_sub.id,
        sub_order.word_count_matrix,
        updated_by=sub_order.created_by,
    )
    from workflow_crud import init_workflow

    # 子订单与母订单一致：初始工作流必须同事务落库，否则子订单不会出现在工作台。
    init_workflow(db, sub_order_id=db_sub.id, commit=False)
    return db_sub


def create_sub_order(
    db: Session, sub_order: TranslationSubOrderCreate,
    idempotency_key: Optional[str] = None,
) -> TranslationSubOrder:
    db_sub = _create_sub_order_in_transaction(db, sub_order, idempotency_key=idempotency_key)
    _sync_project_name_with_sub_order_count(db, sub_order.parent_project_id)
    db.commit()
    return get_sub_order(db, db_sub.id)


def normalize_sub_project_name(value: Optional[str]) -> str:
    return str(value or '').strip().casefold()


def partition_sub_project_names(
    names: List[str], existing_names: List[Optional[str]],
) -> tuple[List[str], List[dict]]:
    existing_keys = {
        normalize_sub_project_name(name)
        for name in existing_names
        if normalize_sub_project_name(name)
    }
    accepted: List[str] = []
    skipped: List[dict] = []
    request_keys: set[str] = set()
    for name in names:
        key = normalize_sub_project_name(name)
        if key in existing_keys:
            skipped.append({'name': name, 'reason': '当前母订单已存在同名子订单'})
            continue
        if key in request_keys:
            skipped.append({'name': name, 'reason': '本次导入内容中名称重复'})
            continue
        request_keys.add(key)
        accepted.append(name)
    return accepted, skipped


def create_sub_orders_bulk(
    db: Session,
    payload: TranslationSubOrderBulkCreate,
    created_by: Optional[UUID] = None,
) -> tuple[List[TranslationSubOrder], List[dict]]:
    parent = (
        db.query(TranslationProject)
        .filter(TranslationProject.id == payload.parent_project_id)
        .with_for_update()
        .first()
    )
    if not parent:
        raise ValueError('母订单不存在')

    existing_names = [
        item.sub_project_name
        for item in db.query(TranslationSubOrder)
        .filter(TranslationSubOrder.parent_project_id == payload.parent_project_id)
        .all()
    ]
    accepted_names, skipped = partition_sub_project_names(payload.sub_project_names, existing_names)
    defaults = payload.defaults.model_dump()
    created: List[TranslationSubOrder] = []
    for name in accepted_names:
        sub_order = TranslationSubOrderCreate(
            parent_project_id=payload.parent_project_id,
            sub_project_name=name,
            created_by=created_by,
            **defaults,
        )
        created.append(_create_sub_order_in_transaction(db, sub_order))

    if created:
        _sync_project_name_with_sub_order_count(db, payload.parent_project_id)
    db.commit()
    for item in created:
        db.refresh(item)
    if created:
        _attach_manuscript_assignees(db, sub_orders=created)
    return created, skipped


def update_sub_order(db: Session, sub_order_id: UUID, sub_order_update: TranslationSubOrderUpdate) -> Optional[TranslationSubOrder]:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return None
    update_data = sub_order_update.model_dump(exclude_unset=True, exclude={'word_count_matrix'})
    if 'translator_id' in update_data:
        _validate_written_translator(db, update_data.get('translator_id'))
    for field, value in update_data.items():
        setattr(db_sub, field, value)
    db_sub.updated_at = datetime.now()
    db.commit()
    return get_sub_order(db, db_sub.id)


def delete_sub_order(db: Session, sub_order_id: UUID) -> bool:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return False
    parent_project_id = db_sub.parent_project_id
    db.delete(db_sub)
    db.flush()
    _sync_project_name_with_sub_order_count(db, parent_project_id)
    db.commit()
    return True
