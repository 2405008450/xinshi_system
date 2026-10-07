"""标注项目查询、写入、咨询联动与历史迁移服务。"""

from __future__ import annotations

import re
import hashlib
import json
from datetime import date, datetime, time
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Date as SqlDate, DateTime as SqlDateTime, Numeric, String, cast, exists as db_exists, func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload
from utils import normalize_email_subject_order_no
from project_audit_service import record_project_operation
from annotation_manager_change_service import record_annotation_manager_change
from annotation_custom_field_image_service import delete_custom_field_image_files

from concurrency import VERSION_FIELD, assert_fresh

import workflow_models  # noqa: F401  注册笔译项目既有关系
import recruitment_models  # noqa: F401  注册统一工作台招聘项目关系
import annotation_ops_models  # noqa: F401  注册标注运营关系
from annotation_ops_models import (
    AnnotationAccountAssignment,
    AnnotationCustomFieldImage,
    AnnotationProjectStatusHistory,
)
from annotation_models import (
    AnnotationProject,
    AnnotationProjectAssignee,
    AnnotationProjectLanguageItem,
    AnnotationProjectPriceItem,
)
from annotation_schemas import (
    ANNOTATION_PROJECT_PRIORITY_LABELS,
    ANNOTATION_PROJECT_STATUS_LABELS,
    ANNOTATION_PROJECT_TYPE_LABELS,
    AnnotationNamePreviewRequest,
    AnnotationProjectCreate,
    AnnotationProjectUpdate,
    normalize_annotation_order_no,
)
from interpretation_models import InterpretationLanguage, InterpretationProject
from models import (
    AppUser, Client, Consultation, SubClient, TranslationProject,
    TranslationSubOrder,
)
from resource_request_models import ResourceRequest
from project_order_no_models import ProjectOrderNoReservation
from field_filtering import apply_scalar_filter, apply_scalar_specs


ANNOTATION_TYPE_VALUES = {"标注项目", "annotation"}
TRANSLATION_TYPE_VALUES = {
    "笔译项目", "translation", "笔译",
    "配音项目", "dubbing",
    "字幕项目", "subtitle",
    "公证项目", "notarization",
    "认证项目", "certification",
    "其他项目", "equipment_rental", "other", "其他",
}


class AnnotationProjectDeleteConflict(ValueError):
    """标注项目仍有必须由用户先处理的业务引用。"""


class AnnotationOrderNoConflict(ValueError):
    """标注订单号已经被当前或历史项目占用。"""


def _project_manager_ids(responsibilities) -> list[UUID]:
    """按责任表顺序返回项目经理，过滤角色池占位行并去重。"""
    return list(dict.fromkeys(
        item.assignee_id
        for item in (responsibilities or [])
        if item.role_code == "project_manager" and item.assignee_id is not None
    ))


def _record_project_manager_changes(
    db: Session, *, project, previous_ids: list[UUID], current_ids: list[UUID],
    change_mode: str, actor_user_id: Optional[UUID], reason: str,
) -> None:
    """多人负责人按新增/移除分别留痕，避免把无关的两个人记录成一次替换。"""
    previous_set = set(previous_ids)
    current_set = set(current_ids)
    for manager_id in previous_ids:
        if manager_id not in current_set:
            record_annotation_manager_change(
                db, project=project, manager_role="project_manager",
                previous_manager_id=manager_id, new_manager_id=None,
                change_mode=change_mode, actor_user_id=actor_user_id, reason=reason,
            )
    for manager_id in current_ids:
        if manager_id not in previous_set:
            record_annotation_manager_change(
                db, project=project, manager_role="project_manager",
                previous_manager_id=None, new_manager_id=manager_id,
                change_mode=change_mode, actor_user_id=actor_user_id, reason=reason,
            )


def _lock_annotation_order_numbers(db: Session) -> None:
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": "project-order:annotation"},
        )


def reserve_annotation_order_no(
    db: Session,
    *,
    project_id: UUID,
    order_no: str,
    assignment_source: str,
    assigned_by: Optional[UUID],
) -> ProjectOrderNoReservation:
    """永久占用订单号；同一号码即使历史上使用过也不能再次分配。"""
    normalized = normalize_annotation_order_no(order_no)
    _lock_annotation_order_numbers(db)
    existing = db.query(ProjectOrderNoReservation.id).filter(
        ProjectOrderNoReservation.project_type == "annotation",
        ProjectOrderNoReservation.order_no_key == normalized,
    ).first()
    if existing:
        raise AnnotationOrderNoConflict(f"订单号 {normalized} 已被当前或历史标注项目使用")
    reservation = ProjectOrderNoReservation(
        project_type="annotation",
        project_id=project_id,
        order_no=normalized,
        order_no_key=normalized,
        assignment_source=assignment_source,
        assigned_by=assigned_by,
    )
    db.add(reservation)
    return reservation


def _active_account_assignment_label(assignment: AnnotationAccountAssignment) -> str:
    account = getattr(assignment, "account", None)
    platform = getattr(account, "platform", None)
    platform_name = getattr(platform, "platform_name", None)
    account_name = getattr(account, "nickname", None)
    values = [value for value in (platform_name, account_name) if value]
    return " / ".join(values) or str(assignment.id)


def is_annotation_type(value: Optional[str]) -> bool:
    return (value or "").strip() in ANNOTATION_TYPE_VALUES


def is_translation_type(value: Optional[str]) -> bool:
    return (value or "").strip() in TRANSLATION_TYPE_VALUES


def generate_annotation_order_no(
    db: Session, current_time: Optional[datetime] = None
) -> str:
    now = current_time or datetime.now(ZoneInfo("Asia/Hong_Kong"))
    date_text = now.strftime("%y%m%d")
    prefix = f"AP-{date_text}-"
    _lock_annotation_order_numbers(db)
    reserved_rows = (
        db.query(ProjectOrderNoReservation.order_no)
        .filter(
            ProjectOrderNoReservation.project_type == "annotation",
            ProjectOrderNoReservation.order_no.like(f"{prefix}%"),
        )
        .all()
    )
    sequence_pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    used_sequences = []
    for row in reserved_rows:
        order_no = row[0] if isinstance(row, (tuple, list)) else getattr(row, "order_no", row)
        match = sequence_pattern.fullmatch(str(order_no or ""))
        if match:
            used_sequences.append(int(match.group(1)))
    sequence = max(used_sequences, default=0) + 1
    return f"{prefix}{sequence:03d}"


def _project_options():
    return (
        joinedload(AnnotationProject.parent_project),
        joinedload(AnnotationProject.consultation),
        joinedload(AnnotationProject.client),
        joinedload(AnnotationProject.sub_client),
        joinedload(AnnotationProject.client_manager),
        joinedload(AnnotationProject.creator),
        selectinload(AnnotationProject.assignees).joinedload(AnnotationProjectAssignee.person),
        selectinload(AnnotationProject.language_items)
        .joinedload(AnnotationProjectLanguageItem.source_language),
        selectinload(AnnotationProject.language_items)
        .joinedload(AnnotationProjectLanguageItem.target_language),
        selectinload(AnnotationProject.price_items)
        .joinedload(AnnotationProjectPriceItem.source_language),
        selectinload(AnnotationProject.price_items)
        .joinedload(AnnotationProjectPriceItem.target_language),
        selectinload(AnnotationProject.workbench_responsibilities)
        .joinedload(workflow_models.ProjectWorkbenchResponsibility.assignee),
        joinedload(AnnotationProject.arrangement_scope),
    )


def get_annotation_project(
    db: Session, project_id: UUID
) -> Optional[AnnotationProject]:
    project = (
        db.query(AnnotationProject)
        .options(*_project_options())
        .filter(AnnotationProject.id == project_id)
        .first()
    )
    if project:
        project.auto_created_child_count = 0
        _attach_child_statistics(db, [project])
        if not project.parent_project_id:
            from annotation_direction_service import direction_state
            project.direction_summary = direction_state(db, project)[1]
    return project


def _attach_child_statistics(db: Session, projects) -> None:
    """一次聚合当前页的子订单状态，避免逐条加载全部子订单。"""
    ids = [project.id for project in projects]
    if not ids:
        return
    counts = {}
    for parent_id, status, count in db.query(
        AnnotationProject.parent_project_id, AnnotationProject.project_status,
        func.count(AnnotationProject.id),
    ).filter(AnnotationProject.parent_project_id.in_(ids)).group_by(
        AnnotationProject.parent_project_id, AnnotationProject.project_status,
    ).all():
        counts.setdefault(parent_id, {})[status] = count
    for project in projects:
        project.child_status_counts = counts.get(project.id, {})
        project.child_count = sum(project.child_status_counts.values())


def _latest_progress_expressions():
    """返回项目最新进度节点日期和最后填报时间表达式。"""
    ordering = (
        AnnotationProjectStatusHistory.effective_on.desc(),
        AnnotationProjectStatusHistory.changed_at.desc(),
        AnnotationProjectStatusHistory.id.desc(),
    )
    latest_effective_on = (
        select(AnnotationProjectStatusHistory.effective_on)
        .where(AnnotationProjectStatusHistory.project_id == AnnotationProject.id)
        .order_by(*ordering)
        .limit(1)
        .correlate(AnnotationProject)
        .scalar_subquery()
    )
    latest_changed_at = (
        select(func.max(AnnotationProjectStatusHistory.changed_at))
        .where(AnnotationProjectStatusHistory.project_id == AnnotationProject.id)
        .correlate(AnnotationProject)
        .scalar_subquery()
    )
    return latest_effective_on, latest_changed_at


def _annotation_project_ordering(sort, latest_effective_on, latest_changed_at):
    if sort == "latest_progress_desc":
        return (
            latest_changed_at.desc().nullslast(),
            latest_effective_on.desc().nullslast(),
            AnnotationProject.order_no.desc(),
            AnnotationProject.id.desc(),
        )
    return (
        AnnotationProject.order_no.desc(),
        AnnotationProject.id.desc(),
    )


def _keyword_enum_values(keyword: str, labels: dict[str, str]) -> tuple[str, ...]:
    """按内部值或界面中文名称匹配枚举，供基础字段关键词检索使用。"""
    normalized = keyword.strip().casefold()
    if not normalized:
        return ()
    return tuple(
        value
        for value, label in labels.items()
        if normalized in value.casefold() or normalized in label.casefold()
    )


def _apply_filters(
    query,
    *,
    keyword=None,
    project_status=None,
    project_type=None,
    language_id=None,
    client_manager_id=None,
    dispatched_date_start=None,
    dispatched_date_end=None,
    submitted_date_start=None,
    submitted_date_end=None,
    client_id=None,
    sub_client_id=None,
    assignee_person_id=None,
    created_date_start=None,
    created_date_end=None,
    consultation_date_start=None,
    consultation_date_end=None,
    confirmation_date_start=None,
    confirmation_date_end=None,
    field_filters=None,
    order_scope="all",
    parent_project_id=None,
):
    if order_scope not in {"all", "parent", "child"}:
        raise ValueError("无效的订单查询范围")
    if order_scope == "parent":
        query = query.filter(AnnotationProject.parent_project_id.is_(None))
    elif order_scope == "child":
        query = query.filter(AnnotationProject.parent_project_id.is_not(None))
    if parent_project_id is not None:
        query = query.filter(AnnotationProject.parent_project_id == parent_project_id)
    if keyword and keyword.strip():
        normalized_keyword = keyword.strip()
        pattern = f"%{normalized_keyword}%"
        project_type_values = _keyword_enum_values(
            normalized_keyword, ANNOTATION_PROJECT_TYPE_LABELS,
        )
        status_values = _keyword_enum_values(
            normalized_keyword, ANNOTATION_PROJECT_STATUS_LABELS,
        )
        priority_values = _keyword_enum_values(
            normalized_keyword, ANNOTATION_PROJECT_PRIORITY_LABELS,
        )
        keyword_conditions = [
            AnnotationProject.order_no.ilike(pattern),
            AnnotationProject.project_name.ilike(pattern),
            AnnotationProject.customer_order_no.ilike(pattern),
            AnnotationProject.contact_name.ilike(pattern),
            AnnotationProject.language_region.ilike(pattern),
            AnnotationProject.project_status.ilike(pattern),
            AnnotationProject.priority.ilike(pattern),
            Client.client_code.ilike(pattern),
            Client.client_name.ilike(pattern),
            Client.client_short_name.ilike(pattern),
            SubClient.sub_client_code.ilike(pattern),
            SubClient.client_name.ilike(pattern),
            SubClient.client_short_name.ilike(pattern),
        ]
        keyword_conditions.extend(
            AnnotationProject.project_types.contains([value])
            for value in project_type_values
        )
        if status_values:
            keyword_conditions.append(AnnotationProject.project_status.in_(status_values))
        if priority_values:
            keyword_conditions.append(AnnotationProject.priority.in_(priority_values))
        query = query.filter(or_(*keyword_conditions))
    if project_status:
        query = query.filter(AnnotationProject.project_status == project_status)
    if project_type:
        query = query.filter(AnnotationProject.project_types.contains([project_type]))
    if language_id:
        query = query.join(
            AnnotationProjectLanguageItem,
            AnnotationProjectLanguageItem.project_id == AnnotationProject.id,
        ).filter(or_(
            AnnotationProjectLanguageItem.source_language_id == language_id,
            AnnotationProjectLanguageItem.target_language_id == language_id,
        ))
    if client_manager_id:
        query = query.filter(AnnotationProject.client_manager_id == client_manager_id)
    if client_id:
        query = query.filter(AnnotationProject.client_id == client_id)
    if sub_client_id:
        query = query.filter(AnnotationProject.sub_client_id == sub_client_id)
    if assignee_person_id:
        query = query.join(
            AnnotationProjectAssignee,
            AnnotationProjectAssignee.project_id == AnnotationProject.id,
        ).filter(AnnotationProjectAssignee.person_id == assignee_person_id)
    for field, start_value, end_value in (
        (AnnotationProject.task_dispatched_at, dispatched_date_start, dispatched_date_end),
        (AnnotationProject.task_submitted_at, submitted_date_start, submitted_date_end),
        (AnnotationProject.created_at, created_date_start, created_date_end),
        (AnnotationProject.customer_consultation_time, consultation_date_start, consultation_date_end),
        (AnnotationProject.customer_confirmation_time, confirmation_date_start, confirmation_date_end),
    ):
        if start_value:
            query = query.filter(field >= datetime.combine(start_value, time.min))
        if end_value:
            query = query.filter(field <= datetime.combine(end_value, time.max))
    field_filters = field_filters or {}
    latest_progress_effective_on, _ = _latest_progress_expressions()
    query = apply_scalar_specs(query, field_filters, {
        "order_no": (AnnotationProject.order_no, "string"),
        "project_name": (AnnotationProject.project_name, "string"),
        "task_description": (AnnotationProject.task_description, "string"),
        "project_status": (AnnotationProject.project_status, "string"),
        "priority": (AnnotationProject.priority, "string"),
        "contact_name": (AnnotationProject.contact_name, "string"),
        "customer_order_no": (AnnotationProject.customer_order_no, "string"),
        "language_region": (AnnotationProject.language_region, "string"),
        "potential_demand": (AnnotationProject.potential_demand, "string"),
        "client_manager_id": (AnnotationProject.client_manager_id, "uuid"),
        "task_dispatched_at": (AnnotationProject.task_dispatched_at, "datetime"),
        "task_submitted_at": (AnnotationProject.task_submitted_at, "datetime"),
        "customer_consultation_time": (AnnotationProject.customer_consultation_time, "datetime"),
        "customer_confirmation_time": (AnnotationProject.customer_confirmation_time, "datetime"),
        "created_at": (AnnotationProject.created_at, "datetime"),
        "updated_at": (AnnotationProject.updated_at, "datetime"),
    })
    for field, descriptor in field_filters.items():
        if field == "project_types":
            values = descriptor.get("value") or []
            query = query.filter(or_(*(AnnotationProject.project_types.contains([value]) for value in values)))
        elif field in {"client_short_name", "client_code", "client_full_name"}:
            parent_column, sub_column = {
                "client_short_name": (Client.client_short_name, SubClient.client_short_name),
                "client_code": (Client.client_code, SubClient.sub_client_code),
                "client_full_name": (Client.client_name, SubClient.client_name),
            }[field]
            pattern = f"%{str(descriptor.get('value') or '').strip()}%"
            query = query.filter(or_(parent_column.ilike(pattern), sub_column.ilike(pattern)))
        elif field == "language_id":
            values = [UUID(str(value)) for value in descriptor.get("value") or []]
            query = query.join(AnnotationProjectLanguageItem, AnnotationProjectLanguageItem.project_id == AnnotationProject.id).filter(or_(AnnotationProjectLanguageItem.source_language_id.in_(values), AnnotationProjectLanguageItem.target_language_id.in_(values)))
        elif field == "assignee_person_id":
            values = [UUID(str(value)) for value in descriptor.get("value") or []]
            query = query.join(AnnotationProjectAssignee, AnnotationProjectAssignee.project_id == AnnotationProject.id).filter(AnnotationProjectAssignee.person_id.in_(values))
        elif field == "project_manager_id":
            values = [UUID(str(value)) for value in descriptor.get("value") or []]
            responsibility = workflow_models.ProjectWorkbenchResponsibility
            query = query.filter(db_exists().where(
                responsibility.annotation_project_id == AnnotationProject.id,
                responsibility.role_code == "project_manager",
                responsibility.assignee_id.in_(values),
            ))
        elif field == "has_customer_price":
            condition = AnnotationProject.price_items.any()
            query = query.filter(condition if descriptor.get("value") else ~condition)
        elif field == "customer_price":
            conditions = [AnnotationProjectPriceItem.project_id == AnnotationProject.id]
            if descriptor.get("min") not in (None, ""):
                conditions.append(AnnotationProjectPriceItem.amount >= descriptor["min"])
            if descriptor.get("max") not in (None, ""):
                conditions.append(AnnotationProjectPriceItem.amount <= descriptor["max"])
            query = query.filter(db_exists().where(*conditions))
        elif field == "latest_progress_effective_on":
            query = apply_scalar_filter(
                query,
                latest_progress_effective_on,
                descriptor,
                value_type="datetime",
            )
        elif field.startswith("custom:"):
            custom_id = field.split(":", 1)[1]
            expression = AnnotationProject.custom_values[custom_id].astext
            data_type = descriptor.get("data_type")
            if descriptor.get("op") == "contains":
                query = query.filter(cast(expression, String).ilike(f"%{str(descriptor.get('value') or '').strip()}%"))
            elif descriptor.get("op") == "in":
                values = descriptor.get("value") or []
                query = query.filter(or_(*(cast(expression, String).ilike(f"%{value}%") for value in values)))
            elif descriptor.get("op") == "eq" and data_type == "boolean":
                query = query.filter(expression == ("true" if descriptor.get("value") else "false"))
            elif descriptor.get("op") == "between":
                value_type = "number" if data_type == "number" else ("date" if data_type == "date" else ("datetime" if data_type == "datetime" else "string"))
                typed_expression = cast(expression, Numeric if data_type == "number" else (SqlDate if data_type == "date" else SqlDateTime))
                query = apply_scalar_filter(query, typed_expression, descriptor, value_type=value_type)
    return query


def get_annotation_projects(
    db: Session, *, skip: int = 0, limit: int = 100,
    sort: str = "order_no_desc", **filters
) -> list[AnnotationProject]:
    query = (
        db.query(AnnotationProject)
        .options(*_project_options())
        .outerjoin(Client, AnnotationProject.client_id == Client.id)
        .outerjoin(SubClient, AnnotationProject.sub_client_id == SubClient.id)
    )
    query = _apply_filters(query, **filters)
    latest_progress_effective_on, latest_progress_changed_at = _latest_progress_expressions()
    ordering = _annotation_project_ordering(
        sort, latest_progress_effective_on, latest_progress_changed_at,
    )
    rows = (
        query.add_columns(
            func.count(AnnotationProject.id).over().label("_page_total"),
            latest_progress_effective_on.label("_latest_progress_effective_on"),
            latest_progress_changed_at.label("_latest_progress_changed_at"),
        ).distinct()
        .order_by(*ordering)
        .offset(skip).limit(limit).all()
    )
    projects = []
    for project, page_total, latest_effective_on, latest_changed_at in rows:
        project.__dict__["_page_total"] = int(page_total or 0)
        project.__dict__["latest_progress_effective_on"] = latest_effective_on
        project.__dict__["latest_progress_changed_at"] = latest_changed_at
        projects.append(project)
    _attach_child_statistics(db, projects)
    return projects


def count_annotation_projects(db: Session, *, sort: str = "order_no_desc", **filters) -> int:
    query = (
        db.query(AnnotationProject.id)
        .outerjoin(Client, AnnotationProject.client_id == Client.id)
        .outerjoin(SubClient, AnnotationProject.sub_client_id == SubClient.id)
    )
    return _apply_filters(query, **filters).distinct().count()


WRITE_ONLY_CLIENT_FIELDS = {"client_name", "client_short_name", "client_code", "manager_contact"}
NESTED_FIELDS = {"language_items", "price_items", "assignees", "role_assignments", "material_changes"}

# 母订单仅提供创建时的快照，子订单保存后独立维护。
CHILD_CREATE_CONTROL_FIELDS = {"copy_source_language_item_id", "expected_parent_updated_at", "copy_parent_materials"}

def _lock_parent(db, parent_id):
    parent = db.query(AnnotationProject).filter(AnnotationProject.id == parent_id).with_for_update().populate_existing().first()
    if not parent:
        raise ValueError("母订单不存在")
    if parent.parent_project_id:
        raise ValueError("子订单不能继续创建子订单")
    return parent


def _child_create_payload(parent, payload):
    from copy import deepcopy
    from annotation_schemas import AnnotationProjectWrite
    from annotation_child_copy_service import source_direction, copy_prices
    assert_fresh(parent, payload.expected_parent_updated_at)
    if len(payload.language_items) != 1:
        raise ValueError("子订单必须且只能绑定一个语种或语言方向")
    source = source_direction(parent, payload)
    values = payload.model_dump()
    scalar_fields = set(AnnotationProjectWrite.model_fields) - NESTED_FIELDS - WRITE_ONLY_CLIENT_FIELDS
    for field in scalar_fields - payload.model_fields_set:
        values[field] = deepcopy(getattr(parent, field))
    if 'role_assignments' not in payload.model_fields_set:
        values['role_assignments'] = parent.role_assignments
    if 'price_items' not in payload.model_fields_set:
        values['price_items'] = copy_prices(parent, source, payload.language_items[0])
    for field in WRITE_ONLY_CLIENT_FIELDS:
        if field not in payload.model_fields_set:
            values[field] = None
    return AnnotationProjectCreate.model_validate(values)


def _next_child_number(db, parent):
    parent_numbers = {parent.order_no, *(number for (number,) in db.query(ProjectOrderNoReservation.order_no).filter(
        ProjectOrderNoReservation.project_type == "annotation",
        ProjectOrderNoReservation.project_id == parent.id,
    ).all())}
    patterns = [re.compile(rf"^{re.escape(number)}-S(\d+)$") for number in parent_numbers]
    reserved = db.query(ProjectOrderNoReservation.order_no).filter(
        ProjectOrderNoReservation.project_type == "annotation",
        or_(*(ProjectOrderNoReservation.order_no.like(f"{number}-S%") for number in parent_numbers)),
    ).all()
    sequences = [int(match.group(1)) for (number,) in reserved for pattern in patterns if (match := pattern.fullmatch(number))]
    sequence = max(sequences, default=0) + 1
    number = f"{parent.order_no}-S{sequence:03d}"
    if len(number) > 50:
        raise ValueError("母订单号过长，无法生成子订单号")
    return number, sequence



def _sync_child_shared_fields(db, project):
    """兼容既有交接入口；客户信息现在是创建时快照，不再同步覆盖子订单。"""
    return None


def create_annotation_children(db, parent_id, items, actor_id, idempotency_key):
    """整批创建只提交一次；每行幂等键绑定母订单、批次及原始请求。"""
    _lock_annotation_order_numbers(db)
    parent = _lock_parent(db, parent_id)
    # 生效时间未显式传入时使用模型默认值，不参与重试指纹。
    fingerprint_items = [item.model_dump(mode="json", exclude_unset=True) for item in items]
    signature = json.dumps(fingerprint_items, sort_keys=True, ensure_ascii=False)
    batch_key = hashlib.sha256(f"{parent_id}:{idempotency_key}".encode()).hexdigest()
    digest = hashlib.sha256(signature.encode()).hexdigest()[:16]
    prefix = f"child:{batch_key}:"
    existing = db.query(AnnotationProject).filter(AnnotationProject.idempotency_key.like(f"{prefix}%")).order_by(AnnotationProject.child_sequence_no).all()
    if existing:
        if len(existing) != len(items) or any(f":{digest}:" not in row.idempotency_key for row in existing):
            raise ValueError("同一幂等键对应的创建内容已改变，请重新发起创建")
        return [get_annotation_project(db, row.id) for row in existing]
    projects = []
    for index, item in enumerate(items):
        if item.parent_project_id and item.parent_project_id != parent_id:
            raise ValueError("子订单所属母订单与请求地址不一致")
        payload = AnnotationProjectCreate.model_validate({**item.model_dump(exclude_unset=True), "parent_project_id": parent_id})
        projects.append(create_annotation_project(db, payload, actor_id, idempotency_key=f"{prefix}{digest}:{index}", operation_source="child_order_create", commit=False))
    db.commit()
    return [get_annotation_project(db, row.id) for row in projects]


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


def _validate_write_references(db: Session, payload) -> None:
    language_ids = {
        value
        for item in payload.language_items
        for value in (item.source_language_id, item.target_language_id)
        if value is not None
    }
    if language_ids:
        found = {
            value for (value,) in db.query(InterpretationLanguage.id)
            .filter(InterpretationLanguage.id.in_(language_ids)).all()
        }
        if found != language_ids:
            raise ValueError("所选语种不存在或已失效")
    if payload.client_manager_id:
        manager = db.query(AppUser).filter(
            AppUser.id == payload.client_manager_id,
            AppUser.is_active.is_(True),
        ).first()
        if not manager:
            raise ValueError("所选客户经理不存在或已停用")


def _validate_annotation_assignees(db: Session, payload) -> None:
    if not payload.assignees:
        return
    from resource_models import ResourceCapability, ResourcePerson

    person_ids = {item.person_id for item in payload.assignees}
    eligible_ids = {
        value for (value,) in db.query(ResourcePerson.id)
        .join(ResourceCapability, ResourceCapability.person_id == ResourcePerson.id)
        .filter(
            ResourcePerson.id.in_(person_ids),
            ResourcePerson.status != "inactive",
            ResourceCapability.capability_type == "annotation",
            ResourceCapability.status == "active",
        ).all()
    }
    if eligible_ids != person_ids:
        raise ValueError("所选人员不存在、已停用或不具备有效的标注能力")


def _sync_nested(db: Session, project: AnnotationProject, payload) -> None:
    _validate_write_references(db, payload)
    _validate_annotation_assignees(db, payload)

    collections = (
        (project.language_items, payload.language_items, AnnotationProjectLanguageItem, "语种"),
        (project.price_items, payload.price_items, AnnotationProjectPriceItem, "价格"),
        (project.assignees, payload.assignees, AnnotationProjectAssignee, "人员安排"),
    )

    # 先把现有排序号移到远离正常区间的正数，避免交换顺序时触发项目内 sequence_no 唯一约束。
    for current_rows, _items, _model, _label in collections:
        for index, row in enumerate(current_rows, start=1):
            row.sequence_no = 1_000_000 + index
    db.flush()

    for current_rows, items, model, label in collections:
        current_by_id = {row.id: row for row in current_rows}
        requested_ids = {item.id for item in items if item.id is not None}
        unknown_ids = requested_ids - set(current_by_id)
        if unknown_ids:
            raise ValueError(f"{label}明细包含不属于当前项目的记录")

        for row in list(current_rows):
            if row.id not in requested_ids:
                current_rows.remove(row)

        for index, item in enumerate(items, start=1):
            values = item.model_dump(exclude={"id", "rate"})
            row = current_by_id.get(item.id) if item.id else None
            if model is AnnotationProjectAssignee:
                from annotation_custom_field_service import validate_custom_values
                values["custom_values"] = validate_custom_values(
                    db, "assignment", project.id, values.get("custom_values") or {},
                    row.custom_values if row else None,
                )
            if row is None:
                row = model()
                current_rows.append(row)
            for key, value in values.items():
                setattr(row, key, value)
            row.sequence_no = index
            if model is AnnotationProjectAssignee and 'rate' in item.model_fields_set:
                from annotation_ops_models import AnnotationAssigneeRate
                if item.rate is None:
                    row.rate = None
                else:
                    if row.rate is None:
                        row.rate = AnnotationAssigneeRate()
                    for key, value in item.rate.model_dump().items():
                        setattr(row.rate, key, value)
                    row.rate.updated_at = datetime.now()
            if hasattr(row, "updated_at"):
                row.updated_at = datetime.now()

    language_item_ids = {item.id for item in project.language_items if item.id is not None}
    for assignee in project.assignees:
        if assignee.language_item_id and assignee.language_item_id not in language_item_ids:
            raise ValueError("人员安排引用了不属于当前项目的语种")


def create_annotation_project(
    db: Session, payload: AnnotationProjectCreate, created_by: Optional[UUID],
    idempotency_key: Optional[str] = None,
    operation_source: str = "project_form",
    commit: bool = True,
) -> AnnotationProject:
    parent = None
    child_sequence_no = None
    copy_people_from_parent = "assignees" not in payload.model_fields_set
    if payload.parent_project_id:
        _lock_annotation_order_numbers(db)
        parent = _lock_parent(db, payload.parent_project_id)
        payload = _child_create_payload(parent, payload)
        order_no, child_sequence_no = _next_child_number(db, parent)
    else:
        order_no = generate_annotation_order_no(db)
    data = payload.model_dump(exclude=NESTED_FIELDS | CHILD_CREATE_CONTROL_FIELDS)
    from annotation_custom_field_service import validate_custom_values
    data["custom_values"] = validate_custom_values(
        db, "project", None, data.get("custom_values") or {}, parent.custom_values if parent else None,
    )
    _resolve_client(db, data)
    for key in WRITE_ONLY_CLIENT_FIELDS:
        data.pop(key, None)
    data["email_subject_preview"] = normalize_email_subject_order_no(
        data.get("email_subject_preview"), order_no
    )
    project = AnnotationProject(
        order_no=order_no, created_by=created_by,
        child_sequence_no=child_sequence_no,
        idempotency_key=idempotency_key, **data
    )
    db.add(project)
    db.flush()
    reserve_annotation_order_no(
        db,
        project_id=project.id,
        order_no=order_no,
        assignment_source=operation_source,
        assigned_by=created_by,
    )
    from annotation_ops_models import AnnotationProjectStatusHistory
    db.add(AnnotationProjectStatusHistory(
        project_id=project.id,
        from_status=None,
        to_status=project.project_status,
        effective_on=project.status_effective_on,
        changed_by=created_by,
        entry_kind="status",
    ))
    from project_workbench_service import assignment_map_from_payload, ensure_project_responsibilities, validate_assignment_map
    assignments = assignment_map_from_payload(payload.role_assignments)
    validate_assignment_map(db, assignments)
    ensure_project_responsibilities(db, 'annotation', project.id, assignments)
    if parent:
        from annotation_child_copy_service import copy_scoped_fields
        field_mapping = copy_scoped_fields(db, parent, project, created_by)
    _sync_nested(db, project, payload)
    db.flush()
    if parent:
        from annotation_child_copy_service import source_direction, copy_people, copy_materials
        if copy_people_from_parent:
            copy_people(db, parent, project, source_direction(parent, payload), field_mapping)
        if payload.copy_parent_materials:
            copy_materials(db, parent.id, project.id)
    from annotation_material_service import apply_changes
    apply_changes(db, project.id, payload.material_changes, created_by)
    project.updated_at = datetime.now()
    record_project_operation(
        db, project_type="annotation", operation_type="create", project=project,
        actor_user_id=created_by, operation_source=operation_source,
    )
    auto_count = 0
    if not parent:
        from annotation_direction_service import ensure_direction_children
        auto_count = len(ensure_direction_children(db, project, created_by))
    if commit:
        db.commit()
        result = get_annotation_project(db, project.id)
        result.auto_created_child_count = auto_count
        return result
    db.flush()
    return project


def update_annotation_project(
    db: Session, project_id: UUID, payload: AnnotationProjectUpdate,
    changed_by: Optional[UUID] = None,
) -> Optional[AnnotationProject]:
    _lock_annotation_order_numbers(db)
    existing = db.get(AnnotationProject, project_id)
    parent = _lock_parent(db, existing.parent_project_id) if existing and existing.parent_project_id else None
    # 序列化项目保存，确保版本递增和乐观锁检查在同一锁内。
    db.query(AnnotationProject).filter(AnnotationProject.id == project_id).with_for_update().populate_existing().first()
    project = get_annotation_project(db, project_id)
    if not project:
        return None
    assert_fresh(project, payload.expected_updated_at)
    previous_client_manager_id = project.client_manager_id
    previous_project_manager_ids = _project_manager_ids(project.workbench_responsibilities)
    data = payload.model_dump(exclude=NESTED_FIELDS | {VERSION_FIELD})
    if parent:
        if len(payload.language_items) != 1:
            raise ValueError("子订单必须且只能绑定一个语种或语言方向")
    from annotation_custom_field_service import validate_custom_values
    data["custom_values"] = validate_custom_values(
        db, "project", None, data.get("custom_values") or {}, project.custom_values,
    )
    _resolve_client(db, data)
    for key in WRITE_ONLY_CLIENT_FIELDS:
        data.pop(key, None)
    previous_status = project.project_status
    previous_effective_on = project.status_effective_on
    for key, value in data.items():
        setattr(project, key, value)
    if (
        project.project_status != previous_status
        or project.status_effective_on != previous_effective_on
    ):
        from annotation_ops_models import AnnotationProjectStatusHistory
        db.add(AnnotationProjectStatusHistory(
            project_id=project.id,
            from_status=previous_status,
            to_status=project.project_status,
            effective_on=project.status_effective_on,
            changed_by=changed_by,
            entry_kind="status",
        ))
    from project_workbench_service import assignment_map_from_payload, ensure_active_project_responsibilities, validate_assignment_map
    assignments = assignment_map_from_payload(payload.role_assignments) if 'role_assignments' in payload.model_fields_set else None
    validate_assignment_map(db, assignments)
    responsibility_rows = ensure_active_project_responsibilities(
        db, 'annotation', project.id, project.project_status, assignments,
    )
    current_project_manager_ids = (
        _project_manager_ids(responsibility_rows)
        if responsibility_rows else previous_project_manager_ids
    )
    _sync_nested(db, project, payload)
    from annotation_material_service import apply_changes
    if payload.material_changes is not None and payload.expected_updated_at is None:
        raise ValueError('保存项目资料必须携带项目版本，请刷新后重试')
    apply_changes(db, project.id, payload.material_changes, changed_by)
    project.updated_at = datetime.now()
    record_annotation_manager_change(
        db,
        project=project,
        manager_role="client_manager",
        previous_manager_id=previous_client_manager_id,
        new_manager_id=project.client_manager_id,
        change_mode="project_edit",
        actor_user_id=changed_by,
        reason="编辑标注项目时修改负责人",
    )
    _record_project_manager_changes(
        db, project=project,
        previous_ids=previous_project_manager_ids,
        current_ids=current_project_manager_ids,
        change_mode="project_edit", actor_user_id=changed_by,
        reason="编辑标注项目时修改负责人",
    )
    from annotation_direction_service import ensure_direction_children
    auto_count = len(ensure_direction_children(db, project, changed_by)) if not parent else 0
    db.commit()
    result = get_annotation_project(db, project.id)
    result.auto_created_child_count = auto_count
    return result


def update_annotation_project_order_no(
    db: Session,
    project_id: UUID,
    new_order_no: str,
    reason: str,
    expected_updated_at: Optional[datetime],
    changed_by: Optional[UUID],
) -> Optional[AnnotationProject]:
    # 与创建子订单保持“全局编号锁 → 母订单行锁”的顺序，避免并发改号死锁。
    _lock_annotation_order_numbers(db)
    project = (
        db.query(AnnotationProject)
        .filter(AnnotationProject.id == project_id)
        .with_for_update()
        .first()
    )
    if not project:
        return None
    assert_fresh(project, expected_updated_at)
    if getattr(project, "parent_project_id", None):
        raise ValueError("子订单号由系统生成，不允许手动修改")
    if db.query(AnnotationProject.id).filter(AnnotationProject.parent_project_id == project.id).first():
        raise ValueError("已有子订单的母订单不能修改订单号")
    normalized = normalize_annotation_order_no(new_order_no)
    previous_order_no = project.order_no
    if normalized == previous_order_no:
        raise ValueError("新订单号不能与当前订单号相同")
    reserve_annotation_order_no(
        db,
        project_id=project.id,
        order_no=normalized,
        assignment_source="manual_change",
        assigned_by=changed_by,
    )
    project.order_no = normalized
    if project.email_subject_preview and previous_order_no in project.email_subject_preview:
        project.email_subject_preview = project.email_subject_preview.replace(
            previous_order_no, normalized, 1,
        )
    project.updated_at = datetime.now()
    record_project_operation(
        db,
        project_type="annotation",
        operation_type="order_no_change",
        project=project,
        actor_user_id=changed_by,
        operation_source="project_order_no_change",
        previous_order_no=previous_order_no,
        change_reason=reason.strip(),
    )
    db.commit()
    return get_annotation_project(db, project.id)


def update_annotation_project_status(
    db: Session,
    project_id: UUID,
    project_status: str,
    effective_on: datetime,
    change_note: Optional[str] = None,
    changed_by: Optional[UUID] = None,
    progress_only: bool = False,
) -> Optional[AnnotationProject]:
    project = get_annotation_project(db, project_id)
    if not project:
        return None
    if progress_only and project_status != project.project_status:
        reached_status = (
            db.query(AnnotationProjectStatusHistory.id)
            .filter(
                AnnotationProjectStatusHistory.project_id == project.id,
                AnnotationProjectStatusHistory.to_status == project_status,
            )
            .first()
        )
        if reached_status is None:
            raise ValueError("只能为项目已经流转到的状态补充具体进度")
    if not progress_only and (
        project.project_status == project_status
        and project.status_effective_on == effective_on
    ):
        return project
    previous_status = project.project_status
    if progress_only:
        history_from_status = project_status
    else:
        history_from_status = previous_status
        project.project_status = project_status
        project.status_effective_on = effective_on
    project.updated_at = datetime.now()
    db.add(AnnotationProjectStatusHistory(
        project_id=project.id,
        from_status=history_from_status,
        to_status=project_status,
        effective_on=effective_on,
        changed_by=changed_by,
        change_note=change_note,
        entry_kind="progress" if progress_only else "status",
    ))
    if not progress_only:
        from project_workbench_service import ensure_active_project_responsibilities
        ensure_active_project_responsibilities(db, 'annotation', project.id, project_status)
    db.commit()
    return get_annotation_project(db, project.id)


def update_annotation_project_priority(
    db: Session,
    project_id: UUID,
    priority: str,
) -> Optional[AnnotationProject]:
    project = get_annotation_project(db, project_id)
    if not project:
        return None
    if project.priority == priority:
        return project
    project.priority = priority
    project.updated_at = datetime.now()
    db.commit()
    return get_annotation_project(db, project.id)


def update_annotation_project_managers(
    db: Session,
    project_id: UUID,
    client_manager_id: Optional[UUID],
    project_manager_ids: list[UUID] | UUID | None,
    changed_by: Optional[UUID] = None,
) -> Optional[AnnotationProject]:
    """更新标注项目的客户经理和项目经理用户关联。"""
    existing = db.get(AnnotationProject, project_id)
    if existing and existing.parent_project_id:
        _lock_parent(db, existing.parent_project_id)
    db.query(AnnotationProject).filter(AnnotationProject.id == project_id).with_for_update().populate_existing().first()
    project = get_annotation_project(db, project_id)
    if not project:
        return None
    previous_client_manager_id = project.client_manager_id

    if client_manager_id and client_manager_id != project.client_manager_id:
        client_manager = db.query(AppUser).filter(
            AppUser.id == client_manager_id,
            AppUser.is_active.is_(True),
        ).first()
        if not client_manager:
            raise ValueError("所选客户经理不存在或已停用")

    from project_workbench_service import (
        ensure_project_responsibilities,
        validate_assignment_map,
    )

    current_project_manager_ids = _project_manager_ids(project.workbench_responsibilities)
    submitted_manager_ids = (
        project_manager_ids if isinstance(project_manager_ids, list)
        else ([project_manager_ids] if project_manager_ids else [])
    )
    normalized_project_manager_ids = list(dict.fromkeys(submitted_manager_ids))
    assignments = {"project_manager": normalized_project_manager_ids}
    if normalized_project_manager_ids != current_project_manager_ids:
        validate_assignment_map(db, assignments)
    project.client_manager_id = client_manager_id
    ensure_project_responsibilities(db, "annotation", project.id, assignments)
    project.updated_at = datetime.now()
    record_annotation_manager_change(
        db,
        project=project,
        manager_role="client_manager",
        previous_manager_id=previous_client_manager_id,
        new_manager_id=client_manager_id,
        change_mode="inline_edit",
        actor_user_id=changed_by,
        reason="标注项目列表直接修改负责人",
    )
    _record_project_manager_changes(
        db, project=project,
        previous_ids=current_project_manager_ids,
        current_ids=normalized_project_manager_ids,
        change_mode="inline_edit", actor_user_id=changed_by,
        reason="标注项目列表直接修改负责人",
    )
    db.commit()
    return get_annotation_project(db, project.id)


def delete_annotation_project(
    db: Session, project_id: UUID, *, actor_user_id: Optional[UUID] = None,
    operation_source: str = "project_delete",
) -> bool:
    _lock_annotation_order_numbers(db)
    existing = db.get(AnnotationProject, project_id)
    if existing and existing.parent_project_id:
        _lock_parent(db, existing.parent_project_id)
    project = db.query(AnnotationProject).filter(AnnotationProject.id == project_id).with_for_update().first()
    if not project:
        return False
    if db.query(AnnotationProject.id).filter(AnnotationProject.parent_project_id == project.id).first():
        raise AnnotationProjectDeleteConflict("请先删除该母订单的全部子订单")

    resource_requests = db.query(ResourceRequest).filter(
        ResourceRequest.annotation_project_id == project_id,
    ).all()
    account_assignments = db.query(AnnotationAccountAssignment).filter(
        AnnotationAccountAssignment.project_id == project_id,
    ).all()
    active_assignments = [item for item in account_assignments if item.released_on is None]

    blockers = []
    if resource_requests:
        request_labels = "、".join(
            item.request_no for item in resource_requests[:3] if item.request_no
        )
        suffix = f"（{request_labels}{'等' if len(resource_requests) > 3 else ''}）" if request_labels else ""
        blockers.append(f"关联资源需求 {len(resource_requests)} 条{suffix}")
    if active_assignments:
        assignment_labels = "、".join(
            _active_account_assignment_label(item) for item in active_assignments[:3]
        )
        suffix = f"（{assignment_labels}{'等' if len(active_assignments) > 3 else ''}）" if assignment_labels else ""
        blockers.append(f"未释放的标注账号分配 {len(active_assignments)} 条{suffix}")
    if blockers:
        raise AnnotationProjectDeleteConflict(
            f"无法删除标注项目 {project.order_no}：{'；'.join(blockers)}。请先处理这些关联记录"
        )

    # 已释放的账号分配属于被删除项目的历史明细。硬删除项目时一并删除，
    # 否则其语种关联会以 RESTRICT 方式阻止项目语种级联删除。
    for assignment in account_assignments:
        db.delete(assignment)
    if account_assignments:
        db.flush()

    image_storage_names = [
        value for (value,) in db.query(AnnotationCustomFieldImage.storage_name).filter(
            AnnotationCustomFieldImage.project_id == project_id,
        ).all()
    ]
    from project_workbench_service import cancel_pending_project_handovers
    cancel_pending_project_handovers(db, 'annotation', project_id)
    record_project_operation(
        db, project_type="annotation", operation_type="delete", project=project,
        actor_user_id=actor_user_id, operation_source=operation_source,
    )
    from annotation_material_service import remove_project_materials
    remove_project_materials(db, project.id)
    db.delete(project)
    db.commit()
    delete_custom_field_image_files(image_storage_names)
    return True


def _language_labels(db: Session, language_items) -> list[str]:
    ids = {
        value
        for item in language_items
        for value in (item.source_language_id, item.target_language_id)
        if value is not None
    }
    labels = {
        row.id: row.label
        for row in db.query(InterpretationLanguage)
        .filter(InterpretationLanguage.id.in_(ids)).all()
    } if ids else {}
    if len(labels) != len(ids):
        raise ValueError("所选语种不存在或已失效")
    return [
        f"{labels[item.source_language_id]}→{labels[item.target_language_id]}"
        if item.target_language_id else labels[item.source_language_id]
        for item in language_items
    ]


def build_annotation_project_name(
    client_short_name: Optional[str],
    project_types: list[str],
    language_labels: list[str],
    name_date: Optional[date] = None,
) -> str:
    client_name = (client_short_name or "").strip()
    type_labels = [ANNOTATION_PROJECT_TYPE_LABELS[value] for value in project_types]
    if not client_name and not language_labels and not type_labels:
        return ""
    project_date = name_date or datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
    parts = [client_name, f"{project_date:%Y%m%d}"]
    if language_labels:
        summary = "、".join(language_labels[:3])
        if len(language_labels) > 3:
            summary += "等方向"
        parts.append(summary)
    if type_labels:
        parts.append("、".join(type_labels))
    business_text = "-".join(part for part in parts if part)
    return f"【{business_text}】"


def preview_annotation_project_name(
    db: Session, payload: AnnotationNamePreviewRequest
) -> str:
    return build_annotation_project_name(
        payload.client_short_name,
        payload.project_types,
        _language_labels(db, payload.language_items),
        payload.name_date,
    )


def ensure_annotation_project_for_consultation(
    db: Session, consultation: Consultation, created_by: Optional[UUID],
    *, order_no: Optional[str] = None, project_name: Optional[str] = None,
    email_subject_preview: Optional[str] = None,
) -> tuple[AnnotationProject, bool]:
    existing = db.query(AnnotationProject).filter(
        AnnotationProject.consultation_id == consultation.id
    ).first()
    if existing:
        if project_name is not None:
            existing.project_name = project_name
        if email_subject_preview is not None:
            existing.email_subject_preview = email_subject_preview
        return existing, False
    if db.query(InterpretationProject.id).filter(
        InterpretationProject.consultation_id == consultation.id
    ).first():
        raise ValueError("该咨询已生成口译项目，不能再生成标注项目")
    translation = db.query(TranslationProject).filter(
        TranslationProject.consultation_id == consultation.id,
        TranslationProject.annotation_migrated_at.is_(None),
    ).first()
    if translation:
        raise ValueError("该咨询已生成笔译项目，请先执行标注历史迁移")
    project = AnnotationProject(
        order_no=order_no or generate_annotation_order_no(db),
        project_name=project_name,
        consultation_id=consultation.id,
        client_id=consultation.client_id,
        project_status="initial_consultation",
        customer_consultation_time=consultation.consultation_time,
        customer_confirmation_time=datetime.now(),
        email_subject_preview=email_subject_preview,
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    reserve_annotation_order_no(
        db,
        project_id=project.id,
        order_no=project.order_no,
        assignment_source="consultation_confirmation",
        assigned_by=created_by,
    )
    record_project_operation(
        db, project_type="annotation", operation_type="create", project=project,
        actor_user_id=created_by, operation_source="consultation_confirmation",
    )
    return project, True


def validate_consultation_annotation_type_change(
    db: Session, consultation_id: UUID, target_type: Optional[str]
) -> None:
    has_annotation = db.query(AnnotationProject.id).filter(
        AnnotationProject.consultation_id == consultation_id
    ).first()
    if has_annotation and not is_annotation_type(target_type):
        raise ValueError("该咨询已生成标注项目，不能修改为其他咨询类型")
    if is_annotation_type(target_type):
        has_translation = db.query(TranslationProject.id).filter(
            TranslationProject.consultation_id == consultation_id,
            TranslationProject.annotation_migrated_at.is_(None),
        ).first()
        has_interpretation = db.query(InterpretationProject.id).filter(
            InterpretationProject.consultation_id == consultation_id
        ).first()
        if has_translation or has_interpretation:
            raise ValueError("该咨询已生成其他类型项目，不能修改为标注项目")


LEGACY_STATUS_MAP = {
    "pending": "initial_consultation",
    "pending_confirmation": "initial_consultation",
    "confirmed": "initial_consultation",
    "trial": "trial_in_progress",
    "trial_translation": "trial_in_progress",
    "sent_to_client": "sent_to_client",
    "feedback_sent_to_client": "sent_to_client",
    "completed": "sent_to_client",
    "client_feedback": "client_feedback",
    "cancelled": "cancelled",
    "partially_cancelled": "partially_cancelled",
}


def _legacy_status(value: Optional[str]) -> str:
    return LEGACY_STATUS_MAP.get(value or "", "project_in_progress")


def _get_or_create_language(db: Session, label: str) -> InterpretationLanguage:
    normalized = " ".join(label.split()).strip()
    if len(normalized) > 100:
        normalized = normalized[:100].rstrip()
    existing = db.query(InterpretationLanguage).filter(
        func.lower(InterpretationLanguage.label) == normalized.lower()
    ).first()
    if existing:
        return existing
    language = InterpretationLanguage(label=normalized, is_custom=True)
    db.add(language)
    db.flush()
    return language


def _legacy_language_items(db: Session, value: Optional[str]):
    items = []
    seen = set()
    for raw_item in re.split(r"[；;，,、\n]+", value or ""):
        raw_item = raw_item.strip()
        if not raw_item:
            continue
        pieces = re.split(r"\s*(?:→|->|⇒|=>|翻译成|译成)\s*", raw_item, maxsplit=1)
        source = _get_or_create_language(db, pieces[0])
        target = _get_or_create_language(db, pieces[1]) if len(pieces) == 2 else None
        key = source.id, target.id if target else None
        if key in seen or (target and source.id == target.id):
            continue
        seen.add(key)
        items.append(AnnotationProjectLanguageItem(
            sequence_no=len(items) + 1,
            source_language_id=source.id,
            target_language_id=target.id if target else None,
        ))
    return items


def ensure_translation_languages_in_catalog(db: Session) -> int:
    """把既有笔译项目/子订单字符串中的语种补入共享目录。"""
    values = [
        value for (value,) in db.query(TranslationProject.language_pair)
        .filter(TranslationProject.language_pair.is_not(None)).all()
    ]
    values.extend(
        value for (value,) in db.query(TranslationSubOrder.language_pair)
        .filter(TranslationSubOrder.language_pair.is_not(None)).all()
    )
    before = db.query(func.count(InterpretationLanguage.id)).scalar() or 0
    for value in values:
        for raw_item in re.split(r"[；;，,、\n]+", value or ""):
            raw_item = raw_item.strip()
            if not raw_item:
                continue
            pieces = re.split(
                r"\s*(?:→|->|⇒|=>|翻译成|译成)\s*", raw_item, maxsplit=1
            )
            for label in pieces:
                if label.strip():
                    _get_or_create_language(db, label)
    db.commit()
    after = db.query(func.count(InterpretationLanguage.id)).scalar() or 0
    return max(0, after - before)


def migrate_legacy_annotation_projects(db: Session) -> dict[str, int]:
    """迁移误存于笔译表的标注项目；保留并归档原记录。"""
    candidates = (
        db.query(TranslationProject)
        .outerjoin(Consultation, TranslationProject.consultation_id == Consultation.id)
        .filter(
            TranslationProject.annotation_migrated_at.is_(None),
            or_(
                TranslationProject.task_type.in_(ANNOTATION_TYPE_VALUES),
                Consultation.consultation_type.in_(ANNOTATION_TYPE_VALUES),
            ),
        )
        .order_by(TranslationProject.created_at.asc(), TranslationProject.id.asc())
        .all()
    )
    result = {"migrated": 0, "skipped": 0, "failed": 0}
    for legacy in candidates:
        try:
            with db.begin_nested():
                existing = db.query(AnnotationProject).filter(or_(
                    AnnotationProject.legacy_translation_project_id == legacy.id,
                    AnnotationProject.consultation_id == legacy.consultation_id
                    if legacy.consultation_id else text("false"),
                )).first()
                if existing:
                    legacy.annotation_project_id = existing.id
                    legacy.annotation_migrated_at = datetime.now()
                    result["skipped"] += 1
                    continue
                type_by_label = {
                    label: code for code, label in ANNOTATION_PROJECT_TYPE_LABELS.items()
                }
                project_types = []
                if legacy.service_content in ANNOTATION_PROJECT_TYPE_LABELS:
                    project_types = [legacy.service_content]
                elif legacy.service_content in type_by_label:
                    project_types = [type_by_label[legacy.service_content]]
                dispatched_at = legacy.translator_assignment_time
                submitted_at = legacy.sent_to_client_time
                if dispatched_at and submitted_at and submitted_at < dispatched_at:
                    submitted_at = None
                project = AnnotationProject(
                    order_no=generate_annotation_order_no(db, legacy.created_at),
                    project_name=legacy.project_name,
                    project_types=project_types,
                    task_description=legacy.service_content,
                    consultation_id=legacy.consultation_id,
                    client_id=legacy.client_id,
                    sub_client_id=legacy.sub_client_id,
                    customer_order_no=legacy.customer_order_no,
                    project_status=_legacy_status(legacy.project_status),
                    task_dispatched_at=dispatched_at,
                    task_submitted_at=submitted_at,
                    client_manager_id=legacy.project_manager_id,
                    customer_consultation_time=legacy.customer_reception_time,
                    legacy_translation_project_id=legacy.id,
                    legacy_order_no=legacy.order_no,
                    legacy_status=legacy.project_status,
                    created_by=legacy.created_by,
                    created_at=legacy.created_at or datetime.now(),
                    updated_at=legacy.updated_at or datetime.now(),
                )
                project.language_items = _legacy_language_items(db, legacy.language_pair)
                db.add(project)
                db.flush()
                reserve_annotation_order_no(
                    db,
                    project_id=project.id,
                    order_no=project.order_no,
                    assignment_source="legacy_migration",
                    assigned_by=legacy.created_by,
                )
                legacy.annotation_project_id = project.id
                legacy.annotation_migrated_at = datetime.now()
                result["migrated"] += 1
        except Exception:
            result["failed"] += 1
            db.expire_all()
    db.commit()
    print(
        "标注项目历史迁移："
        f"迁移 {result['migrated']}，跳过 {result['skipped']}，失败 {result['failed']}"
    )
    return result
