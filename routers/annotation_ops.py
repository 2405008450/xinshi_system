"""标注运营 API。"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from annotation_custom_field_service import create_custom_field, deactivate_custom_field, list_custom_fields, update_custom_field
from annotation_custom_field_image_service import (
    IMAGE_SIGNATURES,
    MAX_IMAGE_BYTES,
    create_custom_field_image,
    delete_pending_custom_field_image,
    get_accessible_custom_field_image,
    get_custom_field_image_dir,
)
from annotation_account_import_service import (
    decode_json_list, decode_json_object, import_accounts, parse_import_payload,
)
from annotation_ops_schemas import (
    AccountAnnotatorOccupancyResponse, AccountAssignmentResponse, AccountAssignmentWrite, AccountBatchResult, AccountBatchWrite, AccountReleaseWrite,
    AccountPersonProfileResponse, AccountResponse, AccountStatsResponse, AccountWrite,
    AnnotationWorkflowResponse, AnnotationWorkflowWrite,
    AssigneeRateResponse, AssigneeRateWrite, CredentialBatchRevealItem, CredentialBatchRevealRequest,
    CredentialRevealRequest, CredentialRevealResponse,
    CustomFieldImageResponse, CustomFieldResponse, CustomFieldWrite, PlatformResponse, PlatformWrite,
    ReleaseAllResponse, StatusHistoryResponse, TrialResponse, TrialWrite,
)
from annotation_ops_service import (
    account_stats, assign_account, batch_save_accounts, count_accounts, count_platforms, count_trials,
    delete_account, delete_annotation_workflow, delete_assignee_rate, delete_platform, delete_trial,
    get_account_person_profile, list_account_assignments, list_accounts, list_annotator_occupancy, list_annotation_workflow, list_person_accounts,
    list_platforms, list_status_history, list_trials, release_account, release_all_person_accounts,
    reveal_credential, reveal_credentials_batch, save_account, save_annotation_workflow, save_assignee_rate, save_platform, save_trial,
)
from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(prefix="/annotation-ops", tags=["annotation_ops"])
account_router = APIRouter(dependencies=[Depends(require_any_permission(
    "annotation_accounts:read", "annotation_accounts:write",
))])
project_router = APIRouter(dependencies=[Depends(require_module_access("projects:read", "projects:write"))])


def _run(db: Session, callback):
    try:
        return callback()
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        detail = str(exc.orig) if isinstance(exc, IntegrityError) else str(exc)
        raise HTTPException(status_code=400, detail=detail)


@account_router.get("/platforms", response_model=List[PlatformResponse], dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def platforms(client_id: Optional[UUID] = None, skip: int = 0, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return list_platforms(db, client_id, skip, limit)


@account_router.get("/platforms/count", dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def platforms_count(client_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return {"total": count_platforms(db, client_id)}


@account_router.post("/platforms", response_model=PlatformResponse, status_code=201, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def create_platform(payload: PlatformWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return _run(db, lambda: save_platform(db, payload, user.id))


@account_router.put("/platforms/{platform_id}", response_model=PlatformResponse, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def edit_platform(platform_id: UUID, payload: PlatformWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = _run(db, lambda: save_platform(db, payload, user.id, platform_id))
    if not row: raise HTTPException(404, "标注平台不存在")
    return row


@account_router.delete("/platforms/{platform_id}", status_code=204, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def remove_platform(platform_id: UUID, db: Session = Depends(get_db)):
    if not delete_platform(db, platform_id): raise HTTPException(404, "标注平台不存在")


def _account_filters(
    client_id=None, platform_id=None, project_id=None, person_id=None,
    assignment_state=None, account_status=None, registration_status=None,
    language_item_id=None, keyword=None,
):
    return {key: value for key, value in locals().items() if value is not None}


@account_router.get("/accounts", response_model=List[AccountResponse], dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def accounts(
    client_id: Optional[UUID] = None, platform_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None, person_id: Optional[UUID] = None,
    assignment_state: Optional[str] = None, account_status: Optional[str] = None,
    registration_status: Optional[str] = None, language_item_id: Optional[UUID] = None,
    keyword: Optional[str] = None, skip: int = 0, limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_accounts(db, skip, limit, **_account_filters(client_id, platform_id, project_id, person_id, assignment_state, account_status, registration_status, language_item_id, keyword))


@account_router.get("/accounts/count", dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def accounts_count(
    client_id: Optional[UUID] = None, platform_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None, person_id: Optional[UUID] = None,
    assignment_state: Optional[str] = None, account_status: Optional[str] = None,
    registration_status: Optional[str] = None, language_item_id: Optional[UUID] = None,
    keyword: Optional[str] = None, db: Session = Depends(get_db),
):
    return {"total": count_accounts(db, **_account_filters(client_id, platform_id, project_id, person_id, assignment_state, account_status, registration_status, language_item_id, keyword))}


@account_router.post("/accounts", response_model=AccountResponse, status_code=201, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def create_account(payload: AccountWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return _run(db, lambda: save_account(db, payload, user.id))


@account_router.post("/accounts/batch-save", response_model=AccountBatchResult, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def save_accounts_batch(payload: AccountBatchWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return batch_save_accounts(db, payload.client_id, payload.rows, user.id)


@account_router.post(
    "/accounts/import/preview",
    dependencies=[Depends(require_any_permission("annotation_accounts:write"))],
)
async def preview_accounts_import(
    file: UploadFile = File(...), defaults_json: str = Form(...),
    sheet_name: Optional[str] = Form(None), header_row: Optional[int] = Form(None),
    mapping_json: Optional[str] = Form(None), db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "暂时只支持 .xlsx 文件")
    content = await file.read()
    try:
        result = parse_import_payload(
            db, content, decode_json_object(defaults_json, "批次默认值"),
            sheet_name=sheet_name, header_row=header_row,
            mapping=decode_json_list(mapping_json, "字段映射"),
        )
        result.pop("_parsedRows", None)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@account_router.post(
    "/accounts/import",
    dependencies=[Depends(require_any_permission("annotation_accounts:write"))],
)
async def commit_accounts_import(
    file: UploadFile = File(...), defaults_json: str = Form(...),
    sheet_name: Optional[str] = Form(None), header_row: Optional[int] = Form(None),
    mapping_json: str = Form(...), db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "暂时只支持 .xlsx 文件")
    content = await file.read()
    try:
        return import_accounts(
            db, content, decode_json_object(defaults_json, "批次默认值"), user.id,
            sheet_name=sheet_name, header_row=header_row,
            mapping=decode_json_list(mapping_json, "字段映射"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@account_router.get(
    "/accounts/annotator-occupancy",
    response_model=List[AccountAnnotatorOccupancyResponse],
    dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))],
)
def annotator_occupancy(project_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    return list_annotator_occupancy(db, project_id)


@account_router.post(
    "/accounts/batch-reveal", response_model=List[CredentialBatchRevealItem],
    dependencies=[Depends(require_any_permission("annotation_accounts:reveal"))],
)
def reveal_accounts_batch(payload: CredentialBatchRevealRequest, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return reveal_credentials_batch(
        db, payload.account_ids, user, payload.access_reason,
        request.client.host if request.client else None,
    )


@account_router.put("/accounts/{account_id}", response_model=AccountResponse, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def edit_account(account_id: UUID, payload: AccountWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = _run(db, lambda: save_account(db, payload, user.id, account_id))
    if not row: raise HTTPException(404, "平台账号不存在")
    return row


@account_router.delete("/accounts/{account_id}", status_code=204, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def remove_account(account_id: UUID, db: Session = Depends(get_db)):
    if not delete_account(db, account_id): raise HTTPException(404, "平台账号不存在")


@account_router.post("/accounts/{account_id}/assign", response_model=AccountAssignmentResponse, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def assign(account_id: UUID, payload: AccountAssignmentWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = _run(db, lambda: assign_account(db, account_id, payload, user.id))
    if not row: raise HTTPException(404, "平台账号不存在")
    return row


@account_router.post("/accounts/{account_id}/release", response_model=AccountAssignmentResponse, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def release(account_id: UUID, payload: AccountReleaseWrite, db: Session = Depends(get_db)):
    row = _run(db, lambda: release_account(db, account_id, payload))
    if not row: raise HTTPException(404, "平台账号不存在")
    return row


@account_router.get("/accounts/{account_id}/assignments", response_model=List[AccountAssignmentResponse], dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def assignments(account_id: UUID, db: Session = Depends(get_db)):
    return list_account_assignments(db, account_id)


@account_router.post(
    "/accounts/{account_id}/reveal", response_model=CredentialRevealResponse,
    dependencies=[Depends(require_any_permission("annotation_accounts:reveal"))],
)
def reveal(account_id: UUID, payload: CredentialRevealRequest, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = _run(db, lambda: reveal_credential(db, account_id, user, payload.access_reason, request.client.host if request.client else None))
    if not row: raise HTTPException(404, "平台账号不存在")
    return row


@account_router.get("/account-stats", response_model=List[AccountStatsResponse], dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def stats(client_id: Optional[UUID] = None, expiring_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return account_stats(db, client_id, expiring_days)


@account_router.get("/persons/{person_id}/accounts", response_model=List[AccountResponse], dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))])
def person_accounts(person_id: UUID, include_history: bool = False, db: Session = Depends(get_db)):
    return list_person_accounts(db, person_id, include_history)


@account_router.get(
    "/persons/{person_id}/profile", response_model=AccountPersonProfileResponse,
    dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))],
)
def person_profile(person_id: UUID, db: Session = Depends(get_db)):
    row = get_account_person_profile(db, person_id)
    if not row:
        raise HTTPException(404, "人才档案不存在")
    return row


@account_router.post("/persons/{person_id}/release-all", response_model=ReleaseAllResponse, dependencies=[Depends(require_any_permission("annotation_accounts:write"))])
def release_all(person_id: UUID, payload: AccountReleaseWrite, db: Session = Depends(get_db)):
    return {"released_count": _run(db, lambda: release_all_person_accounts(db, person_id, payload))}


@project_router.get("/trials", response_model=List[TrialResponse])
def trials(project_id: Optional[UUID] = None, skip: int = 0, limit: int = Query(100, ge=1, le=500), keyword: Optional[str] = None, trial_status: Optional[str] = None, db: Session = Depends(get_db)):
    return list_trials(db, project_id, skip, limit, keyword, trial_status)


@project_router.get("/trials/count")
def trials_count(project_id: Optional[UUID] = None, keyword: Optional[str] = None, trial_status: Optional[str] = None, db: Session = Depends(get_db)):
    return {"total": count_trials(db, project_id, keyword, trial_status)}


@project_router.post("/trials", response_model=TrialResponse, status_code=201, dependencies=[Depends(require_any_permission("projects:write"))])
def create_trial(payload: TrialWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return _run(db, lambda: save_trial(db, payload, user.id))


@project_router.put("/trials/{trial_id}", response_model=TrialResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def edit_trial(trial_id: UUID, payload: TrialWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = _run(db, lambda: save_trial(db, payload, user.id, trial_id))
    if not row: raise HTTPException(404, "试标记录不存在")
    return row


@project_router.delete("/trials/{trial_id}", status_code=204, dependencies=[Depends(require_any_permission("projects:write"))])
def remove_trial(trial_id: UUID, db: Session = Depends(get_db)):
    if not delete_trial(db, trial_id): raise HTTPException(404, "试标记录不存在")


@project_router.put("/assignees/{assignee_id}/rate", response_model=AssigneeRateResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def upsert_rate(assignee_id: UUID, payload: AssigneeRateWrite, db: Session = Depends(get_db)):
    row = _run(db, lambda: save_assignee_rate(db, assignee_id, payload))
    if not row: raise HTTPException(404, "正式安排不存在")
    return row


@project_router.delete("/assignees/{assignee_id}/rate", status_code=204, dependencies=[Depends(require_any_permission("projects:write"))])
def remove_rate(assignee_id: UUID, db: Session = Depends(get_db)):
    if not delete_assignee_rate(db, assignee_id): raise HTTPException(404, "计价记录不存在")


@project_router.get("/projects/{project_id}/workflow", response_model=List[AnnotationWorkflowResponse])
def workflow_rows(project_id: UUID, language_item_id: Optional[UUID] = None, keyword: Optional[str] = None, assignment_role: Optional[str] = None, assignment_status: Optional[str] = None, db: Session = Depends(get_db)):
    return list_annotation_workflow(db, project_id, language_item_id, keyword, assignment_role, assignment_status)


@project_router.get("/workflow", response_model=List[AnnotationWorkflowResponse])
def all_workflow_rows(project_id: Optional[UUID] = None, language_item_id: Optional[UUID] = None, keyword: Optional[str] = None, assignment_role: Optional[str] = None, assignment_status: Optional[str] = None, db: Session = Depends(get_db)):
    return list_annotation_workflow(db, project_id, language_item_id, keyword, assignment_role, assignment_status)


@project_router.post(
    "/projects/{project_id}/workflow", response_model=AnnotationWorkflowResponse,
    status_code=201, dependencies=[Depends(require_any_permission("projects:write"))],
)
def create_workflow_row(project_id: UUID, payload: AnnotationWorkflowWrite, db: Session = Depends(get_db)):
    return _run(db, lambda: save_annotation_workflow(db, project_id, payload))


@project_router.put(
    "/projects/{project_id}/workflow/{assignee_id}", response_model=AnnotationWorkflowResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def edit_workflow_row(project_id: UUID, assignee_id: UUID, payload: AnnotationWorkflowWrite, db: Session = Depends(get_db)):
    row = _run(db, lambda: save_annotation_workflow(db, project_id, payload, assignee_id))
    if not row:
        raise HTTPException(404, "标注流程记录不存在")
    return row


@project_router.delete(
    "/projects/{project_id}/workflow/{assignee_id}", status_code=204,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def remove_workflow_row(project_id: UUID, assignee_id: UUID, db: Session = Depends(get_db)):
    if not delete_annotation_workflow(db, project_id, assignee_id):
        raise HTTPException(404, "标注流程记录不存在")


@project_router.get("/projects/{project_id}/status-history", response_model=List[StatusHistoryResponse])
def status_history(project_id: UUID, db: Session = Depends(get_db)):
    return list_status_history(db, project_id)


@project_router.get("/custom-fields", response_model=List[CustomFieldResponse])
def custom_fields(table_code: str, project_id: Optional[UUID] = None, include_inactive: bool = False, db: Session = Depends(get_db)):
    return _run(db, lambda: list_custom_fields(db, table_code, project_id, include_inactive))


@project_router.post("/custom-fields", response_model=CustomFieldResponse, status_code=201, dependencies=[Depends(require_any_permission("projects:write"))])
def create_field(payload: CustomFieldWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return _run(db, lambda: create_custom_field(db, payload, user.id))


@project_router.put("/custom-fields/{field_id}", response_model=CustomFieldResponse, dependencies=[Depends(require_any_permission("projects:write"))])
def edit_field(field_id: UUID, payload: CustomFieldWrite, db: Session = Depends(get_db)):
    row = _run(db, lambda: update_custom_field(db, field_id, payload))
    if not row: raise HTTPException(404, "动态字段不存在")
    return row


@project_router.delete("/custom-fields/{field_id}", status_code=204, dependencies=[Depends(require_any_permission("projects:write"))])
def deactivate_field(field_id: UUID, db: Session = Depends(get_db)):
    if not deactivate_custom_field(db, field_id): raise HTTPException(404, "动态字段不存在")


@account_router.post(
    "/custom-field-images",
    response_model=CustomFieldImageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("annotation_accounts:write"))],
)
async def upload_custom_field_image(
    project_id: UUID = Form(...),
    field_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    content_type = (file.content_type or "").lower()
    if content_type not in IMAGE_SIGNATURES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "仅支持 JPEG、PNG、GIF、WebP 图片")
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "单张图片不能超过 10MB")
    try:
        return create_custom_field_image(
            db,
            project_id=project_id,
            field_id=field_id,
            uploaded_by=user.id,
            original_name=file.filename or "image",
            content_type=content_type,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@account_router.get(
    "/custom-field-images/{image_id}",
    dependencies=[Depends(require_any_permission("annotation_accounts:read", "annotation_accounts:write"))],
)
def read_custom_field_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    image = get_accessible_custom_field_image(db, image_id, user.id)
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    path = get_custom_field_image_dir() / image.storage_name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片文件不存在")
    return FileResponse(path, media_type=image.content_type, filename=image.original_name, content_disposition_type="inline")


@account_router.delete(
    "/custom-field-images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_any_permission("annotation_accounts:write"))],
)
def remove_pending_custom_field_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    try:
        deleted = delete_pending_custom_field_image(db, image_id, user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "待保存图片不存在")


router.include_router(account_router)
router.include_router(project_router)
