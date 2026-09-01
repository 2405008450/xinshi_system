"""稿件安排 API。"""
import json
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from mail_service import (
    MailAttachment,
    MailConfigurationError,
    MailDeliveryError,
    get_mail_status,
)
from mail_inline_image_service import load_owned_images, load_owned_or_bound_images
from manuscript_schemas import (
    ManuscriptArrangementContext,
    ManuscriptArrangementCreate,
    ManuscriptArrangementResponse,
    ManuscriptArrangementUpdate,
    ManuscriptBatchSendResponse,
    ManuscriptDispatchCreate,
    ManuscriptDispatchResponse,
    ManuscriptDispatchUpdate,
    ManuscriptMailPreview,
    ManuscriptMailPathsResponse,
    ManuscriptMailPathsUpdate,
    ManuscriptMailStatus,
    ManuscriptQuickTranslatorCreate,
    ManuscriptTranslatorItem,
    ManuscriptSettlementUpdate,
)
from manuscript_service import (
    cancel_dispatch,
    confirm_dispatch,
    create_arrangement,
    create_dispatch,
    create_quick_translator,
    delete_arrangement,
    get_arrangement,
    get_arrangement_context,
    get_arrangement_mail_preview,
    list_arrangements,
    list_dispatches,
    send_arrangement,
    send_dispatch,
    update_arrangement,
    update_dispatch,
    update_dispatch_mail_paths,
    update_settlement,
)
from models import AppUser
from routers.auth import get_current_user, require_any_role, require_module_access


router = APIRouter(
    prefix="/manuscript-arrangements",
    tags=["manuscript-arrangements"],
    dependencies=[
        Depends(require_module_access("projects:read", "projects:write")),
        Depends(require_any_role("项目经理", "项目助理")),
    ],
)

MAX_MANUSCRIPT_ATTACHMENT_BYTES = 50 * 1024 * 1024
# 为 50MB 手动附件、正文图片和自动生成的共享文件压缩包预留总量空间。
MAX_MANUSCRIPT_MAIL_CONTENT_BYTES = 75 * 1024 * 1024


@router.post(
    "/translators/quick-create",
    response_model=ManuscriptTranslatorItem,
    status_code=status.HTTP_201_CREATED,
)
def quick_create_translator_endpoint(
    payload: ManuscriptQuickTranslatorCreate,
    db: Session = Depends(get_db),
):
    """在派稿过程中快捷建立可立即选择的笔译人员。"""
    try:
        return create_quick_translator(db, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _inline_images(
    db: Session,
    current_user: AppUser,
    value: str,
    *,
    scope_id: Optional[UUID] = None,
) -> list:
    try:
        raw_ids = json.loads(value or "[]")
        if not isinstance(raw_ids, list):
            raise ValueError
        image_ids = [UUID(str(item)) for item in raw_ids]
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="正文图片参数格式错误") from exc
    try:
        if scope_id:
            return load_owned_or_bound_images(
                db, image_ids, current_user.id,
                scope_type="manuscript_arrangement", scope_id=scope_id,
            )
        return load_owned_images(db, image_ids, current_user.id)
    except Exception as exc:
        _raise_business_error(exc)


def _validate_total_mail_content(attachment: Optional[MailAttachment], images: list) -> None:
    total = (len(attachment.content) if attachment else 0) + sum(item.file_size for item in images)
    if total > MAX_MANUSCRIPT_MAIL_CONTENT_BYTES:
        raise HTTPException(status_code=413, detail="邮件附件与正文图片合计不能超过 75MB")


def _validate_mail_html(value: Optional[str], max_length: int) -> None:
    if value and len(value) > max_length:
        raise HTTPException(status_code=413, detail="邮件正文内容过长")


def _validate_mail_subject(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="邮件标题不能为空")
    if len(normalized) > 500:
        raise HTTPException(status_code=413, detail="邮件标题不能超过 500 个字符")
    return normalized


def validate_manuscript_attachment(
    filename: Optional[str],
    content_type: Optional[str],
    content: bytes,
) -> MailAttachment:
    """校验并规范化一次性稿件附件。"""
    if not content:
        raise HTTPException(status_code=400, detail="上传文件内容为空")
    if len(content) > MAX_MANUSCRIPT_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="上传文件不能超过 50MB")
    normalized_name = (filename or "附件").replace("\\", "/").rsplit("/", 1)[-1]
    normalized_name = re.sub(r"[\x00-\x1f\x7f]", "_", normalized_name).strip()
    if not normalized_name:
        normalized_name = "附件"
    return MailAttachment(
        filename=normalized_name[:255],
        content=content,
        content_type=content_type or "application/octet-stream",
    )


async def _read_manuscript_attachment(
    upload: Optional[UploadFile],
) -> Optional[MailAttachment]:
    if upload is None:
        return None
    try:
        content = await upload.read(MAX_MANUSCRIPT_ATTACHMENT_BYTES + 1)
        return validate_manuscript_attachment(
            upload.filename,
            upload.content_type,
            content,
        )
    finally:
        await upload.close()


def _raise_business_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, MailConfigurationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, MailDeliveryError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


@router.get("/context", response_model=ManuscriptArrangementContext)
def read_context(
    keyword: Optional[str] = None,
    project_limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return get_arrangement_context(
        db,
        current_user=current_user,
        keyword=keyword,
        project_limit=project_limit,
    )


@router.get("/mail-status", response_model=ManuscriptMailStatus)
def read_mail_status():
    """返回脱敏后的邮件服务配置状态。"""
    return get_mail_status()


@router.get("/batches", response_model=list[ManuscriptDispatchResponse])
def read_dispatches(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    keyword: Optional[str] = None,
    dispatch_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return list_dispatches(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        keyword=keyword,
        status=dispatch_status,
    )


@router.post(
    "/batches",
    response_model=ManuscriptDispatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dispatch_endpoint(
    payload: ManuscriptDispatchCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return create_dispatch(db, payload, current_user)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)


@router.put("/batches/{dispatch_id}", response_model=ManuscriptDispatchResponse)
def update_dispatch_endpoint(
    dispatch_id: UUID,
    payload: ManuscriptDispatchUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        dispatch = update_dispatch(db, dispatch_id, payload, current_user)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not dispatch:
        raise HTTPException(status_code=404, detail="派稿批次不存在")
    return dispatch


@router.post(
    "/batches/{dispatch_id}/confirm",
    response_model=ManuscriptDispatchResponse,
)
def confirm_dispatch_endpoint(
    dispatch_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        dispatch = confirm_dispatch(db, dispatch_id, current_user)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not dispatch:
        raise HTTPException(status_code=404, detail="派稿批次不存在")
    return dispatch


@router.post(
    "/batches/{dispatch_id}/cancel",
    response_model=ManuscriptDispatchResponse,
)
def cancel_dispatch_endpoint(
    dispatch_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        dispatch = cancel_dispatch(db, dispatch_id, current_user)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not dispatch:
        raise HTTPException(status_code=404, detail="派稿批次不存在")
    return dispatch


@router.post(
    "/batches/{dispatch_id}/send",
    response_model=ManuscriptBatchSendResponse,
)
async def send_dispatch_endpoint(
    dispatch_id: UUID,
    attachment: Optional[UploadFile] = File(None),
    subject: Optional[str] = Form(None),
    body: Optional[str] = Form(None),
    inline_image_html: Optional[str] = Form(None),
    inline_image_ids_json: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    mail_attachment = await _read_manuscript_attachment(attachment)
    subject = _validate_mail_subject(subject)
    images = _inline_images(db, current_user, inline_image_ids_json)
    _validate_mail_html(body, 20000)
    _validate_mail_html(inline_image_html, 50000)
    _validate_total_mail_content(mail_attachment, images)
    try:
        dispatch, sent_count, failed_count, skipped_count = send_dispatch(
            db,
            dispatch_id,
            current_user,
            attachment=mail_attachment,
            subject_override=subject,
            body_override=body,
            inline_images=images,
            append_inline_html=inline_image_html,
        )
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    return {
        "dispatch": dispatch,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
    }


@router.post(
    "/batches/{dispatch_id}/arrangements/{arrangement_id}/send",
    response_model=ManuscriptArrangementResponse,
)
async def send_dispatch_arrangement_endpoint(
    dispatch_id: UUID,
    arrangement_id: UUID,
    attachment: Optional[UploadFile] = File(None),
    subject: Optional[str] = Form(None),
    body: Optional[str] = Form(None),
    body_html: Optional[str] = Form(None),
    inline_image_ids_json: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    current = get_arrangement(db, arrangement_id)
    if not current or current.dispatch_id != dispatch_id:
        raise HTTPException(status_code=404, detail="译员派稿明细不存在")
    mail_attachment = await _read_manuscript_attachment(attachment)
    subject = _validate_mail_subject(subject)
    images = _inline_images(db, current_user, inline_image_ids_json, scope_id=arrangement_id)
    _validate_mail_html(body, 20000)
    _validate_mail_html(body_html, 100000)
    _validate_total_mail_content(mail_attachment, images)
    try:
        arrangement = send_arrangement(
            db,
            arrangement_id,
            current_user,
            attachment=mail_attachment,
            subject_override=subject,
            body_override=body,
            body_html=body_html,
            inline_images=images,
        )
    except Exception as exc:
        _raise_business_error(exc)
    return arrangement


@router.get(
    "/batches/{dispatch_id}/arrangements/{arrangement_id}/mail-preview",
    response_model=ManuscriptMailPreview,
)
def read_arrangement_mail_preview(
    dispatch_id: UUID,
    arrangement_id: UUID,
    db: Session = Depends(get_db),
):
    current = get_arrangement(db, arrangement_id)
    if not current or current.dispatch_id != dispatch_id:
        raise HTTPException(status_code=404, detail="译员派稿明细不存在")
    try:
        preview = get_arrangement_mail_preview(db, arrangement_id)
    except Exception as exc:
        _raise_business_error(exc)
    return preview


@router.patch(
    "/batches/{dispatch_id}/mail-paths",
    response_model=ManuscriptMailPathsResponse,
)
def update_dispatch_mail_paths_endpoint(
    dispatch_id: UUID,
    payload: ManuscriptMailPathsUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        result = update_dispatch_mail_paths(
            db, dispatch_id, payload, current_user
        )
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not result:
        raise HTTPException(status_code=404, detail="派稿批次不存在")
    return result


@router.patch(
    "/batches/{dispatch_id}/arrangements/{arrangement_id}/settlement",
    response_model=ManuscriptArrangementResponse,
)
def update_settlement_endpoint(
    dispatch_id: UUID,
    arrangement_id: UUID,
    payload: ManuscriptSettlementUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    current = get_arrangement(db, arrangement_id)
    if not current or current.dispatch_id != dispatch_id:
        raise HTTPException(status_code=404, detail="译员派稿明细不存在")
    try:
        arrangement = update_settlement(
            db, arrangement_id, payload, current_user
        )
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    return arrangement


# 以下接口保留给现有单译员调用方使用。
@router.get("", response_model=list[ManuscriptArrangementResponse])
def read_arrangements(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    keyword: Optional[str] = None,
    arrangement_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return list_arrangements(
        db,
        skip=skip,
        limit=limit,
        keyword=keyword,
        status=arrangement_status,
    )


@router.post(
    "",
    response_model=ManuscriptArrangementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_arrangement_endpoint(
    payload: ManuscriptArrangementCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return create_arrangement(db, payload, current_user)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)


@router.put("/{arrangement_id}", response_model=ManuscriptArrangementResponse)
def update_arrangement_endpoint(
    arrangement_id: UUID,
    payload: ManuscriptArrangementUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        arrangement = update_arrangement(
            db, arrangement_id, payload, current_user
        )
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not arrangement:
        raise HTTPException(status_code=404, detail="稿件安排不存在")
    return arrangement


@router.post(
    "/{arrangement_id}/send",
    response_model=ManuscriptArrangementResponse,
)
async def send_arrangement_endpoint(
    arrangement_id: UUID,
    attachment: Optional[UploadFile] = File(None),
    subject: Optional[str] = Form(None),
    body: Optional[str] = Form(None),
    body_html: Optional[str] = Form(None),
    inline_image_ids_json: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    mail_attachment = await _read_manuscript_attachment(attachment)
    subject = _validate_mail_subject(subject)
    images = _inline_images(db, current_user, inline_image_ids_json, scope_id=arrangement_id)
    _validate_mail_html(body, 20000)
    _validate_mail_html(body_html, 100000)
    _validate_total_mail_content(mail_attachment, images)
    try:
        arrangement = send_arrangement(
            db,
            arrangement_id,
            current_user,
            attachment=mail_attachment,
            subject_override=subject,
            body_override=body,
            body_html=body_html,
            inline_images=images,
        )
    except Exception as exc:
        _raise_business_error(exc)
    if not arrangement:
        raise HTTPException(status_code=404, detail="稿件安排不存在")
    return arrangement


@router.delete("/{arrangement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_arrangement_endpoint(
    arrangement_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        deleted = delete_arrangement(db, arrangement_id, current_user)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="稿件安排不存在")
    return None
