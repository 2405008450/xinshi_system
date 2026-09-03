"""招聘项目查询、编号、命名及咨询联动。"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from utils import normalize_email_subject_order_no
from project_audit_service import record_project_operation

from concurrency import VERSION_FIELD, assert_fresh

import workflow_models  # noqa: F401  注册 TranslationProject 的既有工作流关系
from annotation_models import AnnotationProject
from interpretation_models import InterpretationLanguage, InterpretationProject
from models import AppUser, Client, Consultation, SubClient, TranslationProject
from recruitment_models import (
    RecruitmentCandidate,
    RecruitmentCandidateCommunication,
    RecruitmentCandidateInterview,
    RecruitmentProject,
    RecruitmentProjectLanguageDirection,
    RecruitmentProjectProgress,
    RecruitmentResumeSource,
)
from recruitment_schemas import (
    RecruitmentCandidateCreate,
    RecruitmentCandidateCommunicationCreate,
    RecruitmentCandidateCommunicationUpdate,
    RecruitmentCandidatePatch,
    RecruitmentCandidateUpdate,
    RecruitmentNamePreviewRequest,
    RecruitmentProgressCreate,
    RecruitmentProjectCreate,
    RecruitmentProjectUpdate,
)
from field_filtering import apply_scalar_specs


RECRUITMENT_TYPE_VALUES = {"招聘项目", "recruitment", "招聘"}
DEFAULT_CLIENT_MANAGER_NAME = "欧阳靖琳"
DEFAULT_RESUME_SOURCES = ("BOSS", "智联", "小红书", "微信", "广外校友推荐")
NESTED_FIELDS = {"language_directions", "role_assignments"}
WRITE_ONLY_CLIENT_FIELDS = {"client_name", "client_short_name", "client_code", "manager_contact"}


def is_recruitment_type(value: Optional[str]) -> bool:
    return (value or "").strip() in RECRUITMENT_TYPE_VALUES


def generate_recruitment_order_no(db: Session, current_time: Optional[datetime] = None) -> str:
    now = current_time or datetime.now(ZoneInfo("Asia/Hong_Kong"))
    date_text = now.strftime("%y%m%d")
    prefix = f"HP-{date_text}-"
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"recruitment-order:{date_text}"},
        )
    last = (
        db.query(RecruitmentProject.order_no)
        .filter(RecruitmentProject.order_no.like(f"{prefix}%"))
        .order_by(RecruitmentProject.order_no.desc())
        .limit(1)
        .scalar()
    )
    sequence = 1
    if last:
        try:
            sequence = int(last.rsplit("-", 1)[-1]) + 1
        except ValueError:
            sequence = 1
    return f"{prefix}{sequence:03d}"


def _project_options():
    return (
        selectinload(RecruitmentProject.client),
        selectinload(RecruitmentProject.sub_client),
        selectinload(RecruitmentProject.client_manager),
        selectinload(RecruitmentProject.language_directions).selectinload(RecruitmentProjectLanguageDirection.source_language),
        selectinload(RecruitmentProject.language_directions).selectinload(RecruitmentProjectLanguageDirection.target_language),
        selectinload(RecruitmentProject.progress_records).selectinload(RecruitmentProjectProgress.operator),
        selectinload(RecruitmentProject.candidates).selectinload(RecruitmentCandidate.owner),
        selectinload(RecruitmentProject.candidates).selectinload(RecruitmentCandidate.resume_source),
        selectinload(RecruitmentProject.candidates).selectinload(RecruitmentCandidate.communications),
        selectinload(RecruitmentProject.workbench_responsibilities)
        .selectinload(workflow_models.ProjectWorkbenchResponsibility.assignee),
    )


def get_recruitment_project(db: Session, project_id: UUID) -> Optional[RecruitmentProject]:
    return db.query(RecruitmentProject).options(*_project_options()).filter(RecruitmentProject.id == project_id).first()


def _apply_filters(
    query,
    *,
    keyword=None,
    project_status=None,
    client_id=None,
    sub_client_id=None,
    language_id=None,
    client_manager_id=None,
    employment_date_start=None,
    employment_date_end=None,
    target_onboard_date_start=None,
    target_onboard_date_end=None,
    created_date_start=None,
    created_date_end=None,
    field_filters=None,
):
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            RecruitmentProject.order_no.ilike(pattern),
            RecruitmentProject.project_name.ilike(pattern),
            RecruitmentProject.position_title.ilike(pattern),
            RecruitmentProject.job_description.ilike(pattern),
            RecruitmentProject.work_location.ilike(pattern),
            RecruitmentProject.customer_order_no.ilike(pattern),
            Client.client_name.ilike(pattern),
            Client.client_short_name.ilike(pattern),
            SubClient.client_name.ilike(pattern),
            SubClient.client_short_name.ilike(pattern),
        ))
    if project_status:
        query = query.filter(RecruitmentProject.project_status == project_status)
    if client_id:
        query = query.filter(RecruitmentProject.client_id == client_id)
    if sub_client_id:
        query = query.filter(RecruitmentProject.sub_client_id == sub_client_id)
    if language_id:
        query = query.join(
            RecruitmentProjectLanguageDirection,
            RecruitmentProjectLanguageDirection.project_id == RecruitmentProject.id,
        ).filter(or_(
            RecruitmentProjectLanguageDirection.source_language_id == language_id,
            RecruitmentProjectLanguageDirection.target_language_id == language_id,
        ))
    if client_manager_id:
        query = query.filter(RecruitmentProject.client_manager_id == client_manager_id)
    if employment_date_start:
        query = query.filter(RecruitmentProject.employment_end >= employment_date_start)
    if employment_date_end:
        query = query.filter(RecruitmentProject.employment_start <= employment_date_end)
    if target_onboard_date_start:
        query = query.filter(RecruitmentProject.target_onboard_date >= target_onboard_date_start)
    if target_onboard_date_end:
        query = query.filter(RecruitmentProject.target_onboard_date <= target_onboard_date_end)
    if created_date_start:
        query = query.filter(RecruitmentProject.created_at >= datetime.combine(created_date_start, time.min))
    if created_date_end:
        query = query.filter(RecruitmentProject.created_at <= datetime.combine(created_date_end, time.max))
    field_filters = field_filters or {}
    query = apply_scalar_specs(query, field_filters, {
        "order_no": (RecruitmentProject.order_no, "string"),
        "project_name": (RecruitmentProject.project_name, "string"),
        "job_description": (RecruitmentProject.job_description, "string"),
        "position_title": (RecruitmentProject.position_title, "string"),
        "client_manager_id": (RecruitmentProject.client_manager_id, "uuid"),
        "project_status": (RecruitmentProject.project_status, "string"),
        "contact_name": (RecruitmentProject.contact_name, "string"),
        "customer_order_no": (RecruitmentProject.customer_order_no, "string"),
        "target_onboard_date": (RecruitmentProject.target_onboard_date, "date"),
        "work_location": (RecruitmentProject.work_location, "string"),
        "service_fee_amount": (RecruitmentProject.service_fee_amount, "number"),
        "customer_consultation_time": (RecruitmentProject.customer_consultation_time, "datetime"),
        "customer_confirmation_time": (RecruitmentProject.customer_confirmation_time, "datetime"),
        "remarks": (RecruitmentProject.remarks, "string"),
        "created_at": (RecruitmentProject.created_at, "datetime"),
        "updated_at": (RecruitmentProject.updated_at, "datetime"),
    })
    for field, descriptor in field_filters.items():
        if field in {"client_short_name", "client_code", "client_name", "client_domain"}:
            parent_column, sub_column = {
                "client_short_name": (Client.client_short_name, SubClient.client_short_name),
                "client_code": (Client.client_code, SubClient.sub_client_code),
                "client_name": (Client.client_name, SubClient.client_name),
                "client_domain": (func.concat_ws(" / ", Client.field_level1, Client.field_level2), func.concat_ws(" / ", SubClient.field_level1, SubClient.field_level2)),
            }[field]
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(parent_column.ilike(pattern), sub_column.ilike(pattern)))
        elif field == "language_id":
            values = [UUID(str(value)) for value in descriptor.get("value") or []]
            query = query.join(RecruitmentProjectLanguageDirection, RecruitmentProjectLanguageDirection.project_id == RecruitmentProject.id).filter(or_(RecruitmentProjectLanguageDirection.source_language_id.in_(values), RecruitmentProjectLanguageDirection.target_language_id.in_(values)))
        elif field in {"headcount", "employment_period"}:
            lower = descriptor.get("min", descriptor.get("from"))
            upper = descriptor.get("max", descriptor.get("to"))
            if field == "headcount":
                if lower not in (None, ""):
                    query = query.filter(RecruitmentProject.headcount_max >= int(lower))
                if upper not in (None, ""):
                    query = query.filter(RecruitmentProject.headcount_min <= int(upper))
            else:
                if lower:
                    query = query.filter(RecruitmentProject.employment_end >= datetime.fromisoformat(str(lower)).date())
                if upper:
                    query = query.filter(RecruitmentProject.employment_start <= datetime.fromisoformat(str(upper)).date())
        elif field == "candidate_count":
            candidate_count = select(func.count(RecruitmentCandidate.id)).where(RecruitmentCandidate.project_id == RecruitmentProject.id).correlate(RecruitmentProject).scalar_subquery()
            if descriptor.get("min") not in (None, ""):
                query = query.filter(candidate_count >= int(descriptor["min"]))
            if descriptor.get("max") not in (None, ""):
                query = query.filter(candidate_count <= int(descriptor["max"]))
    return query


def get_recruitment_projects(db: Session, *, skip=0, limit=100, **filters) -> list[RecruitmentProject]:
    query = (
        db.query(RecruitmentProject)
        .options(*_project_options())
        .outerjoin(Client, RecruitmentProject.client_id == Client.id)
        .outerjoin(SubClient, RecruitmentProject.sub_client_id == SubClient.id)
    )
    return (
        _apply_filters(query, **filters)
        .distinct()
        .order_by(RecruitmentProject.created_at.desc(), RecruitmentProject.id.desc())
        .offset(skip).limit(limit).all()
    )


def count_recruitment_projects(db: Session, **filters) -> int:
    query = (
        db.query(RecruitmentProject.id)
        .outerjoin(Client, RecruitmentProject.client_id == Client.id)
        .outerjoin(SubClient, RecruitmentProject.sub_client_id == SubClient.id)
    )
    return _apply_filters(query, **filters).distinct().count()


def _resolve_client(db: Session, data: dict) -> None:
    client_id = data.get("client_id")
    sub_client_id = data.get("sub_client_id")
    if sub_client_id:
        sub_client = db.query(SubClient).filter(SubClient.id == sub_client_id).first()
        if not sub_client:
            raise ValueError("所选子客户不存在")
        if client_id and sub_client.parent_client_id != client_id:
            raise ValueError("所选子客户不属于当前客户")
        data["client_id"] = sub_client.parent_client_id
        return
    if client_id:
        if not db.query(Client.id).filter(Client.id == client_id).first():
            raise ValueError("所选客户不存在")
        return

    from crud import _resolve_or_create_project_client

    client_id, sub_client_id, _created = _resolve_or_create_project_client(
        db,
        data.get("client_short_name"),
        data.get("client_code"),
        data.get("client_name"),
        data.get("manager_contact"),
    )
    if client_id:
        data["client_id"] = client_id
    if sub_client_id:
        data["sub_client_id"] = sub_client_id


def _unique_active_user_by_name(db: Session, name: Optional[str]) -> Optional[AppUser]:
    if not name or not name.strip():
        return None
    rows = db.query(AppUser).filter(
        AppUser.is_active.is_(True),
        func.lower(func.trim(AppUser.full_name)) == name.strip().lower(),
    ).limit(2).all()
    return rows[0] if len(rows) == 1 else None


def _default_client_manager(db: Session, client_id: Optional[UUID]) -> Optional[AppUser]:
    manager_name = None
    if client_id:
        client = db.query(Client).filter(Client.id == client_id).first()
        manager_name = client.client_manager if client else None
    return _unique_active_user_by_name(db, manager_name) or _unique_active_user_by_name(db, DEFAULT_CLIENT_MANAGER_NAME)


def _set_client_manager(db: Session, data: dict, existing: Optional[RecruitmentProject] = None) -> None:
    manager_id = data.get("client_manager_id")
    manager = None
    if manager_id:
        manager = db.query(AppUser).filter(AppUser.id == manager_id).first()
        if not manager:
            raise ValueError("所选现客户经理不存在")
    elif existing is None:
        manager = _default_client_manager(db, data.get("client_id"))
        data["client_manager_id"] = manager.id if manager else None
    if manager:
        data["client_manager_name_snapshot"] = manager.full_name or manager.username
    elif existing is not None and "client_manager_id" in data and not manager_id:
        data["client_manager_name_snapshot"] = None


def _sync_languages(db: Session, project: RecruitmentProject, payload) -> None:
    language_ids = {
        language_id
        for item in payload.language_directions
        for language_id in (item.source_language_id, item.target_language_id)
        if language_id
    }
    if language_ids:
        found = {
            language_id for (language_id,) in db.query(InterpretationLanguage.id)
            .filter(InterpretationLanguage.id.in_(language_ids)).all()
        }
        if found != language_ids:
            raise ValueError("所选语种不存在或已失效")
    project.language_directions.clear()
    db.flush()
    project.language_directions = [
        RecruitmentProjectLanguageDirection(sequence_no=index, **item.model_dump())
        for index, item in enumerate(payload.language_directions, start=1)
    ]


def _add_progress(
    db: Session,
    project: RecruitmentProject,
    *,
    operator_id: Optional[UUID],
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    note: Optional[str] = None,
    is_system: bool = True,
    occurred_at: Optional[datetime] = None,
) -> RecruitmentProjectProgress:
    record = RecruitmentProjectProgress(
        project=project,
        operator_id=operator_id,
        from_status=from_status,
        to_status=to_status,
        note=note,
        is_system=is_system,
        occurred_at=occurred_at or datetime.now(),
    )
    db.add(record)
    return record


def create_recruitment_project(
    db: Session, payload: RecruitmentProjectCreate, created_by: Optional[UUID],
    idempotency_key: Optional[str] = None,
    operation_source: str = "project_form",
) -> RecruitmentProject:
    data = payload.model_dump(exclude=NESTED_FIELDS)
    _resolve_client(db, data)
    for key in WRITE_ONLY_CLIENT_FIELDS:
        data.pop(key, None)
    _set_client_manager(db, data)
    order_no = generate_recruitment_order_no(db)
    data["email_subject_preview"] = normalize_email_subject_order_no(
        data.get("email_subject_preview"), order_no
    )
    project = RecruitmentProject(
        order_no=order_no, created_by=created_by,
        idempotency_key=idempotency_key, **data,
    )
    db.add(project)
    db.flush()
    from project_workbench_service import assignment_map_from_payload, ensure_project_responsibilities, validate_assignment_map
    assignments = assignment_map_from_payload(payload.role_assignments)
    validate_assignment_map(db, assignments)
    ensure_project_responsibilities(db, 'recruitment', project.id, assignments)
    _sync_languages(db, project, payload)
    _add_progress(db, project, operator_id=created_by, to_status=project.project_status, note="创建招聘项目")
    record_project_operation(
        db, project_type="recruitment", operation_type="create", project=project,
        actor_user_id=created_by, operation_source=operation_source,
    )
    db.commit()
    return get_recruitment_project(db, project.id)


def update_recruitment_project(
    db: Session, project_id: UUID, payload: RecruitmentProjectUpdate, operator_id: Optional[UUID]
) -> Optional[RecruitmentProject]:
    project = get_recruitment_project(db, project_id)
    if not project:
        return None
    assert_fresh(project, payload.expected_updated_at)
    old_status = project.project_status
    data = payload.model_dump(exclude=NESTED_FIELDS | {VERSION_FIELD})
    # 来源咨询一经建项即不可通过普通编辑解绑或换绑。
    data.pop("consultation_id", None)
    _resolve_client(db, data)
    for key in WRITE_ONLY_CLIENT_FIELDS:
        data.pop(key, None)
    _set_client_manager(db, data, existing=project)
    for key, value in data.items():
        setattr(project, key, value)
    from project_workbench_service import assignment_map_from_payload, ensure_active_project_responsibilities, validate_assignment_map
    assignments = assignment_map_from_payload(payload.role_assignments) if 'role_assignments' in payload.model_fields_set else None
    validate_assignment_map(db, assignments)
    ensure_active_project_responsibilities(db, 'recruitment', project.id, project.project_status, assignments)
    _sync_languages(db, project, payload)
    if old_status != project.project_status:
        _add_progress(
            db, project, operator_id=operator_id, from_status=old_status,
            to_status=project.project_status, note="项目状态变更",
        )
    project.updated_at = datetime.now()
    db.commit()
    return get_recruitment_project(db, project.id)


def update_recruitment_project_status(
    db: Session, project_id: UUID, project_status: str, operator_id: Optional[UUID]
) -> Optional[RecruitmentProject]:
    project = get_recruitment_project(db, project_id)
    if not project:
        return None
    old_status = project.project_status
    if old_status == project_status:
        return project
    project.project_status = project_status
    project.updated_at = datetime.now()
    from project_workbench_service import ensure_active_project_responsibilities
    ensure_active_project_responsibilities(db, 'recruitment', project.id, project_status)
    _add_progress(
        db, project, operator_id=operator_id, from_status=old_status,
        to_status=project_status, note="项目状态变更",
    )
    db.commit()
    return get_recruitment_project(db, project.id)


def delete_recruitment_project(
    db: Session, project_id: UUID, *, actor_user_id: Optional[UUID] = None,
    operation_source: str = "project_delete",
) -> bool:
    project = db.query(RecruitmentProject).filter(RecruitmentProject.id == project_id).first()
    if not project:
        return False
    from project_workbench_service import cancel_pending_project_handovers
    cancel_pending_project_handovers(db, 'recruitment', project_id)
    record_project_operation(
        db, project_type="recruitment", operation_type="delete", project=project,
        actor_user_id=actor_user_id, operation_source=operation_source,
    )
    db.delete(project)
    db.commit()
    return True


def _direction_labels(db: Session, directions) -> list[str]:
    ids = {
        language_id for item in directions
        for language_id in (item.source_language_id, item.target_language_id) if language_id
    }
    languages = {
        row.id: row.label for row in db.query(InterpretationLanguage).filter(InterpretationLanguage.id.in_(ids)).all()
    } if ids else {}
    if len(languages) != len(ids):
        raise ValueError("所选语种不存在或已失效")
    return [
        languages[item.source_language_id]
        if item.direction_type == "single"
        else f"{languages[item.source_language_id]}翻译成{languages[item.target_language_id]}"
        for item in directions
    ]


def build_recruitment_project_name(payload: RecruitmentNamePreviewRequest, labels: list[str]) -> str:
    period = f"{payload.employment_start:%Y年%m月%d日}—{payload.employment_end:%Y年%m月%d日}"
    direction = "、".join(labels[:3]) + ("等方向" if len(labels) > 3 else "")
    return f"{period}{payload.work_location.strip()}{direction}{payload.position_title.strip()}"


def preview_recruitment_project_name(db: Session, payload: RecruitmentNamePreviewRequest) -> str:
    return build_recruitment_project_name(payload, _direction_labels(db, payload.language_directions))


def add_manual_progress(
    db: Session, project_id: UUID, payload: RecruitmentProgressCreate, operator_id: Optional[UUID]
) -> Optional[RecruitmentProjectProgress]:
    project = db.query(RecruitmentProject).filter(RecruitmentProject.id == project_id).first()
    if not project:
        return None
    record = _add_progress(
        db, project, operator_id=operator_id, note=payload.note,
        is_system=False, occurred_at=payload.occurred_at,
    )
    db.commit()
    db.refresh(record)
    return record


def create_candidate(
    db: Session, project_id: UUID, payload: RecruitmentCandidateCreate
) -> Optional[RecruitmentCandidate]:
    if not db.query(RecruitmentProject.id).filter(RecruitmentProject.id == project_id).first():
        return None
    data = payload.model_dump()
    allow_duplicate = data.pop("allow_duplicate", False)
    interviews = data.pop("interviews", None)
    from resource_models import ResourcePerson
    from resource_service import (
        TalentDuplicateError,
        extract_contact_identifiers,
        find_duplicate_talents,
    )

    person_id = data.get("person_id")
    if person_id:
        if not db.query(ResourcePerson.id).filter(ResourcePerson.id == person_id).first():
            raise ValueError("所选人才档案不存在")
    else:
        phone, email = extract_contact_identifiers(data.get("contact_info"))
        duplicates = find_duplicate_talents(db, phone=phone, email=email)
        if duplicates and not allow_duplicate:
            raise TalentDuplicateError(duplicates)
        person = ResourcePerson(
            full_name=data["candidate_name"],
            contact_info=data.get("contact_info"),
            primary_phone=phone,
            primary_email=email,
            resume_path=data.get("resume_path"),
            status="standby",
            duplicate_review_required=bool(duplicates),
        )
        db.add(person)
        db.flush()
        data["person_id"] = person.id
    if data.get("owner_id") and not db.query(AppUser.id).filter(AppUser.id == data["owner_id"]).first():
        raise ValueError("所选跟进人不存在")
    _validate_resume_source(db, data.get("resume_source_id"))
    candidate = RecruitmentCandidate(project_id=project_id, **data)
    db.add(candidate)
    db.flush()
    if interviews is not None:
        _sync_candidate_interviews(db, candidate, interviews)
    db.commit()
    return get_candidate(db, candidate.id)


def update_candidate(
    db: Session, candidate_id: UUID, payload: RecruitmentCandidateUpdate
) -> Optional[RecruitmentCandidate]:
    candidate = db.query(RecruitmentCandidate).filter(RecruitmentCandidate.id == candidate_id).first()
    if not candidate:
        return None
    data = payload.model_dump()
    interviews = data.pop("interviews", None)
    if not data.get("person_id"):
        data["person_id"] = candidate.person_id
    if data.get("person_id"):
        from resource_models import ResourcePerson
        if not db.query(ResourcePerson.id).filter(ResourcePerson.id == data["person_id"]).first():
            raise ValueError("所选人才档案不存在")
    if data.get("owner_id") and not db.query(AppUser.id).filter(AppUser.id == data["owner_id"]).first():
        raise ValueError("所选跟进人不存在")
    _validate_resume_source(db, data.get("resume_source_id"))
    for key, value in data.items():
        setattr(candidate, key, value)
    if interviews is not None:
        _sync_candidate_interviews(db, candidate, interviews)
    candidate.updated_at = datetime.now()
    db.commit()
    return get_candidate(db, candidate_id)


def _candidate_options():
    return (
        selectinload(RecruitmentCandidate.person),
        selectinload(RecruitmentCandidate.owner),
        selectinload(RecruitmentCandidate.resume_source),
        selectinload(RecruitmentCandidate.communications),
        selectinload(RecruitmentCandidate.interviews),
    )


def get_candidate(db: Session, candidate_id: UUID) -> Optional[RecruitmentCandidate]:
    return (
        db.query(RecruitmentCandidate)
        .options(*_candidate_options())
        .filter(RecruitmentCandidate.id == candidate_id)
        .first()
    )


def _validate_resume_source(db: Session, source_id: Optional[UUID]) -> None:
    if source_id and not db.query(RecruitmentResumeSource.id).filter(RecruitmentResumeSource.id == source_id).first():
        raise ValueError("所选简历来源不存在")


def _sync_candidate_interviews(db: Session, candidate: RecruitmentCandidate, interviews) -> None:
    """按连续轮次同步面试记录，并保留固定一面/二面字段用于旧接口兼容。"""
    existing_by_round = {item.round_no: item for item in candidate.interviews}
    retained_rounds = set()
    now = datetime.now()
    for item in interviews:
        values = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        round_no = values["round_no"]
        retained_rounds.add(round_no)
        record = existing_by_round.get(round_no)
        if record is None:
            record = RecruitmentCandidateInterview(
                candidate=candidate,
                round_no=round_no,
            )
            db.add(record)
        record.interview_date = values.get("interview_date")
        record.details = values.get("details")
        record.updated_at = now

    for round_no, record in existing_by_round.items():
        if round_no not in retained_rounds:
            db.delete(record)

    values_by_round = {
        (item.round_no if hasattr(item, "round_no") else item["round_no"]): item
        for item in interviews
    }
    for round_no, prefix in ((1, "first_interview"), (2, "second_interview")):
        item = values_by_round.get(round_no)
        values = item.model_dump() if hasattr(item, "model_dump") else (dict(item) if item else {})
        setattr(candidate, f"{prefix}_date", values.get("interview_date"))
        setattr(candidate, f"{prefix}_details", values.get("details"))


def patch_candidate(
    db: Session, candidate_id: UUID, payload: RecruitmentCandidatePatch
) -> Optional[RecruitmentCandidate]:
    candidate = db.query(RecruitmentCandidate).filter(RecruitmentCandidate.id == candidate_id).first()
    if not candidate:
        return None
    data = payload.model_dump(exclude_unset=True)
    interviews = data.pop("interviews", None)
    if "resume_source_id" in data:
        _validate_resume_source(db, data["resume_source_id"])
    for key, value in data.items():
        setattr(candidate, key, value)
    if interviews is not None:
        _sync_candidate_interviews(db, candidate, interviews)
    candidate.updated_at = datetime.now()
    db.commit()
    return get_candidate(db, candidate_id)


def get_resume_sources(db: Session) -> list[RecruitmentResumeSource]:
    return db.query(RecruitmentResumeSource).order_by(
        RecruitmentResumeSource.is_custom.asc(), RecruitmentResumeSource.label.asc()
    ).all()


def ensure_default_resume_sources(db: Session) -> None:
    existing = {label.lower() for (label,) in db.query(RecruitmentResumeSource.label).all()}
    for label in DEFAULT_RESUME_SOURCES:
        if label.lower() not in existing:
            db.add(RecruitmentResumeSource(label=label, is_custom=False))
    db.commit()


def create_or_get_resume_source(
    db: Session, label: str, created_by: Optional[UUID]
) -> RecruitmentResumeSource:
    normalized = label.strip()
    existing = db.query(RecruitmentResumeSource).filter(
        func.lower(func.trim(RecruitmentResumeSource.label)) == normalized.lower()
    ).first()
    if existing:
        return existing
    source = RecruitmentResumeSource(label=normalized, is_custom=True, created_by=created_by)
    db.add(source)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(RecruitmentResumeSource).filter(
            func.lower(func.trim(RecruitmentResumeSource.label)) == normalized.lower()
        ).first()
        if existing:
            return existing
        raise
    db.refresh(source)
    return source


def create_candidate_communication(
    db: Session, candidate_id: UUID, payload: RecruitmentCandidateCommunicationCreate
) -> Optional[RecruitmentCandidateCommunication]:
    if not db.query(RecruitmentCandidate.id).filter(RecruitmentCandidate.id == candidate_id).first():
        return None
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"recruitment-candidate-communication:{candidate_id}"},
        )
    last_sequence = db.query(func.max(RecruitmentCandidateCommunication.sequence_no)).filter(
        RecruitmentCandidateCommunication.candidate_id == candidate_id
    ).scalar() or 0
    record = RecruitmentCandidateCommunication(
        candidate_id=candidate_id,
        sequence_no=last_sequence + 1,
        **payload.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_candidate_communication(
    db: Session, communication_id: UUID, payload: RecruitmentCandidateCommunicationUpdate
) -> Optional[RecruitmentCandidateCommunication]:
    record = db.query(RecruitmentCandidateCommunication).filter(
        RecruitmentCandidateCommunication.id == communication_id
    ).first()
    if not record:
        return None
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    record.updated_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def delete_candidate(db: Session, candidate_id: UUID) -> bool:
    candidate = db.query(RecruitmentCandidate).filter(RecruitmentCandidate.id == candidate_id).first()
    if not candidate:
        return False
    db.delete(candidate)
    db.commit()
    return True


def ensure_recruitment_project_for_consultation(
    db: Session, consultation: Consultation, created_by: Optional[UUID],
    *, order_no: Optional[str] = None, project_name: Optional[str] = None,
    email_subject_preview: Optional[str] = None,
) -> tuple[RecruitmentProject, bool]:
    existing = db.query(RecruitmentProject).filter(RecruitmentProject.consultation_id == consultation.id).first()
    if existing:
        if project_name is not None:
            existing.project_name = project_name
        if email_subject_preview is not None:
            existing.email_subject_preview = email_subject_preview
        return existing, False
    if db.query(TranslationProject.id).filter(TranslationProject.consultation_id == consultation.id).first():
        raise ValueError("该咨询已生成笔译项目，不能再生成招聘项目")
    if db.query(InterpretationProject.id).filter(InterpretationProject.consultation_id == consultation.id).first():
        raise ValueError("该咨询已生成口译项目，不能再生成招聘项目")
    if db.query(AnnotationProject.id).filter(AnnotationProject.consultation_id == consultation.id).first():
        raise ValueError("该咨询已生成标注项目，不能再生成招聘项目")
    manager = _default_client_manager(db, consultation.client_id)
    now = datetime.now()
    project = RecruitmentProject(
        order_no=order_no or generate_recruitment_order_no(db),
        project_name=project_name,
        consultation_id=consultation.id,
        client_id=consultation.client_id,
        client_manager_id=manager.id if manager else None,
        client_manager_name_snapshot=(manager.full_name or manager.username) if manager else None,
        project_status="pending_setup",
        target_onboard_type="date",
        customer_consultation_time=consultation.consultation_time,
        customer_confirmation_time=now,
        email_subject_preview=email_subject_preview,
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    _add_progress(db, project, operator_id=created_by, to_status="pending_setup", note="咨询确认后自动建项")
    record_project_operation(
        db, project_type="recruitment", operation_type="create", project=project,
        actor_user_id=created_by, operation_source="consultation_confirmation",
    )
    return project, True


def validate_consultation_recruitment_type_change(
    db: Session, consultation_id: UUID, target_type: Optional[str]
) -> None:
    has_recruitment = db.query(RecruitmentProject.id).filter(RecruitmentProject.consultation_id == consultation_id).first()
    if has_recruitment and not is_recruitment_type(target_type):
        raise ValueError("该咨询已生成招聘项目，不能修改为其他咨询类型")
    if is_recruitment_type(target_type):
        conflicts = (
            db.query(TranslationProject.id).filter(TranslationProject.consultation_id == consultation_id).first()
            or db.query(InterpretationProject.id).filter(InterpretationProject.consultation_id == consultation_id).first()
            or db.query(AnnotationProject.id).filter(AnnotationProject.consultation_id == consultation_id).first()
        )
        if conflicts:
            raise ValueError("该咨询已生成其他类型项目，不能修改为招聘项目")
