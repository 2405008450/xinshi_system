"""口译项目业务逻辑、查询与命名。"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, selectinload

from concurrency import VERSION_FIELD, assert_fresh

import workflow_models  # noqa: F401  注册 TranslationProject 的既有工作流关系
from interpretation_models import (
    InterpretationLanguage,
    InterpretationProject,
    InterpretationProjectInterpreter,
    InterpretationProjectLanguageDirection,
    InterpretationProjectTimeRange,
)
from interpretation_schemas import (
    PROJECT_TYPE_LABELS,
    InterpretationNamePreviewRequest,
    InterpretationProjectCreate,
    InterpretationProjectUpdate,
)
from language_catalog import LANGUAGE_VARIANTS
from models import Client, Consultation, SubClient, TranslationProject, Translator


INTERPRETATION_TYPE_VALUES = {"口译项目", "interpretation", "口译"}


def is_interpretation_type(value: Optional[str]) -> bool:
    return (value or "").strip() in INTERPRETATION_TYPE_VALUES


def ensure_default_interpretation_languages(db: Session) -> None:
    existing = {row[0] for row in db.query(InterpretationLanguage.label).all()}
    changed = False
    for item in LANGUAGE_VARIANTS:
        if item["label"] in existing:
            continue
        db.add(InterpretationLanguage(label=item["label"], is_custom=False))
        changed = True
    if changed:
        db.commit()


def generate_interpretation_order_no(db: Session, current_time: Optional[datetime] = None) -> str:
    now = current_time or datetime.now(ZoneInfo("Asia/Hong_Kong"))
    date_text = now.strftime("%y%m%d")
    prefix = f"IP-{date_text}-"
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"interpretation-order:{date_text}"},
        )
    last_order_no = (
        db.query(InterpretationProject.order_no)
        .filter(InterpretationProject.order_no.like(f"{prefix}%"))
        .order_by(InterpretationProject.order_no.desc())
        .limit(1)
        .scalar()
    )
    sequence = 1
    if last_order_no:
        try:
            sequence = int(last_order_no.rsplit("-", 1)[-1]) + 1
        except ValueError:
            sequence = 1
    return f"{prefix}{sequence:03d}"


def _time_period_label(start: datetime, end: datetime) -> str:
    if start.date() != end.date():
        return ""
    start_time, end_time = start.time(), end.time()
    if start_time >= time(8, 0) and end_time <= time(12, 0):
        return "上午"
    if start_time >= time(13, 0) and start_time < time(18, 0) and end_time <= time(18, 0):
        return "下午"
    if start_time >= time(18, 0) and end_time <= time(23, 59, 59, 999999):
        return "晚上"
    return ""


def format_interpretation_date_ranges(time_ranges) -> str:
    pieces = []
    previous_year = None
    for item in time_ranges:
        start = item.scheduled_start
        end = item.scheduled_end
        year_prefix = f"{start.year}年" if start.year != previous_year else ""
        if start.date() == end.date():
            piece = f"{year_prefix}{start.month}月{start.day}日{_time_period_label(start, end)}"
        elif start.year == end.year and start.month == end.month:
            piece = f"{year_prefix}{start.month}月{start.day}-{end.day}日"
        elif start.year == end.year:
            piece = f"{year_prefix}{start.month}月{start.day}日-{end.month}月{end.day}日"
        else:
            piece = (
                f"{year_prefix}{start.month}月{start.day}日-"
                f"{end.year}年{end.month}月{end.day}日"
            )
        pieces.append(piece)
        previous_year = end.year
    return "；".join(pieces)


def build_interpretation_project_name(
    payload: InterpretationNamePreviewRequest,
    direction_labels: list[str],
) -> str:
    missing = []
    if not payload.time_ranges:
        missing.append("预定时间")
    if not payload.locations:
        missing.append("项目地点")
    if not direction_labels:
        missing.append("口译方向")
    if not payload.project_types:
        missing.append("项目类型")
    if missing:
        raise ValueError(f"请先填写：{'、'.join(missing)}")

    date_text = format_interpretation_date_ranges(payload.time_ranges)
    location_text = "、".join(payload.locations)
    direction_text = "；".join(direction_labels)
    type_text = "；".join(PROJECT_TYPE_LABELS[value] for value in payload.project_types)
    return f"{date_text}{location_text}{direction_text}{type_text}项目"


def preview_interpretation_project_name(
    db: Session, payload: InterpretationNamePreviewRequest
) -> str:
    ids = {
        language_id
        for item in payload.language_directions
        for language_id in (item.source_language_id, item.target_language_id)
    }
    languages = {
        item.id: item.label
        for item in db.query(InterpretationLanguage).filter(InterpretationLanguage.id.in_(ids)).all()
    } if ids else {}
    if len(languages) != len(ids):
        raise ValueError("所选口译语种不存在或已失效")
    labels = [
        f"{languages[item.source_language_id]} ↔ {languages[item.target_language_id]}"
        for item in payload.language_directions
    ]
    return build_interpretation_project_name(payload, labels)


def _project_options():
    return (
        selectinload(InterpretationProject.client),
        selectinload(InterpretationProject.sub_client),
        selectinload(InterpretationProject.time_ranges),
        selectinload(InterpretationProject.language_directions)
        .selectinload(InterpretationProjectLanguageDirection.source_language),
        selectinload(InterpretationProject.language_directions)
        .selectinload(InterpretationProjectLanguageDirection.target_language),
        selectinload(InterpretationProject.interpreter_assignments)
        .selectinload(InterpretationProjectInterpreter.translator),
        selectinload(InterpretationProject.workbench_responsibilities)
        .selectinload(workflow_models.ProjectWorkbenchResponsibility.assignee),
    )


def get_interpretation_project(db: Session, project_id: UUID) -> Optional[InterpretationProject]:
    return (
        db.query(InterpretationProject)
        .options(*_project_options())
        .filter(InterpretationProject.id == project_id)
        .first()
    )


def get_interpretation_projects(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
    project_status: Optional[str] = None,
    project_type: Optional[str] = None,
    scheduled_date_start=None,
    scheduled_date_end=None,
    translator_id: Optional[UUID] = None,
) -> list[InterpretationProject]:
    query = (
        db.query(InterpretationProject)
        .options(*_project_options())
        .outerjoin(Client, InterpretationProject.client_id == Client.id)
        .outerjoin(SubClient, InterpretationProject.sub_client_id == SubClient.id)
    )
    query = _apply_filters(
        query,
        keyword=keyword,
        project_status=project_status,
        project_type=project_type,
        scheduled_date_start=scheduled_date_start,
        scheduled_date_end=scheduled_date_end,
        translator_id=translator_id,
    )
    return (
        query.distinct()
        .order_by(InterpretationProject.created_at.desc(), InterpretationProject.id.desc())
        .offset(skip).limit(limit).all()
    )


def count_interpretation_projects(db: Session, **filters) -> int:
    query = (
        db.query(InterpretationProject.id)
        .outerjoin(Client, InterpretationProject.client_id == Client.id)
        .outerjoin(SubClient, InterpretationProject.sub_client_id == SubClient.id)
    )
    query = _apply_filters(query, **filters)
    return query.distinct().count()


def _apply_filters(
    query,
    *,
    keyword=None,
    project_status=None,
    project_type=None,
    scheduled_date_start=None,
    scheduled_date_end=None,
    translator_id=None,
):
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            InterpretationProject.order_no.ilike(pattern),
            InterpretationProject.project_name.ilike(pattern),
            InterpretationProject.task_description.ilike(pattern),
            InterpretationProject.customer_order_no.ilike(pattern),
            Client.client_name.ilike(pattern),
            Client.client_short_name.ilike(pattern),
            SubClient.client_name.ilike(pattern),
            SubClient.client_short_name.ilike(pattern),
        ))
    if project_status:
        query = query.filter(InterpretationProject.project_status == project_status)
    if project_type:
        query = query.filter(InterpretationProject.project_types.contains([project_type]))
    if scheduled_date_start or scheduled_date_end:
        query = query.join(
            InterpretationProjectTimeRange,
            InterpretationProjectTimeRange.project_id == InterpretationProject.id,
        )
        if scheduled_date_start:
            query = query.filter(
                InterpretationProjectTimeRange.scheduled_end >= datetime.combine(scheduled_date_start, time.min)
            )
        if scheduled_date_end:
            query = query.filter(
                InterpretationProjectTimeRange.scheduled_start <= datetime.combine(scheduled_date_end, time.max)
            )
    if translator_id:
        query = query.join(
            InterpretationProjectInterpreter,
            InterpretationProjectInterpreter.project_id == InterpretationProject.id,
        ).filter(InterpretationProjectInterpreter.translator_id == translator_id)
    return query


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
    )
    if client_id:
        data["client_id"] = client_id
    if sub_client_id:
        data["sub_client_id"] = sub_client_id


WRITE_ONLY_CLIENT_FIELDS = {"client_name", "client_short_name", "client_code"}
NESTED_FIELDS = {"time_ranges", "language_directions", "interpreter_assignments", "role_assignments"}


def _sync_nested(db: Session, project: InterpretationProject, payload) -> None:
    existing_translator_ids = {item.translator_id for item in project.interpreter_assignments}
    language_ids = {
        value
        for item in payload.language_directions
        for value in (item.source_language_id, item.target_language_id)
    }
    if language_ids:
        found = {
            value for (value,) in db.query(InterpretationLanguage.id)
            .filter(InterpretationLanguage.id.in_(language_ids)).all()
        }
        if found != language_ids:
            raise ValueError("所选口译语种不存在或已失效")
    translator_ids = {item.translator_id for item in payload.interpreter_assignments}
    if translator_ids:
        found = {
            value for (value,) in db.query(Translator.id)
            .filter(Translator.id.in_(translator_ids)).all()
        }
        if found != translator_ids:
            raise ValueError("所选译员不存在或已失效")
        from resource_service import translator_has_capability
        ineligible = {
            translator_id for translator_id in translator_ids - existing_translator_ids
            if not translator_has_capability(db, translator_id, "interpretation")
        }
        if ineligible:
            raise ValueError("所选人员已停用或不具备有效的口译能力")

    # 先删除并落库旧关系，再按相同 sequence_no 重建，避免唯一约束下
    # SQLAlchemy 先 INSERT 后 DELETE 导致编辑已有项目时冲突。
    project.time_ranges.clear()
    project.language_directions.clear()
    project.interpreter_assignments.clear()
    db.flush()

    project.time_ranges = [
        InterpretationProjectTimeRange(sequence_no=index, **item.model_dump())
        for index, item in enumerate(payload.time_ranges, start=1)
    ]
    project.language_directions = [
        InterpretationProjectLanguageDirection(sequence_no=index, **item.model_dump())
        for index, item in enumerate(payload.language_directions, start=1)
    ]
    project.interpreter_assignments = [
        InterpretationProjectInterpreter(sequence_no=index, **item.model_dump())
        for index, item in enumerate(payload.interpreter_assignments, start=1)
    ]


def create_interpretation_project(
    db: Session, payload: InterpretationProjectCreate, created_by: Optional[UUID]
) -> InterpretationProject:
    data = payload.model_dump(exclude=NESTED_FIELDS)
    _resolve_client(db, data)
    for key in WRITE_ONLY_CLIENT_FIELDS:
        data.pop(key, None)
    project = InterpretationProject(
        order_no=generate_interpretation_order_no(db),
        created_by=created_by,
        **data,
    )
    db.add(project)
    db.flush()
    from project_workbench_service import assignment_map_from_payload, ensure_project_responsibilities, validate_assignment_map
    assignments = assignment_map_from_payload(payload.role_assignments)
    validate_assignment_map(db, assignments)
    ensure_project_responsibilities(db, 'interpretation', project.id, assignments)
    _sync_nested(db, project, payload)
    project.updated_at = datetime.now()
    db.commit()
    return get_interpretation_project(db, project.id)


def update_interpretation_project(
    db: Session, project_id: UUID, payload: InterpretationProjectUpdate
) -> Optional[InterpretationProject]:
    project = get_interpretation_project(db, project_id)
    if not project:
        return None
    assert_fresh(project, payload.expected_updated_at)
    data = payload.model_dump(exclude=NESTED_FIELDS | {VERSION_FIELD})
    _resolve_client(db, data)
    for key in WRITE_ONLY_CLIENT_FIELDS:
        data.pop(key, None)
    for key, value in data.items():
        setattr(project, key, value)
    from project_workbench_service import assignment_map_from_payload, ensure_active_project_responsibilities, validate_assignment_map
    assignments = assignment_map_from_payload(payload.role_assignments) if 'role_assignments' in payload.model_fields_set else None
    validate_assignment_map(db, assignments)
    ensure_active_project_responsibilities(db, 'interpretation', project.id, project.project_status, assignments)
    _sync_nested(db, project, payload)
    project.updated_at = datetime.now()
    db.commit()
    return get_interpretation_project(db, project.id)


def update_interpretation_project_status(
    db: Session, project_id: UUID, project_status: str
) -> Optional[InterpretationProject]:
    project = get_interpretation_project(db, project_id)
    if not project:
        return None
    if project.project_status == project_status:
        return project
    project.project_status = project_status
    project.updated_at = datetime.now()
    from project_workbench_service import ensure_active_project_responsibilities
    ensure_active_project_responsibilities(db, 'interpretation', project.id, project_status)
    db.commit()
    return get_interpretation_project(db, project.id)


def delete_interpretation_project(db: Session, project_id: UUID) -> bool:
    project = db.query(InterpretationProject).filter(InterpretationProject.id == project_id).first()
    if not project:
        return False
    from project_workbench_service import cancel_pending_project_handovers
    cancel_pending_project_handovers(db, 'interpretation', project_id)
    db.delete(project)
    db.commit()
    return True


def ensure_interpretation_project_for_consultation(
    db: Session,
    consultation: Consultation,
    created_by: Optional[UUID],
    *,
    order_no: Optional[str] = None,
    project_name: Optional[str] = None,
    customer_order_no: Optional[str] = None,
    email_subject_preview: Optional[str] = None,
) -> tuple[InterpretationProject, bool]:
    existing = db.query(InterpretationProject).filter(
        InterpretationProject.consultation_id == consultation.id
    ).first()
    if existing:
        if project_name is not None:
            existing.project_name = project_name
        if customer_order_no is not None:
            existing.customer_order_no = customer_order_no
        if email_subject_preview is not None:
            existing.email_subject_preview = email_subject_preview
        db.flush()
        return existing, False
    translation_project = db.query(TranslationProject.id).filter(
        TranslationProject.consultation_id == consultation.id
    ).first()
    if translation_project:
        raise ValueError("该咨询已生成笔译项目，不能再生成口译项目")
    project = InterpretationProject(
        order_no=order_no or generate_interpretation_order_no(db),
        project_name=project_name,
        consultation_id=consultation.id,
        client_id=consultation.client_id,
        project_status="initial_follow_up",
        customer_consultation_time=consultation.consultation_time,
        customer_confirmation_time=datetime.now(),
        customer_order_no=customer_order_no,
        email_subject_preview=email_subject_preview,
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    return project, True


def validate_consultation_project_type_change(
    db: Session, consultation_id: UUID, target_type: Optional[str]
) -> None:
    has_interpretation = db.query(InterpretationProject.id).filter(
        InterpretationProject.consultation_id == consultation_id
    ).first()
    has_translation = db.query(TranslationProject.id).filter(
        TranslationProject.consultation_id == consultation_id
    ).first()
    if has_interpretation and not is_interpretation_type(target_type):
        raise ValueError("该咨询已生成口译项目，不能修改为其他咨询类型")
    if has_translation and is_interpretation_type(target_type):
        raise ValueError("该咨询已生成笔译项目，不能修改为口译项目")
