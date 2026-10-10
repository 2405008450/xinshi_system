"""客户进度写入、集合摘要与双线检索。"""

from datetime import datetime, time, timedelta

from sqlalchemy import DateTime, Interval, String, func, inspect, literal, select, union_all
from sqlalchemy.orm import aliased

from annotation_customer_progress_models import AnnotationCustomerProgress
from annotation_models import AnnotationProject
from annotation_ops_models import AnnotationProjectStatusHistory
from annotation_progress_time import BUSINESS_TIMEZONE, business_datetime, business_now
from concurrency import StaleUpdateError
from models import AppUser
from project_audit_service import record_project_operation
from workflow_models import ProjectWorkbenchResponsibility


class CustomerProgressUnavailable(ValueError):
    pass


def customer_progress_available(db):
    """迁移尚未发布时不让既有项目列表失效，不在启动时建表。"""
    return inspect(db.connection()).has_table(AnnotationCustomerProgress.__tablename__)


def require_customer_progress(db):
    if not customer_progress_available(db):
        raise CustomerProgressUnavailable("客户进度功能尚未完成数据库迁移，请联系管理员安排发布")
    return True


def attach_customer_progress_summary(db, projects):
    if not projects:
        return
    for project in projects:
        project.latest_customer_progress_note = None
        project.latest_customer_progress_effective_on = None
    if not customer_progress_available(db):
        return
    model = AnnotationCustomerProgress
    ranked = select(
        model.project_id, model.change_note, model.effective_on,
        func.row_number().over(
            partition_by=model.project_id,
            order_by=(model.effective_on.desc(), model.changed_at.desc(), model.id.desc()),
        ).label("position"),
    ).where(model.project_id.in_([project.id for project in projects])).subquery()
    summaries = {
        row.project_id: row
        for row in db.execute(select(ranked).where(ranked.c.position == 1))
    }
    for project in projects:
        row = summaries.get(project.id)
        if row:
            project.latest_customer_progress_note = row.change_note
            project.latest_customer_progress_effective_on = business_datetime(row.effective_on)


def _display_name(user):
    if not user:
        return None
    return (user.full_name or "").strip() or user.username


def _response_rows(db, rows):
    ids = {user_id for row in rows for user_id in (row.changed_by, row.updated_by) if user_id}
    users = {user.id: user for user in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    return [{
        "id": row.id, "project_id": row.project_id, "track": "customer", "change_note": row.change_note,
        "effective_on": business_datetime(row.effective_on), "changed_at": business_datetime(row.changed_at),
        "changed_by": row.changed_by, "changed_by_name": _display_name(users.get(row.changed_by)),
        "updated_at": business_datetime(row.updated_at), "updated_by": row.updated_by,
        "updated_by_name": _display_name(users.get(row.updated_by)),
    } for row in rows]


def list_customer_progress(db, project_id):
    require_customer_progress(db)
    if not db.get(AnnotationProject, project_id):
        return None
    model = AnnotationCustomerProgress
    rows = db.query(model).filter(model.project_id == project_id).order_by(
        model.effective_on.desc(), model.changed_at.desc(), model.id.desc(),
    ).all()
    return _response_rows(db, rows)


def create_customer_progress(db, project_id, payload, user_id):
    require_customer_progress(db)
    if not db.get(AnnotationProject, project_id):
        return None
    now = business_now()
    row = AnnotationCustomerProgress(
        project_id=project_id, change_note=payload.change_note,
        effective_on=payload.effective_on, changed_by=user_id,
        changed_at=now, updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _response_rows(db, [row])[0]


def _locked_fresh_record(db, record_id, expected_updated_at):
    row = db.query(AnnotationCustomerProgress).filter(
        AnnotationCustomerProgress.id == record_id,
    ).with_for_update().populate_existing().first()
    if row and business_datetime(row.updated_at) != business_datetime(expected_updated_at):
        raise StaleUpdateError()
    return row


def update_customer_progress(db, record_id, payload, user_id):
    require_customer_progress(db)
    row = _locked_fresh_record(db, record_id, payload.expected_updated_at)
    if not row:
        return None
    row.change_note = payload.change_note
    row.effective_on = payload.effective_on
    row.updated_by = user_id
    # 确保连续操作也生成不同版本，保留原填写时间和填写人。
    row.updated_at = max(business_now(), business_datetime(row.updated_at) + timedelta(microseconds=1))
    db.commit()
    db.refresh(row)
    return _response_rows(db, [row])[0]


def delete_customer_progress(db, record_id, payload, user_id):
    require_customer_progress(db)
    row = _locked_fresh_record(db, record_id, payload.expected_updated_at)
    if not row:
        return False
    project = db.get(AnnotationProject, row.project_id)
    snapshot = _response_rows(db, [row])[0]
    audit = record_project_operation(
        db, project_type="annotation", operation_type="progress_delete", project=project,
        actor_user_id=user_id, operation_source="customer_progress_record_delete",
        change_reason=payload.reason, snapshot_extra={"deleted_progress_record": snapshot},
    )
    # 审计字段为 timestamptz，保存实际时刻，不能删除偏移后再入库。
    audit.occurred_at = business_now()
    db.delete(row)
    db.commit()
    return True


def _progress_source(model, track):
    customer = track == "customer"

    def timestamp(column):
        if customer:
            return column
        return func.timezone(
            literal(timedelta(hours=8), type_=Interval()), column, type_=DateTime(timezone=True),
        )
    return select(
        model.id, model.project_id,
        literal(None, type_=String).label("from_status") if customer else model.from_status,
        literal(None, type_=String).label("to_status") if customer else model.to_status,
        timestamp(model.effective_on).label("effective_on"), timestamp(model.changed_at).label("changed_at"),
        model.changed_by, model.change_note,
        literal("progress").label("entry_kind") if customer else model.entry_kind,
        timestamp(model.updated_at).label("updated_at"), model.updated_by, literal(track).label("track"),
    )


def search_progress_records(db, *, track, skip=0, limit=10, keyword=None, date_from=None, date_to=None):
    """统一排序、筛选和分页，在 UNION ALL 外计算总数，避免两线分别分页。"""
    available = require_customer_progress(db) if track == "customer" else customer_progress_available(db)
    sources = []
    if track in {"project", "all"}:
        sources.append(_progress_source(AnnotationProjectStatusHistory, "project"))
    if track in {"customer", "all"} and available:
        sources.append(_progress_source(AnnotationCustomerProgress, "customer"))
    records = (union_all(*sources) if len(sources) > 1 else sources[0]).subquery()
    changed_user, client_user, manager_user = aliased(AppUser), aliased(AppUser), aliased(AppUser)
    assignment = aliased(ProjectWorkbenchResponsibility)
    manager_display_name = func.coalesce(
        func.nullif(func.btrim(manager_user.full_name), ""), manager_user.username,
    )
    manager_names = (
        select(func.string_agg(func.distinct(manager_display_name), "、"))
        .select_from(assignment)
        .join(manager_user, manager_user.id == assignment.assignee_id)
        .where(
            assignment.annotation_project_id == AnnotationProject.id,
            assignment.role_code == "project_manager",
            assignment.assignee_id.isnot(None),
        )
        .correlate(AnnotationProject).scalar_subquery()
    )
    query = select(
        records, AnnotationProject.order_no.label("project_order_no"), AnnotationProject.project_name,
        AnnotationProject.project_status.label("project_current_status"),
        func.coalesce(
            func.nullif(func.btrim(changed_user.full_name), ""), changed_user.username,
        ).label("changed_by_name"),
        func.coalesce(
            func.nullif(func.btrim(client_user.full_name), ""), client_user.username,
        ).label("client_manager_name"),
        manager_names.label("project_manager_name"), func.count().over().label("page_total"),
    ).join(
        AnnotationProject, AnnotationProject.id == records.c.project_id,
    ).outerjoin(
        changed_user, changed_user.id == records.c.changed_by,
    ).outerjoin(
        client_user, client_user.id == AnnotationProject.client_manager_id,
    ).where(records.c.change_note.isnot(None), func.btrim(records.c.change_note) != "")
    if keyword is not None:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            records.c.change_note.ilike(f"%{escaped}%", escape="\\"),
            records.c.effective_on >= datetime.combine(date_from, time.min, BUSINESS_TIMEZONE),
            records.c.effective_on < datetime.combine(date_to + timedelta(days=1), time.min, BUSINESS_TIMEZONE),
        )
    ordering = [records.c.changed_at.desc(), records.c.id.desc(), records.c.track]
    if keyword is not None:
        ordering.insert(0, records.c.effective_on.desc())
    rows = db.execute(query.order_by(*ordering).offset(skip).limit(limit)).mappings().all()
    if rows:
        total = int(rows[0]["page_total"])
    elif skip:
        total = int(db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    else:
        total = 0
    items = []
    for row in rows:
        item = dict(row)
        item.pop("page_total", None)
        if item["track"] == "customer":
            item["record_type"] = "customer_progress"
        else:
            item["record_type"] = "progress" if item["entry_kind"] == "progress" else "status_change"
        for key in ("effective_on", "changed_at", "updated_at"):
            item[key] = business_datetime(item[key])
        items.append(item)
    return {"items": items, "total": total}
