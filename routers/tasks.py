"""统一工作项、非项目任务、工作记录和个人日报接口。"""
from datetime import date
from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from daily_report_mail_schemas import (
    DailyReportMailAccountStatus,
    DailyReportMailAccountWrite,
    DailyReportMailDeliveryResponse,
    DailyReportMailPreviewResponse,
    DailyReportMailSendRequest,
)
from daily_report_mail_service import (
    build_daily_report_mail_preview,
    delete_mail_account,
    list_daily_report_deliveries,
    save_mail_account,
    send_daily_report_mail,
    serialize_delivery,
    serialize_mail_account,
    verify_mail_account,
)
from models import AppUser
from pydantic import BaseModel, Field
from work_report_categories import add_category, category_catalog
import work_report_access as report_access
import work_report_collaboration as report_collaboration
from permission_service import user_has_permission
from routers.auth import get_current_user, require_permission
from task_models import DailyReport, NonProjectTaskRecurrence
from task_schemas import (
    DailyReportResponse,
    DailyReportSaveRequest,
    NonProjectTaskCreate,
    NonProjectTaskResponse,
    NonProjectTaskUpdate,
    RecurrenceCreate,
    RecurrenceResponse,
    TaskStatusChange,
    WorkEntryCreate,
    WorkEntryResponse,
    WorkEntryUpdate,
    WorkItemResponse,
)
from task_service import (
    change_task_status,
    create_non_project_task,
    create_recurrence,
    create_work_entry,
    generate_recurrence_instances,
    get_my_work_items,
    get_non_project_task,
    list_non_project_tasks,
    list_work_entries,
    preview_daily_report,
    report_to_xlsx,
    save_daily_report,
    serialize_non_project_task,
    serialize_report,
    update_non_project_task,
    update_work_entry,
    withdraw_daily_report,
)


work_items_router = APIRouter(prefix="/work-items", tags=["work-items"])
tasks_router = APIRouter(prefix="/non-project-tasks", tags=["non-project-tasks"])
entries_router = APIRouter(prefix="/work-entries", tags=["work-entries"])
reports_router = APIRouter(prefix="/daily-reports", tags=["daily-reports"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _ensure_permission(db: Session, user: AppUser, permission: str) -> None:
    if not user_has_permission(db, user.id, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限：{permission}",
        )


@work_items_router.get(
    "/my",
    response_model=list[WorkItemResponse],
    dependencies=[Depends(require_permission("tasks:read"))],
)
def my_work_items(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return get_my_work_items(db, current_user)


@tasks_router.post("", response_model=NonProjectTaskResponse, status_code=201)
def create_task(
    payload: NonProjectTaskCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    try:
        return serialize_non_project_task(
            create_non_project_task(db, current_user, payload)
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@tasks_router.get(
    "",
    response_model=list[NonProjectTaskResponse],
    dependencies=[Depends(require_permission("tasks:read"))],
)
def list_tasks(
    include_created: bool = False,
    task_status: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return [
        serialize_non_project_task(item)
        for item in list_non_project_tasks(
            db, current_user, include_created=include_created, status=task_status
        )
    ]


@tasks_router.patch("/{task_id}", response_model=NonProjectTaskResponse)
def update_task(
    task_id: UUID,
    payload: NonProjectTaskUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    try:
        return serialize_non_project_task(
            update_non_project_task(db, task_id, current_user, payload)
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@tasks_router.post("/{task_id}/actions/{action}", response_model=NonProjectTaskResponse)
def task_action(
    task_id: UUID,
    action: str,
    payload: TaskStatusChange,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    try:
        return serialize_non_project_task(
            change_task_status(db, task_id, current_user, action, payload.note)
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@tasks_router.post(
    "/recurrences",
    response_model=RecurrenceResponse,
    status_code=201,
)
def create_task_recurrence(
    payload: RecurrenceCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    try:
        return create_recurrence(db, current_user, payload)
    except (PermissionError, LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@tasks_router.get(
    "/recurrences",
    response_model=list[RecurrenceResponse],
    dependencies=[Depends(require_permission("tasks:read"))],
)
def list_task_recurrences(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return (
        db.query(NonProjectTaskRecurrence)
        .filter(
            (NonProjectTaskRecurrence.assignee_id == current_user.id)
            | (NonProjectTaskRecurrence.assigner_id == current_user.id)
        )
        .order_by(NonProjectTaskRecurrence.created_at.desc())
        .all()
    )


@tasks_router.patch(
    "/recurrences/{recurrence_id}/active",
    response_model=RecurrenceResponse,
)
def set_recurrence_active(
    recurrence_id: UUID,
    active: bool,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    rule = (
        db.query(NonProjectTaskRecurrence)
        .filter(NonProjectTaskRecurrence.id == recurrence_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="周期任务不存在")
    if (
        rule.assigner_id != current_user.id
        and not user_has_permission(db, current_user.id, "tasks:assign")
    ):
        raise HTTPException(status_code=403, detail="无权修改该周期任务")
    rule.is_active = active
    db.commit()
    db.refresh(rule)
    return rule


@tasks_router.post("/recurrences/generate")
def generate_recurrences(
    through_date: date,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:assign")
    try:
        return {"created_count": generate_recurrence_instances(db, through_date)}
    except ValueError as exc:
        raise _http_error(exc) from exc


@entries_router.post("", response_model=WorkEntryResponse, status_code=201)
def add_work_entry(
    payload: WorkEntryCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    try:
        return create_work_entry(db, current_user, payload)
    except (PermissionError, LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@entries_router.get(
    "",
    response_model=list[WorkEntryResponse],
    dependencies=[Depends(require_permission("tasks:read"))],
)
def get_work_entries(
    work_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return list_work_entries(db, current_user.id, work_date)


@entries_router.patch("/{entry_id}", response_model=WorkEntryResponse)
def edit_work_entry(
    entry_id: UUID,
    payload: WorkEntryUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    _ensure_permission(db, current_user, "tasks:self_write")
    try:
        return update_work_entry(db, entry_id, current_user, payload)
    except (PermissionError, LookupError, ValueError) as exc:
        raise _http_error(exc) from exc


@reports_router.get('/access-context')
def report_access_context(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.access_context(db, user)


@reports_router.get('/access-settings')
def report_access_settings(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.settings(db, user)


@reports_router.post('/access-settings')
def create_report_access_rule(payload: report_access.AccessRuleWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.save_rule(db, user, payload)


@reports_router.put('/access-settings/{rule_id}')
def update_report_access_rule(rule_id: UUID, payload: report_access.AccessRuleWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.save_rule(db, user, payload, rule_id)


@reports_router.get('/review-directory')
def report_review_directory(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.review_directory(db,user)


@reports_router.get('/statistics')
def work_report_statistics(anchor: date, period: str='day', department_id: Optional[UUID]=None, keyword: Optional[str]=None,sender_id:Optional[UUID]=None, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.report_statistics(db,user,anchor,period,department_id,keyword,sender_id)


@reports_router.get('/feedback-inbox')
def work_report_feedback_inbox(date_from: Optional[date]=None,date_to: Optional[date]=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_collaboration.feedback_inbox(db,user,date_from,date_to,page,page_size)


@reports_router.get('/feedback/{report_id}')
def work_report_feedback(report_id:UUID,db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_collaboration.feedback_rows(db,user,report_id)


@reports_router.post('/feedback/{report_id}')
def write_work_report_feedback(report_id:UUID,payload:report_collaboration.FeedbackWrite,db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_collaboration.add_feedback(db,user,report_id,payload)


@reports_router.get('/history/{report_id}')
def work_report_history(report_id:UUID,db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_collaboration.revision_history(db,user,report_id)


@reports_router.post('/{report_date}/amend',response_model=DailyReportResponse,dependencies=[Depends(require_permission('reports:read'))])
def amend_work_report(report_date:date,payload:DailyReportSaveRequest,db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    try:return serialize_report(save_daily_report(db,user,report_date,payload,finalize=True,amend=True))
    except (ValueError,PermissionError) as exc:raise _http_error(exc) from exc


@reports_router.get('/received-senders')
def received_report_senders(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    ids = report_access.sender_ids_for_rules(db, report_access.receiving_rules(db, user))
    return [{'id': str(person.id), 'name': person.full_name or person.username, 'username': person.username} for person in report_access.active_people(db).filter(AppUser.id.in_(ids)).order_by(AppUser.full_name, AppUser.username)]


@reports_router.get('/received')
def list_received_reports(date_from: Optional[date] = None, date_to: Optional[date] = None, sender_id: Optional[UUID] = None, department_id:Optional[UUID]=None,keyword:Optional[str]=None,page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.received_reports(db, user, date_from, date_to, sender_id, page, page_size,department_id,keyword)


@reports_router.get('/received/{report_id}')
def read_received_report(report_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return report_access.received_report(db, user, report_id)


@reports_router.get("/editor-context", dependencies=[Depends(require_permission("reports:read"))])
def report_editor_context(db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    from department_models import Department, DepartmentMember
    from organization_service import ready
    from task_models import DailyReportItem
    names = [current_user.department] if current_user.department else []
    if ready(db):
        names.extend(name for name, in db.query(Department.name).join(DepartmentMember, Department.id == DepartmentMember.department_id).filter(DepartmentMember.user_id == current_user.id).order_by(Department.name))
    history = db.query(DailyReportItem.progress_content).join(DailyReport, DailyReport.id == DailyReportItem.report_id).filter(DailyReport.user_id == current_user.id).order_by(DailyReport.report_date.desc(), DailyReportItem.sort_order).limit(500).all()
    return {"user_name": current_user.full_name or current_user.username, "departments": list(dict.fromkeys(names)), "task_history": list(dict.fromkeys(text.strip() for text, in history if text and text.strip()))[:200], **category_catalog(db, current_user)}


class ReportCategoryCreate(BaseModel):
    parent: str = Field(max_length=20)
    name: str = Field(min_length=1, max_length=80)


@reports_router.post('/categories', dependencies=[Depends(require_permission('reports:read'))])
def create_report_category(payload: ReportCategoryCreate, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    try:
        return add_category(db, current_user, payload.parent, payload.name)
    except (ValueError, PermissionError) as exc:
        raise _http_error(exc) from exc


@reports_router.get(
    "/preview",
    response_model=DailyReportResponse,
    dependencies=[Depends(require_permission("reports:read"))],
)
def report_preview(
    report_date: date,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return preview_daily_report(db, current_user, report_date, refresh=refresh)


@reports_router.get(
    "/mail-account",
    response_model=DailyReportMailAccountStatus,
    dependencies=[Depends(require_permission("reports:read"))],
)
def read_mail_account(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return serialize_mail_account(db, current_user)


@reports_router.put(
    "/mail-account",
    response_model=DailyReportMailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def bind_mail_account(
    payload: DailyReportMailAccountWrite,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return save_mail_account(db, current_user, payload.authorization_code)
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc


@reports_router.post(
    "/mail-account/verify",
    response_model=DailyReportMailAccountStatus,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def verify_current_mail_account(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return verify_mail_account(db, current_user)
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc


@reports_router.delete(
    "/mail-account",
    status_code=204,
    dependencies=[Depends(require_permission("system:users:write"))],
)
def remove_mail_account(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    delete_mail_account(db, current_user)


@reports_router.put(
    "/{report_date}",
    response_model=DailyReportResponse,
    dependencies=[Depends(require_permission("reports:read"))],
)
def save_report(
    report_date: date,
    payload: DailyReportSaveRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return serialize_report(
            save_daily_report(db, current_user, report_date, payload)
        )
    except (ValueError, PermissionError) as exc:
        raise _http_error(exc) from exc


@reports_router.post(
    "/{report_date}/finalize",
    response_model=DailyReportResponse,
    dependencies=[Depends(require_permission("reports:read"))],
)
def finalize_report(
    report_date: date,
    payload: DailyReportSaveRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return serialize_report(
            save_daily_report(
                db, current_user, report_date, payload, finalize=True
            )
        )
    except (ValueError, PermissionError) as exc:
        raise _http_error(exc) from exc


@reports_router.post(
    "/{report_date}/withdraw",
    response_model=DailyReportResponse,
    dependencies=[Depends(require_permission("reports:read"))],
)
def withdraw_report(
    report_date: date,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return serialize_report(withdraw_daily_report(db, current_user, report_date))
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise _http_error(exc) from exc


@reports_router.get(
    "/{report_date}/mail-preview",
    response_model=DailyReportMailPreviewResponse,
    dependencies=[Depends(require_permission("reports:read"))],
)
def report_mail_preview(
    report_date: date,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return build_daily_report_mail_preview(db, current_user, report_date)
    except Exception as exc:
        raise _http_error(exc) from exc


@reports_router.post(
    "/{report_date}/send",
    response_model=DailyReportMailDeliveryResponse,
    dependencies=[Depends(require_permission("reports:read"))],
)
def send_report_mail(
    report_date: date,
    payload: DailyReportMailSendRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return serialize_delivery(send_daily_report_mail(db, current_user, report_date, payload))
    except Exception as exc:
        db.rollback()
        raise _http_error(exc) from exc


@reports_router.get(
    "/{report_date}/deliveries",
    response_model=list[DailyReportMailDeliveryResponse],
    dependencies=[Depends(require_permission("reports:read"))],
)
def report_mail_deliveries(
    report_date: date,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return [
        serialize_delivery(item)
        for item in list_daily_report_deliveries(db, current_user.id, report_date)
    ]


@reports_router.get(
    "/{report_date}/export",
    dependencies=[Depends(require_permission("reports:export"))],
)
def export_report(
    report_date: date,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    report = (
        db.query(DailyReport)
        .filter(
            DailyReport.user_id == current_user.id,
            DailyReport.report_date == report_date,
        )
        .first()
    )
    if not report or report.status != "finalized":
        raise HTTPException(status_code=409, detail="请先确认日报再导出")
    content = report_to_xlsx(report)
    filename = f"daily-report-{report_date.isoformat()}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
