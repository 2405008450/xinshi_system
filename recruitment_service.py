"""招聘项目查询、编号、命名及咨询联动。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import workflow_models  # noqa: F401  注册 TranslationProject 的既有工作流关系
from annotation_models import AnnotationProject
from interpretation_models import InterpretationLanguage, InterpretationProject
from models import AppUser, Client, Consultation, SubClient, TranslationProject
from recruitment_models import (
    RecruitmentCandidate,
    RecruitmentCandidateCommunication,
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


RECRUITMENT_TYPE_VALUES = {"招聘项目", "recruitment", "招聘"}
DEFAULT_CLIENT_MANAGER_NAME = "欧阳靖琳"
DEFAULT_RESUME_SOURCES = ("BOSS", "智联", "小红书", "微信", "广外校友推荐")
NESTED_FIELDS = {"language_directions"}


def is_recruitment_type(value: Optional[str]) -> bool:
    return (value or "").strip() in RECRUITMENT_TYPE_VALUES


def generate_recruitment_order_no(db: Session, current_time: Optional[datetime] = None) -> str:
    now = current_time or datetime.now(ZoneInfo("Asia/Hong_Kong"))
    date_text = now.strftime("%Y%m%d")
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
    )


def get_recruitment_project(db: Session, project_id: UUID) -> Optional[RecruitmentProject]:
    return db.query(RecruitmentProject).options(*_project_options()).filter(RecruitmentProject.id == project_id).first()


def _apply_filters(
    query,
    *,
    keyword=None,
    project_status=None,
    client_manager_id=None,
    employment_date_start=None,
    employment_date_end=None,
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
    if client_manager_id:
        query = query.filter(RecruitmentProject.client_manager_id == client_manager_id)
    if employment_date_start:
        query = query.filter(RecruitmentProject.employment_end >= employment_date_start)
    if employment_date_end:
        query = query.filter(RecruitmentProject.employment_start <= employment_date_end)
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
    elif client_id and not db.query(Client.id).filter(Client.id == client_id).first():
        raise ValueError("所选客户不存在")


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
    db: Session, payload: RecruitmentProjectCreate, created_by: Optional[UUID]
) -> RecruitmentProject:
    data = payload.model_dump(exclude=NESTED_FIELDS)
    _resolve_client(db, data)
    _set_client_manager(db, data)
    project = RecruitmentProject(order_no=generate_recruitment_order_no(db), created_by=created_by, **data)
    db.add(project)
    db.flush()
    _sync_languages(db, project, payload)
    _add_progress(db, project, operator_id=created_by, to_status=project.project_status, note="创建招聘项目")
    db.commit()
    return get_recruitment_project(db, project.id)


def update_recruitment_project(
    db: Session, project_id: UUID, payload: RecruitmentProjectUpdate, operator_id: Optional[UUID]
) -> Optional[RecruitmentProject]:
    project = get_recruitment_project(db, project_id)
    if not project:
        return None
    old_status = project.project_status
    data = payload.model_dump(exclude=NESTED_FIELDS)
    # 来源咨询一经建项即不可通过普通编辑解绑或换绑。
    data.pop("consultation_id", None)
    _resolve_client(db, data)
    _set_client_manager(db, data, existing=project)
    for key, value in data.items():
        setattr(project, key, value)
    _sync_languages(db, project, payload)
    if old_status != project.project_status:
        _add_progress(
            db, project, operator_id=operator_id, from_status=old_status,
            to_status=project.project_status, note="项目状态变更",
        )
    project.updated_at = datetime.now()
    db.commit()
    return get_recruitment_project(db, project.id)


def delete_recruitment_project(db: Session, project_id: UUID) -> bool:
    project = db.query(RecruitmentProject).filter(RecruitmentProject.id == project_id).first()
    if not project:
        return False
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
    if data.get("owner_id") and not db.query(AppUser.id).filter(AppUser.id == data["owner_id"]).first():
        raise ValueError("所选跟进人不存在")
    _validate_resume_source(db, data.get("resume_source_id"))
    candidate = RecruitmentCandidate(project_id=project_id, **data)
    db.add(candidate)
    db.commit()
    return get_candidate(db, candidate.id)


def update_candidate(
    db: Session, candidate_id: UUID, payload: RecruitmentCandidateUpdate
) -> Optional[RecruitmentCandidate]:
    candidate = db.query(RecruitmentCandidate).filter(RecruitmentCandidate.id == candidate_id).first()
    if not candidate:
        return None
    data = payload.model_dump()
    if data.get("owner_id") and not db.query(AppUser.id).filter(AppUser.id == data["owner_id"]).first():
        raise ValueError("所选跟进人不存在")
    _validate_resume_source(db, data.get("resume_source_id"))
    for key, value in data.items():
        setattr(candidate, key, value)
    candidate.updated_at = datetime.now()
    db.commit()
    return get_candidate(db, candidate_id)


def _candidate_options():
    return (
        selectinload(RecruitmentCandidate.owner),
        selectinload(RecruitmentCandidate.resume_source),
        selectinload(RecruitmentCandidate.communications),
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


def patch_candidate(
    db: Session, candidate_id: UUID, payload: RecruitmentCandidatePatch
) -> Optional[RecruitmentCandidate]:
    candidate = db.query(RecruitmentCandidate).filter(RecruitmentCandidate.id == candidate_id).first()
    if not candidate:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "resume_source_id" in data:
        _validate_resume_source(db, data["resume_source_id"])
    for key, value in data.items():
        setattr(candidate, key, value)
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
    db: Session, consultation: Consultation, created_by: Optional[UUID]
) -> tuple[RecruitmentProject, bool]:
    existing = db.query(RecruitmentProject).filter(RecruitmentProject.consultation_id == consultation.id).first()
    if existing:
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
        order_no=generate_recruitment_order_no(db),
        consultation_id=consultation.id,
        client_id=consultation.client_id,
        client_manager_id=manager.id if manager else None,
        client_manager_name_snapshot=(manager.full_name or manager.username) if manager else None,
        project_status="pending_setup",
        target_onboard_type="date",
        customer_consultation_time=consultation.consultation_time,
        customer_confirmation_time=now,
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    _add_progress(db, project, operator_id=created_by, to_status="pending_setup", note="咨询确认后自动建项")
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
