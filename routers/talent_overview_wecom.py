"""人才概览企微群接口，沿用人才概览的访问与写入权限。"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user, require_any_permission
from talent_overview_wecom_schemas import (
    LanguageManagementWrite, WecomArchiveWrite, WecomCountVoid,
    WecomCountWrite, WecomGroupCreate, WecomGroupWrite,
)
import talent_overview_wecom_service as service

router = APIRouter(prefix="/talents/overview", tags=["talent_overview_wecom"], dependencies=[Depends(get_current_user)])
write = [Depends(require_any_permission("talents:write", "translators:write"))]


def _call(db, callback, *, commit=False):
    try:
        result = callback()
        if commit:
            db.commit()
        return result
    except Exception as exc:
        db.rollback()
        if isinstance(exc, LookupError):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise


@router.get("/languages/{overview_key}/management")
def read_language(overview_key: str, db: Session = Depends(get_db)):
    return _call(db, lambda: service.get_language_management(db, overview_key))


@router.put("/languages/{overview_key}/management", dependencies=write)
def save_language(overview_key: str, payload: LanguageManagementWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _call(db, lambda: service.save_language_management(db, overview_key, payload, user), commit=True)


@router.get("/languages/{overview_key}/groups")
def read_groups(overview_key: str, include_archived: bool = False, db: Session = Depends(get_db)):
    return _call(db, lambda: service.list_groups(db, overview_key, include_archived))


@router.post("/languages/{overview_key}/groups", dependencies=write, status_code=201)
def add_group(overview_key: str, payload: WecomGroupCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _call(db, lambda: service.create_group(db, overview_key, payload, user), commit=True)


@router.get("/groups/{group_id}")
def read_group(group_id: UUID, db: Session = Depends(get_db)):
    return _call(db, lambda: service.get_group(db, group_id))


@router.put("/groups/{group_id}", dependencies=write)
def edit_group(group_id: UUID, payload: WecomGroupWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _call(db, lambda: service.update_group(db, group_id, payload, user), commit=True)


@router.put("/groups/{group_id}/archive", dependencies=write)
def set_archive(group_id: UUID, payload: WecomArchiveWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _call(db, lambda: service.archive_group(db, group_id, payload, user), commit=True)


@router.post("/groups/{group_id}/counts", dependencies=write, status_code=201)
def add_count(group_id: UUID, payload: WecomCountWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _call(db, lambda: service.register_count(db, group_id, payload, user), commit=True)


@router.put("/groups/{group_id}/counts/{count_id}/void", dependencies=write)
def invalidate_count(group_id: UUID, count_id: int, payload: WecomCountVoid, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _call(db, lambda: service.void_count(db, group_id, count_id, payload, user), commit=True)


@router.get("/groups/{group_id}/counts")
def read_counts(group_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    return _call(db, lambda: service.counts_page(db, group_id, page, page_size))


@router.get("/groups/{group_id}/history")
def read_group_history(group_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    return _call(db, lambda: service.history_page(db, group_id=group_id, page=page, page_size=page_size))


@router.get("/languages/{overview_key}/history")
def read_language_history(overview_key: str, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    return _call(db, lambda: service.history_page(db, overview_key=overview_key, page=page, page_size=page_size))
