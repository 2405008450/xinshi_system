"""稿件安排 API。"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from mail_service import MailConfigurationError, MailDeliveryError, get_mail_status
from manuscript_schemas import (
    ManuscriptArrangementContext,
    ManuscriptArrangementCreate,
    ManuscriptArrangementResponse,
    ManuscriptArrangementUpdate,
    ManuscriptBatchSendResponse,
    ManuscriptDispatchCreate,
    ManuscriptDispatchResponse,
    ManuscriptDispatchUpdate,
    ManuscriptMailStatus,
    ManuscriptSettlementUpdate,
)
from manuscript_service import (
    cancel_dispatch,
    confirm_dispatch,
    create_arrangement,
    create_dispatch,
    delete_arrangement,
    get_arrangement,
    get_arrangement_context,
    list_arrangements,
    list_dispatches,
    send_arrangement,
    send_dispatch,
    update_arrangement,
    update_dispatch,
    update_settlement,
)
from models import AppUser
from routers.auth import get_current_user, require_module_access


router = APIRouter(
    prefix="/manuscript-arrangements",
    tags=["manuscript-arrangements"],
    dependencies=[
        Depends(require_module_access("projects:read", "projects:write"))
    ],
)


def _raise_business_error(exc: Exception) -> None:
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
):
    return get_arrangement_context(
        db,
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
):
    return list_dispatches(
        db,
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
):
    try:
        dispatch = cancel_dispatch(db, dispatch_id)
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
def send_dispatch_endpoint(
    dispatch_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        dispatch, sent_count, failed_count, skipped_count = send_dispatch(
            db,
            dispatch_id,
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
def send_dispatch_arrangement_endpoint(
    dispatch_id: UUID,
    arrangement_id: UUID,
    db: Session = Depends(get_db),
):
    current = get_arrangement(db, arrangement_id)
    if not current or current.dispatch_id != dispatch_id:
        raise HTTPException(status_code=404, detail="译员派稿明细不存在")
    try:
        arrangement = send_arrangement(db, arrangement_id)
    except Exception as exc:
        _raise_business_error(exc)
    return arrangement


@router.patch(
    "/batches/{dispatch_id}/arrangements/{arrangement_id}/settlement",
    response_model=ManuscriptArrangementResponse,
)
def update_settlement_endpoint(
    dispatch_id: UUID,
    arrangement_id: UUID,
    payload: ManuscriptSettlementUpdate,
    db: Session = Depends(get_db),
):
    current = get_arrangement(db, arrangement_id)
    if not current or current.dispatch_id != dispatch_id:
        raise HTTPException(status_code=404, detail="译员派稿明细不存在")
    try:
        arrangement = update_settlement(db, arrangement_id, payload)
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
):
    try:
        arrangement = update_arrangement(db, arrangement_id, payload)
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
def send_arrangement_endpoint(
    arrangement_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        arrangement = send_arrangement(db, arrangement_id)
    except Exception as exc:
        _raise_business_error(exc)
    if not arrangement:
        raise HTTPException(status_code=404, detail="稿件安排不存在")
    return arrangement


@router.delete("/{arrangement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_arrangement_endpoint(
    arrangement_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        deleted = delete_arrangement(db, arrangement_id)
    except Exception as exc:
        db.rollback()
        _raise_business_error(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="稿件安排不存在")
    return None
