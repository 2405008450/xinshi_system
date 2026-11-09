from search_matching import keyword_ilike, keyword_like, keyword_or
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import Integer, String, and_, case, cast, exists as db_exists, func, or_, select

from models import AppUser, Role, TranslationProject, TranslationSubOrder, TranslationSubOrderChargeItem, UserRole, ProjectFile, Client, ClientContact, SubClient, Translator, Consultation, FinanceRecord, AppNotification, ProjectRoleAssignment
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
from utils import generate_order_no, normalize_email_subject_order_no
from project_audit_service import record_project_operation
from department_utils import department_filter_values
from mail_group_members import remove_unavailable_user_memberships
from field_filtering import apply_scalar_specs
from concurrency import VERSION_FIELD, assert_fresh
from language_catalog import compact_translation_direction, validate_language_pairs_against_catalog
from translation_project_identity import normalize_translation_name_payload
from fastapi import HTTPException


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
    office_city_id: Optional[UUID] = None,
    active_only: bool = False,
) -> List[AppUser]:
    query = db.query(AppUser).filter(AppUser.is_deleted.is_(False))
    from office_management import filter_users
    query=filter_users(db,query,office_city_id,active_only)
    if username:
        query = query.filter(keyword_ilike(AppUser.username, f"%{username}%"))
    if full_name:
        query = query.filter(keyword_ilike(AppUser.full_name, f"%{full_name}%"))
    if department:
        from organization_service import department_condition
        query = query.filter(department_condition(db, [department]))
    rows = (
        query.add_columns(func.count(AppUser.id).over().label("_page_total"))
        .order_by(AppUser.created_at.desc(), AppUser.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    users = []
    for user, page_total in rows:
        user.__dict__["_page_total"] = int(page_total or 0)
        users.append(user)
    return users


def count_users(
    db: Session,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    department: Optional[str] = None,
    office_city_id: Optional[UUID] = None,
    active_only: bool = False,
) -> int:
    query = db.query(AppUser.id).filter(AppUser.is_deleted.is_(False))
    from office_management import filter_users
    query=filter_users(db,query,office_city_id,active_only)
    if username:
        query = query.filter(keyword_ilike(AppUser.username, f"%{username}%"))
    if full_name:
        query = query.filter(keyword_ilike(AppUser.full_name, f"%{full_name}%"))
    if department:
        from organization_service import department_condition
        query = query.filter(department_condition(db, [department]))
    return query.count()


def create_user(db: Session, user: AppUserCreate) -> AppUser:
    from department_service import canonical_name
    from office_management import validate_city,write_user,attach_users
    if 'office_city_id' in user.model_fields_set:validate_city(db,user.office_city_id)
    hashed = hash_password(user.password)
    db_user = AppUser(
        username=user.username,
        password_hash=hashed,
        full_name=user.full_name,
        email=normalize_user_email(user.email),
        is_active=user.is_active,
        department=canonical_name(db,user.department),
    )
    db.add(db_user)
    from organization_service import sync_primary
    sync_primary(db, db_user)
    from employee_employment import write as write_employment
    if 'hire_date' in user.model_fields_set:write_employment(db,db_user,user.hire_date)
    if 'office_city_id' in user.model_fields_set:write_user(db,db_user,user.office_city_id)
    db.commit()
    db.refresh(db_user)
    from organization_service import publish
    publish(db)
    from employee_employment import attach as attach_employment
    attach_employment(db,[db_user])
    attach_users(db,[db_user])
    return db_user


def update_user(db: Session, user_id: UUID, user_update: AppUserUpdate) -> Optional[AppUser]:
    db_user = get_user(db, user_id)
    if not db_user or db_user.is_deleted:
        return None
    
    previous_department = db_user.department
    update_data = user_update.model_dump(exclude_unset=True)
    employment_changed='hire_date' in update_data
    hire_date=update_data.pop('hire_date',None)
    city_changed='office_city_id' in update_data
    city_id=update_data.pop('office_city_id',None)
    from office_management import validate_city,write_user,attach_users
    if city_changed:validate_city(db,city_id)
    if 'department' in update_data:
        from department_service import canonical_name
        update_data['department'] = canonical_name(db,update_data['department'])
    if "email" in update_data:
        update_data["email"] = normalize_user_email(update_data["email"])

    for field, value in update_data.items():
        setattr(db_user, field, value)

    if "department" in update_data:
        from organization_service import sync_primary
        sync_primary(db, db_user, previous_department)
    remove_unavailable_user_memberships(db, db_user)
    if employment_changed:
        from employee_employment import write as write_employment
        write_employment(db,db_user,hire_date)
    if city_changed:write_user(db,db_user,city_id)
    db.commit()
    db.refresh(db_user)
    if 'department' in update_data:
        from organization_service import publish
        publish(db)
    from employee_employment import attach as attach_employment
    attach_employment(db,[db_user])
    attach_users(db,[db_user])
    return db_user


def reset_user_password(db: Session, user_id: UUID, new_password: str) -> Optional[AppUser]:
    db_user = get_user(db, user_id)
    if not db_user or db_user.is_deleted:
        return None

    db_user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: UUID) -> bool:
    # 不物理删除：历史请假、排班、消息、项目和审计继续指向原人员。
    db_user = db.query(AppUser).filter(AppUser.id == user_id).with_for_update().first()
    if not db_user:
        return False
    if not db_user.is_deleted:
        from chat_time import now
        from business_time import business_now
        db_user.is_active = False
        db_user.is_deleted = True
        db_user.deleted_at = now()
        db_user.updated_at = business_now()
    db.commit()
    from organization_service import publish
    publish(db)
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
    from chat_time import now
    today = now()
    date_text = today.strftime("%y%m%d")
    prefix = f"CL-{date_text}-"
    legacy_prefix = f"CL-{today.strftime('%y-%m%d')}-"
    last_records = [
        (
            db.query(Client)
            .filter(keyword_like(Client.client_code, f"{current_prefix}%"))
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

    from business_numbering import allocate
    return allocate(db, 'client', prefix, new_seq)


def get_client(db: Session, client_id: UUID) -> Optional[Client]:
    client = db.query(Client).options(selectinload(Client.sub_clients)).filter(Client.id == client_id).first()
    if client:
        from translation_customer_type import attach_clients
        attach_clients(db, [client])
        from client_cooperation_auto import attach_clients as attach_cooperation
        attach_cooperation(db,[client])
        from client_operator import attach_clients as attach_operator
        attach_operator(db, [client])
        attach_contact_people(db,clients=[client])
    return client


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
    from client_cooperation_auto import expressions as cooperation_expressions
    client_state,client_start=cooperation_expressions(Client)
    sub_state,sub_start=cooperation_expressions(SubClient)
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
            query = query.filter(keyword_or(lambda _search_part: or_(
                keyword_ilike(client_column, _search_part),
                Client.sub_clients.any(keyword_ilike(sub_client_column, _search_part)),
            ), pattern))

    if client_name and client_name.strip():
        pattern = f"%{client_name.strip()}%"
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(Client.client_name, _search_part),
            keyword_ilike(Client.client_short_name, _search_part),
            Client.sub_clients.any(or_(
                keyword_ilike(SubClient.client_name, _search_part),
                keyword_ilike(SubClient.client_short_name, _search_part),
            )),
        ), pattern))
    if english_name and english_name.strip():
        pattern = f"%{english_name.strip()}%"
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(Client.english_name, _search_part),
            keyword_ilike(Client.english_short_name, _search_part),
            Client.sub_clients.any(or_(
                keyword_ilike(SubClient.english_name, _search_part),
                keyword_ilike(SubClient.english_short_name, _search_part),
            )),
        ), pattern))
    if client_status:
        query = query.filter(or_(
            client_state == client_status,
            Client.sub_clients.any(sub_state == client_status),
        ))
    if cooperation_start_date_from:
        start_at = datetime.combine(cooperation_start_date_from, time.min)
        query = query.filter(or_(
            client_start >= start_at,
            Client.sub_clients.any(sub_start >= start_at),
        ))
    if cooperation_start_date_to:
        end_at = datetime.combine(cooperation_start_date_to, time.max)
        query = query.filter(or_(
            client_start <= end_at,
            Client.sub_clients.any(sub_start <= end_at),
        ))
    for field, descriptor in (field_filters or {}).items():
        if field == "cooperation_start_date":
            start_value, end_value = descriptor.get("from"), descriptor.get("to")
            if start_value:
                start_at = datetime.combine(date.fromisoformat(str(start_value)), time.min)
                query = query.filter(or_(client_start >= start_at, Client.sub_clients.any(sub_start >= start_at)))
            if end_value:
                end_at = datetime.combine(date.fromisoformat(str(end_value)), time.max)
                query = query.filter(or_(client_start <= end_at, Client.sub_clients.any(sub_start <= end_at)))
            continue
        if field == "client_status":
            values = descriptor.get("value") or []
            query = query.filter(or_(client_state.in_(values), Client.sub_clients.any(sub_state.in_(values))))
            continue
        if field == "client_name" and descriptor.get("op") == "contains":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(keyword_or(lambda _search_part: or_(
                keyword_ilike(Client.client_name, _search_part), keyword_ilike(Client.client_short_name, _search_part),
                Client.sub_clients.any(or_(keyword_ilike(SubClient.client_name, _search_part), keyword_ilike(SubClient.client_short_name, _search_part))),
            ), pattern))
            continue
        if field == "english_name" and descriptor.get("op") == "contains":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(keyword_or(lambda _search_part: or_(
                keyword_ilike(Client.english_name, _search_part), keyword_ilike(Client.english_short_name, _search_part),
                Client.sub_clients.any(or_(keyword_ilike(SubClient.english_name, _search_part), keyword_ilike(SubClient.english_short_name, _search_part))),
            ), pattern))
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
            query = query.filter(keyword_or(lambda _search_part: or_(keyword_ilike(columns[0], _search_part), Client.sub_clients.any(keyword_ilike(columns[1], _search_part))), pattern))
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
    rows = query.add_columns(func.count(Client.id).over().label("_page_total")).offset(skip).limit(limit).all()
    clients = []
    for client, page_total in rows:
        client.__dict__["_page_total"] = int(page_total or 0)
        clients.append(client)
    from translation_customer_type import attach_clients
    attach_clients(db, clients)
    from client_cooperation_auto import attach_clients as attach_cooperation
    attach_cooperation(db,clients)
    from client_operator import attach_clients as attach_operator
    attach_operator(db, clients)
    attach_contact_people(db,clients=clients)
    return clients


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
    *, actor=None,
) -> Client:
    data = client.model_dump(exclude={'customer_type','contact_names','contact_people'})
    if not getattr(db,'info',{}).get('client_contacts_visible',True):data.pop('manager_contact',None)
    if not data.get('client_code'):
        data['client_code'] = generate_client_code(db)
    db_client = Client(idempotency_key=idempotency_key, **data)
    db.add(db_client)
    db.flush()
    from translation_customer_type import save_client
    save_client(db, db_client, client.customer_type)
    from client_operator import record
    record(db, db_client.id, actor, 'client_create')
    if client.contact_names is not None:
        replace_contact_people(db, db_client, client.contact_names)
    if client.contact_people is not None:
        from client_contact_people import replace_details
        replace_details(db, db_client, client.contact_people)
    db.commit()
    db.refresh(db_client)
    return get_client(db,db_client.id)

def update_client(db: Session, client_id: UUID, client_update: ClientUpdate) -> Optional[Client]:
    db_client = get_client(db, client_id)
    if not db_client:
        return None
    update_data = client_update.model_dump(exclude_unset=True, exclude={VERSION_FIELD, 'customer_type','contact_names','contact_people'})
    if not getattr(db,'info',{}).get('client_contacts_visible',True):update_data.pop('manager_contact',None)
    assert_fresh(db_client, client_update.expected_updated_at)
    if 'customer_type' in client_update.model_fields_set:
        from translation_customer_type import save_client
        save_client(db, db_client, client_update.customer_type)
    if "client_code" in update_data:
        next_code = (update_data["client_code"] or "").strip()
        if not next_code:
            raise ValueError("客户编号不能为空")
        update_data["client_code"] = next_code
    for field, value in update_data.items():
        setattr(db_client, field, value)
    db_client.updated_at = datetime.now()
    if client_update.contact_names is not None:
        replace_contact_people(db, db_client, client_update.contact_names)
    if client_update.contact_people is not None:
        from client_contact_people import replace_details
        replace_details(db, db_client, client_update.contact_people)
    db.commit()
    db.refresh(db_client)
    return get_client(db,db_client.id)

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
    if not getattr(db,'info',{}).get('client_contacts_visible',True):update_data.pop('manager_contact',None)
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
        .filter(keyword_like(SubClient.sub_client_code, f"{base_no}.%"))
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

    from business_numbering import allocate
    return allocate(db, f'subclient:{parent_id}', base_no + '.', new_seq)

def get_sub_client(db: Session, sub_client_id: UUID) -> Optional[SubClient]:
    client = db.query(SubClient).filter(SubClient.id == sub_client_id).first()
    if client:
        from translation_customer_type import attach_clients
        attach_clients(db, sub_clients=[client])
        from client_cooperation_auto import attach_clients as attach_cooperation
        attach_cooperation(db,sub_clients=[client])
        attach_contact_people(db,sub_clients=[client])
    return client

def create_sub_client(
    db: Session, sub_client: SubClientCreate, idempotency_key: Optional[str] = None,
) -> SubClient:
    sub_code = sub_client.sub_client_code or generate_sub_client_code(db, sub_client.parent_client_id)
    data = sub_client.model_dump(exclude={'sub_client_code', 'customer_type','contact_names','contact_people'})
    if not getattr(db,'info',{}).get('client_contacts_visible',True):data.pop('manager_contact',None)
    db_sub = SubClient(
        sub_client_code=sub_code, idempotency_key=idempotency_key, **data,
    )
    db.add(db_sub)
    db.flush()
    from translation_customer_type import save_client
    save_client(db, db_sub, sub_client.customer_type)
    if sub_client.contact_names is not None:
        replace_contact_people(db, db_sub, sub_client.contact_names)
    if sub_client.contact_people is not None:
        from client_contact_people import replace_details
        replace_details(db, db_sub, sub_client.contact_people)
    db.commit()
    db.refresh(db_sub)
    return get_sub_client(db,db_sub.id)

def update_sub_client(db: Session, sub_id: UUID, sub_update: SubClientUpdate) -> Optional[SubClient]:
    db_sub = get_sub_client(db, sub_id)
    if not db_sub:
        return None
    update_data = sub_update.model_dump(exclude_unset=True, exclude={VERSION_FIELD, 'customer_type','contact_names','contact_people'})
    if not getattr(db,'info',{}).get('client_contacts_visible',True):update_data.pop('manager_contact',None)
    assert_fresh(db_sub, sub_update.expected_updated_at)
    if 'customer_type' in sub_update.model_fields_set:
        from translation_customer_type import save_client
        save_client(db, db_sub, sub_update.customer_type)
    if "sub_client_code" in update_data:
        next_code = (update_data["sub_client_code"] or "").strip()
        if not next_code:
            raise ValueError("子客户编号不能为空")
        update_data["sub_client_code"] = next_code
    for field, value in update_data.items():
        setattr(db_sub, field, value)
    db_sub.updated_at = datetime.now()
    if sub_update.contact_names is not None:
        replace_contact_people(db, db_sub, sub_update.contact_names)
    if sub_update.contact_people is not None:
        from client_contact_people import replace_details
        replace_details(db, db_sub, sub_update.contact_people)
    db.commit()
    db.refresh(db_sub)
    return get_sub_client(db,db_sub.id)

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
    from resource_models import ResourcePerson
    from talent_duplicate_service import review_ready
    if review_ready(db):
        query = query.filter(~db.query(ResourcePerson.id).filter(
            ResourcePerson.id == Translator.resource_person_id,
            ResourcePerson.archived_into_id.is_not(None),
        ).exists())
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
        query = query.filter(keyword_ilike(Translator.translator_code, f"%{translator_code}%"))
    if translator_name:
        query = query.filter(keyword_ilike(Translator.translator_name, f"%{translator_name}%"))
    if cooperation_type:
        query = query.filter(Translator.cooperation_type == cooperation_type)
    if languages:
        query = query.filter(keyword_ilike(Translator.languages, f"%{languages}%"))
    if translation_type:
        query = query.filter(Translator.translation_type == translation_type)
    if direction:
        query = query.filter(Translator.direction == direction)
    if status:
        query = query.filter(Translator.status == status)
    if available_time_slot:
        query = query.filter(keyword_ilike(Translator.available_time_slot, f"%{available_time_slot}%"))
    if domain_keyword:
        query = query.filter(keyword_ilike(Translator.domain_skills.cast(String), f"%{domain_keyword}%"))
    if contact_keyword and contact_keyword.strip():
        pattern = f"%{contact_keyword.strip()}%"
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(Translator.contact_info, _search_part),
            keyword_ilike(Translator.phone, _search_part),
            keyword_ilike(Translator.phone2, _search_part),
            keyword_ilike(Translator.email1, _search_part),
            keyword_ilike(Translator.email2, _search_part),
            keyword_ilike(Translator.other_contact, _search_part),
        ), pattern))
    if quality_score and quality_score.strip():
        query = query.filter(keyword_ilike(Translator.quality_score, f"%{quality_score.strip()}%"))
    if gender and gender.strip():
        query = query.filter(keyword_ilike(Translator.gender, f"%{gender.strip()}%"))
    if nationality and nationality.strip():
        query = query.filter(keyword_ilike(Translator.nationality, f"%{nationality.strip()}%"))
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
from translation_project_contact import attach as attach_project_contacts, save as save_project_contact
from client_contact_people import attach as attach_contact_people, replace as replace_contact_people


def _attach_manuscript_assignees(
    db: Session,
    *,
    projects: Optional[List[TranslationProject]] = None,
    sub_orders: Optional[List[TranslationSubOrder]] = None,
) -> None:
    """把有效派稿明细汇总到项目响应，不再依赖单一 translator_id。"""
    projects = projects or []
    from translation_mother_split import attach as attach_mother_split
    attach_mother_split(db,projects,sub_orders or [])
    from translation_customer_type import attach as attach_customer_types
    attach_customer_types(db, projects)
    attach_project_contacts(db, projects)
    from translation_document_requirements import attach as attach_document_requirements
    attach_document_requirements(db, projects)
    from translation_payment_confirmation import attach as attach_payment_confirmation
    attach_payment_confirmation(db, projects)
    from translation_statement_status import attach as attach_statement_status
    attach_statement_status(db,projects)
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
            "translator_return_time": row.planned_delivery_at,
            "completion_remarks": row.completion_remarks,
            "settlement_method": getattr(row, "settlement_method", None),
            "translator_pricing_method": getattr(row, "translator_pricing_method", None),
            "translator_unit_price": row.translator_unit_price,
            "translator_total_price": row.translator_total_price,
            "remarks": getattr(row, "remarks", None),
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
    from translation_folder_orders import attach as attach_folder_orders,attach_folder_roots
    attach_folder_roots(db, projects)
    attach_folder_orders(db, sub_orders)
    _attach_word_count_matrices(db, projects=projects, sub_orders=sub_orders)
    from translation_order_inheritance import attach as attach_inheritance
    attach_inheritance(db, projects=projects, sub_orders=sub_orders)


def _sync_assigned_translator_completions(
    db: Session,
    updates,
    *,
    project_id: UUID,
    sub_order_id: Optional[UUID],
) -> None:
    """把项目端填写的译员交付及价格信息原位写回稿件安排明细。"""
    if updates is None:
        return

    from manuscript_models import ManuscriptArrangement, ManuscriptDispatch

    update_by_id = {item.arrangement_id: item for item in updates}
    if len(update_by_id) != len(updates):
        raise ValueError("译员任务完成情况中存在重复的稿件安排明细")
    if not update_by_id:
        return

    rows = (
        db.query(ManuscriptArrangement)
        .join(ManuscriptDispatch, ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id)
        .filter(
            ManuscriptArrangement.id.in_(update_by_id),
            ManuscriptArrangement.translation_project_id == project_id,
            ManuscriptArrangement.sub_order_id == sub_order_id,
            ManuscriptArrangement.status != "cancelled",
            ManuscriptDispatch.status != "cancelled",
            ManuscriptDispatch.confirmed_at.is_not(None),
        )
        .all()
    )
    if len(rows) != len(update_by_id):
        raise ValueError("当前项目不存在对应的有效译员安排，请刷新后重试")

    now = datetime.now()
    for row in rows:
        update = update_by_id[row.id]
        if "translator_return_time" in update.model_fields_set:
            row.planned_delivery_at = update.translator_return_time
            # 稿件安排以 final 节点作为全稿预定时间来源；这里必须同步修改，
            # 否则以后再次编辑稿件安排时会被旧节点时间覆盖。
            final_milestone = next(
                (
                    item
                    for item in (getattr(row, "milestones", None) or [])
                    if item.milestone_type == "final"
                ),
                None,
            )
            if final_milestone:
                final_milestone.planned_at = update.translator_return_time
                final_milestone.updated_at = now
        if "completion_remarks" in update.model_fields_set:
            value = update.completion_remarks
            row.completion_remarks = value.strip() if value and value.strip() else None
        for field in ("translator_unit_price", "translator_total_price"):
            if field in update.model_fields_set:
                setattr(row, field, getattr(update, field))
        row.updated_at = now


def _attach_word_count_matrices(
    db: Session,
    *,
    projects: Optional[List[TranslationProject]] = None,
    sub_orders: Optional[List[TranslationSubOrder]] = None,
) -> None:
    """为项目响应批量挂载矩阵数据，并补齐每位译员的预定/实际矩阵。"""
    from word_count_models import WordCountMetric

    from word_count_service import METRIC_TYPES
    metric_types = METRIC_TYPES
    dimensions = ("company", "customer", "preliminary", "translator_estimate")

    def empty_values():
        return {metric_type: None for metric_type in metric_types}

    def empty_matrix():
        return {dimension: empty_values() for dimension in dimensions}

    projects = projects or []
    explicit_sub_orders = sub_orders or []
    # 子订单详情也需要整棵树，才能汇总其下级；按母订单批量加载，避免逐条查询。
    missing_project_ids = {row.parent_project_id for row in explicit_sub_orders} - {row.id for row in projects}
    if missing_project_ids:
        projects = [*projects, *db.query(TranslationProject).filter(TranslationProject.id.in_(missing_project_ids)).all()]
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
        _attach_customer_charge_amounts([*project_map.values(), *all_sub_orders])
        return

    import preliminary_word_count as preliminary
    import translation_duration_metrics as duration
    metric_rows=db.query(WordCountMetric).filter(or_(*filters)).all()+preliminary.rows(db,project_map,sub_order_map)+duration.rows(db,project_map,sub_order_map,arrangement_map)
    for metric in metric_rows:
        if metric.project_id in project_map and metric.dimension in dimensions:
            project_map[metric.project_id].word_count_matrix[metric.dimension][metric.metric_type] = float(metric.count_value) if metric.metric_type in {'minutes','hours'} else metric.count_value
        elif metric.sub_order_id in sub_order_map and metric.dimension in dimensions:
            sub_order_map[metric.sub_order_id].word_count_matrix[metric.dimension][metric.metric_type] = float(metric.count_value) if metric.metric_type in {'minutes','hours'} else metric.count_value
        elif metric.arrangement_id in arrangement_map and metric.dimension in {"planned", "actual"}:
            arrangement_map[metric.arrangement_id][metric.dimension][metric.metric_type] = float(metric.count_value) if metric.metric_type in {'minutes','hours'} else metric.count_value

    from word_count_service import attach_order_sources
    attach_order_sources(list(project_map.values()), list(sub_order_map.values()))

    _attach_customer_charge_amounts([*project_map.values(), *all_sub_orders])


def _attach_customer_charge_amounts(owners) -> None:
    """补齐母/子订单收费项的数量、建议金额及旧版兼容字段。"""
    from sqlalchemy.orm import object_session
    import translation_quantity_basis as quantity_basis
    session=next((object_session(owner) for owner in owners if hasattr(owner,'_sa_instance_state') and object_session(owner) is not None),None)
    bases=quantity_basis.metadata(session,[charge.id for owner in owners for charge in getattr(owner,'customer_charge_items',[])]) if session else {}
    import customer_translation_rates as customer_rates
    directions=customer_rates.metadata(session,[charge.id for owner in owners for charge in getattr(owner,'customer_charge_items',[])]) if session else {}
    for owner in owners:
        customer_values = (getattr(owner, "word_count_matrix", {}) or {}).get("customer", {})
        for charge in getattr(owner, "customer_charge_items", []) or []:
            charge.quantity_basis=bases.get(charge.id)
            charge.language_pair=directions[charge.id].language_pair if charge.id in directions else None
            quantity = (quantity_basis.resolve(getattr(owner,'word_count_matrix',{}),bases[charge.id])[0] if getattr(charge,'id',None) in bases else customer_values.get(charge.metric_type)) if charge.pricing_mode == "metric" else None
            unit_price_excl_tax = getattr(charge, 'unit_price_excl_tax', None)
            if unit_price_excl_tax is None:
                unit_price_excl_tax = charge.unit_price

            def calculated_total(unit_price):
                if (
                    charge.pricing_mode != "metric"
                    or quantity is None
                    or charge.unit_size is None
                    or unit_price is None
                ):
                    return None
                return (
                    Decimal(quantity) / Decimal(charge.unit_size) * Decimal(unit_price)
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            calculated_excl_tax = calculated_total(unit_price_excl_tax)
            calculated_incl_tax = calculated_total(getattr(charge, 'unit_price_incl_tax', None))
            total_excl_tax = getattr(charge, 'total_excl_tax', None)
            if total_excl_tax is None:
                total_excl_tax = charge.amount_override
            if total_excl_tax is None:
                total_excl_tax = calculated_excl_tax
            charge.quantity = quantity
            charge.unit_price_excl_tax = unit_price_excl_tax
            charge.calculated_total_excl_tax = calculated_excl_tax
            charge.calculated_total_incl_tax = calculated_incl_tax
            charge.calculated_amount = calculated_excl_tax
            charge.final_amount = total_excl_tax


def _attach_project_client_fields(project: TranslationProject) -> None:
    """通用客户字段始终返回母客户，子客户通过独立字段精确表达。"""
    parent_client = project.client
    sub_client = project.sub_client

    project.client_name = parent_client.client_name if parent_client else None
    project.client_short_name = parent_client.client_short_name if parent_client else None
    project.client_code = parent_client.client_code if parent_client else None
    state = project.__dict__.get('_project_client_manager')
    project.client_manager = state.new_manager_name if state else (parent_client.client_manager if parent_client else None)
    from project_client_manager import attach
    from sqlalchemy.orm import object_session
    if isinstance(project, TranslationProject) and object_session(project) and '_project_client_manager' not in project.__dict__:
        attach(object_session(project), 'translation', [project])
    project.manager_contact = parent_client.manager_contact if parent_client else None
    project.sub_client_name = (
        (sub_client.client_name or sub_client.client_short_name)
        if sub_client
        else None
    )
    project.sub_client_short_name = sub_client.client_short_name if sub_client else None
    project.sub_client_code = sub_client.sub_client_code if sub_client else None


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


def _resolve_or_create_project_sub_client(
    db: Session,
    parent_client_id: Optional[UUID],
    sub_client_short_name: Optional[str],
    sub_client_name: Optional[str] = None,
) -> Optional[UUID]:
    """在指定母客户下按名称复用或新建待完善的子客户。"""
    normalized_name = (sub_client_short_name or "").strip()
    if not normalized_name:
        return None
    if not parent_client_id:
        raise ValueError("请先选择或输入母客户")

    name_key = normalized_name.lower()
    existing = (
        db.query(SubClient)
        .filter(
            SubClient.parent_client_id == parent_client_id,
            or_(
                func.lower(func.trim(SubClient.client_short_name)) == name_key,
                func.lower(func.trim(SubClient.client_name)) == name_key,
            ),
        )
        .order_by(SubClient.created_at.asc(), SubClient.id.asc())
        .first()
    )
    if existing:
        return existing.id

    full_name = (sub_client_name or "").strip()
    if not full_name:
        raise ValueError("新增子客户时请填写子客户全称")

    sub_client = SubClient(
        parent_client_id=parent_client_id,
        sub_client_code=generate_sub_client_code(db, parent_client_id),
        client_name=full_name,
        client_short_name=normalized_name,
        client_status="pending",
    )
    db.add(sub_client)
    db.flush()
    return sub_client.id


def _resolve_or_create_project_client(
    db: Session,
    client_short_name: Optional[str],
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    manager_contact: Optional[str] = None,
    *,
    is_consultation: bool = False,
) -> tuple[Optional[UUID], Optional[UUID], bool]:
    """按简称/编号关联已有客户；简称不存在时创建一条待完善的母客户记录。"""
    if not getattr(db,'info',{}).get('client_contacts_visible',True):manager_contact=None
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

    if not normalized_client_name:
        if is_consultation:
            raise ValueError("新增客户时请填写客户全称")
        raise ValueError(
            "未匹配到已有客户。若为新客户咨询，请先到“新咨询管理”录入客户及咨询信息，"
            "再继续创建项目；若为已有客户，请从客户列表中选择。"
        )

    client = Client(
        client_code=generate_client_code(db),
        client_name=normalized_client_name,
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
    """按客户、翻译方向和客户交稿时间生成项目名称。"""
    normalized_short_name = (client_short_name or "").strip()
    if not normalized_short_name:
        return ""

    parts = [normalized_short_name]
    normalized_language_pair = compact_translation_direction(language_pair)
    if normalized_language_pair:
        parts.append(normalized_language_pair)
    deadline = customer_deadline_time
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError:
            deadline = None
    if deadline:
        parts.append(f'{deadline.month}月{deadline.day}日{deadline.hour}点回稿')
    if not normalized_language_pair and not deadline:
        parts.append((current_time or datetime.now()).strftime("%y%m%d"))
    if normalized_language_pair or deadline:
        base_name = "，".join(parts)
        return f"{base_name}，{sub_order_count}批" if sub_order_count > 0 else base_name
    base_name = "-".join(parts)
    return f"{base_name}-{sub_order_count}批" if sub_order_count > 0 else base_name


def _is_auto_project_name(
    project_name: Optional[str],
    client_short_name: Optional[str],
) -> bool:
    """判断当前名称是否仍遵循自动命名格式，避免覆盖人工修改。"""
    normalized_project_name = (project_name or "").strip()
    normalized_short_name = (client_short_name or "").strip()
    if not normalized_short_name:
        return False

    current_prefix = f"{normalized_short_name}，"
    if normalized_project_name.startswith(current_prefix):
        suffix = normalized_project_name[len(current_prefix):]
        return bool(re.fullmatch(r".+，\d{1,2}月\d{1,2}日\d{1,2}点回稿(?:，\d+批)?", suffix))

    prefix = f"{normalized_short_name}-"
    if not normalized_project_name.startswith(prefix):
        return False
    suffix = normalized_project_name[len(prefix):]
    if re.fullmatch(r".+-\d{8}-\d{2}:?\d{2}回(?:-\d+批)?", suffix):
        return True
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


def get_translation_project(db: Session, project_id: UUID) -> Optional[TranslationProject]:
    project = (
        db.query(TranslationProject)
        .options(
            joinedload(TranslationProject.client),
            joinedload(TranslationProject.sub_client),
            joinedload(TranslationProject.translator),
            joinedload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .joinedload(ProjectRoleAssignment.assignee),
            joinedload(TranslationProject.project_file),
            selectinload(TranslationProject.customer_charge_items),
            selectinload(TranslationProject.sub_orders).joinedload(TranslationSubOrder.translator),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
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
            selectinload(TranslationProject.customer_charge_items),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
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


def _valid_project_translator_return_time_conditions():
    """返回母项目有效译员回稿时间的统一关联条件。"""
    from manuscript_models import ManuscriptArrangement, ManuscriptDispatch

    return ManuscriptArrangement, ManuscriptDispatch, (
        ManuscriptArrangement.translation_project_id == TranslationProject.id,
        ManuscriptArrangement.sub_order_id.is_(None),
        ManuscriptArrangement.planned_delivery_at.is_not(None),
        ManuscriptArrangement.status != "cancelled",
        ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
        ManuscriptDispatch.status != "cancelled",
        ManuscriptDispatch.confirmed_at.is_not(None),
    )


def _translation_filter_date(value) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="筛选值格式不正确") from exc


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
        from project_client_manager import manager_name_expression
        from translation_customer_type import ClientCustomerType
        customer_type = select(ClientCustomerType.customer_type).where(or_(
            and_(TranslationProject.sub_client_id.is_not(None), ClientCustomerType.sub_client_id == TranslationProject.sub_client_id),
            and_(TranslationProject.sub_client_id.is_(None), ClientCustomerType.client_id == TranslationProject.client_id),
        )).correlate(TranslationProject).scalar_subquery()
        pattern = f"%{keyword.strip()}%"
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(TranslationProject.order_no, _search_part),
            keyword_ilike(TranslationProject.language_pair, _search_part),
            keyword_ilike(customer_type, _search_part),
            keyword_ilike(manager_name_expression('translation', TranslationProject.id, Client.client_manager), _search_part),
            TranslationProject.sub_orders.any(
                keyword_ilike(TranslationSubOrder.sub_order_no, _search_part)
            ),
            TranslationProject.sub_orders.any(
                keyword_ilike(TranslationSubOrder.sub_project_name, _search_part)
            ),
            keyword_ilike(TranslationProject.project_name, _search_part),
            keyword_ilike(TranslationProject.source_file_name, _search_part),
            keyword_ilike(TranslationProject.customer_order_no, _search_part),
            keyword_ilike(Client.client_name, _search_part),
            keyword_ilike(Client.client_short_name, _search_part),
            keyword_ilike(SubClient.client_name, _search_part),
            keyword_ilike(SubClient.client_short_name, _search_part),
        ), pattern))
    if created_by:
        query = query.filter(TranslationProject.created_by == created_by)
    if project_name:
        query = query.filter(keyword_ilike(TranslationProject.project_name, f"%{project_name}%"))
    if order_no:
        query = query.filter(keyword_ilike(TranslationProject.order_no, f"%{order_no}%"))
    if project_status:
        query = query.filter(or_(
            TranslationProject.project_status == project_status,
            TranslationProject.sub_orders.any(
                TranslationSubOrder.status == project_status
            ),
        ))
    if client_short_name:
        query = query.filter(keyword_ilike(Client.client_short_name, f"%{client_short_name}%"))
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
    from managed_project_filters import apply_managed_filter
    query = apply_managed_filter(query, 'translation', field_filters)
    excluded_statuses = field_filters.get('excluded_project_status', {}).get('value') or []
    if excluded_statuses:
        # 排除母项目状态，不因子订单状态不同而重新纳入；兼容历史别名及空格。
        status_value = func.lower(func.trim(func.coalesce(TranslationProject.project_status, '')))
        status_value = case({'pending':'pending_confirmation', 'in_progress':'confirmed',
                             'completed':'sent_to_client', 'terminated':'cancelled',
                             '待确认':'pending_confirmation', '已安排':'arranged', '已发客户':'sent_to_client',
                             '反馈后发客户':'feedback_sent_to_client', '已暂停':'paused', '已取消':'cancelled'},
                            value=status_value, else_=status_value)
        query = query.filter(status_value.notin_(excluded_statuses))
    query = apply_scalar_specs(query, field_filters, {
        "client_id": (TranslationProject.client_id, "uuid"),
        "order_no": (TranslationProject.order_no, "string"),
        "project_name": (TranslationProject.project_name, "string"),
        "source_file_name": (TranslationProject.source_file_name, "string"),
        "service_content": (TranslationProject.service_content, "string"),
        "task_type": (TranslationProject.task_type, "string"),
        "customer_order_no": (TranslationProject.customer_order_no, "string"),
        "project_manager_id": (TranslationProject.project_manager_id, "uuid"),
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
        "translator_assignment_time": (TranslationProject.translator_assignment_time, "datetime"),
        "client_feedback": (TranslationProject.client_feedback, "string"),
        "created_at": (TranslationProject.created_at, "datetime"),
        "updated_at": (TranslationProject.updated_at, "datetime"),
        "pm_confirmed_by": (TranslationProject.pm_confirmed_by, "uuid"),
    })
    project_status_descriptor = field_filters.get("project_status")
    if project_status_descriptor:
        project_status_values = [
            str(value) for value in (project_status_descriptor.get("value") or [])
        ]
        query = query.filter(or_(
            TranslationProject.project_status.in_(project_status_values),
            TranslationProject.sub_orders.any(
                TranslationSubOrder.status.in_(project_status_values)
            ),
        ))
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
        count_match=db_exists().where(and_(*conditions))
        if not word_count_dimension or 'preliminary' in (word_count_dimension.get('value') or []):
            import preliminary_word_count as preliminary
            if preliminary.ready(query.session):
                model=preliminary.PreliminaryWordCountMetric
                preliminary_conditions=[model.project_id==TranslationProject.id]
                if word_count_metric_type:preliminary_conditions.append(model.metric_type.in_(word_count_metric_type.get('value') or []))
                if word_count_descriptor.get('min') not in (None,''):preliminary_conditions.append(model.count_value>=int(word_count_descriptor['min']))
                if word_count_descriptor.get('max') not in (None,''):preliminary_conditions.append(model.count_value<=int(word_count_descriptor['max']))
                count_match=or_(count_match,db_exists().where(and_(*preliminary_conditions)))
        import translation_duration_metrics as duration
        if duration.ready(query.session):
            model=duration.TranslationDurationMetric
            duration_conditions=[model.project_id==TranslationProject.id]
            if word_count_dimension:duration_conditions.append(model.dimension.in_(word_count_dimension.get('value') or []))
            if word_count_metric_type:duration_conditions.append(model.metric_type.in_(word_count_metric_type.get('value') or []))
            if word_count_descriptor.get('min') not in (None,''):duration_conditions.append(model.count_value>=Decimal(str(word_count_descriptor['min'])))
            if word_count_descriptor.get('max') not in (None,''):duration_conditions.append(model.count_value<=Decimal(str(word_count_descriptor['max'])))
            count_match=or_(count_match,db_exists().where(and_(*duration_conditions)))
        query = query.filter(count_match)

    translator_return_time_descriptor = field_filters.get("translator_return_time")
    if translator_return_time_descriptor:
        ManuscriptArrangement, _ManuscriptDispatch, conditions = (
            _valid_project_translator_return_time_conditions()
        )
        return_time_conditions = list(conditions)
        lower = _translation_filter_date(translator_return_time_descriptor.get("from"))
        upper = _translation_filter_date(translator_return_time_descriptor.get("to"))
        if lower is not None:
            return_time_conditions.append(
                ManuscriptArrangement.planned_delivery_at >= datetime.combine(lower, time.min)
            )
        if upper is not None:
            return_time_conditions.append(
                ManuscriptArrangement.planned_delivery_at
                < datetime.combine(upper + timedelta(days=1), time.min)
            )
        query = query.filter(db_exists().where(and_(*return_time_conditions)))

    from project_client_manager import manager_name_expression
    for field, descriptor in field_filters.items():
        if field == 'finance_manager_ids':
            from project_client_manager import manager_ids_expression
            value=descriptor['value']
            query=query.filter(manager_ids_expression('translation',TranslationProject.id,[UUID(item) for item in value['ids']],value['names'],Client.client_manager))
        elif field == 'finance_manager_self':
            from project_client_manager import manager_self_expression
            value=descriptor['value']
            query=query.filter(manager_self_expression('translation',TranslationProject.id,UUID(value['id']),value['names'],Client.client_manager))
        elif field == 'finance_billing_month':
            month = descriptor.get('value')
            query = query.filter(or_(
                TranslationProject.order_no.like(f"TP-{month[2:4]}{month[5:7]}__-%"),
                TranslationProject.order_no.like(f"TP-{month[:4]}{month[5:7]}__-%"),
            ))
        elif field == 'finance_client_id':
            query = query.filter(TranslationProject.client_id == UUID(descriptor['value']))
        elif field == 'finance_payment_status':
            from translation_payment_filters import payment_status_condition
            query = query.filter(payment_status_condition(query.session,descriptor['value']))
        elif field == 'finance_payment_exclude_full':
            from translation_payment_filters import payment_status_condition
            query = query.filter(~payment_status_condition(query.session,'full'))
        elif field == 'finance_payment_project_id':
            query = query.filter(TranslationProject.id==UUID(descriptor['value']))
        elif field == 'finance_client_ids':
            query = query.filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id).in_([UUID(value) for value in descriptor['value']]))
        elif field == 'finance_client':
            from search_matching import keyword_any
            from sqlalchemy.orm import aliased
            parent=aliased(Client)
            parent_name=select(parent.client_name).where(parent.id==SubClient.parent_client_id).correlate(SubClient).scalar_subquery()
            parent_short_name=select(parent.client_short_name).where(parent.id==SubClient.parent_client_id).correlate(SubClient).scalar_subquery()
            query = query.filter(keyword_any([Client.client_name, Client.client_short_name,parent_name,parent_short_name], descriptor.get('value')))
        elif field == 'finance_statement_required':
            from translation_document_requirements import required_expression
            query = query.filter(required_expression(query.session).is_(descriptor['value']))
        elif field == "contact_name":
            from translation_project_contact import TranslationProjectContact
            from search_matching import keyword_any
            query = query.filter(db_exists().where(and_(TranslationProjectContact.project_id == TranslationProject.id, keyword_any([TranslationProjectContact.contact_name], descriptor.get('value')))))
        elif field in {
            "client_name", "client_short_name", "client_code", "client_manager", "manager_contact",
            "sub_client_name", "sub_client_short_name", "sub_client_code",
        }:
            column = {
                "client_name": Client.client_name,
                "client_short_name": Client.client_short_name,
                "client_code": Client.client_code,
                "client_manager": manager_name_expression("translation", TranslationProject.id, Client.client_manager),
                "manager_contact": Client.manager_contact,
                "sub_client_name": SubClient.client_name,
                "sub_client_short_name": SubClient.client_short_name,
                "sub_client_code": SubClient.sub_client_code,
            }[field]
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(keyword_ilike(column, pattern))
        elif field in {"word_count", "word_count_dimension", "word_count_metric_type", "translator_return_time"}:
            continue
        elif field == "translator_assigned":
            from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
            confirmed_arrangement = db_exists().where(and_(
                ManuscriptArrangement.translation_project_id == TranslationProject.id,
                ManuscriptArrangement.sub_order_id.is_(None),
                ManuscriptArrangement.status != "cancelled",
                ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
                ManuscriptDispatch.status != "cancelled",
                ManuscriptDispatch.confirmed_at.is_not(None),
            ))
            assigned = or_(TranslationProject.translator_id.is_not(None), confirmed_arrangement)
            query = query.filter(assigned if descriptor.get("value") is True else ~assigned)
        elif field == "translator_name":
            if descriptor.get("op") != "contains":
                raise HTTPException(status_code=422, detail="译员姓名只支持包含筛选")
            keyword = str(descriptor.get("value") or "").strip()
            if keyword:
                from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
                pattern = f"%{keyword}%"
                confirmed_arrangement = db_exists().where(and_(
                    ManuscriptArrangement.translation_project_id == TranslationProject.id,
                    ManuscriptArrangement.status != "cancelled",
                    keyword_ilike(ManuscriptArrangement.translator_name_snapshot, pattern),
                    ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
                    ManuscriptDispatch.status != "cancelled",
                    ManuscriptDispatch.confirmed_at.is_not(None),
                ))
                query = query.filter(or_(
                    TranslationProject.translator.has(keyword_ilike(Translator.translator_name, pattern)),
                    confirmed_arrangement,
                ))
        elif field == "translator_id":
            translator_ids = descriptor.get("value") or []
            if not isinstance(translator_ids, (list, tuple, set)):
                translator_ids = [translator_ids]
            if translator_ids:
                from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
                confirmed_arrangement = db_exists().where(and_(
                    ManuscriptArrangement.translation_project_id == TranslationProject.id,
                    ManuscriptArrangement.translator_id.in_(translator_ids),
                    ManuscriptArrangement.status != "cancelled",
                    ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
                    ManuscriptDispatch.status != "cancelled",
                    ManuscriptDispatch.confirmed_at.is_not(None),
                ))
                query = query.filter(or_(
                    TranslationProject.translator_id.in_(translator_ids),
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
                ProjectRoleAssignment.assignee.has(keyword_or(lambda _search_part: or_(
                    keyword_ilike(AppUser.full_name, _search_part), keyword_ilike(AppUser.username, _search_part)
                ), f"%{keyword}%")),
            )))
        elif field in {"project_specialist_id", "project_assistant_id", "layout_specialist_id"}:
            role_code = {
                "project_specialist_id": "project_specialist",
                "project_assistant_id": "project_assistant",
                "layout_specialist_id": "layout_specialist",
            }[field]
            assignee_ids = [UUID(str(value)) for value in descriptor.get("value") or []]
            if assignee_ids:
                query = query.filter(TranslationProject.project_role_assignments.any(and_(
                    ProjectRoleAssignment.role_code == role_code,
                    ProjectRoleAssignment.assignee_id.in_(assignee_ids),
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
            query = query.filter(TranslationProject.project_file.any(keyword_ilike(file_column, f"%{keyword}%")))
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
            joinedload(TranslationProject.client),
            joinedload(TranslationProject.sub_client),
            joinedload(TranslationProject.translator),
            joinedload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_role_assignments)
            .joinedload(ProjectRoleAssignment.assignee),
            joinedload(TranslationProject.project_file),
            selectinload(TranslationProject.customer_charge_items),
            selectinload(TranslationProject.sub_orders).joinedload(TranslationSubOrder.translator),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
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
    if sort in {'client_short_name_asc','client_short_name_desc'}:
        parent_name=select(func.coalesce(func.nullif(Client.client_short_name,''),Client.client_name)).where(Client.id==SubClient.parent_client_id).correlate(SubClient).scalar_subquery()
        name=func.coalesce(func.nullif(Client.client_short_name,''),func.nullif(Client.client_name,''),parent_name)
        ordering=((name.asc() if sort.endswith('_asc') else name.desc()).nullslast(),TranslationProject.created_at.desc(),TranslationProject.id.desc())
    elif sort in {
        "order_no_desc",
        "unfinished_first_order_no_desc",
        "customer_deadline_time_asc",
        "translator_return_time_asc", "translator_return_time_desc", "customer_deadline_time_desc",
        "assigned_translator_name_asc", "assigned_translator_name_desc",
    }:
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
        elif sort in {'customer_deadline_time_asc','customer_deadline_time_desc'}:
            column=TranslationProject.customer_deadline_time
            ordering=((column.asc() if sort.endswith('_asc') else column.desc()).nullslast(),*order_no_ordering)
        elif sort in {'translator_return_time_asc','translator_return_time_desc'}:
            ManuscriptArrangement,ManuscriptDispatch,conditions=_valid_project_translator_return_time_conditions()
            earliest=select(func.min(ManuscriptArrangement.planned_delivery_at)).join(
                ManuscriptDispatch,ManuscriptDispatch.id==ManuscriptArrangement.dispatch_id).where(*conditions).correlate(TranslationProject).scalar_subquery()
            ordering=((earliest.asc() if sort.endswith('_asc') else earliest.desc()).nullslast(),*order_no_ordering)
        elif sort in {'assigned_translator_name_asc','assigned_translator_name_desc'}:
            from translation_project_sorting import translator_name_sort_expression
            name_rank=translator_name_sort_expression(db,query)
            ordering=((name_rank.asc() if sort.endswith('_asc') else name_rank.desc()).nullslast(),*order_no_ordering)
        else:
            ordering = order_no_ordering
    else:
        ordering = (
            TranslationProject.created_at.desc(),
            TranslationProject.id.desc(),
        )
    rows = (
        query.add_columns(func.count(TranslationProject.id).over().label("_page_total"))
        .order_by(*ordering)
        .offset(skip)
        .limit(limit)
        .all()
    )
    projects = []
    for project, page_total in rows:
        project.__dict__["_page_total"] = int(page_total or 0)
        projects.append(project)
    from project_client_manager import attach as attach_client_managers
    attach_client_managers(db, 'translation', projects)
    for project in projects:
        _attach_project_client_fields(project)
        _attach_project_file_detail_fields(project)
    _attach_manuscript_assignees(db, projects=projects)
    if sort in {'assigned_translator_name_asc','assigned_translator_name_desc'}:
        from translation_project_sorting import translator_name_key
        for project in projects:
            project.assigned_translators.sort(key=lambda item:translator_name_key(item.get('translator_name')))
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


def _normalize_catalog_language_pairs(db: Session, value: Optional[str]) -> Optional[str]:
    """使用包含已停用项的完整共享目录校验笔译方向，兼容历史记录。"""
    if value is None:
        return None
    from interpretation_models import InterpretationLanguage

    labels = [row[0] for row in db.query(InterpretationLanguage.label).all()]
    return validate_language_pairs_against_catalog(value, labels)


def _append_selected_source_files(db, parent, files, actor_id):
    """与项目保存共用事务，重复提交跳过相同文件，同名异路径明确拒绝。"""
    import ntpath
    if not files:
        return
    existing = db.query(TranslationSubOrder).filter(
        TranslationSubOrder.parent_project_id == parent.id
    ).all()
    names = {item.sub_project_name.casefold(): (item.network_file_path or '').casefold() for item in existing}
    paths = {path for path in names.values() if path}
    for item in files:
        if ntpath.basename(item.path).casefold() != item.name.casefold():
            raise ValueError('所选文件名称与路径不一致，请重新选择')
        name, path = item.name.casefold(), item.path.casefold()
        if name in names:
            if names[name] == path:
                continue
            raise ValueError(f'已存在同名子订单：{item.name}，请核对文件路径')
        if path in paths:
            continue
        _create_sub_order_in_transaction(db, TranslationSubOrderCreate(
            parent_project_id=parent.id, sub_project_name=item.name,
            network_file_path=item.path, language_pair=parent.language_pair,
            priority=parent.priority, customer_deadline_time=parent.customer_deadline_time,
            created_by=actor_id,
        ))
        names[name] = path
        paths.add(path)
    db.expire(parent, ['sub_orders'])


def create_translation_project(
    db: Session,
    project: TranslationProjectCreate,
    *,
    commit: bool = True,
    order_no: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    operation_source: str = "project_form",
    folder_root: bool = False,
) -> TranslationProject:
    order_no = order_no or generate_order_no(db)
    role_assignments = project.role_assignments
    project_data = project.model_dump(exclude={
        'client_short_name', 'client_code', 'client_name', 'contact_name', 'sub_client_name', 'manager_contact', 'sub_client_short_name',
        'word_count_matrix', 'customer_charge_items', 'role_assignments', 'client_manager_id', 'client_manager_change_reason', 'selected_source_files', 'initial_sub_order_names', 'initial_folder_import', 'initial_sub_order_details', 'submission_mode', 'sub_orders_reviewed', 'customer_type', 'statement_required', 'quotation_draft', 'payment_draft', 'payment_version', 'payment_confirmation'
    })
    if 'source_file_name' not in project.model_fields_set:
        project_data.pop('source_file_name', None)
    normalize_translation_name_payload(project_data, has_sub_orders=bool(project.initial_sub_order_names or project.selected_source_files) or bool(project.initial_folder_import) or folder_root)
    project_data['email_subject_preview'] = normalize_email_subject_order_no(
        project_data.get('email_subject_preview'), order_no
    )
    project_data['language_pair'] = _normalize_catalog_language_pairs(
        db, project_data.get('language_pair')
    )
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
            client_name=project.client_name,
            manager_contact=project.manager_contact,
        )
        if client_id:
            project_data['client_id'] = client_id
        if sub_client_id:
            project_data['sub_client_id'] = sub_client_id

    if not project_data.get('sub_client_id') and (project.sub_client_short_name or '').strip():
        project_data['sub_client_id'] = _resolve_or_create_project_sub_client(
            db,
            project_data.get('client_id'),
            project.sub_client_short_name,
            sub_client_name=project.sub_client_name,
        )

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
    if 'contact_name' in project.model_fields_set:
        save_project_contact(db, db_project, project.contact_name, project.created_by)
    from translation_customer_type import save as save_customer_type
    if 'customer_type' in project.model_fields_set:
        save_customer_type(db, db_project, project.customer_type)
    from translation_document_requirements import save as save_document_requirements
    save_document_requirements(db, db_project, statement_required=project.statement_required,
        quotation_draft=project.quotation_draft, actor_id=project.created_by)
    if project.payment_draft is not None:
        from translation_payment_service import save as save_payments
        save_payments(db, db_project, project.payment_draft, project.payment_version, project.created_by, project.payment_confirmation)
    elif project.payment_confirmation is not None:
        from translation_payment_confirmation import save as save_payment_confirmation
        save_payment_confirmation(db,db_project.id,project.payment_confirmation,project.created_by)
    from project_client_manager import apply as apply_client_manager
    apply_client_manager(db, 'translation', db_project, project.client_manager_id, project.client_manager_change_reason, project.created_by, creating=True)
    _sync_project_role_assignments(db, db_project, role_assignments)

    from word_count_service import save_created_entity_matrix
    save_created_entity_matrix(
        db,
        "project",
        db_project.id,
        project.word_count_matrix,
        updated_by=project.created_by,
    )
    _replace_customer_charge_items(
        db,
        db_project,
        project.customer_charge_items,
        customer_values=project.word_count_matrix.customer.model_dump(),
    )

    from workflow_crud import init_workflow

    # 项目与初始工作流必须处于同一个事务中，避免接口失败但项目已单独落库。
    init_workflow(db, db_project.id, commit=False)
    from customer_finance_sync import inherit_translation
    inherit_translation(db,db_project,project.created_by)
    _append_selected_source_files(db, db_project, project.selected_source_files, project.created_by)
    auto_created = 0
    if project.initial_folder_import:
        from translation_folder_orders import FolderImport, import_folders
        import_folders(db, FolderImport(parent_project_id=db_project.id, **project.initial_folder_import.model_dump()), project.created_by, commit=False, update_root=False)
        db.expire(db_project, ["sub_orders"])
    initial_offset = max((int(row.sub_order_no.rsplit(".",1)[-1]) for row in db_project.sub_orders if row.sub_order_no.count(".")==1), default=0) if project.initial_folder_import else 0
    for index, name in enumerate(project.initial_sub_order_names, initial_offset+1):
        initial_values = dict(project.initial_sub_order_details.get(f'{index:03d}', {}))
        initial_values.pop('sub_project_name', None)
        initial_child = _create_sub_order_in_transaction(db, TranslationSubOrderCreate(
            **{'language_pair':db_project.language_pair, 'priority':db_project.priority,
               'customer_deadline_time':db_project.customer_deadline_time, **initial_values,
               'parent_project_id':db_project.id, 'sub_project_name':name, 'created_by':project.created_by},
        ))
        auto_created += getattr(initial_child, 'auto_created_child_count', 0)
    from translation_direction_service import ensure_direction_children
    if not project.initial_folder_import:
        auto_created += len(ensure_direction_children(db, db_project, project.created_by))
    db_project.auto_created_child_count = auto_created
    from translation_project_submission import apply as apply_submission, apply_initial_details
    apply_initial_details(db, db_project, project.initial_sub_order_details)
    apply_submission(db, db_project, project.submission_mode, project.sub_orders_reviewed)
    if project.initial_sub_order_names or project.initial_folder_import:
        db.expire(db_project, ['sub_orders'])
    record_project_operation(
        db,
        project_type="translation",
        operation_type="create",
        project=db_project,
        actor_user_id=project.created_by,
        operation_source=operation_source,
    )
    if commit:
        db.commit()
    else:
        db.flush()
    return get_translation_project(db, db_project.id)


def update_translation_project(db: Session, project_id: UUID, project_update: TranslationProjectUpdate, actor_user_id: Optional[UUID] = None) -> Optional[TranslationProject]:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return None
    
    role_assignments_provided = (
        'role_assignments' in project_update.model_fields_set
        and project_update.role_assignments is not None
    )
    role_assignments = project_update.role_assignments if role_assignments_provided else None
    completion_updates = project_update.assigned_translator_completions
    charge_updates = project_update.customer_charge_items
    matrix_update = project_update.word_count_matrix
    update_data = project_update.model_dump(
        exclude_unset=True,
        exclude={'selected_source_files', 'submission_mode','sub_orders_reviewed','client_short_name', 'client_code', 'client_name', 'contact_name', 'sub_client_name', 'manager_contact', 'sub_client_short_name', 'word_count_matrix', 'customer_charge_items', 'role_assignments', 'assigned_translator_completions', 'client_manager_id', 'client_manager_change_reason', 'customer_type', 'statement_required', 'quotation_draft', 'payment_draft', 'payment_version', 'payment_confirmation', VERSION_FIELD},
    )
    update_data.pop('mother_split_reviewed', None)
    db.query(TranslationProject).filter(TranslationProject.id == project_id).with_for_update().populate_existing().one()
    assert_fresh(db_project, project_update.expected_updated_at)
    from translation_order_inheritance import prepare as prepare_inheritance, synchronize as synchronize_inheritance, FIELDS as INHERITED_FIELDS
    inheritance_context = prepare_inheritance(db, project_id) if any(('status' if key == 'project_status' else key) in INHERITED_FIELDS for key in update_data) else None
    if 'client_manager_id' in project_update.model_fields_set:
        from project_client_manager import apply as apply_client_manager
        apply_client_manager(db, 'translation', db_project, project_update.client_manager_id, project_update.client_manager_change_reason, actor_user_id)
    from translation_folder_orders import is_folder_root
    normalize_translation_name_payload(update_data, has_sub_orders=bool(db_project.sub_orders or project_update.selected_source_files) or is_folder_root(db,db_project.id))
    if 'project_name' in update_data and db_project.source_file_name and 'source_file_name' not in update_data:
        update_data['project_name'] = db_project.source_file_name
    if 'language_pair' in update_data:
        update_data['language_pair'] = _normalize_catalog_language_pairs(
            db, update_data.get('language_pair')
        )
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
            client_name=project_update.client_name,
            manager_contact=project_update.manager_contact,
        )
        if client_id:
            update_data['client_id'] = client_id
            # 从原客户（尤其是子客户）切换到手工输入客户时，同步清除旧子客户关联。
            update_data['sub_client_id'] = sub_client_id

    if not update_data.get('sub_client_id') and (project_update.sub_client_short_name or '').strip():
        update_data['sub_client_id'] = _resolve_or_create_project_sub_client(
            db,
            update_data.get('client_id', db_project.client_id),
            project_update.sub_client_short_name,
            sub_client_name=project_update.sub_client_name,
        )

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
    if 'contact_name' in project_update.model_fields_set:
        save_project_contact(db, db_project, project_update.contact_name, actor_user_id)
    if 'customer_type' in project_update.model_fields_set:
        from translation_customer_type import save as save_customer_type
        save_customer_type(db, db_project, project_update.customer_type)
    from translation_document_requirements import save as save_document_requirements
    save_document_requirements(db, db_project, statement_required=project_update.statement_required,
        quotation_draft=project_update.quotation_draft, actor_id=actor_user_id)
    if project_update.payment_draft is not None:
        from translation_payment_service import save as save_payments
        save_payments(db, db_project, project_update.payment_draft, project_update.payment_version, actor_user_id, project_update.payment_confirmation)
    elif project_update.payment_confirmation is not None:
        from translation_payment_confirmation import save as save_payment_confirmation
        save_payment_confirmation(db,db_project.id,project_update.payment_confirmation,actor_user_id)
    if 'project_status' in update_data:
        from project_workbench_service import cancel_pending_project_handovers, is_active_project
        if not is_active_project('translation', db_project.project_status):
            cancel_pending_project_handovers(
                db,
                'translation',
                db_project.id,
                reason='项目已交付或离开工作台活跃范围',
            )
    if role_assignments_provided:
        _sync_project_role_assignments(db, db_project, role_assignments)
    _sync_assigned_translator_completions(
        db,
        completion_updates,
        project_id=db_project.id,
        sub_order_id=None,
    )
    if matrix_update is not None:
        from word_count_service import replace_entity_matrix
        replace_entity_matrix(
            db,
            'project',
            db_project.id,
            matrix_update,
            updated_by=None,
        )
        customer_values = matrix_update.customer.model_dump()
    else:
        customer_values = (getattr(db_project, 'word_count_matrix', {}) or {}).get('customer', {})
    if charge_updates is not None:
        _replace_customer_charge_items(
            db, db_project, charge_updates, customer_values=customer_values,
        )
    elif matrix_update is not None:
        _validate_charge_metric_values(db_project.customer_charge_items, customer_values)
    from translation_direction_service import ensure_direction_children
    if inheritance_context:
        synchronize_inheritance(db, inheritance_context)
    from translation_project_submission import apply as apply_submission
    db_project.auto_created_child_count = len(ensure_direction_children(db, db_project, actor_user_id)) if 'language_pair' in update_data else 0
    apply_submission(db, db_project, project_update.submission_mode, project_update.sub_orders_reviewed)
    from annotation_progress_time import business_now
    db_project.updated_at = business_now()
    if project_update.mother_split_reviewed:
        from translation_mother_split import review
        review(db,db_project,actor_user_id)
    
    _append_selected_source_files(db, db_project, project_update.selected_source_files, actor_user_id)
    db.commit()
    db.refresh(db_project)
    
    db_project.__dict__.pop('_project_client_manager', None)
    # Reload with client_short_name
    return get_translation_project(db, project_id)


def delete_translation_project(
    db: Session, project_id: UUID, *, actor_user_id: Optional[UUID] = None,
    operation_source: str = "project_delete",
) -> bool:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return False
    from project_workbench_service import cancel_pending_project_handovers
    cancel_pending_project_handovers(db, 'translation', project_id)
    record_project_operation(
        db, project_type="translation", operation_type="delete", project=db_project,
        actor_user_id=actor_user_id, operation_source=operation_source,
    )
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


def _notification_query(
    db: Session,
    recipient_user_id: UUID,
    unread_only: bool = False,
    channel: str = 'all',
    notification_type: Optional[str] = None,
    notification_types: Optional[List[str]] = None,
    notification_ids: Optional[List[UUID]] = None,
    keyword: Optional[str] = None,
    read_status: str = 'all',
):
    from notification_channels import filter_notification_channel
    query = db.query(AppNotification).filter(AppNotification.recipient_user_id == recipient_user_id)
    query = filter_notification_channel(query, AppNotification, channel)
    from notification_channels import filter_notification_visibility
    query = filter_notification_visibility(query, AppNotification, db, recipient_user_id)
    if notification_type:
        query = query.filter(AppNotification.notification_type == notification_type)
    if notification_types:
        query = query.filter(AppNotification.notification_type.in_(notification_types))
    if notification_ids is not None:
        query = query.filter(AppNotification.id.in_(notification_ids))
    if unread_only:
        query = query.filter(AppNotification.is_read == False)
    if read_status in {'read', 'unread'}:
        query = query.filter(AppNotification.is_read == (read_status == 'read'))
    if keyword:
        from search_matching import keyword_any
        query = query.filter(keyword_any([AppNotification.title, AppNotification.content], keyword))
    return query


def get_notifications(
    db: Session, recipient_user_id: UUID, skip: int = 0, limit: int = 20,
    unread_only: bool = False, channel: str = 'all',
    notification_type: Optional[str] = None, notification_types: Optional[List[str]] = None,
    keyword: Optional[str] = None, read_status: str = 'all',
    notification_ids: Optional[List[UUID]] = None,
) -> List[AppNotification]:
    query = _notification_query(db, recipient_user_id, unread_only, channel, notification_type, notification_types, notification_ids, keyword, read_status)
    rows = query.order_by(AppNotification.created_at.desc(), AppNotification.id.desc()).offset(skip).limit(limit).all()
    from resource_request_dispatch import annotate_sender_entries
    annotate_sender_entries(db, recipient_user_id, rows)
    return rows


def count_notifications(db: Session, recipient_user_id: UUID, **filters) -> int:
    return _notification_query(db, recipient_user_id, **filters).count()


def count_unread_notifications(db: Session, recipient_user_id: UUID, channel: str = 'all', notification_type: Optional[str] = None, notification_types: Optional[List[str]] = None) -> int:
    from notification_channels import filter_notification_channel
    query = (
        db.query(AppNotification.id)
        .filter(
            AppNotification.recipient_user_id == recipient_user_id,
            AppNotification.is_read == False,
        )
    )
    if notification_type:
        query = query.filter(AppNotification.notification_type == notification_type)
    if notification_types:
        query = query.filter(AppNotification.notification_type.in_(notification_types))
    from notification_channels import filter_notification_visibility
    return filter_notification_visibility(filter_notification_channel(query, AppNotification, channel), AppNotification, db, recipient_user_id).count()


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


def mark_all_notifications_read(db: Session, recipient_user_id: UUID, channel: str = 'all') -> int:
    from notification_channels import filter_notification_channel
    query = (
        db.query(AppNotification)
        .filter(
            AppNotification.recipient_user_id == recipient_user_id,
            AppNotification.is_read == False,
        )
    )
    notifications = filter_notification_channel(query, AppNotification, channel).all()
    if not notifications:
        return 0
    # read_at 延续既有 UTC 无时区存储语义，避免更改历史数据含义。
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
    db.commit()
    return len(notifications)


# ProjectFile CRUD
PROJECT_FILE_STATUS_SEQUENCE = {
    'cost_calculation': 0,
    'simple_requirement': 0,
    'source_file_simple_requirement': 0,
    'pending': 0,
    'pending_confirmation': 0,
    'in_progress': 1,
    'confirmed': 1,
    'organized': 2,
    'arranged': 2,
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
        from project_workbench_service import cancel_pending_project_handovers, is_active_project
        if not is_active_project('translation', project.project_status):
            cancel_pending_project_handovers(
                db,
                'translation',
                project.id,
                reason='项目已交付或离开工作台活跃范围',
            )
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
            keyword_ilike(TranslationProject.order_no, f'%{order_no}%')
        )
    return q.offset(skip).limit(limit).all()


def count_project_files(db: Session, order_no: Optional[str] = None) -> int:
    q = db.query(ProjectFile.id)
    if order_no:
        q = q.join(ProjectFile.translation_project).filter(
            keyword_ilike(TranslationProject.order_no, f'%{order_no}%')
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
    from chat_time import now
    today_str = now().strftime("%y%m%d")
    prefix = f"EQ-{today_str}-"

    last_consultation = (
        db.query(Consultation)
        .filter(keyword_like(Consultation.consultation_code, f"EQ-{today_str}-%"))
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

    from business_numbering import allocate
    return allocate(db, 'consultation', prefix, new_seq)


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
    from consultation_outcome import FAILURE_KEY
    consultation.failure_reason = (consultation.project_intake or {}).get(FAILURE_KEY)
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
    from consultation_contacts import read_contacts
    read_contacts(db, consultation)
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
    '（音视频）转录/字幕项目': ('（音视频）转录/字幕项目', '字幕项目', 'subtitle'),
    '字幕项目': ('（音视频）转录/字幕项目', '字幕项目', 'subtitle'),
    'subtitle': ('（音视频）转录/字幕项目', '字幕项目', 'subtitle'),
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
    field_filters: Optional[dict] = None,
):
    if keyword and keyword.strip():
        keyword_pattern = f"%{keyword.strip()}%"
        query = query.filter(keyword_or(lambda _search_part: or_(
            keyword_ilike(Consultation.consultation_code, _search_part),
            keyword_ilike(Consultation.project_name, _search_part),
            keyword_ilike(Consultation.customer_order_no, _search_part),
            keyword_ilike(Client.client_name, _search_part),
            keyword_ilike(Client.client_short_name, _search_part),
            keyword_ilike(SubClient.client_name, _search_part),
            keyword_ilike(SubClient.client_short_name, _search_part),
        ), keyword_pattern))
    if consultation_code:
        query = query.filter(keyword_ilike(Consultation.consultation_code, f"%{consultation_code}%"))
    if client_name:
        client_keyword = client_name.strip()
        if client_keyword:
            keyword_pattern = f"%{client_keyword}%"
            query = query.filter(keyword_or(lambda _search_part: or_(
                keyword_ilike(Client.client_name, _search_part),
                keyword_ilike(Client.client_short_name, _search_part),
                keyword_ilike(SubClient.client_name, _search_part),
                keyword_ilike(SubClient.client_short_name, _search_part),
            ), keyword_pattern))
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
        query = query.filter(keyword_ilike(Consultation.client_source, f"%{client_source.strip()}%"))
    if customer_service_id:
        query = query.filter(Consultation.customer_service_id == customer_service_id)
    if sales_person_id:
        query = query.filter(Consultation.sales_person_id == sales_person_id)
    if follow_up_person_id:
        query = query.filter(Consultation.follow_up_person_id == follow_up_person_id)
    if follow_up_status and follow_up_status.strip():
        query = query.filter(keyword_ilike(Consultation.follow_up_status, f"%{follow_up_status.strip()}%"))
    field_filters = field_filters or {}
    from managed_project_filters import apply_managed_filter
    query = apply_managed_filter(query, 'consultation', field_filters)
    query = apply_scalar_specs(query, field_filters, {
        "consultation_code": (Consultation.consultation_code, "string"),
        "status": (Consultation.status, "string"),
        "consultation_time": (Consultation.consultation_time, "datetime"),
        "client_source": (Consultation.client_source, "string"),
        "source_keyword": (Consultation.source_keyword, "string"),
        "handling_method": (Consultation.handling_method, "string"),
        "customer_service_id": (Consultation.customer_service_id, "uuid"),
        "sales_person_id": (Consultation.sales_person_id, "uuid"),
        "editor_id": (Consultation.editor_id, "uuid"),
        "follow_up_person_id": (Consultation.follow_up_person_id, "uuid"),
        "follow_up_count": (Consultation.follow_up_count, "integer"),
        "follow_up_time": (Consultation.follow_up_time, "datetime"),
        "follow_up_status": (Consultation.follow_up_status, "string"),
        "consultation_description": (Consultation.consultation_description, "string"),
        "follow_up_remarks": (Consultation.follow_up_remarks, "string"),
        "remarks": (Consultation.remarks, "string"),
        "created_at": (Consultation.created_at, "datetime"),
        "updated_at": (Consultation.updated_at, "datetime"),
    })
    for field, descriptor in field_filters.items():
        if field in {"client_code", "client_name", "client_short_name"}:
            column = {
                "client_code": Client.client_code,
                "client_name": Client.client_name,
                "client_short_name": Client.client_short_name,
            }[field]
            keyword_value = str(descriptor.get("value") or "").strip()
            if keyword_value:
                query = query.filter(keyword_ilike(column, f"%{keyword_value}%"))
        elif field == "consultation_type":
            values = []
            for value in descriptor.get("value") or []:
                values.extend(CONSULTATION_TYPE_FILTER_ALIASES.get(str(value), (str(value),)))
            if values:
                query = query.filter(Consultation.consultation_type.in_(set(values)))
        elif field == "consultation_method":
            values = [str(value) for value in descriptor.get("value") or []]
            if values:
                regular_values = [value for value in values if value != "other"]
                conditions = []
                if regular_values:
                    conditions.append(Consultation.consultation_method.in_(regular_values))
                if "other" in values:
                    conditions.append(or_(
                        Consultation.consultation_method.notin_(["phone", "email", "online", "onsite"]),
                        Consultation.consultation_method.is_(None),
                    ))
                query = query.filter(or_(*conditions))
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
    field_filters: Optional[dict] = None,
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
        field_filters=field_filters,
    )

    results = (
        query.add_columns(func.count(Consultation.id).over().label("_page_total"))
        .order_by(Consultation.created_at.desc()).offset(skip).limit(limit).all()
    )
    
    consultations = []
    for consultation, client_code, db_client_name, client_short_name, manager_contact, sub_client, page_total in results:
        consultation.__dict__["_page_total"] = int(page_total or 0)
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
    field_filters: Optional[dict] = None,
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
        field_filters=field_filters,
    )
    return query.count()


def create_consultation(
    db: Session,
    consultation: ConsultationCreate,
    *,
    idempotency_key: Optional[str] = None,
    commit: bool = True,
    actor=None,
) -> Consultation:
    consultation_code = generate_consultation_code(db)

    consultation_data = consultation.model_dump(exclude={
        'consultation_code',
        'client_code',
        'client_name',
        'client_short_name',
        'manager_contact',
        'contact_people', 'contact_people_updated_at',
        'failure_reason',
    })
    from consultation_work_report import preserve_capture
    consultation_data['project_intake'] = preserve_capture(None, consultation_data.get('project_intake'))
    created_client_id = None
    from consultation_outcome import apply_failure
    consultation_data['project_intake'] = apply_failure(consultation, consultation_data['project_intake'], consultation_data.get('status'))
    if not consultation_data.get('client_id') and (consultation.client_short_name or '').strip():
        client_id, _sub_client_id, _created = _resolve_or_create_project_client(
            db,
            consultation.client_short_name,
            consultation.client_code,
            consultation.client_name,
            is_consultation=True,
        )
        consultation_data['client_id'] = client_id
        if _created:
            created_client_id = client_id

    from consultation_contacts import sync_contacts
    sync_contacts(db, consultation_data.get('client_id'), consultation_data.get('sub_client_id'),
                  consultation.contact_people, consultation.contact_people_updated_at)
    # 旧客户端联系方式兼容；多联系人提交时由联系人同步维护主联系方式。
    if consultation.contact_people is None and 'manager_contact' in consultation.model_fields_set and consultation_data.get('client_id'):
        client = db.query(Client).filter(Client.id == consultation_data['client_id']).first()
        if client:
            client.manager_contact = (consultation.manager_contact or '').strip() or None

    db_consultation = Consultation(
        consultation_code=consultation_code,
        idempotency_key=idempotency_key,
        **consultation_data,
    )
    db.add(db_consultation)
    if created_client_id and actor is not None:
        db.flush()
        from client_operator import record
        record(db, created_client_id, actor, 'consultation_create', db_consultation)
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
    actor=None,
) -> Optional[Consultation]:
    db_consultation = get_consultation(db, consultation_id)
    if not db_consultation:
        return None
    update_data = consultation_update.model_dump(
        exclude_unset=True,
        exclude={'client_code', 'client_name', 'client_short_name', 'manager_contact', 'contact_people', 'contact_people_updated_at', 'failure_reason', VERSION_FIELD},
    )
    assert_fresh(db_consultation, consultation_update.expected_updated_at)
    if 'project_intake' in update_data:
        from consultation_work_report import preserve_capture
        update_data['project_intake'] = preserve_capture(db_consultation.project_intake, update_data['project_intake'])
    from consultation_outcome import apply_failure
    next_intake = apply_failure(consultation_update, update_data.get('project_intake', db_consultation.project_intake),
                               update_data.get('status', db_consultation.status), db_consultation)
    if next_intake != (db_consultation.project_intake or {}):
        update_data['project_intake'] = next_intake
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
            is_consultation=True,
        )
        if client_id:
            update_data['client_id'] = client_id
            if _created:
                from client_operator import record
                record(db, client_id, actor, 'consultation_edit_create', db_consultation)

    from consultation_contacts import sync_contacts
    sync_contacts(db, update_data.get('client_id', db_consultation.client_id),
                  update_data.get('sub_client_id', db_consultation.sub_client_id),
                  consultation_update.contact_people, consultation_update.contact_people_updated_at)
    # 只在请求明确携带该字段时同步客户资料，避免列表内联更新状态时误清空联系方式。
    if consultation_update.contact_people is None and 'manager_contact' in consultation_update.model_fields_set:
        target_client_id = update_data.get('client_id', db_consultation.client_id)
        if target_client_id:
            client = db.query(Client).filter(Client.id == target_client_id).first()
            if client:
                client.manager_contact = (consultation_update.manager_contact or '').strip() or None

    for field, value in update_data.items():
        setattr(db_consultation, field, value)
    # updated_at 的数据库默认值只在新增时生效，编辑时使用服务器时间主动刷新。
    from annotation_progress_time import business_now
    db_consultation.updated_at = business_now().replace(tzinfo=None)
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
        .filter(keyword_like(TranslationSubOrder.sub_order_no, f"{base_no}.%"))
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

    from business_numbering import allocate
    return allocate(db, f'translation_suborder:{parent_project_id}', base_no + '.', new_seq)


def get_sub_order(db: Session, sub_order_id: UUID) -> Optional[TranslationSubOrder]:
    sub_order = (
        db.query(TranslationSubOrder)
        .options(
            selectinload(TranslationSubOrder.translator),
            selectinload(TranslationSubOrder.customer_charge_items),
        )
        .filter(TranslationSubOrder.id == sub_order_id)
        .first()
    )
    if sub_order:
        _attach_manuscript_assignees(db, sub_orders=[sub_order])
    return sub_order


def get_sub_orders_by_project(db: Session, parent_project_id: UUID) -> List[TranslationSubOrder]:
    sub_orders = (
        db.query(TranslationSubOrder)
        .options(
            selectinload(TranslationSubOrder.translator),
            selectinload(TranslationSubOrder.customer_charge_items),
        )
        .filter(TranslationSubOrder.parent_project_id == parent_project_id)
        .order_by(TranslationSubOrder.sub_order_no)
        .all()
    )
    _attach_manuscript_assignees(db, sub_orders=sub_orders)
    return sub_orders


def get_all_sub_orders(db: Session, skip: int = 0, limit: int = 200, sub_order_no: Optional[str] = None, project_name: Optional[str] = None) -> List[TranslationSubOrder]:
    q = db.query(TranslationSubOrder).options(
        selectinload(TranslationSubOrder.translator),
        selectinload(TranslationSubOrder.customer_charge_items),
    )
    if sub_order_no:
        q = q.filter(keyword_ilike(TranslationSubOrder.sub_order_no, f'%{sub_order_no}%'))
    if project_name:
        q = q.filter(keyword_ilike(TranslationSubOrder.sub_project_name, f'%{project_name}%'))
    sub_orders = q.offset(skip).limit(limit).all()
    _attach_manuscript_assignees(db, sub_orders=sub_orders)
    return sub_orders


def _create_sub_order_in_transaction(
    db: Session, sub_order: TranslationSubOrderCreate,
    idempotency_key: Optional[str] = None,
) -> TranslationSubOrder:
    from translation_file_name_rules import normalize_single_file_name
    from translation_folder_orders import TranslationOrderFolder, folder_name
    from translation_direction_service import next_number
    import re
    root=db.query(TranslationProject).filter_by(id=sub_order.parent_project_id).with_for_update().first()
    if not root:raise ValueError('母订单不存在')
    parent=root
    if sub_order.parent_sub_order_id:
        parent=db.query(TranslationSubOrder).filter_by(id=sub_order.parent_sub_order_id,parent_project_id=root.id).first()
        if not parent:raise ValueError('上级子订单不存在或不属于本项目')
    sub_order_no=sub_order.sub_order_no or next_number(db,root,parent)
    if not re.fullmatch(re.escape(root.order_no)+r'(\.\d+){1,4}',sub_order_no):raise ValueError('子订单最多四级，编号必须属于当前母订单')
    prefix=sub_order_no.rsplit('.',1)[0]
    if prefix!=root.order_no and not db.query(TranslationSubOrder.id).filter_by(parent_project_id=root.id,sub_order_no=prefix).first():raise ValueError('请先创建上级子订单')
    if prefix != root.order_no:
        parent = db.query(TranslationSubOrder).filter_by(parent_project_id=root.id, sub_order_no=prefix).one()
    folder=sub_order.folder_info
    file_name=folder_name(sub_order.sub_project_name) if folder else normalize_single_file_name(sub_order.sub_project_name)
    if folder:
        from path_security import validate_managed_path
        if folder.get('source_kind') not in ('local','unc','manifest') or not folder.get('root_path') or not folder.get('relative_path'):raise ValueError('文件夹信息不完整')
        parts=folder['relative_path'].replace('\\','/').split('/')
        if len(parts)>4 or folder_name(parts[-1])!=file_name:raise ValueError('文件夹层级或名称不匹配')
        for name in parts:folder_name(name)
        folder={**folder,'root_path':validate_managed_path(folder['root_path']),'files':[normalize_single_file_name(name) for name in folder.get('files',[])]}
    from translation_order_inheritance import attach_creation_parent, create_state
    attach_creation_parent(db, parent)
    data = sub_order.model_dump(exclude={'preserve_original_file','sub_order_no', 'word_count_matrix', 'customer_charge_items','folder_info','parent_sub_order_id','service_content','customer_requirement_professional','customer_requirement_special'})
    data['sub_project_name'] = file_name
    data['language_pair'] = _normalize_catalog_language_pairs(db, data.get('language_pair'))
    from translation_direction_service import validate_direction_level, ensure_direction_children
    validate_direction_level(sub_order_no, data['language_pair'])
    _validate_written_translator(db, data.get('translator_id'))
    db_sub = TranslationSubOrder(
        sub_order_no=sub_order_no, idempotency_key=idempotency_key, **data,
    )
    db.add(db_sub)
    db.flush()
    create_state(db, db_sub, parent, sub_order)
    if folder:
        db.add(TranslationOrderFolder(sub_order_id=db_sub.id,**{key:folder[key] for key in ('source_kind','root_path','relative_path','files')}))
        db.flush()
        db_sub.folder_info=folder
    from word_count_service import save_created_entity_matrix
    save_created_entity_matrix(
        db,
        "suborder",
        db_sub.id,
        sub_order.word_count_matrix,
        updated_by=sub_order.created_by,
    )
    _replace_customer_charge_items(
        db,
        db_sub,
        sub_order.customer_charge_items,
        customer_values=sub_order.word_count_matrix.customer.model_dump(),
    )
    from workflow_crud import init_workflow

    from translation_customer_finance import inherit_new_order
    inherit_new_order(db, db_sub)
    # 子订单与母订单一致：初始工作流必须同事务落库，否则子订单不会出现在工作台。
    init_workflow(db, sub_order_id=db_sub.id, commit=False)
    db_sub.auto_created_child_count = len(ensure_direction_children(db, db_sub, sub_order.created_by)) if 'language_pair' in sub_order.model_fields_set else 0
    db.expire(root, ['sub_orders'])
    return db_sub


def create_sub_order(
    db: Session, sub_order: TranslationSubOrderCreate,
    idempotency_key: Optional[str] = None,
) -> TranslationSubOrder:
    if sub_order.preserve_original_file and not sub_order.parent_sub_order_id:
        from translation_mother_split import preserve_original
        root=db.query(TranslationProject).filter_by(id=sub_order.parent_project_id).with_for_update().first()
        if not root:raise ValueError('母订单不存在')
        original=preserve_original(db,root,sub_order.created_by)
        if original:sub_order=sub_order.model_copy(update={'sub_order_no':None})
    db_sub = _create_sub_order_in_transaction(db, sub_order, idempotency_key=idempotency_key)
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

    if payload.preserve_original_file:
        from translation_mother_split import preserve_original
        preserve_original(db,parent,created_by)
    existing_names = [
        item.sub_project_name
        for item in db.query(TranslationSubOrder)
        .filter(TranslationSubOrder.parent_project_id == payload.parent_project_id)
        .all()
    ]
    accepted_names, skipped = partition_sub_project_names(payload.sub_project_names, existing_names)
    shared_files = {}
    if payload.source_folder_path:
        from project_file_service import inspect_suborder_shared_folder
        from path_security import validate_managed_path
        listing = inspect_suborder_shared_folder(payload.source_folder_path)
        shared_files = {item['name']: item['network_file_path'] for item in listing['files']}
        if any(name not in shared_files for name in payload.sub_project_names):
            raise ValueError('部分文件已不在共享文件夹第一层，请重新读取后选择')
        shared_files = {name: validate_managed_path(shared_files[name]) for name in payload.sub_project_names}
    defaults = payload.defaults.model_dump(exclude_unset=True)
    # 批量数量创建和按文件名创建都只继承公共字段，字数必须逐个子订单补录。
    from word_count_schemas import WordCountCreateMatrix
    defaults['word_count_matrix'] = WordCountCreateMatrix()
    created: List[TranslationSubOrder] = []
    for name in accepted_names:
        item_defaults = dict(defaults)
        if payload.source_directory is not None:
            from project_file_service import source_file_path
            item_defaults['network_file_path'] = source_file_path(payload.source_directory, name)
        if shared_files:
            item_defaults['network_file_path'] = shared_files[name]
        sub_order = TranslationSubOrderCreate(
            parent_project_id=payload.parent_project_id,
            sub_project_name=name,
            created_by=created_by,
            **item_defaults,
        )
        created.append(_create_sub_order_in_transaction(db, sub_order))

    db.commit()
    for item in created:
        db.refresh(item)
    if created:
        _attach_manuscript_assignees(db, sub_orders=created)
    return created, skipped


def update_sub_order(db: Session, sub_order_id: UUID, sub_order_update: TranslationSubOrderUpdate, *, commit: bool = True) -> Optional[TranslationSubOrder]:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return None
    from translation_order_inheritance import prepare as prepare_inheritance, update_state, synchronize as synchronize_inheritance
    inheritance_context = prepare_inheritance(db, db_sub.parent_project_id)
    completion_updates = sub_order_update.assigned_translator_completions
    charge_updates = sub_order_update.customer_charge_items
    matrix_update = sub_order_update.word_count_matrix
    update_data = sub_order_update.model_dump(
        exclude_unset=True,
        exclude={'word_count_matrix', 'customer_charge_items', 'assigned_translator_completions', 'inherit_fields'},
    )
    if 'sub_project_name' in update_data:
        from translation_file_name_rules import normalize_single_file_name
        from translation_folder_orders import info, folder_name
        update_data['sub_project_name'] = folder_name(update_data['sub_project_name']) if info(db,db_sub.id) else normalize_single_file_name(update_data['sub_project_name'])
    if 'language_pair' in update_data:
        update_data['language_pair'] = _normalize_catalog_language_pairs(
            db, update_data.get('language_pair')
        )
    from translation_direction_service import validate_direction_level, ensure_direction_children
    validate_direction_level(db_sub.sub_order_no, update_data.get('language_pair', db_sub.language_pair))
    if 'translator_id' in update_data:
        _validate_written_translator(db, update_data.get('translator_id'))
    update_state(inheritance_context, db_sub, update_data, sub_order_update.inherit_fields)
    for field, value in update_data.items():
        setattr(db_sub, field, value)
    _sync_assigned_translator_completions(
        db,
        completion_updates,
        project_id=db_sub.parent_project_id,
        sub_order_id=db_sub.id,
    )
    if matrix_update is not None:
        from word_count_service import replace_entity_matrix
        replace_entity_matrix(
            db,
            'suborder',
            db_sub.id,
            matrix_update,
            updated_by=None,
        )
        customer_values = matrix_update.customer.model_dump()
    else:
        customer_values = (getattr(db_sub, 'word_count_matrix', {}) or {}).get('customer', {})
    if charge_updates is not None:
        _replace_customer_charge_items(
            db, db_sub, charge_updates, customer_values=customer_values,
        )
    elif matrix_update is not None:
        _validate_charge_metric_values(db_sub.customer_charge_items, customer_values)
    synchronize_inheritance(db, inheritance_context)
    db_sub.auto_created_child_count = len(ensure_direction_children(db, db_sub, db.info.get('number_actor'))) if 'language_pair' in update_data else 0
    from annotation_progress_time import business_now
    db_sub.updated_at = business_now()
    if commit:
        db.commit()
    else:
        db.flush()
    return get_sub_order(db, db_sub.id)


def _validate_charge_metric_values(items, customer_values: dict) -> None:
    from sqlalchemy.orm import object_session
    import translation_quantity_basis as quantity_basis
    session=next((object_session(row) for row in items or [] if hasattr(row,'_sa_instance_state') and object_session(row) is not None),None)
    bases=quantity_basis.metadata(session,[row.id for row in items or []]) if session else {}
    for charge in items or []:
        if getattr(charge,'id',None) in bases:continue
        if charge.pricing_mode == 'metric' and customer_values.get(charge.metric_type) is None:
            raise ValueError(f'收费项“{charge.item_name}”对应的客户字数口径不能清空')


def _replace_customer_charge_items(
    db: Session,
    owner: TranslationProject | TranslationSubOrder,
    items,
    *,
    customer_values: dict,
) -> None:
    """按稳定 ID 更新收费项，并删除本次未提交的旧收费项。"""
    from annotation_progress_time import business_now
    existing = {
        item.id: item
        for item in list(getattr(owner, 'customer_charge_items', []) or [])
    }
    kept_ids = set()
    normalized = []
    for index, payload in enumerate(items or [], start=1):
        import translation_quantity_basis as quantity_basis
        has_basis=bool(payload.id and payload.id in quantity_basis.metadata(db,[payload.id]))
        if payload.pricing_mode == 'metric' and customer_values.get(payload.metric_type) is None and not has_basis and not payload.quantity_basis:
            raise ValueError(f'收费项“{payload.item_name}”对应的客户字数口径尚未填写')
        row = existing.get(payload.id) if payload.id else None
        if payload.id and row is None:
            raise ValueError('客户收费项不存在或不属于当前订单')
        if row is None:
            row = TranslationSubOrderChargeItem(
                translation_project_id=owner.id if isinstance(owner, TranslationProject) else None,
                sub_order_id=owner.id if isinstance(owner, TranslationSubOrder) else None,
            )
            if not hasattr(owner, 'customer_charge_items'):
                owner.customer_charge_items = []
            owner.customer_charge_items.append(row)
        else:
            kept_ids.add(row.id)
        values = payload.model_dump(exclude={'id','language_pair','quantity_basis'})
        values['sequence_no'] = index
        values['metric_type'] = values['metric_type'] if payload.pricing_mode == 'metric' else None
        values['unit_size'] = values['unit_size'] if payload.pricing_mode == 'metric' else None
        values['unit_price_excl_tax'] = values['unit_price_excl_tax'] if payload.pricing_mode == 'metric' else None
        values['unit_price_incl_tax'] = values['unit_price_incl_tax'] if payload.pricing_mode == 'metric' else None
        # 旧字段与新的不含税字段同步，兼容尚未升级的调用方。
        values['unit_price'] = values['unit_price_excl_tax']
        values['amount_override'] = values['total_excl_tax']
        for field, value in values.items():
            setattr(row, field, value)
        row.updated_at = business_now().replace(tzinfo=None)
        normalized.append(row)
        if payload.quantity_basis or payload.language_pair:
            db.flush()
            if payload.quantity_basis and payload.pricing_mode == 'metric':
                from word_count_service import hierarchy_matrix
                entity_type = 'project' if isinstance(owner, TranslationProject) else 'suborder'
                # 计费校验与列表展示均使用本单独立填报值，不取下级统计。
                matrix = hierarchy_matrix(db, entity_type, owner).word_count_matrix
                if not quantity_basis.valid(payload.quantity_basis) or quantity_basis.resolve(matrix,payload.quantity_basis)[0] is None:
                    raise ValueError('请先填写并选择有效的项目字数统计项')
                quantity_basis.store(db,row,payload.quantity_basis,matrix)
            if payload.language_pair and payload.pricing_mode == 'metric':
                import customer_translation_rates as customer_rates
                meta=db.get(customer_rates.TranslationChargeDirection,row.id)
                if meta is None:meta=customer_rates.TranslationChargeDirection(charge_id=row.id);db.add(meta)
                meta.language_pair=customer_rates.direction(db,payload.language_pair)
                customer_rates.invalidate_metadata(db)
    for item_id, row in existing.items():
        if item_id not in kept_ids:
            db.delete(row)
    owner.customer_charge_items = normalized


def delete_sub_order(db: Session, sub_order_id: UUID) -> bool:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return False
    if db.query(TranslationSubOrder.id).filter(TranslationSubOrder.parent_project_id==db_sub.parent_project_id,TranslationSubOrder.sub_order_no.startswith(db_sub.sub_order_no+'.',autoescape=True)).first():
        raise ValueError('该订单还有下级订单，请先删除下级订单')
    db.delete(db_sub)
    db.flush()
    db.commit()
    return True
