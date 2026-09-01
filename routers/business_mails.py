"""内部项目邮件组、策略和发送 API。"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from business_mail_schemas import (
    BusinessMailPreviewRequest, BusinessMailPreviewResponse, BusinessMailResponse,
    BusinessMailSendRequest, MailRecipientGroupResponse, MailRecipientGroupWrite,
    ProjectMailPolicyResponse, ProjectMailPolicyWrite, ProjectMailStatusResponse,
)
from daily_report_mail_schemas import DailyReportMailPolicyResponse, DailyReportMailPolicyWrite
from daily_report_mail_service import list_daily_report_policies, save_daily_report_policy
from business_mail_service import (
    build_preview, create_and_send, delete_group, list_groups, list_mails,
    retry_mail, save_group, save_policy, serialize_group, serialize_mail,
    serialize_policy, _policy,
)
from database import get_db
from mail_service import get_mail_status
from routers.auth import get_current_user, require_any_permission, require_module_access


settings_router = APIRouter(
    prefix="/mail-settings", tags=["mail-settings"],
    dependencies=[Depends(require_module_access("system:mail_settings:read", "system:mail_settings:write"))],
)
mail_router = APIRouter(prefix="/project-mails", tags=["project-mails"])


def _raise(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc))
    raise exc


@settings_router.get("/status", response_model=ProjectMailStatusResponse)
def read_status():
    return get_mail_status()


@settings_router.get("/groups", response_model=list[MailRecipientGroupResponse])
def read_groups(db: Session = Depends(get_db)):
    return [serialize_group(item) for item in list_groups(db)]


@settings_router.post("/groups", response_model=MailRecipientGroupResponse, status_code=201)
def create_group(payload: MailRecipientGroupWrite, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        return serialize_group(save_group(db, payload, current_user.id))
    except Exception as exc:
        db.rollback(); _raise(exc)


@settings_router.put("/groups/{group_id}", response_model=MailRecipientGroupResponse)
def update_group(group_id: UUID, payload: MailRecipientGroupWrite, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        return serialize_group(save_group(db, payload, current_user.id, group_id))
    except Exception as exc:
        db.rollback(); _raise(exc)


@settings_router.delete("/groups/{group_id}", status_code=204)
def remove_group(group_id: UUID, db: Session = Depends(get_db)):
    try:
        if not delete_group(db, group_id):
            raise HTTPException(status_code=404, detail="邮件组不存在")
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback(); _raise(exc)


@settings_router.get("/policies/{project_type}", response_model=ProjectMailPolicyResponse)
def read_policy(project_type: str, db: Session = Depends(get_db)):
    try:
        return serialize_policy(_policy(db, project_type), project_type)
    except Exception as exc:
        _raise(exc)


@settings_router.put("/policies/{project_type}", response_model=ProjectMailPolicyResponse)
def update_policy(project_type: str, payload: ProjectMailPolicyWrite, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        return serialize_policy(save_policy(db, project_type, payload, current_user.id), project_type)
    except Exception as exc:
        db.rollback(); _raise(exc)


@settings_router.get("/daily-report-policies", response_model=list[DailyReportMailPolicyResponse])
def read_daily_report_policies(db: Session = Depends(get_db)):
    return list_daily_report_policies(db)


@settings_router.put("/daily-report-policies/{user_id}", response_model=DailyReportMailPolicyResponse)
def update_daily_report_policy(
    user_id: UUID,
    payload: DailyReportMailPolicyWrite,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return save_daily_report_policy(db, user_id, payload, current_user.id)
    except Exception as exc:
        db.rollback(); _raise(exc)


@mail_router.post("/preview", response_model=BusinessMailPreviewResponse, dependencies=[Depends(require_any_permission("consultations:write", "projects:write"))])
def preview(
    payload: BusinessMailPreviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return build_preview(
            db,
            payload.project_type,
            project_id=payload.project_id,
            source=payload.source,
            current_user=current_user,
        )
    except Exception as exc:
        _raise(exc)


@mail_router.get(
    "/recipient-groups",
    response_model=list[MailRecipientGroupResponse],
    dependencies=[Depends(require_any_permission("consultations:write", "projects:write"))],
)
def available_recipient_groups(db: Session = Depends(get_db)):
    return [serialize_group(item) for item in list_groups(db) if item.is_active]


@mail_router.post("/", response_model=BusinessMailResponse, dependencies=[Depends(require_any_permission("consultations:write", "projects:write"))])
def send(payload: BusinessMailSendRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        return serialize_mail(create_and_send(db, payload, current_user))
    except Exception as exc:
        db.rollback(); _raise(exc)


@mail_router.post("/{mail_id}/retry", response_model=BusinessMailResponse, dependencies=[Depends(require_any_permission("consultations:write", "projects:write"))])
def retry(
    mail_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return serialize_mail(retry_mail(db, mail_id, current_user))
    except Exception as exc:
        db.rollback(); _raise(exc)


@mail_router.get("/", response_model=list[BusinessMailResponse], dependencies=[Depends(require_any_permission("consultations:read", "projects:read"))])
def history(consultation_id: Optional[UUID] = None, project_type: Optional[str] = Query(None), project_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    try:
        return [serialize_mail(item) for item in list_mails(db, consultation_id=consultation_id, project_type=project_type, project_id=project_id)]
    except Exception as exc:
        _raise(exc)
