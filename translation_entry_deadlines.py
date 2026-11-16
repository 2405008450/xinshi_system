"""笔译项目的录入时限和首次逾期记录。"""
from datetime import datetime, time, timedelta

from fastapi import HTTPException

from annotation_progress_time import business_datetime, business_now
from models import EmployeeLeave, TranslationProject
from translation_document_requirements import TranslationProjectDocuments, ready
from work_report_calendar import is_workday


def deadline(db, received_on, manager_id, file_count, word_count):
    if file_count >= 51 and word_count > 100_000:
        workdays = 6
    elif 11 <= file_count <= 50 and 50_000 < word_count <= 100_000:
        workdays = 4
    else:
        workdays = 2

    day = received_on + timedelta(days=1)
    # EmployeeLeave stores UTC+8 wall-clock times without a timezone.
    leaves = db.query(EmployeeLeave.start_date, EmployeeLeave.end_date).filter(
        EmployeeLeave.employee_id == manager_id,
        EmployeeLeave.end_date > datetime.combine(day, time.min),
    ).all()
    remaining = workdays
    while True:
        if is_workday(day):
            start = datetime.combine(day, time.min)
            end = start + timedelta(days=1)
            if not any(leave_start < end and leave_end > start for leave_start, leave_end in leaves):
                remaining -= 1
                if remaining == 0:
                    return {"workdays": workdays, "due_on": day}
        day += timedelta(days=1)


def incomplete_entries(node):
    from translation_customer_finance import matches_missing_fields
    from translation_direction_service import stored_directions

    # 字数按末级统计。上级采用固定收费时，其整棵子树免填单价。
    if node["children"]:
        children = [incomplete_entries(child) for child in node["children"]]
        return (
            any(words for words, _ in children),
            node["pricing_mode"] != "fixed" and any(price for _, price in children),
        )
    prices = node.get("prices") or []
    missing_price = bool(
        node["pricing_mode"] != "fixed" and (
            not prices or matches_missing_fields(node, unit_price=True)
            or set(stored_directions(node.get("language_pair"))) - {price.get("language_pair") for price in prices}
        )
    )
    return matches_missing_fields(node, word_count=True), missing_price


def project_status(db, project_id):
    """调用方负责事务提交。锁定母订单，同一项目的首次逾期只登记一次。"""
    import crud
    from translation_customer_finance import tree

    locked = db.query(TranslationProject.id).filter_by(
        id=project_id, annotation_migrated_at=None,
    ).with_for_update().first()
    if not locked:
        return None
    project = crud.get_translation_project(db, project_id, refresh=True)
    if not project:
        return None
    documents = db.get(TranslationProjectDocuments, project_id, populate_existing=True) if ready(db) else None
    data = dict(documents.quotation_data or {}) if documents else {}
    history = dict(data.get("_entry_deadline_overdue", {}))
    status = {"first_overdue": history, "overdue": {}}
    manager_id = project.client_manager_id
    matrix = project.word_count_matrix
    rows = [matrix.get(key, {}) for key in ("company", "customer", "preliminary", "translator_estimate")]
    files = next((row["documents"] for row in rows if row.get("documents")), None)
    words = next((row["words"] for row in rows if row.get("words") is not None), None)
    if not (project.customer_reception_time and manager_id and files and words is not None):
        return status

    received = business_datetime(project.customer_reception_time).date()
    try:
        status.update(deadline(db, received, manager_id, files, words))
    except HTTPException as error:
        return {**status, "calendar_error": error.detail}

    now = business_now()
    if now.date() <= status["due_on"]:
        return status
    missing = incomplete_entries(tree(project, summary_only=True, include_version=False)["item"])
    due_on = status["due_on"]
    status["overdue"] = dict(zip(("word_count", "unit_price"), missing))
    updated = {**history}
    for key, overdue in status["overdue"].items():
        if overdue and key not in updated:
            updated[key] = {
                "due_on": due_on.isoformat(),
                "overdue_on": (due_on + timedelta(days=1)).isoformat(),
                "recorded_at": now.isoformat(),
            }
    if updated != history:
        if documents is None:
            if not ready(db):
                return {**status, "record_error": "录入逾期记录存储尚未初始化"}
            documents = TranslationProjectDocuments(project_id=project_id, quotation_revision=0)
            db.add(documents)
        documents.quotation_data = {**data, "_entry_deadline_overdue": updated}
        status["first_overdue"] = updated
    return status
