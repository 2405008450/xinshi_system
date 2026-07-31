from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import String, and_, func, or_

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


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> List[AppUser]:
    query = db.query(AppUser)
    if username:
        query = query.filter(AppUser.username.ilike(f"%{username}%"))
    if full_name:
        query = query.filter(AppUser.full_name.ilike(f"%{full_name}%"))
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
) -> int:
    query = db.query(AppUser.id)
    if username:
        query = query.filter(AppUser.username.ilike(f"%{username}%"))
    if full_name:
        query = query.filter(AppUser.full_name.ilike(f"%{full_name}%"))
    return query.count()


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

    return f"{prefix}{new_seq:03d}"


def get_client(db: Session, client_id: UUID) -> Optional[Client]:
    return db.query(Client).options(selectinload(Client.sub_clients)).filter(Client.id == client_id).first()

def get_clients(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    client_short_name: Optional[str] = None,
    frequent_first: bool = False,
) -> List[Client]:
    query = db.query(Client).options(selectinload(Client.sub_clients))
    if client_code:
        pattern = f"%{client_code}%"
        query = query.filter(
            or_(
                Client.client_code.ilike(pattern),
                Client.sub_clients.any(SubClient.sub_client_code.ilike(pattern)),
            )
        )
    if client_name:
        pattern = f"%{client_name}%"
        query = query.filter(
            or_(
                Client.client_name.ilike(pattern),
                Client.sub_clients.any(SubClient.client_name.ilike(pattern)),
            )
        )
    if client_short_name:
        pattern = f"%{client_short_name}%"
        query = query.filter(
            or_(
                Client.client_short_name.ilike(pattern),
                Client.sub_clients.any(SubClient.client_short_name.ilike(pattern)),
            )
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
    return query.offset(skip).limit(limit).all()


def count_clients(
    db: Session,
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    client_short_name: Optional[str] = None,
) -> int:
    query = db.query(Client.id)
    if client_code:
        pattern = f"%{client_code}%"
        query = query.filter(
            or_(
                Client.client_code.ilike(pattern),
                Client.sub_clients.any(SubClient.sub_client_code.ilike(pattern)),
            )
        )
    if client_name:
        pattern = f"%{client_name}%"
        query = query.filter(
            or_(
                Client.client_name.ilike(pattern),
                Client.sub_clients.any(SubClient.client_name.ilike(pattern)),
            )
        )
    if client_short_name:
        pattern = f"%{client_short_name}%"
        query = query.filter(
            or_(
                Client.client_short_name.ilike(pattern),
                Client.sub_clients.any(SubClient.client_short_name.ilike(pattern)),
            )
        )
    return query.count()


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
    db_translator = Translator(**payload)
    db.add(db_translator)
    db.commit()
    db.refresh(db_translator)
    return db_translator

def update_translator(db: Session, translator_id: UUID, translator_update: TranslatorUpdate) -> Optional[Translator]:
    db_translator = get_translator(db, translator_id)
    if not db_translator:
        return None
    payload = _normalize_translator_payload(translator_update.model_dump(exclude_unset=True), current=db_translator)
    for field, value in payload.items():
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
            "planned_word_count": row.planned_word_count,
            "actual_word_count": row.actual_word_count,
            "word_count_type": row.word_count_type,
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


def build_auto_project_name(
    client_short_name: Optional[str],
    sub_order_count: int = 0,
    current_time: Optional[datetime] = None,
) -> str:
    """按客户简称、当前日期和子订单数量生成项目名称。"""
    normalized_short_name = (client_short_name or "").strip()
    if not normalized_short_name:
        return ""

    date_text = (current_time or datetime.now()).strftime("%y%m%d")
    base_name = f"{normalized_short_name}-{date_text}"
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
        .filter(TranslationProject.id == project_id)
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
            selectinload(TranslationProject.project_file),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
        )
        .filter(TranslationProject.id == project_id)
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
            selectinload(TranslationProject.project_file),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
        )
        .filter(TranslationProject.order_no == order_no)
        .first()
    )
    if not project:
        return None
    _attach_project_client_fields(project)
    _attach_project_file_detail_fields(project)
    _attach_manuscript_assignees(db, projects=[project])
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
        db.query(TranslationProject)
        .options(
            selectinload(TranslationProject.client),
            selectinload(TranslationProject.sub_client),
            selectinload(TranslationProject.translator),
            selectinload(TranslationProject.project_manager),
            selectinload(TranslationProject.project_file),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.translator),
        )
        .outerjoin(Client, TranslationProject.client_id == Client.id)
        .outerjoin(SubClient, TranslationProject.sub_client_id == SubClient.id)
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
        pattern = f"%{client_short_name}%"
        query = query.filter(
            or_(
                Client.client_short_name.ilike(pattern),
                SubClient.client_short_name.ilike(pattern),
            )
        )
    projects = (
        query
        .order_by(TranslationProject.created_at.desc(), TranslationProject.id.desc())
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
    created_by: Optional[UUID] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    project_status: Optional[str] = None,
    client_short_name: Optional[str] = None
) -> int:
    query = (
        db.query(TranslationProject.id)
        .outerjoin(Client, TranslationProject.client_id == Client.id)
        .outerjoin(SubClient, TranslationProject.sub_client_id == SubClient.id)
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
        pattern = f"%{client_short_name}%"
        query = query.filter(
            or_(
                Client.client_short_name.ilike(pattern),
                SubClient.client_short_name.ilike(pattern),
            )
        )
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

    project_data['client_id'] = _resolve_project_client_link(
        db,
        project_data.get('client_id'),
        project_data.get('sub_client_id'),
    )
    _validate_project_manager(db, project_data.get('project_manager_id'))
    _normalize_project_business_details(project_data)

    db_project = TranslationProject(
        order_no=order_no,
        **project_data
    )
    db.add(db_project)
    db.flush()

    from workflow_crud import init_workflow

    # 项目与初始工作流必须处于同一个事务中，避免接口失败但项目已单独落库。
    init_workflow(db, db_project.id, commit=False)
    db.commit()
    return get_translation_project(db, db_project.id)


def update_translation_project(db: Session, project_id: UUID, project_update: TranslationProjectUpdate) -> Optional[TranslationProject]:
    db_project = get_translation_project(db, project_id)
    if not db_project:
        return None
    
    update_data = project_update.model_dump(exclude_unset=True, exclude={'client_short_name', 'client_code'})
    
    # 未显式选择客户 ID 时，仍允许通过精确简称或客户编号补齐外键。
    if project_update.client_short_name and not update_data.get('client_id'):
        client = db.query(Client).filter(Client.client_short_name == project_update.client_short_name).first()
        if client:
            update_data['client_id'] = client.id
    elif project_update.client_code and not update_data.get('client_id'):
        client = db.query(Client).filter(Client.client_code == project_update.client_code).first()
        if client:
            update_data['client_id'] = client.id

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
        _validate_project_manager(db, update_data.get('project_manager_id'))
    _normalize_project_business_details(update_data, db_project)

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
    """根据母订单号生成三位子单流水号，如 TP-260302-014.001。"""
    parent = db.query(TranslationProject).filter(TranslationProject.id == parent_project_id).first()
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


def create_sub_order(db: Session, sub_order: TranslationSubOrderCreate) -> TranslationSubOrder:
    sub_order_no = sub_order.sub_order_no or generate_sub_order_no(db, sub_order.parent_project_id)
    data = sub_order.model_dump(exclude={'sub_order_no'})
    db_sub = TranslationSubOrder(sub_order_no=sub_order_no, **data)
    db.add(db_sub)
    db.flush()
    _sync_project_name_with_sub_order_count(db, sub_order.parent_project_id)
    db.commit()
    return get_sub_order(db, db_sub.id)


def update_sub_order(db: Session, sub_order_id: UUID, sub_order_update: TranslationSubOrderUpdate) -> Optional[TranslationSubOrder]:
    db_sub = get_sub_order(db, sub_order_id)
    if not db_sub:
        return None
    for field, value in sub_order_update.model_dump(exclude_unset=True).items():
        setattr(db_sub, field, value)
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
