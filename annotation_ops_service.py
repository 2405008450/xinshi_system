"""标注平台账号、试标、计价和状态履历服务。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from annotation_custom_field_service import validate_custom_values
from annotation_models import AnnotationProject, AnnotationProjectAssignee, AnnotationProjectLanguageItem
from annotation_ops_models import (
    AnnotationAccountAssignment, AnnotationAccountAssignmentLanguage,
    AnnotationAccountPasswordHistory, AnnotationAssigneeRate,
    AnnotationCredentialAccessLog, AnnotationPlatform, AnnotationPlatformAccount,
    AnnotationProjectStatusHistory, AnnotationTrialRecord,
)
from models import AppUser, Client, SubClient
from resource_models import ResourceAnnotationLanguageSkill, ResourceCapability, ResourcePerson


logger = logging.getLogger("credential_audit")


def _normalize_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("平台链接格式无效")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _next_sequence(db: Session, model, *conditions) -> int:
    return int(db.query(func.coalesce(func.max(model.sequence_no), 0)).filter(*conditions).scalar() or 0) + 1


def _platform_query(db: Session, client_id: UUID | None = None):
    query = db.query(AnnotationPlatform)
    if client_id is not None:
        query = query.filter(AnnotationPlatform.client_id == client_id)
    return query


def list_platforms(db: Session, client_id: UUID | None = None, skip: int = 0, limit: int = 100):
    return _platform_query(db, client_id).order_by(AnnotationPlatform.sequence_no).offset(skip).limit(limit).all()


def count_platforms(db: Session, client_id: UUID | None = None) -> int:
    return _platform_query(db, client_id).count()


def save_platform(db: Session, payload, created_by: UUID | None, platform_id: UUID | None = None):
    if payload.client_id and not db.get(Client, payload.client_id):
        raise ValueError("客户不存在")
    if payload.sub_client_id:
        sub_client = db.get(SubClient, payload.sub_client_id)
        if not sub_client or sub_client.parent_client_id != payload.client_id:
            raise ValueError("子客户不属于所选客户")
    if payload.origin_project_id and not db.get(AnnotationProject, payload.origin_project_id):
        raise ValueError("来源标注项目不存在")
    row = db.get(AnnotationPlatform, platform_id) if platform_id else AnnotationPlatform(created_by=created_by)
    if platform_id and not row:
        return None
    normalized_url = _normalize_url(payload.platform_url)
    duplicate = db.query(AnnotationPlatform.id).filter(
        AnnotationPlatform.client_id.is_(None) if payload.client_id is None else AnnotationPlatform.client_id == payload.client_id,
        AnnotationPlatform.platform_url_normalized == normalized_url,
    )
    if platform_id:
        duplicate = duplicate.filter(AnnotationPlatform.id != platform_id)
    if duplicate.first():
        raise ValueError("当前客户已存在相同平台链接")
    row.client_id = payload.client_id
    row.sub_client_id = payload.sub_client_id
    row.origin_project_id = payload.origin_project_id
    row.platform_name = (payload.platform_name or "").strip() or None
    row.platform_url = payload.platform_url.strip()
    row.platform_url_normalized = normalized_url
    row.login_notes = (payload.login_notes or "").strip() or None
    row.is_active = payload.is_active
    if not platform_id:
        client_condition = AnnotationPlatform.client_id.is_(None) if payload.client_id is None else AnnotationPlatform.client_id == payload.client_id
        row.sequence_no = payload.sequence_no or _next_sequence(db, AnnotationPlatform, client_condition)
        db.add(row)
    elif payload.sequence_no:
        row.sequence_no = payload.sequence_no
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def delete_platform(db: Session, platform_id: UUID) -> bool:
    row = db.get(AnnotationPlatform, platform_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def _active_assignment(row: AnnotationPlatformAccount):
    return next((item for item in row.assignments if item.released_on is None), None)


def _mask_login_account(value: str | None) -> str | None:
    """列表只返回可识别但不可直接使用的登录账号。"""
    if not value:
        return None
    if "@" in value:
        local, domain = value.split("@", 1)
        visible = local[:2] if len(local) > 2 else local[:1]
        return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * max(3, len(value) - 4)}{value[-2:]}"


def _assignment_dict(row: AnnotationAccountAssignment) -> dict:
    language_rows = sorted(row.languages, key=lambda item: str(item.language_item_id))
    return {
        "id": row.id, "account_id": row.account_id, "person_id": row.person_id,
        "person_name": getattr(row.person, "full_name", None),
        "resource_code": getattr(row.person, "resource_code", None),
        "person_gender": getattr(row.person, "gender", None),
        "project_id": row.project_id, "project_name": getattr(row.project, "project_name", None),
        "assigned_on": row.assigned_on, "released_on": row.released_on,
        "release_reason": row.release_reason, "assignment_note": row.assignment_note,
        "assigned_by": row.assigned_by,
        "language_item_ids": [item.language_item_id for item in language_rows],
        "language_labels": [getattr(item.language_item, "display", None) for item in language_rows if getattr(item, "language_item", None)],
        "custom_values": row.custom_values or {},
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _account_dict(row: AnnotationPlatformAccount) -> dict:
    assignment = _active_assignment(row)
    assignment_data = _assignment_dict(assignment) if assignment else {}
    return {
        "id": row.id, "platform_id": row.platform_id, "parent_account_id": row.parent_account_id,
        "owner_id": row.owner_id, "owner_name": (row.owner.full_name or row.owner.username) if row.owner else None,
        "nickname": row.nickname, "masked_login_account": _mask_login_account(row.login_account),
        "login_account": row.login_account, "password": row.password,
        "account_status": row.account_status,
        "registration_status": row.registration_status, "account_source": row.account_source,
        "expires_on": row.expires_on, "remarks": row.remarks, "sequence_no": row.sequence_no,
        "custom_values": row.custom_values or {}, "has_login_account": bool(row.login_account),
        "has_password": bool(row.password), "password_updated_at": row.password_updated_at,
        "platform_name": row.platform.platform_name, "platform_url": row.platform.platform_url,
        "client_id": row.platform.client_id, "sub_client_id": row.platform.sub_client_id,
        "current_assignment_id": assignment_data.get("id"),
        "person_id": assignment_data.get("person_id"), "person_name": assignment_data.get("person_name"),
        "resource_code": assignment_data.get("resource_code"), "project_id": assignment_data.get("project_id"),
        "project_name": assignment_data.get("project_name"), "assigned_on": assignment_data.get("assigned_on"),
        "person_gender": assignment_data.get("person_gender"),
        "assignment_custom_values": assignment_data.get("custom_values", {}),
        "language_item_ids": assignment_data.get("language_item_ids", []),
        "language_labels": assignment_data.get("language_labels", []),
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _account_query(
    db: Session, *, client_id: UUID | None = None, platform_id: UUID | None = None,
    project_id: UUID | None = None, person_id: UUID | None = None,
    assignment_state: str | None = None, account_status: str | None = None,
    registration_status: str | None = None, language_item_id: UUID | None = None,
    keyword: str | None = None, eager: bool = True,
):
    query = (
        db.query(AnnotationPlatformAccount)
        .join(AnnotationPlatform, AnnotationPlatform.id == AnnotationPlatformAccount.platform_id)
        .outerjoin(
            AnnotationAccountAssignment,
            and_(AnnotationAccountAssignment.account_id == AnnotationPlatformAccount.id, AnnotationAccountAssignment.released_on.is_(None)),
        )
        .outerjoin(ResourcePerson, ResourcePerson.id == AnnotationAccountAssignment.person_id)
    )
    if eager:
        query = query.options(
            joinedload(AnnotationPlatformAccount.platform),
            joinedload(AnnotationPlatformAccount.owner),
            selectinload(AnnotationPlatformAccount.assignments).joinedload(AnnotationAccountAssignment.person),
            selectinload(AnnotationPlatformAccount.assignments).joinedload(AnnotationAccountAssignment.project),
            selectinload(AnnotationPlatformAccount.assignments).selectinload(AnnotationAccountAssignment.languages).joinedload(AnnotationAccountAssignmentLanguage.language_item),
        )
    if client_id:
        query = query.filter(AnnotationPlatform.client_id == client_id)
    if platform_id:
        query = query.filter(AnnotationPlatformAccount.platform_id == platform_id)
    if project_id:
        query = query.filter(AnnotationAccountAssignment.project_id == project_id)
    if person_id:
        query = query.filter(AnnotationAccountAssignment.person_id == person_id)
    if assignment_state == "assigned":
        query = query.filter(AnnotationAccountAssignment.person_id.is_not(None))
    elif assignment_state == "unassigned":
        query = query.filter(AnnotationAccountAssignment.person_id.is_(None))
    if account_status:
        query = query.filter(AnnotationPlatformAccount.account_status == account_status)
    if registration_status:
        query = query.filter(AnnotationPlatformAccount.registration_status == registration_status)
    if language_item_id:
        query = query.filter(AnnotationAccountAssignment.languages.any(AnnotationAccountAssignmentLanguage.language_item_id == language_item_id))
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(or_(
            ResourcePerson.resource_code.ilike(pattern),
            ResourcePerson.full_name.ilike(pattern),
            AnnotationPlatformAccount.nickname.ilike(pattern),
            AnnotationPlatformAccount.login_account.ilike(pattern),
            AnnotationPlatform.platform_name.ilike(pattern),
            AnnotationPlatform.platform_url.ilike(pattern),
        ))
    return query


def list_accounts(db: Session, skip: int = 0, limit: int = 100, **filters):
    rows = _account_query(db, **filters).order_by(AnnotationPlatform.sequence_no, AnnotationPlatformAccount.sequence_no).offset(skip).limit(limit).all()
    return [_account_dict(row) for row in rows]


def count_accounts(db: Session, **filters) -> int:
    return _account_query(db, eager=False, **filters).with_entities(func.count(AnnotationPlatformAccount.id)).scalar() or 0


def _ensure_unique_login(db: Session, platform_id: UUID, login_account: str, account_id: UUID | None = None):
    normalized_account = login_account.strip().casefold()
    duplicate = db.query(AnnotationPlatformAccount.id).filter(
        AnnotationPlatformAccount.platform_id == platform_id,
        AnnotationPlatformAccount.login_account_normalized == normalized_account,
    )
    if account_id:
        duplicate = duplicate.filter(AnnotationPlatformAccount.id != account_id)
    if duplicate.first():
        raise ValueError("当前平台已存在相同登录账号")


def _apply_account(db: Session, payload, created_by: UUID | None, account_id: UUID | None = None, *, enforce_assignment_state: bool = True):
    platform = db.get(AnnotationPlatform, payload.platform_id)
    if not platform:
        raise ValueError("标注平台不存在")
    row = db.get(AnnotationPlatformAccount, account_id) if account_id else AnnotationPlatformAccount(platform_id=payload.platform_id, created_by=created_by)
    if account_id and not row:
        return None
    if account_id and row.platform_id != payload.platform_id:
        raise ValueError("账号创建后不能更换平台")
    owner_id = payload.owner_id or (getattr(row, "owner_id", None) if account_id else created_by)
    if payload.owner_id and not db.get(AppUser, owner_id):
        raise ValueError("负责人不存在")
    row.owner_id = owner_id
    if payload.parent_account_id:
        parent = db.get(AnnotationPlatformAccount, payload.parent_account_id)
        if not parent or parent.platform_id != payload.platform_id or parent.id == account_id:
            raise ValueError("主账号必须属于同一平台且不能指向自身")
    login_account = payload.login_account.strip() if payload.login_account else None
    password = payload.password if payload.password else None
    previous_password = row.password
    if not account_id and bool(login_account) != bool(password):
        raise ValueError("登录账号和密码必须同时填写")
    if login_account:
        _ensure_unique_login(db, payload.platform_id, login_account, account_id)
        row.login_account = login_account
        row.login_account_normalized = login_account.casefold()
    if password and password != previous_password:
        if previous_password:
            db.add(AnnotationAccountPasswordHistory(
                account_id=row.id, password=previous_password,
                effective_from=row.password_updated_at or row.created_at or datetime.now(), changed_by=created_by,
            ))
        row.password = password
        row.password_updated_at = datetime.now()
    if payload.registration_status == "registered" and (not row.login_account or not row.password):
        raise ValueError("已注册账号必须填写登录账号和密码")
    has_active_assignment = bool(account_id and db.query(AnnotationAccountAssignment.id).filter(
        AnnotationAccountAssignment.account_id == account_id,
        AnnotationAccountAssignment.released_on.is_(None),
        AnnotationAccountAssignment.person_id.is_not(None),
    ).first())
    if enforce_assignment_state:
        if has_active_assignment and payload.account_status != "assigned":
            raise ValueError("账号仍在分配中，请先释放后再修改账号状态")
        if not has_active_assignment and payload.account_status == "assigned":
            raise ValueError("只有完成分配后账号状态才能设为已分配")
    row.parent_account_id = payload.parent_account_id
    row.nickname = (payload.nickname or "").strip() or None
    row.account_status = payload.account_status
    row.registration_status = payload.registration_status
    row.account_source = payload.account_source
    row.expires_on = payload.expires_on
    row.remarks = (payload.remarks or "").strip() or None
    row.custom_values = validate_custom_values(
        db, "account", None, payload.custom_values, row.custom_values if account_id else None,
    )
    if not account_id:
        row.sequence_no = payload.sequence_no or _next_sequence(db, AnnotationPlatformAccount, AnnotationPlatformAccount.platform_id == payload.platform_id)
        db.add(row)
    elif payload.sequence_no:
        row.sequence_no = payload.sequence_no
    row.updated_at = datetime.now()
    return row


def save_account(db: Session, payload, created_by: UUID | None, account_id: UUID | None = None):
    row = _apply_account(db, payload, created_by, account_id)
    if not row:
        return None
    db.commit()
    refreshed = _account_query(db, platform_id=payload.platform_id).filter(AnnotationPlatformAccount.id == row.id).one()
    return _account_dict(refreshed)


def delete_account(db: Session, account_id: UUID) -> bool:
    row = db.get(AnnotationPlatformAccount, account_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def _validate_assignment_languages(db: Session, project_id: UUID | None, language_item_ids) -> list[UUID]:
    language_ids = list(dict.fromkeys(language_item_ids))
    if language_ids and not project_id:
        raise ValueError("选择语种时必须指定项目")
    if language_ids:
        found = {value for (value,) in db.query(AnnotationProjectLanguageItem.id).filter(
            AnnotationProjectLanguageItem.project_id == project_id,
            AnnotationProjectLanguageItem.id.in_(language_ids),
        ).all()}
        if found != set(language_ids):
            raise ValueError("分配语种必须属于所选项目")
    return language_ids


def _validate_annotator_assignment(
    db: Session,
    *,
    person_id: UUID,
    project_id: UUID | None,
    language_ids: list[UUID],
    exclude_account_id: UUID | None = None,
) -> None:
    capability = db.query(ResourceCapability.id).filter(
        ResourceCapability.person_id == person_id,
        ResourceCapability.capability_type == "annotation",
        ResourceCapability.status == "active",
    ).first()
    if not capability:
        raise ValueError("所选人员不是有效的标注员")
    active_assignment = db.query(AnnotationAccountAssignment.id).filter(
        AnnotationAccountAssignment.person_id == person_id,
        AnnotationAccountAssignment.released_on.is_(None),
    )
    if exclude_account_id:
        active_assignment = active_assignment.filter(
            AnnotationAccountAssignment.account_id != exclude_account_id
        )
    if active_assignment.first():
        raise ValueError("该标注员已绑定其他有效账号，请先释放原账号")

    if not language_ids:
        return

    language_items = db.query(AnnotationProjectLanguageItem).filter(
        AnnotationProjectLanguageItem.id.in_(language_ids)
    ).all()
    skill_keys = {
        (row.source_language_id, row.target_language_id)
        for row in db.query(ResourceAnnotationLanguageSkill).filter(
            ResourceAnnotationLanguageSkill.person_id == person_id
        ).all()
    }
    missing_labels = [
        item.display for item in language_items
        if (item.source_language_id, item.target_language_id) not in skill_keys
    ]
    if missing_labels:
        raise ValueError(f"所选标注员未配置以下标注语言方向：{'、'.join(missing_labels)}")

def list_annotator_occupancy(db: Session, project_id: UUID | None = None):
    rows = db.query(
        AnnotationAccountAssignment.person_id,
        AnnotationAccountAssignment.account_id,
        AnnotationAccountAssignment.project_id,
        AnnotationAccountAssignmentLanguage.language_item_id,
    ).outerjoin(
        AnnotationAccountAssignmentLanguage,
        AnnotationAccountAssignmentLanguage.assignment_id == AnnotationAccountAssignment.id,
    ).filter(
        AnnotationAccountAssignment.released_on.is_(None),
        AnnotationAccountAssignment.person_id.is_not(None),
    )
    if project_id:
        rows = rows.filter(AnnotationAccountAssignment.project_id == project_id)
    rows = rows.all()
    return [
        {
            "person_id": row.person_id,
            "account_id": row.account_id,
            "project_id": row.project_id,
            "language_item_id": row.language_item_id,
        }
        for row in rows
    ]


def _apply_assignment(db: Session, account: AnnotationPlatformAccount, payload, assigned_by: UUID | None):
    if account.account_status in {"suspended", "banned", "retired"}:
        raise ValueError("暂停、封禁或退役账号不能分配")
    if db.query(AnnotationAccountAssignment.id).filter(AnnotationAccountAssignment.account_id == account.id, AnnotationAccountAssignment.released_on.is_(None)).first():
        raise ValueError("账号当前已分配，请先释放")
    if not db.get(ResourcePerson, payload.person_id):
        raise ValueError("标注人员不存在")
    if not payload.project_id:
        raise ValueError("绑定标注员时必须选择项目")
    project = db.get(AnnotationProject, payload.project_id) if payload.project_id else None
    if payload.project_id and not project:
        raise ValueError("标注项目不存在")
    if project and project.client_id != account.platform.client_id:
        raise ValueError("账号平台客户与标注项目客户不一致")
    language_ids = _validate_assignment_languages(db, payload.project_id, payload.language_item_ids)
    if not language_ids:
        raise ValueError("绑定标注员时必须选择语言方向")
    _validate_annotator_assignment(
        db,
        person_id=payload.person_id,
        project_id=payload.project_id,
        language_ids=language_ids,
        exclude_account_id=account.id,
    )
    row = AnnotationAccountAssignment(
        account_id=account.id, person_id=payload.person_id, project_id=payload.project_id,
        assigned_on=payload.assigned_on, assignment_note=(payload.assignment_note or "").strip() or None,
        assigned_by=assigned_by,
        custom_values=validate_custom_values(
            db, "account_assignment", payload.project_id,
            getattr(payload, "custom_values", {}) or {}, None,
        ),
    )
    row.languages = [AnnotationAccountAssignmentLanguage(language_item_id=value) for value in language_ids]
    db.add(row)
    account.account_status = "assigned"
    account.updated_at = datetime.now()
    return row


def assign_account(db: Session, account_id: UUID, payload, assigned_by: UUID | None):
    account = db.get(AnnotationPlatformAccount, account_id)
    if not account:
        return None
    row = _apply_assignment(db, account, payload, assigned_by)
    db.commit()
    refreshed = db.query(AnnotationAccountAssignment).options(
        joinedload(AnnotationAccountAssignment.person), joinedload(AnnotationAccountAssignment.project),
        selectinload(AnnotationAccountAssignment.languages).joinedload(AnnotationAccountAssignmentLanguage.language_item),
    ).filter(AnnotationAccountAssignment.id == row.id).one()
    return _assignment_dict(refreshed)


def _apply_release(db: Session, account: AnnotationPlatformAccount, payload):
    assignment = db.query(AnnotationAccountAssignment).filter(
        AnnotationAccountAssignment.account_id == account.id,
        AnnotationAccountAssignment.released_on.is_(None),
    ).first()
    if not assignment:
        raise ValueError("账号当前未分配")
    if payload.released_on < assignment.assigned_on:
        raise ValueError("释放日期不能早于分配日期")
    assignment.released_on = payload.released_on
    assignment.release_reason = payload.release_reason
    if payload.assignment_note is not None:
        assignment.assignment_note = payload.assignment_note.strip() or None
    assignment.updated_at = datetime.now()
    if account.account_status == "assigned":
        account.account_status = "available"
    account.updated_at = datetime.now()
    return assignment


def release_account(db: Session, account_id: UUID, payload):
    account = db.get(AnnotationPlatformAccount, account_id)
    if not account:
        return None
    assignment = _apply_release(db, account, payload)
    db.commit()
    return _assignment_dict(assignment)


def list_account_assignments(db: Session, account_id: UUID):
    rows = db.query(AnnotationAccountAssignment).options(
        joinedload(AnnotationAccountAssignment.person), joinedload(AnnotationAccountAssignment.project),
        selectinload(AnnotationAccountAssignment.languages).joinedload(AnnotationAccountAssignmentLanguage.language_item),
    ).filter(AnnotationAccountAssignment.account_id == account_id).order_by(AnnotationAccountAssignment.assigned_on.desc(), AnnotationAccountAssignment.created_at.desc()).all()
    return [_assignment_dict(row) for row in rows]


def get_account_person_profile(db: Session, person_id: UUID) -> dict | None:
    person = (
        db.query(ResourcePerson)
        .options(selectinload(ResourcePerson.annotation_profile))
        .filter(ResourcePerson.id == person_id)
        .first()
    )
    if not person:
        return None
    age = None
    if person.birth_date:
        today = date.today()
        age = today.year - person.birth_date.year - (
            (today.month, today.day) < (person.birth_date.month, person.birth_date.day)
        )
    profile = person.annotation_profile
    return {
        "id": person.id,
        "resource_code": person.resource_code,
        "full_name": person.full_name,
        "gender": person.gender,
        "birth_date": person.birth_date,
        "age": age,
        "native_place": person.native_place,
        "residence_address": person.residence_address,
        "dialects": list(person.dialects or []),
        "dialect_regions": list(person.dialect_regions or []),
        "nationality": person.nationality,
        "ethnicity": person.ethnicity,
        "cooperation_type": person.cooperation_type,
        "status": person.status,
        "annotation_task_types": list(profile.task_types or []) if profile else [],
        "annotation_data_modalities": list(profile.data_modalities or []) if profile else [],
        "annotation_tools": list(profile.tools or []) if profile else [],
        "annotation_quality_score": profile.quality_score if profile else None,
        "annotation_remarks": profile.remarks if profile else None,
    }


def reveal_credential(db: Session, account_id: UUID, user: AppUser, access_reason: str | None = None, client_ip: str | None = None):
    row = db.get(AnnotationPlatformAccount, account_id)
    if not row:
        return None
    if not row.login_account or not row.password:
        raise ValueError("账号尚未设置完整凭据")
    cleartext = {
        "login_account": row.login_account,
        "password": row.password,
    }
    db.add(AnnotationCredentialAccessLog(
        account_id=account_id, user_id=user.id, access_reason=(access_reason or "").strip() or None,
        client_ip=client_ip,
    ))
    db.commit()
    logger.info("credential_reveal user_id=%s account_id=%s", user.id, row.id)
    return cleartext


def reveal_credentials_batch(db: Session, account_ids: list[UUID], user: AppUser, access_reason: str | None = None, client_ip: str | None = None):
    unique_ids = list(dict.fromkeys(account_ids))
    rows = db.query(AnnotationPlatformAccount).filter(AnnotationPlatformAccount.id.in_(unique_ids)).all()
    row_map = {row.id: row for row in rows}
    result = []
    for account_id in unique_ids:
        row = row_map.get(account_id)
        if not row:
            continue
        db.add(AnnotationCredentialAccessLog(
            account_id=account_id, user_id=user.id,
            access_reason=(access_reason or "").strip() or None, client_ip=client_ip,
        ))
        result.append({"id": row.id, "login_account": row.login_account, "password": row.password})
    db.commit()
    logger.info("credential_batch_reveal user_id=%s account_count=%s", user.id, len(result))
    return result


def _active_assignment_for_update(db: Session, account_id: UUID):
    return db.query(AnnotationAccountAssignment).options(
        selectinload(AnnotationAccountAssignment.languages),
    ).filter(
        AnnotationAccountAssignment.account_id == account_id,
        AnnotationAccountAssignment.released_on.is_(None),
    ).first()


def batch_save_accounts(db: Session, client_id: UUID, items, user_id: UUID | None):
    processed = []
    seen_keys = set()
    seen_assignment_keys = set()
    for item in items:
        if item.row_key in seen_keys:
            processed.append((item.row_key, None, "批量数据中存在重复行标识"))
            continue
        seen_keys.add(item.row_key)
        try:
            with db.begin_nested():
                platform = db.get(AnnotationPlatform, item.account.platform_id)
                if not platform or platform.client_id != client_id:
                    raise ValueError("所选平台不属于当前客户")
                if item.project_id and not item.language_item_ids:
                    raise ValueError("选择项目时必须同时选择账号适用语言")
                if item.language_item_ids and not item.project_id:
                    raise ValueError("选择语种时必须同时选择项目")
                if item.person_id and not item.project_id:
                    raise ValueError("绑定标注员时必须选择项目")
                if item.person_id and not item.language_item_ids:
                    raise ValueError("绑定标注员时必须选择语言方向")
                project = db.get(AnnotationProject, item.project_id) if item.project_id else None
                if item.project_id and not project:
                    raise ValueError("标注项目不存在")
                if project and project.client_id != platform.client_id:
                    raise ValueError("账号平台客户与标注项目客户不一致")
                desired_languages = _validate_assignment_languages(
                    db, item.project_id, item.language_item_ids,
                )
                assignment_keys = {
                    (item.person_id, item.project_id, language_id)
                    for language_id in item.language_item_ids
                } if item.person_id else set()
                if assignment_keys & seen_assignment_keys:
                    raise ValueError("同一批次中，该标注员已在当前项目的所选语言方向绑定其他账号")

                account = _apply_account(
                    db, item.account, user_id, item.id, enforce_assignment_state=False,
                )
                if not account:
                    raise ValueError("平台账号不存在")
                db.flush()
                active = _active_assignment_for_update(db, account.id)

                if not item.project_id:
                    if active:
                        _apply_release(db, account, SimpleNamespace(
                            released_on=date.today(), release_reason="other",
                            assignment_note="在线表格清除项目分配",
                        ))
                        # SessionLocal 关闭了 autoflush；先落库再复查，避免把已解除账号误判为仍在分配。
                        db.flush()
                elif active and active.person_id == item.person_id and active.project_id == item.project_id:
                    current_languages = {row.language_item_id for row in active.languages}
                    if current_languages != set(desired_languages):
                        _validate_assignment_languages(db, item.project_id, desired_languages)
                        if item.person_id:
                            _validate_annotator_assignment(
                                db,
                                person_id=item.person_id,
                                project_id=item.project_id,
                                language_ids=desired_languages,
                                exclude_account_id=account.id,
                            )
                        active.languages = [
                            AnnotationAccountAssignmentLanguage(language_item_id=value)
                            for value in desired_languages
                        ]
                        active.updated_at = datetime.now()
                    active.custom_values = validate_custom_values(
                        db, "account_assignment", item.project_id,
                        item.assignment_custom_values, active.custom_values,
                    )
                else:
                    if active:
                        _apply_release(db, account, SimpleNamespace(
                            released_on=date.today(), release_reason="reassigned",
                            assignment_note="在线表格重新分配",
                        ))
                        db.flush()
                    account.account_status = "available"
                    if item.person_id:
                        _apply_assignment(db, account, SimpleNamespace(
                            person_id=item.person_id, project_id=item.project_id,
                            assigned_on=date.today(), assignment_note="在线表格分配",
                            language_item_ids=desired_languages,
                            custom_values=item.assignment_custom_values,
                        ), user_id)
                    else:
                        context = AnnotationAccountAssignment(
                            account_id=account.id,
                            person_id=None,
                            project_id=item.project_id,
                            assigned_on=date.today(),
                            assignment_note="在线表格设置项目和适用语言",
                            assigned_by=user_id,
                            custom_values=validate_custom_values(
                                db, "account_assignment", item.project_id,
                                item.assignment_custom_values, None,
                            ),
                        )
                        context.languages = [
                            AnnotationAccountAssignmentLanguage(language_item_id=value)
                            for value in desired_languages
                        ]
                        db.add(context)
                    db.flush()

                active_after_save = _active_assignment_for_update(db, account.id)
                has_person_assignment = bool(active_after_save and active_after_save.person_id)
                account.account_status = "assigned" if has_person_assignment else (
                    "available" if item.account.account_status == "assigned" else item.account.account_status
                )
                account.updated_at = datetime.now()
                db.flush()
                seen_assignment_keys.update(assignment_keys)
                processed.append((item.row_key, account.id, None))
        except (ValueError, IntegrityError) as exc:
            message = str(exc.orig) if isinstance(exc, IntegrityError) else str(exc)
            processed.append((item.row_key, None, message))

    db.commit()
    results = []
    for row_key, account_id, error in processed:
        if error:
            results.append({"row_key": row_key, "success": False, "error": error})
            continue
        refreshed = _account_query(db).filter(AnnotationPlatformAccount.id == account_id).one()
        results.append({"row_key": row_key, "success": True, "account": _account_dict(refreshed)})
    return {"results": results}


def _account_stats_query(db: Session, client_id: UUID | None = None, expiring_days: int = 30):
    deadline = date.today() + timedelta(days=expiring_days)
    query = db.query(
        AnnotationPlatform.id.label("platform_id"), AnnotationPlatform.platform_name,
        AnnotationPlatform.platform_url, func.count(AnnotationPlatformAccount.id).label("total"),
        func.sum(case((AnnotationPlatformAccount.account_status == "available", 1), else_=0)).label("available"),
        func.sum(case((AnnotationPlatformAccount.account_status == "assigned", 1), else_=0)).label("assigned"),
        func.sum(case((AnnotationPlatformAccount.account_status == "suspended", 1), else_=0)).label("suspended"),
        func.sum(case((AnnotationPlatformAccount.account_status == "banned", 1), else_=0)).label("banned"),
        func.sum(case((AnnotationPlatformAccount.account_status == "retired", 1), else_=0)).label("retired"),
        func.sum(case((and_(AnnotationPlatformAccount.expires_on.is_not(None), AnnotationPlatformAccount.expires_on <= deadline, AnnotationPlatformAccount.expires_on >= date.today()), 1), else_=0)).label("expiring_soon"),
    ).outerjoin(AnnotationPlatformAccount, AnnotationPlatformAccount.platform_id == AnnotationPlatform.id)
    if client_id:
        query = query.filter(AnnotationPlatform.client_id == client_id)
    return query.group_by(AnnotationPlatform.id).order_by(AnnotationPlatform.sequence_no)


def account_stats(db: Session, client_id: UUID | None = None, expiring_days: int = 30):
    rows = _account_stats_query(db, client_id, expiring_days).all()
    return [{
        "platform_id": row.platform_id, "platform_name": row.platform_name,
        "platform_url": row.platform_url, "total": int(row.total or 0),
        "available": int(row.available or 0), "assigned": int(row.assigned or 0),
        "suspended": int(row.suspended or 0), "banned": int(row.banned or 0),
        "retired": int(row.retired or 0), "expiring_soon": int(row.expiring_soon or 0),
    } for row in rows]


def list_person_accounts(db: Session, person_id: UUID, include_history: bool = False):
    if include_history:
        ids = db.query(AnnotationAccountAssignment.account_id).filter(AnnotationAccountAssignment.person_id == person_id)
        rows = _account_query(db).filter(AnnotationPlatformAccount.id.in_(ids)).all()
        return [_account_dict(row) for row in rows]
    return list_accounts(db, person_id=person_id, skip=0, limit=500)


def release_all_person_accounts(db: Session, person_id: UUID, payload):
    rows = db.query(AnnotationAccountAssignment).filter(
        AnnotationAccountAssignment.person_id == person_id,
        AnnotationAccountAssignment.released_on.is_(None),
    ).all()
    for assignment in rows:
        if payload.released_on < assignment.assigned_on:
            raise ValueError("释放日期不能早于分配日期")
        assignment.released_on = payload.released_on
        assignment.release_reason = payload.release_reason
        if payload.assignment_note is not None:
            assignment.assignment_note = payload.assignment_note.strip() or None
        assignment.updated_at = datetime.now()
        account = assignment.account
        if account.account_status == "assigned":
            account.account_status = "available"
            account.updated_at = datetime.now()
    db.commit()
    return len(rows)


def _validate_trial_member(db: Session, project_id: UUID, person_id: UUID, account_id: UUID | None):
    project = db.get(AnnotationProject, project_id)
    if not project:
        raise ValueError("标注项目不存在")

    capability = db.query(ResourceCapability.id).filter(
        ResourceCapability.person_id == person_id,
        ResourceCapability.capability_type == "annotation",
        ResourceCapability.status == "active",
    ).first()
    if not capability:
        raise ValueError("所选人员不是有效的标注员")

    project_language_keys = {
        (source_language_id, target_language_id)
        for source_language_id, target_language_id in db.query(
        AnnotationProjectLanguageItem.source_language_id,
        AnnotationProjectLanguageItem.target_language_id,
        ).filter(AnnotationProjectLanguageItem.project_id == project_id).all()
    }
    if project_language_keys:
        person_language_keys = {
            (source_language_id, target_language_id)
            for source_language_id, target_language_id in db.query(
            ResourceAnnotationLanguageSkill.source_language_id,
            ResourceAnnotationLanguageSkill.target_language_id,
            ).filter(ResourceAnnotationLanguageSkill.person_id == person_id).all()
        }
        if project_language_keys.isdisjoint(person_language_keys):
            raise ValueError("所选标注员的语言方向与项目语种不匹配")

    if not account_id:
        return
    account = db.get(AnnotationPlatformAccount, account_id)
    assignment = db.query(AnnotationAccountAssignment).filter(
        AnnotationAccountAssignment.account_id == account_id,
        AnnotationAccountAssignment.person_id == person_id,
        AnnotationAccountAssignment.project_id == project_id,
        AnnotationAccountAssignment.released_on.is_(None),
    ).first()
    if not account or not assignment:
        raise ValueError("平台账号必须是“标注员账号”中该项目与标注员当前绑定的账号")


def _trial_dict(db: Session, row: AnnotationTrialRecord) -> dict:
    person = db.get(ResourcePerson, row.person_id)
    project = db.get(AnnotationProject, row.project_id)
    return {key: getattr(row, key) for key in (
        "id", "project_id", "person_id", "platform_account_id", "round_no", "sequence_no",
        "willingness_text", "trial_status", "trial_result", "result_note", "custom_values",
        "created_by", "created_at", "updated_at"
    )} | {
        "person_name": getattr(person, "full_name", None),
        "resource_code": getattr(person, "resource_code", None),
        "project_order_no": getattr(project, "order_no", None),
        "project_name": getattr(project, "project_name", None),
        "project_status": getattr(project, "project_status", None),
        "client_short_name": getattr(project, "client_short_name", None),
    }


def _trial_query(db: Session, project_id: UUID | None = None, keyword: str | None = None, trial_status: str | None = None):
    query = (
        db.query(AnnotationTrialRecord)
        .join(ResourcePerson, ResourcePerson.id == AnnotationTrialRecord.person_id)
        .join(AnnotationProject, AnnotationProject.id == AnnotationTrialRecord.project_id)
    )
    if project_id:
        query = query.filter(AnnotationTrialRecord.project_id == project_id)
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(or_(
            ResourcePerson.resource_code.ilike(pattern),
            ResourcePerson.full_name.ilike(pattern),
            AnnotationTrialRecord.willingness_text.ilike(pattern),
            AnnotationTrialRecord.result_note.ilike(pattern),
            AnnotationProject.order_no.ilike(pattern),
            AnnotationProject.project_name.ilike(pattern),
        ))
    if trial_status:
        query = query.filter(AnnotationTrialRecord.trial_status == trial_status)
    return query


def list_trials(db: Session, project_id: UUID | None = None, skip: int = 0, limit: int = 100, keyword: str | None = None, trial_status: str | None = None):
    rows = _trial_query(db, project_id, keyword, trial_status).order_by(AnnotationTrialRecord.updated_at.desc(), AnnotationTrialRecord.round_no, AnnotationTrialRecord.sequence_no).offset(skip).limit(limit).all()
    return [_trial_dict(db, row) for row in rows]


def count_trials(db: Session, project_id: UUID | None = None, keyword: str | None = None, trial_status: str | None = None) -> int:
    return _trial_query(db, project_id, keyword, trial_status).count()


def save_trial(db: Session, payload, created_by: UUID | None, trial_id: UUID | None = None):
    _validate_trial_member(db, payload.project_id, payload.person_id, payload.platform_account_id)
    row = db.get(AnnotationTrialRecord, trial_id) if trial_id else AnnotationTrialRecord(project_id=payload.project_id, created_by=created_by)
    if trial_id and not row:
        return None
    if trial_id and row.project_id != payload.project_id:
        raise ValueError("试标记录创建后不能更换项目")
    data = payload.model_dump(exclude={"sequence_no", "custom_values"})
    for key, value in data.items():
        setattr(row, key, value)
    row.custom_values = validate_custom_values(
        db, "trial", payload.project_id, payload.custom_values,
        row.custom_values if trial_id else None,
    )
    row.sequence_no = payload.sequence_no or (row.sequence_no if trial_id else _next_sequence(db, AnnotationTrialRecord, AnnotationTrialRecord.project_id == payload.project_id, AnnotationTrialRecord.round_no == payload.round_no))
    row.updated_at = datetime.now()
    if not trial_id:
        db.add(row)
    db.commit()
    db.refresh(row)
    return _trial_dict(db, row)


def delete_trial(db: Session, trial_id: UUID) -> bool:
    row = db.get(AnnotationTrialRecord, trial_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def save_assignee_rate(db: Session, assignee_id: UUID, payload):
    if not db.get(AnnotationProjectAssignee, assignee_id):
        return None
    row = db.query(AnnotationAssigneeRate).filter(AnnotationAssigneeRate.assignee_id == assignee_id).first()
    if not row:
        row = AnnotationAssigneeRate(assignee_id=assignee_id)
        db.add(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def delete_assignee_rate(db: Session, assignee_id: UUID) -> bool:
    row = db.query(AnnotationAssigneeRate).filter(AnnotationAssigneeRate.assignee_id == assignee_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def _workflow_dict(row: AnnotationProjectAssignee) -> dict:
    rate = row.rate
    project = row.project
    return {
        "id": row.id,
        "project_id": row.project_id,
        "person_id": row.person_id,
        "sequence_no": row.sequence_no,
        "resource_code": row.resource_code,
        "person_name": row.person_name,
        "language_item_id": row.language_item_id,
        "language_display": row.language_item.display if row.language_item else None,
        "assignment_role": row.assignment_role,
        "audio_duration_value": row.audio_duration_value,
        "audio_duration_unit": row.audio_duration_unit,
        "amount": rate.amount if rate else None,
        "unit": rate.unit if rate else None,
        "currency": (rate.currency if rate else None) or "CNY",
        "custom_values": row.custom_values or {},
        "assignment_status": row.assignment_status,
        "quality_score": row.quality_score,
        "evaluation_note": row.evaluation_note,
        "project_order_no": project.order_no,
        "project_name": project.project_name,
        "project_status": project.project_status,
        "client_short_name": project.client_short_name,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_annotation_workflow(
    db: Session, project_id: UUID | None = None, language_item_id: UUID | None = None,
    keyword: str | None = None, assignment_role: str | None = None,
    assignment_status: str | None = None,
) -> list[dict]:
    query = (
        db.query(AnnotationProjectAssignee)
        .join(ResourcePerson, ResourcePerson.id == AnnotationProjectAssignee.person_id)
        .options(
            joinedload(AnnotationProjectAssignee.person),
            joinedload(AnnotationProjectAssignee.language_item),
            joinedload(AnnotationProjectAssignee.rate),
            joinedload(AnnotationProjectAssignee.project).joinedload(AnnotationProject.client),
            joinedload(AnnotationProjectAssignee.project).joinedload(AnnotationProject.sub_client),
        )
    )
    if project_id:
        query = query.filter(AnnotationProjectAssignee.project_id == project_id)
    if language_item_id:
        query = query.filter(AnnotationProjectAssignee.language_item_id == language_item_id)
    if assignment_role:
        query = query.filter(AnnotationProjectAssignee.assignment_role == assignment_role)
    if assignment_status:
        query = query.filter(AnnotationProjectAssignee.assignment_status == assignment_status)
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(or_(
            ResourcePerson.resource_code.ilike(pattern),
            ResourcePerson.full_name.ilike(pattern),
            AnnotationProjectAssignee.project.has(AnnotationProject.order_no.ilike(pattern)),
            AnnotationProjectAssignee.project.has(AnnotationProject.project_name.ilike(pattern)),
        ))
    return [_workflow_dict(row) for row in query.order_by(AnnotationProjectAssignee.updated_at.desc(), AnnotationProjectAssignee.sequence_no).all()]


def save_annotation_workflow(
    db: Session, project_id: UUID, payload, assignee_id: UUID | None = None,
) -> dict | None:
    if not db.get(AnnotationProject, project_id):
        raise ValueError("标注项目不存在")
    if not db.get(ResourcePerson, payload.person_id):
        raise ValueError("所选标注员不存在")
    if payload.language_item_id:
        language_item = db.get(AnnotationProjectLanguageItem, payload.language_item_id)
        if not language_item or language_item.project_id != project_id:
            raise ValueError("所选语种不属于当前标注项目")

    row = db.get(AnnotationProjectAssignee, assignee_id) if assignee_id else None
    if assignee_id and (not row or row.project_id != project_id):
        return None
    if not row:
        row = AnnotationProjectAssignee(
            project_id=project_id,
            sequence_no=_next_sequence(
                db, AnnotationProjectAssignee,
                AnnotationProjectAssignee.project_id == project_id,
            ),
            assignment_role=payload.assignment_role,
            assignment_status="assigned",
            custom_values={},
        )
        db.add(row)

    row.person_id = payload.person_id
    row.assignment_role = payload.assignment_role
    row.language_item_id = payload.language_item_id
    row.audio_duration_value = payload.audio_duration_value
    row.audio_duration_unit = payload.audio_duration_unit
    row.assignment_status = payload.assignment_status
    row.quality_score = payload.quality_score.strip() or None if payload.quality_score else None
    row.evaluation_note = payload.evaluation_note.strip() or None if payload.evaluation_note else None
    row.custom_values = validate_custom_values(
        db, "assignment", project_id, payload.custom_values,
        row.custom_values if assignee_id else None,
    )
    row.updated_at = datetime.now()
    db.flush()

    has_rate = payload.amount is not None
    rate = row.rate
    if has_rate:
        if not rate:
            rate = AnnotationAssigneeRate(assignee_id=row.id)
            db.add(rate)
        rate.amount = payload.amount
        rate.unit = payload.unit
        rate.currency = payload.currency
        rate.updated_at = datetime.now()
    elif rate:
        db.delete(rate)

    db.commit()
    refreshed = (
        db.query(AnnotationProjectAssignee)
        .options(
            joinedload(AnnotationProjectAssignee.person),
            joinedload(AnnotationProjectAssignee.language_item),
            joinedload(AnnotationProjectAssignee.rate),
            joinedload(AnnotationProjectAssignee.project).joinedload(AnnotationProject.client),
            joinedload(AnnotationProjectAssignee.project).joinedload(AnnotationProject.sub_client),
        )
        .filter(AnnotationProjectAssignee.id == row.id)
        .one()
    )
    return _workflow_dict(refreshed)


def delete_annotation_workflow(db: Session, project_id: UUID, assignee_id: UUID) -> bool:
    row = db.get(AnnotationProjectAssignee, assignee_id)
    if not row or row.project_id != project_id:
        return False
    db.delete(row)
    db.commit()
    return True


def list_status_history(db: Session, project_id: UUID):
    rows = db.query(AnnotationProjectStatusHistory).filter(AnnotationProjectStatusHistory.project_id == project_id).order_by(AnnotationProjectStatusHistory.effective_on.desc(), AnnotationProjectStatusHistory.changed_at.desc()).all()
    users = {row.changed_by: db.get(AppUser, row.changed_by) for row in rows if row.changed_by}
    return [{
        "id": row.id, "project_id": row.project_id, "from_status": row.from_status,
        "to_status": row.to_status, "effective_on": row.effective_on, "changed_at": row.changed_at,
        "changed_by": row.changed_by, "changed_by_name": getattr(users.get(row.changed_by), "full_name", None) or getattr(users.get(row.changed_by), "username", None),
        "change_note": row.change_note,
    } for row in rows]
