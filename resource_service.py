"""统一人才资源库查询、写入、兼容同步与历史回填。"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import String, and_, cast, func, inspect, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from interpretation_models import InterpretationLanguage
from resource_models import (
    AnnotationProfile,
    InterpretationProfile,
    ResourceAnnotationLanguageSkill,
    ResourceCapability,
    ResourceCareerProfile,
    ResourcePerson,
    WrittenTranslationProfile,
)
from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate
from field_filtering import apply_scalar_specs


PROFILE_FIELDS = {
    "written_profile": WrittenTranslationProfile,
    "interpretation_profile": InterpretationProfile,
    "annotation_profile": AnnotationProfile,
    "career_profile": ResourceCareerProfile,
}


class TalentDuplicateError(ValueError):
    def __init__(self, duplicates: list[dict]):
        super().__init__("发现联系方式相同的人才档案，请确认是否复用")
        self.duplicates = duplicates


class TalentDeleteConflictError(ValueError):
    """人才仍被业务记录引用时拒绝物理删除，避免破坏历史数据。"""


_OWNED_PERSON_TABLES = {
    "resource_capability",
    "resource_written_translation_profile",
    "resource_interpretation_profile",
    "resource_annotation_profile",
    "resource_annotation_language_skill",
    "resource_career_profile",
}

_REFERENCE_LABELS = {
    "annotation_account_assignment": "标注账号分配",
    "annotation_project_assignee": "标注项目人员",
    "annotation_trial_record": "试标记录",
    "interpretation_project_interpreter": "口译项目人员",
    "recruitment_candidate": "招聘候选人",
    "translator": "历史译员档案",
}


def normalize_phone(value: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", value or "")
    return digits or None


def normalize_email(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    return normalized or None


def extract_contact_identifiers(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    text = value or ""
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    phone_matches = re.findall(r"(?:\+?\d[\d\s()-]{6,}\d)", text)
    phone = normalize_phone(phone_matches[0]) if phone_matches else None
    email = normalize_email(email_match.group(0)) if email_match else None
    return phone, email


def _person_options():
    return (
        selectinload(ResourcePerson.capabilities),
        selectinload(ResourcePerson.written_profile),
        selectinload(ResourcePerson.interpretation_profile),
        selectinload(ResourcePerson.annotation_profile),
        selectinload(ResourcePerson.annotation_language_skills).joinedload(
            ResourceAnnotationLanguageSkill.source_language
        ),
        selectinload(ResourcePerson.annotation_language_skills).joinedload(
            ResourceAnnotationLanguageSkill.target_language
        ),
        selectinload(ResourcePerson.career_profile),
    )


def get_talent(db: Session, person_id: UUID) -> Optional[ResourcePerson]:
    return (
        db.query(ResourcePerson)
        .options(*_person_options())
        .filter(ResourcePerson.id == person_id)
        .first()
    )


def _person_reference_labels(db: Session, person_id: UUID) -> list[str]:
    """从真实数据库外键发现引用，新增业务表后也能自动纳入删除保护。"""
    bind = db.get_bind()
    inspector = inspect(bind)
    preparer = bind.dialect.identifier_preparer
    labels: list[str] = []
    for table_name in inspector.get_table_names():
        if table_name in _OWNED_PERSON_TABLES or table_name == ResourcePerson.__tablename__:
            continue
        for foreign_key in inspector.get_foreign_keys(table_name):
            if foreign_key.get("referred_table") != ResourcePerson.__tablename__:
                continue
            constrained = foreign_key.get("constrained_columns") or []
            referred = foreign_key.get("referred_columns") or []
            for column_name, referred_column in zip(constrained, referred):
                if referred_column != "id":
                    continue
                table_sql = preparer.quote(table_name)
                column_sql = preparer.quote(column_name)
                found = db.execute(
                    text(f"SELECT 1 FROM {table_sql} WHERE {column_sql} = :person_id LIMIT 1"),
                    {"person_id": person_id},
                ).first()
                if found:
                    labels.append(_REFERENCE_LABELS.get(table_name, "其他业务记录"))
                break
    return list(dict.fromkeys(labels))


def delete_talent(db: Session, person_id: UUID) -> bool:
    person = db.query(ResourcePerson).filter(ResourcePerson.id == person_id).first()
    if not person:
        return False
    references = _person_reference_labels(db, person_id)
    if references:
        raise TalentDeleteConflictError(
            f"无法删除人才“{person.full_name}”：仍被{'、'.join(references)}引用。"
            "请先解除关联，或将人才状态改为停用以保留历史记录。"
        )
    try:
        db.delete(person)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TalentDeleteConflictError(
            f"无法删除人才“{person.full_name}”：仍存在关联业务记录，请先解除关联或改为停用。"
        ) from exc
    return True


def _talent_query(
    db: Session,
    *,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    statuses: Optional[Sequence[str]] = None,
    capability_type: Optional[str] = None,
    capability_status: Optional[str] = None,
    cooperation_type: Optional[str] = None,
    industry_keyword: Optional[str] = None,
    review_required: Optional[bool] = None,
    field_filters: Optional[dict] = None,
):
    query = db.query(ResourcePerson)
    if capability_type:
        query = query.join(
            ResourceCapability,
            ResourceCapability.person_id == ResourcePerson.id,
        ).filter(ResourceCapability.capability_type == capability_type)
        query = query.filter(ResourceCapability.status == (capability_status or "active"))
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            ResourcePerson.resource_code.ilike(pattern),
            ResourcePerson.full_name.ilike(pattern),
            ResourcePerson.primary_phone.ilike(pattern),
            ResourcePerson.primary_email.ilike(pattern),
            ResourcePerson.contact_info.ilike(pattern),
        ))
    if status:
        query = query.filter(ResourcePerson.status == status)
    elif statuses:
        query = query.filter(ResourcePerson.status.in_(tuple(statuses)))
    if cooperation_type:
        query = query.filter(ResourcePerson.cooperation_type == cooperation_type)
    if industry_keyword:
        query = query.join(
            ResourceCareerProfile,
            ResourceCareerProfile.person_id == ResourcePerson.id,
        ).filter(ResourceCareerProfile.industries.cast(String).ilike(f"%{industry_keyword.strip()}%"))
    if review_required is not None:
        query = query.filter(or_(
            ResourcePerson.duplicate_review_required == review_required,
            ResourcePerson.capabilities.any(ResourceCapability.review_required == review_required),
        ))
    field_filters = field_filters or {}
    query = apply_scalar_specs(query, field_filters, {
        "resource_code": (ResourcePerson.resource_code, "string"),
        "full_name": (ResourcePerson.full_name, "string"),
        "status": (ResourcePerson.status, "string"),
        "cooperation_type": (ResourcePerson.cooperation_type, "string"),
        "primary_phone": (ResourcePerson.primary_phone, "string"),
        "primary_email": (ResourcePerson.primary_email, "string"),
        "gender": (ResourcePerson.gender, "string"),
        "native_place": (ResourcePerson.native_place, "string"),
        "residence_address": (ResourcePerson.residence_address, "string"),
        "nationality": (ResourcePerson.nationality, "string"),
        "overall_rating": (ResourcePerson.overall_rating, "string"),
        "first_contact_date": (ResourcePerson.first_contact_date, "datetime"),
        "updated_at": (ResourcePerson.updated_at, "datetime"),
        "duplicate_review_required": (ResourcePerson.duplicate_review_required, "boolean"),
    })
    for field, descriptor in field_filters.items():
        if field == "capability_types":
            values = descriptor.get("value") or []
            query = query.filter(ResourcePerson.capabilities.any(and_(
                ResourceCapability.capability_type.in_(values),
                ResourceCapability.status != "inactive",
            )))
        elif field == "language_directions":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(
                ResourcePerson.written_profile.has(WrittenTranslationProfile.languages.ilike(pattern)),
                ResourcePerson.interpretation_profile.has(InterpretationProfile.languages.ilike(pattern)),
            ))
        elif field == "annotation_language_directions":
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(ResourcePerson.annotation_language_skills.any(or_(
                ResourceAnnotationLanguageSkill.source_language.has(InterpretationLanguage.label.ilike(pattern)),
                ResourceAnnotationLanguageSkill.target_language.has(InterpretationLanguage.label.ilike(pattern)),
            )))
        elif field in {"industries", "job_titles"}:
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            column = ResourceCareerProfile.industries if field == "industries" else ResourceCareerProfile.job_titles
            query = query.filter(ResourcePerson.career_profile.has(cast(column, String).ilike(pattern)))
        elif field == "years_experience":
            conditions = []
            if descriptor.get("min") not in (None, ""):
                conditions.append(ResourceCareerProfile.years_experience >= float(descriptor["min"]))
            if descriptor.get("max") not in (None, ""):
                conditions.append(ResourceCareerProfile.years_experience <= float(descriptor["max"]))
            if conditions:
                query = query.filter(ResourcePerson.career_profile.has(and_(*conditions)))
        elif field == "age":
            today = date.today()
            minimum, maximum = descriptor.get("min"), descriptor.get("max")
            if minimum not in (None, ""):
                cutoff = today.replace(year=today.year - int(minimum))
                query = query.filter(ResourcePerson.birth_date <= cutoff)
            if maximum not in (None, ""):
                cutoff = today.replace(year=today.year - int(maximum) - 1)
                query = query.filter(ResourcePerson.birth_date > cutoff)
        elif field in {"dialects", "dialect_regions"}:
            column = ResourcePerson.dialects if field == "dialects" else ResourcePerson.dialect_regions
            query = query.filter(cast(column, String).ilike(f"%{str(descriptor.get('value') or '').strip()}%"))
    return query.distinct()


def get_talents(db: Session, *, skip: int = 0, limit: int = 100, **filters) -> list[ResourcePerson]:
    return (
        _talent_query(db, **filters)
        .options(*_person_options())
        .order_by(ResourcePerson.updated_at.desc(), ResourcePerson.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_talents(db: Session, **filters) -> int:
    return _talent_query(db, **filters).count()


def find_duplicate_talents(
    db: Session,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    exclude_id: Optional[UUID] = None,
) -> list[dict]:
    normalized_phone = normalize_phone(phone)
    normalized_email = normalize_email(email)
    if not normalized_phone and not normalized_email:
        return []
    query = db.query(ResourcePerson)
    conditions = []
    bind = db.get_bind()
    is_postgresql = bind is not None and bind.dialect.name == "postgresql"
    if normalized_phone and is_postgresql:
        conditions.extend([
            func.regexp_replace(ResourcePerson.primary_phone, r"\D", "", "g") == normalized_phone,
            func.regexp_replace(ResourcePerson.secondary_phone, r"\D", "", "g") == normalized_phone,
        ])
    if normalized_email:
        conditions.extend([
            func.lower(func.trim(ResourcePerson.primary_email)) == normalized_email,
            func.lower(func.trim(ResourcePerson.secondary_email)) == normalized_email,
        ])
    if conditions and not (normalized_phone and not is_postgresql):
        query = query.filter(or_(*conditions))
    if exclude_id:
        query = query.filter(ResourcePerson.id != exclude_id)
    result = []
    for person in query.limit(500 if normalized_phone and not is_postgresql else 20).all():
        match_fields = []
        if normalized_phone in {normalize_phone(person.primary_phone), normalize_phone(person.secondary_phone)}:
            match_fields.append("phone")
        if normalized_email in {normalize_email(person.primary_email), normalize_email(person.secondary_email)}:
            match_fields.append("email")
        if not match_fields:
            continue
        result.append({
            "id": str(person.id),
            "resource_code": person.resource_code,
            "full_name": person.full_name,
            "primary_phone": person.primary_phone,
            "primary_email": person.primary_email,
            "match_fields": match_fields,
        })
        if len(result) >= 20:
            break
    return result


def _sync_capabilities(db: Session, person: ResourcePerson, payload) -> None:
    existing = {item.capability_type: item for item in person.capabilities}
    incoming = {item.capability_type: item for item in payload.capabilities}
    for capability_type, capability in incoming.items():
        values = capability.model_dump()
        row = existing.get(capability_type)
        if row:
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_at = datetime.now()
        else:
            person.capabilities.append(ResourceCapability(source="manual", **values))
    for capability_type, row in existing.items():
        if capability_type not in incoming:
            row.status = "inactive"
            row.updated_at = datetime.now()


def _sync_profiles(db: Session, person: ResourcePerson, payload) -> None:
    for field, model in PROFILE_FIELDS.items():
        profile_input = getattr(payload, field)
        current = getattr(person, field)
        if profile_input is None:
            continue
        values = profile_input.model_dump()
        if current is None:
            setattr(person, field, model(**values))
        else:
            for key, value in values.items():
                setattr(current, key, value)


def _sync_annotation_language_skills(db: Session, person: ResourcePerson, payload) -> None:
    incoming = payload.annotation_language_skills
    language_ids = {
        value
        for item in incoming
        for value in (item.source_language_id, item.target_language_id)
        if value is not None
    }
    if language_ids:
        found = {
            value for (value,) in db.query(InterpretationLanguage.id)
            .filter(InterpretationLanguage.id.in_(language_ids)).all()
        }
        if found != language_ids:
            raise ValueError("标注语种/方言中包含不存在的语种")
    existing_by_key = {
        (item.source_language_id, item.target_language_id): item
        for item in person.annotation_language_skills
    }
    incoming_by_key = {
        (item.source_language_id, item.target_language_id): item
        for item in incoming
    }
    for key, row in list(existing_by_key.items()):
        if key not in incoming_by_key:
            person.annotation_language_skills.remove(row)
    for key, item in incoming_by_key.items():
        if key not in existing_by_key:
            person.annotation_language_skills.append(
                ResourceAnnotationLanguageSkill(**item.model_dump())
            )


def _legacy_translation_type(capability_types: set[str]) -> Optional[str]:
    if {"written_translation", "interpretation"}.issubset(capability_types):
        return "笔译/口译"
    if "interpretation" in capability_types:
        return "口译"
    if "written_translation" in capability_types:
        return "笔译"
    return None


def _sync_legacy_translator(db: Session, person: ResourcePerson) -> None:
    """为旧项目外键和排期保留 translator 兼容记录。"""
    from models import Translator

    capability_types = {
        item.capability_type for item in person.capabilities if item.status != "inactive"
    }
    translator = db.query(Translator).filter(Translator.id == person.id).first()
    if not capability_types.intersection({"written_translation", "interpretation"}):
        return
    written = person.written_profile
    oral = person.interpretation_profile
    values = {
        "translator_code": person.resource_code,
        "translator_name": person.full_name,
        "cooperation_type": person.cooperation_type,
        "contact_info": person.contact_info,
        "translation_type": _legacy_translation_type(capability_types),
        "interpretation_level": oral.interpretation_level if oral else None,
        "quality_score": (written.quality_score if written else None) or (oral.quality_score if oral else None),
        "direction": (written.direction if written else None) or (oral.direction if oral else None),
        "languages": (written.languages if written else None) or (oral.languages if oral else None),
        "gender": person.gender,
        "height": person.height,
        "appearance": person.appearance,
        "nationality": person.nationality,
        "ethnicity": person.ethnicity,
        "phone": person.primary_phone,
        "phone2": person.secondary_phone,
        "email1": person.primary_email,
        "email2": person.secondary_email,
        "resume_path": person.resume_path,
        "other_contact": person.other_contact,
        "overall_rating": person.overall_rating,
        "first_contact_date": person.first_contact_date,
        "remarks": person.remarks,
        "status": person.status,
        "resource_person_id": person.id,
        "default_priority": written.default_priority if written else 0,
        "schedule_remarks": written.schedule_remarks if written else None,
        "available_time_slot": written.available_time_slot if written else None,
        "daily_accept_count": written.daily_accept_count if written else None,
        "hourly_speed": written.hourly_speed if written else None,
        "daily_word_capacity": written.daily_word_capacity if written else None,
        "can_cloud_edit": written.can_cloud_edit if written else None,
        "can_revision": written.can_revision if written else None,
        "domain_skills": (written.domain_skills if written else None) or (oral.domain_skills if oral else []),
        "availability_updated_at": written.availability_updated_at if written else None,
    }
    if translator is None:
        translator = Translator(id=person.id, **values)
        db.add(translator)
    else:
        for key, value in values.items():
            setattr(translator, key, value)


def create_talent(
    db: Session, payload: ResourcePersonCreate, idempotency_key: Optional[str] = None,
) -> ResourcePerson:
    duplicates = find_duplicate_talents(
        db, phone=payload.primary_phone, email=payload.primary_email
    )
    if duplicates and not payload.allow_duplicate:
        raise TalentDuplicateError(duplicates)
    data = payload.model_dump(exclude={
        "capabilities", "written_profile", "interpretation_profile",
        "annotation_profile", "annotation_language_skills", "career_profile", "allow_duplicate",
    })
    person = ResourcePerson(
        duplicate_review_required=bool(duplicates and payload.allow_duplicate),
        idempotency_key=idempotency_key, **data,
    )
    db.add(person)
    db.flush()
    _sync_capabilities(db, person, payload)
    _sync_profiles(db, person, payload)
    _sync_annotation_language_skills(db, person, payload)
    db.flush()
    _sync_legacy_translator(db, person)
    db.commit()
    return get_talent(db, person.id)


def update_talent_name(
    db: Session, person_id: UUID, full_name: str
) -> Optional[ResourcePerson]:
    """只修改姓名，避免账号页快速纠错时覆盖人才档案的其他字段。"""
    person = get_talent(db, person_id)
    if not person:
        return None
    if person.full_name != full_name:
        person.full_name = full_name
        person.updated_at = datetime.now()
        db.flush()
        _sync_legacy_translator(db, person)
        db.commit()
        return get_talent(db, person.id)
    return person


def update_talent_status(
    db: Session, person_id: UUID, status: str
) -> Optional[ResourcePerson]:
    person = get_talent(db, person_id)
    if not person:
        return None
    if person.status != status:
        person.status = status
        person.updated_at = datetime.now()
        db.flush()
        _sync_legacy_translator(db, person)
        db.commit()
        return get_talent(db, person.id)
    return person


def update_talent(
    db: Session, person_id: UUID, payload: ResourcePersonUpdate
) -> Optional[ResourcePerson]:
    person = get_talent(db, person_id)
    if not person:
        return None
    duplicates = find_duplicate_talents(
        db, phone=payload.primary_phone, email=payload.primary_email, exclude_id=person_id
    )
    if duplicates and not payload.allow_duplicate:
        raise TalentDuplicateError(duplicates)
    data = payload.model_dump(exclude={
        "capabilities", "written_profile", "interpretation_profile",
        "annotation_profile", "annotation_language_skills", "career_profile", "allow_duplicate",
    })
    for key, value in data.items():
        setattr(person, key, value)
    if duplicates and payload.allow_duplicate:
        person.duplicate_review_required = True
    _sync_capabilities(db, person, payload)
    _sync_profiles(db, person, payload)
    _sync_annotation_language_skills(db, person, payload)
    person.updated_at = datetime.now()
    db.flush()
    _sync_legacy_translator(db, person)
    db.commit()
    return get_talent(db, person.id)


def update_recruitment_talent(
    db: Session, person_id: UUID, payload: ResourcePersonUpdate
) -> Optional[ResourcePerson]:
    """招聘端只更新人员主档与职业档案，不改写专业能力。"""
    person = get_talent(db, person_id)
    if not person:
        return None
    duplicates = find_duplicate_talents(
        db, phone=payload.primary_phone, email=payload.primary_email, exclude_id=person_id
    )
    if duplicates and not payload.allow_duplicate:
        raise TalentDuplicateError(duplicates)
    data = payload.model_dump(exclude={
        "capabilities", "written_profile", "interpretation_profile",
        "annotation_profile", "annotation_language_skills", "career_profile", "allow_duplicate",
    })
    for key, value in data.items():
        setattr(person, key, value)
    if duplicates and payload.allow_duplicate:
        person.duplicate_review_required = True
    if payload.career_profile is not None:
        values = payload.career_profile.model_dump()
        if person.career_profile is None:
            person.career_profile = ResourceCareerProfile(**values)
        else:
            for key, value in values.items():
                setattr(person.career_profile, key, value)
    person.updated_at = datetime.now()
    db.flush()
    _sync_legacy_translator(db, person)
    db.commit()
    return get_talent(db, person.id)


def talent_has_capability(
    db: Session,
    person_id: UUID,
    capability_type: str,
    *,
    active_only: bool = True,
) -> bool:
    query = db.query(ResourceCapability.id).join(ResourcePerson).filter(
        ResourceCapability.person_id == person_id,
        ResourceCapability.capability_type == capability_type,
        ResourcePerson.status != "inactive",
    )
    if active_only:
        query = query.filter(ResourceCapability.status == "active")
    return query.first() is not None


def translator_has_capability(db: Session, translator_id: UUID, capability_type: str) -> bool:
    from models import Translator

    person_id = db.query(Translator.resource_person_id).filter(Translator.id == translator_id).scalar()
    return bool(person_id and talent_has_capability(db, person_id, capability_type))


def sync_legacy_translator_to_talent(db: Session, translator) -> ResourcePerson:
    """旧译员接口新增或修改后同步统一人才主档。"""
    person = db.query(ResourcePerson).filter(ResourcePerson.id == translator.id).first()
    if person is None:
        person = ResourcePerson(id=translator.id, full_name=translator.translator_name)
        db.add(person)
    person.resource_code = translator.translator_code
    person.full_name = translator.translator_name
    person.cooperation_type = translator.cooperation_type
    person.contact_info = translator.contact_info
    person.primary_phone = translator.phone
    person.secondary_phone = translator.phone2
    person.primary_email = normalize_email(translator.email1)
    person.secondary_email = normalize_email(translator.email2)
    person.other_contact = translator.other_contact
    person.resume_path = translator.resume_path
    person.gender = translator.gender
    person.height = translator.height
    person.appearance = translator.appearance
    person.nationality = translator.nationality
    person.ethnicity = translator.ethnicity
    person.overall_rating = translator.overall_rating
    person.first_contact_date = translator.first_contact_date
    person.remarks = translator.remarks
    person.status = translator.status or "standby"
    # 兼容表是已持久化记录，必须先确保新主档已插入，
    # 再更新其外键；否则 PostgreSQL 会在同一次 flush 中先执行 UPDATE。
    db.flush([person])
    translator.resource_person_id = translator.id

    raw_type = (translator.translation_type or "").strip()
    oral = any(token in raw_type for token in ("口译", "同传", "交传"))
    written = "笔译" in raw_type or not oral or "/" in raw_type
    existing = {item.capability_type: item for item in person.capabilities}
    for capability_type in (["written_translation"] if written else []) + (["interpretation"] if oral else []):
        if capability_type not in existing:
            person.capabilities.append(ResourceCapability(
                capability_type=capability_type,
                status="active",
                source="legacy_translator",
                review_required=not bool(raw_type),
            ))
    if written:
        if person.written_profile is None:
            person.written_profile = WrittenTranslationProfile()
        profile = person.written_profile
        for key in (
            "languages", "direction", "domain_skills", "quality_score", "default_priority",
            "daily_accept_count", "hourly_speed", "daily_word_capacity", "can_cloud_edit",
            "can_revision", "available_time_slot", "schedule_remarks", "availability_updated_at",
        ):
            setattr(profile, key, getattr(translator, key))
    if oral:
        if person.interpretation_profile is None:
            person.interpretation_profile = InterpretationProfile()
        profile = person.interpretation_profile
        profile.languages = translator.languages
        profile.direction = translator.direction
        profile.interpretation_level = translator.interpretation_level
        profile.quality_score = translator.quality_score
        profile.domain_skills = translator.domain_skills or []
        profile.interpretation_modes = [
            value for value, token in (("simultaneous", "同传"), ("consecutive", "交传"))
            if token in raw_type
        ]
    return person


def backfill_resource_people(db: Session) -> dict[str, int]:
    """幂等回填旧译员和招聘候选人，不删除或改写历史项目。"""
    from interpretation_models import InterpretationProjectInterpreter
    from manuscript_models import ManuscriptArrangement
    from models import TranslationProject, TranslationSubOrder, Translator
    from recruitment_models import RecruitmentCandidate

    counters = {"translators": 0, "candidates": 0, "candidate_reused": 0}
    written_ids = {
        value for (value,) in db.query(TranslationProject.translator_id)
        .filter(TranslationProject.translator_id.is_not(None)).all()
    }
    written_ids.update(
        value for (value,) in db.query(TranslationSubOrder.translator_id)
        .filter(TranslationSubOrder.translator_id.is_not(None)).all()
    )
    written_ids.update(value for (value,) in db.query(ManuscriptArrangement.translator_id).all())
    oral_ids = {value for (value,) in db.query(InterpretationProjectInterpreter.translator_id).all()}

    for translator in db.query(Translator).all():
        existed = db.query(ResourcePerson.id).filter(ResourcePerson.id == translator.id).first()
        person = sync_legacy_translator_to_talent(db, translator)
        raw_type = (translator.translation_type or "").strip()
        explicit_oral = any(token in raw_type for token in ("口译", "同传", "交传"))
        explicit_written = "笔译" in raw_type
        capability_types = {item.capability_type: item for item in person.capabilities}
        if translator.id in written_ids or explicit_written or not explicit_oral:
            if "written_translation" not in capability_types:
                person.capabilities.append(ResourceCapability(
                    capability_type="written_translation", status="active",
                    source="legacy_backfill", review_required=not explicit_written,
                ))
            elif not explicit_written and translator.id not in written_ids:
                capability_types["written_translation"].review_required = True
        if translator.id in oral_ids or explicit_oral:
            if "interpretation" not in capability_types:
                person.capabilities.append(ResourceCapability(
                    capability_type="interpretation", status="active",
                    source="legacy_backfill", review_required=False,
                ))
        if not existed:
            counters["translators"] += 1
    db.flush()

    for candidate in db.query(RecruitmentCandidate).filter(
        RecruitmentCandidate.person_id.is_(None)
    ).all():
        phone, email = extract_contact_identifiers(candidate.contact_info)
        duplicates = find_duplicate_talents(db, phone=phone, email=email)
        if len(duplicates) == 1:
            candidate.person_id = duplicates[0]["id"]
            counters["candidate_reused"] += 1
            continue
        person = ResourcePerson(
            full_name=candidate.candidate_name,
            contact_info=candidate.contact_info,
            primary_phone=phone,
            primary_email=email,
            resume_path=candidate.resume_path,
            status="standby",
            duplicate_review_required=len(duplicates) > 1,
        )
        db.add(person)
        db.flush()
        candidate.person_id = person.id
        counters["candidates"] += 1
    db.commit()
    return counters
