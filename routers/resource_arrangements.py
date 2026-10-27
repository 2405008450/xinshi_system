"""每日安排接口，挂载到现有资源开拓路由并继承读取权限。"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user, require_any_permission
from resource_development_schemas import ArrangementWrite, ArrangementCompletionWrite, RequestArrangementWrite
from resource_arrangement_service import (
    arrangement_options, carry_preview, complete_arrangement, list_arrangements,
    project_detail, read_arrangement, save_arrangement,
    list_arrangement_requests, arrangement_request_detail, assign_request, arrangement_history,
)

router = APIRouter()
write = Depends(get_current_user)


@router.get('/arrangement-requests')
def read_requests(keyword: str | None = Query(None, max_length=255), skip: int = Query(0, ge=0),
                  limit: int = Query(5, ge=1, le=100), db: Session = Depends(get_db)):
    return list_arrangement_requests(db, keyword, skip, limit)


@router.get('/arrangement-requests/{request_id}')
def read_request(request_id: UUID, db: Session = Depends(get_db)):
    return arrangement_request_detail(db, request_id)


@router.put('/arrangement-requests/{request_id}/dates/{work_date}', dependencies=[write])
def assign_request_date(request_id: UUID, work_date: date, payload: RequestArrangementWrite,
                        db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        day = assign_request(db, user, request_id, work_date, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, '这一天刚刚被其他人保存，请重新加载后重试') from exc
    return read_arrangement(db, user, work_date, day)


@router.get('/arrangement-options')
def read_options(source_type: str | None = None, keyword: str | None = Query(None, max_length=255),
                 db: Session = Depends(get_db)):
    return arrangement_options(db, source_type, keyword)


@router.get('/arrangement-project-detail', dependencies=[Depends(require_any_permission('projects:read', 'projects:write'))])
def read_project(source_type: str, project_id: UUID, db: Session = Depends(get_db)):
    return project_detail(db, source_type, project_id)


@router.get('/arrangements')
def read_days(start: date | None = None, end: date | None = None, skip: int = Query(0, ge=0),
              limit: int = Query(14, ge=1, le=31), db: Session = Depends(get_db), user=Depends(get_current_user)):
    return list_arrangements(db, user, start, end, skip, limit)


@router.get('/arrangements/{work_date}')
def read_day(work_date: date, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return read_arrangement(db, user, work_date)


@router.get('/arrangements/{work_date}/carry-preview', dependencies=[write])
def preview_carry(work_date: date, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return carry_preview(db, user, work_date)


@router.put('/arrangements/{work_date}', dependencies=[write])
def save_day(work_date: date, payload: ArrangementWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        row = save_arrangement(db, user, work_date, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, '这一天刚刚被其他人保存，请重新加载后重试') from exc
    return read_arrangement(db, user, work_date, row)


@router.patch('/arrangements/{work_date}/cells/{platform_id}/completion', dependencies=[write])
def save_completion(work_date: date, platform_id: UUID, payload: ArrangementCompletionWrite,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = complete_arrangement(db, user, work_date, platform_id, payload)
    db.commit()
    return read_arrangement(db, user, work_date, row)


@router.get('/arrangements/{work_date}/cells/{platform_id}/history')
def read_history(work_date: date, platform_id: UUID, skip: int = Query(0, ge=0),
                 limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return arrangement_history(db, work_date, platform_id, skip, limit)
