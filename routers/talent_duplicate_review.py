"""核重读取沿用人才总库登录权限，所有写入强制超级管理员。"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user, require_super_admin
from talent_privacy import can_view_talent_contacts
from talent_duplicate_schemas import DuplicateReviewRequest, DuplicateReviewCommit
from talent_duplicate_service import groups, group_detail, preview, commit, history, undo

router = APIRouter(prefix="/talents/duplicate-review", tags=["talent_duplicate_review"],
                   dependencies=[Depends(get_current_user)])


@router.get("/groups")
def read_groups(keyword: str = "", status: str = Query("pending", pattern="^(pending|different|deferred|all)$"),
                skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    return groups(db, keyword, status, skip, limit, can_view_talent_contacts(db, user))


@router.get("/groups/{key:path}")
def read_group(key: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return group_detail(db, key, can_view_talent_contacts(db, user))


@router.post("/preview")
def preview_action(payload: DuplicateReviewRequest, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    result = preview(db, payload)
    result.pop("before_snapshot", None)
    return result


@router.post("/commit")
def commit_action(payload: DuplicateReviewCommit, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    try:
        return commit(db, payload, user)
    except Exception:
        db.rollback()
        raise


@router.get("/history")
def read_history(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), person_id: UUID | None = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    return history(db, skip, limit, can_view_talent_contacts(db, user), person_id)


@router.post("/operations/{operation_id}/undo")
def undo_action(operation_id: UUID, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    try:
        return undo(db, operation_id, user)
    except Exception:
        db.rollback()
        raise
