"""跨业务资源需求服务。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlalchemy.orm import Session, selectinload

from annotation_models import AnnotationProject
from interpretation_models import InterpretationLanguage, InterpretationProject
from models import Client, SubClient, TranslationProject
from recruitment_models import RecruitmentProject
from resource_request_models import ResourceRequest, ResourceRequestItem, ResourceRequestProgressLog


SOURCE_MODELS = {
    "annotation": (AnnotationProject, "annotation_project_id"),
    "recruitment": (RecruitmentProject, "recruitment_project_id"),
    "interpretation": (InterpretationProject, "interpretation_project_id"),
    "translation": (TranslationProject, "translation_project_id"),
}


def _project_client_snapshot(db: Session, project) -> dict:
    client_id = getattr(project, "client_id", None)
    sub_client_id = getattr(project, "sub_client_id", None)
    client = db.get(Client, client_id) if client_id else None
    sub_client = db.get(SubClient, sub_client_id) if sub_client_id else None
    selected = sub_client or client
    return {
        "client_id": client_id,
        "sub_client_id": sub_client_id,
        "client_code_snapshot": getattr(selected, "sub_client_code", None) or getattr(selected, "client_code", None),
        "client_short_name_snapshot": getattr(selected, "client_short_name", None),
    }


def _first_text(*values) -> str:
    return next((str(value).strip() for value in values if value is not None and str(value).strip()), "")


def _source_detail(project, source_type: str) -> str:
    if source_type == "annotation":
        return _first_text(project.potential_demand, project.task_description)
    if source_type == "recruitment":
        return _first_text(project.resource_request, project.job_description)
    if source_type == "interpretation":
        return _first_text(
            project.resource_request,
            project.interpreter_special_requirements,
            project.task_description,
        )
    return "\n".join(filter(None, [
        _first_text(getattr(project, "customer_requirement_professional", None)),
        _first_text(getattr(project, "customer_requirement_special", None)),
        _first_text(getattr(project, "service_content", None)),
    ]))


def _project_type_values(project, source_type: str) -> list[str]:
    if source_type in {"annotation", "interpretation"}:
        return list(getattr(project, "project_types", None) or [])
    if source_type == "recruitment":
        return ["招聘"]
    task_type = _first_text(getattr(project, "task_type", None))
    return [task_type] if task_type else ["笔译"]


def _translation_language_items(db: Session, language_pair: Optional[str]) -> list[dict]:
    """把笔译项目的受控“源语种→目标语种”文本转换成资源需求明细。"""
    pairs = [part.strip() for part in (language_pair or "").replace("；", ";").split(";") if part.strip()]
    if not pairs:
        return []
    labels = {piece.strip() for pair in pairs for piece in pair.split("→") if piece.strip()}
    language_by_label = {
        row.label: row.id
        for row in db.query(InterpretationLanguage).filter(InterpretationLanguage.label.in_(labels)).all()
    }
    result = []
    for pair in pairs:
        source, separator, target = pair.partition("→")
        source_id = language_by_label.get(source.strip())
        target_id = language_by_label.get(target.strip()) if separator else None
        if source_id:
            result.append({"source_language_id": source_id, "target_language_id": target_id})
    return result


def get_resource_request_source_prefill(db: Session, source_type: str, source_project_id: UUID) -> Optional[dict]:
    """读取来源项目并生成可人工调整的资源需求预填值。"""
    if source_type not in SOURCE_MODELS:
        raise ValueError("不支持的来源类型")
    model, _ = SOURCE_MODELS[source_type]
    project = db.get(model, source_project_id)
    if not project:
        return None

    if source_type == "annotation":
        raw_items = [
            {"source_language_id": item.source_language_id, "target_language_id": item.target_language_id}
            for item in project.language_items
        ]
        project_types = _project_type_values(project, source_type)
    elif source_type == "recruitment":
        count = project.headcount_max or project.headcount_min
        raw_items = [
            {
                "source_language_id": item.source_language_id,
                "target_language_id": item.target_language_id,
                "required_count": count if index == 0 else None,
            }
            for index, item in enumerate(project.language_directions)
        ]
        project_types = _project_type_values(project, source_type)
    elif source_type == "interpretation":
        raw_items = [
            {
                "source_language_id": item.source_language_id,
                "target_language_id": item.target_language_id,
                "required_count": project.required_interpreter_count if index == 0 else None,
            }
            for index, item in enumerate(project.language_directions)
        ]
        project_types = _project_type_values(project, source_type) or ["口译"]
    else:
        raw_items = _translation_language_items(db, project.language_pair)
        project_types = _project_type_values(project, source_type)

    detail = _source_detail(project, source_type)
    if raw_items and detail:
        raw_items[0]["requirement_detail"] = detail
    client_snapshot = _project_client_snapshot(db, project)
    request_category = source_type
    if source_type == "annotation":
        formal_statuses = {"project_in_progress", "sent_to_client", "client_feedback", "partially_cancelled"}
        request_category = "annotation_formal" if project.project_status in formal_statuses else "annotation_trial"
    return {
        "source_type": source_type,
        "request_category": request_category,
        "source_project_types": project_types,
        "order_no": getattr(project, "order_no", None),
        "project_name": getattr(project, "project_name", None) or getattr(project, "order_no", "未命名项目"),
        "project_status": getattr(project, "project_status", None),
        "client_code": client_snapshot["client_code_snapshot"],
        "client_short_name": client_snapshot["client_short_name_snapshot"],
        "request_detail": detail,
        "items": raw_items,
    }


def generate_resource_request_no(db: Session, current_time: Optional[datetime] = None) -> str:
    now = current_time or datetime.now(ZoneInfo("Asia/Hong_Kong"))
    day = now.strftime("%y%m%d")
    prefix = f"RR-{day}-"
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"resource-request:{day}"})
    last_no = (
        db.query(ResourceRequest.request_no)
        .filter(ResourceRequest.request_no.like(f"{prefix}%"))
        .order_by(ResourceRequest.request_no.desc())
        .limit(1)
        .scalar()
    )
    sequence = 1
    if last_no:
        try:
            sequence = int(last_no.rsplit("-", 1)[-1]) + 1
        except ValueError:
            sequence = 1
    return f"{prefix}{sequence:03d}"


def _source_snapshot(db: Session, payload) -> dict:
    if payload.source_type == "other":
        other_values = [value.strip() for value in payload.other_source_name.replace("，", ",").split(",") if value.strip()]
        return {"source_project_name_snapshot": "、".join(other_values), "source_project_types_snapshot": other_values}
    model, field = SOURCE_MODELS[payload.source_type]
    source_id = getattr(payload, field)
    project = db.get(model, source_id)
    if not project:
        raise ValueError("来源项目不存在")
    return {
        "source_project_types_snapshot": _project_type_values(project, payload.source_type),
        "source_order_no_snapshot": getattr(project, "order_no", None),
        "source_project_name_snapshot": getattr(project, "project_name", None) or getattr(project, "order_no", "未命名项目"),
        "source_status_snapshot": getattr(project, "project_status", None),
        **_project_client_snapshot(db, project),
    }


def _sync_items(db: Session, request: ResourceRequest, payload_items) -> None:
    by_id = {row.id: row for row in request.items}
    requested_ids = {item.id for item in payload_items if item.id}
    if requested_ids - set(by_id):
        raise ValueError("资源需求明细包含不属于当前请求的记录")

    # 先临时移开原排序号，避免交换两条明细顺序时触发唯一约束。
    # sequence_no 有 > 0 约束，不能使用负数；使用远离正常序号的正数区间。
    if by_id:
        for index, row in enumerate(request.items, start=1):
            row.sequence_no = 1_000_000 + index
        db.flush()
    for row in list(request.items):
        if row.id not in requested_ids:
            request.items.remove(row)
    for index, item in enumerate(payload_items, start=1):
        row = by_id.get(item.id) if item.id else ResourceRequestItem()
        if not item.id:
            request.items.append(row)
        for key, value in item.model_dump(exclude={"id"}).items():
            setattr(row, key, value)
        row.sequence_no = index
        row.updated_at = datetime.now()


def create_resource_request(db: Session, payload, user_id: Optional[UUID]):
    data = payload.model_dump(exclude={"items"}) | _source_snapshot(db, payload)
    row = ResourceRequest(request_no=generate_resource_request_no(db), requested_by=user_id, **data)
    _sync_items(db, row, payload.items)
    db.add(row)
    db.flush()
    db.add(ResourceRequestProgressLog(request_id=row.id, progress_percent=0, progress_note="资源需求已创建", changed_by=user_id))
    db.commit()
    return get_resource_request(db, row.id)


def update_resource_request(db: Session, request_id: UUID, payload):
    row = db.query(ResourceRequest).options(selectinload(ResourceRequest.items)).filter(ResourceRequest.id == request_id).first()
    if not row:
        return None
    data = payload.model_dump(exclude={"items"}) | _source_snapshot(db, payload)
    for key, value in data.items():
        setattr(row, key, value)
    _sync_items(db, row, payload.items)
    row.updated_at = datetime.now()
    db.commit()
    return get_resource_request(db, row.id)


def _current_values(db: Session, row: ResourceRequest) -> dict:
    if row.source_type == "other":
        return {"current_project_status": None, "current_order_no": None, "current_project_name": row.other_source_name}
    model, field = SOURCE_MODELS[row.source_type]
    project = db.get(model, getattr(row, field))
    return {
        "current_project_status": getattr(project, "project_status", None),
        "current_order_no": getattr(project, "order_no", None),
        "current_project_name": getattr(project, "project_name", None),
    }


def _detail_dict(db: Session, row: ResourceRequest) -> dict:
    columns = [column.name for column in ResourceRequest.__table__.columns]
    return {name: getattr(row, name) for name in columns} | _current_values(db, row) | {"items": row.items}


def get_resource_request(db: Session, request_id: UUID):
    row = db.query(ResourceRequest).options(selectinload(ResourceRequest.items)).filter(ResourceRequest.id == request_id).first()
    return _detail_dict(db, row) if row else None


def _view_filter_sql(*, keyword=None, source_type=None, request_category=None, request_status=None, priority=None, owner_id=None):
    """为列表和总数构造完全相同的展示视图筛选条件。"""
    clauses, params = ["1=1"], {}
    filters = {"source_type": source_type, "request_category": request_category, "request_status": request_status, "priority": priority, "owner_id": owner_id}
    for key, value in filters.items():
        if value is not None:
            clauses.append(f"{key} = :{key}")
            params[key] = value
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        clauses.append(
            "(request_no ILIKE :keyword OR current_project_name ILIKE :keyword "
            "OR source_project_name_snapshot ILIKE :keyword OR request_detail ILIKE :keyword "
            "OR client_short_name_snapshot ILIKE :keyword "
            "OR EXISTS (SELECT 1 FROM client c WHERE c.id=client_id AND "
            "(c.client_name ILIKE :keyword OR c.english_name ILIKE :keyword)) "
            "OR EXISTS (SELECT 1 FROM sub_client sc WHERE sc.id=sub_client_id AND "
            "(sc.client_name ILIKE :keyword OR sc.english_name ILIKE :keyword)))"
        )
        params["keyword"] = f"%{normalized_keyword}%"
    return " AND ".join(clauses), params


def list_resource_requests(db: Session, *, skip=0, limit=100, keyword=None, source_type=None, request_category=None, request_status=None, priority=None, owner_id=None):
    where_sql, params = _view_filter_sql(
        keyword=keyword, source_type=source_type, request_category=request_category,
        request_status=request_status, priority=priority, owner_id=owner_id,
    )
    params.update({"skip": skip, "limit": limit})
    sql = text(f"SELECT * FROM v_resource_request_display WHERE {where_sql} ORDER BY requested_at DESC LIMIT :limit OFFSET :skip")
    result = [dict(row) for row in db.execute(sql, params).mappings().all()]
    request_ids = [row["id"] for row in result]
    items_by_request = {}
    if request_ids:
        requests = db.query(ResourceRequest).options(selectinload(ResourceRequest.items)).filter(ResourceRequest.id.in_(request_ids)).all()
        items_by_request = {row.id: list(row.items) for row in requests}
    return [row | {"items": items_by_request.get(row["id"], [])} for row in result]


def count_resource_requests(db: Session, **filters) -> int:
    where_sql, params = _view_filter_sql(**filters)
    return int(db.execute(
        text(f"SELECT COUNT(*) FROM v_resource_request_display WHERE {where_sql}"),
        params,
    ).scalar_one())


def update_resource_progress(db: Session, request_id: UUID, payload, user_id: Optional[UUID]):
    row = db.get(ResourceRequest, request_id)
    if not row:
        return None
    row.progress_percent = payload.progress_percent
    if payload.request_status:
        row.request_status = payload.request_status
    if row.progress_percent == 100 and row.request_status != "cancelled":
        row.request_status = "fulfilled"
        row.completed_at = datetime.now()
    elif row.request_status != "fulfilled":
        row.completed_at = None
    row.updated_at = datetime.now()
    db.add(ResourceRequestProgressLog(request_id=row.id, progress_percent=payload.progress_percent, progress_note=payload.progress_note, changed_by=user_id))
    db.commit()
    return get_resource_request(db, row.id)


def list_progress_logs(db: Session, request_id: UUID):
    return db.query(ResourceRequestProgressLog).filter(ResourceRequestProgressLog.request_id == request_id).order_by(ResourceRequestProgressLog.changed_at.desc()).all()


def delete_resource_request(db: Session, request_id: UUID) -> bool:
    row = db.get(ResourceRequest, request_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
