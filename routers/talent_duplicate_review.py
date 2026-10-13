"""核重读取沿用人才总库登录权限，所有写入强制超级管理员。"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse, Response
import json
from database import get_db
from routers.auth import get_current_user, require_super_admin
from talent_privacy import can_view_talent_contacts
from talent_duplicate_schemas import DuplicateReviewRequest, DuplicateReviewCommit, NameMergePreviewRequest, NameMergeCommitRequest
from talent_duplicate_service import groups, group_detail, preview, commit, history, undo, operation_detail

router = APIRouter(prefix="/talents/duplicate-review", tags=["talent_duplicate_review"],
                   dependencies=[Depends(get_current_user)])


@router.get("/groups")
def read_groups(keyword: str = "", status: str = Query("pending", pattern="^(pending|different|deferred|all)$"),
                agent_bucket: str = Query("all", pattern="^(all|high_same|likely_same|different|uncertain|unreviewed)$"),
                skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    visible = can_view_talent_contacts(db, user)
    if agent_bucket != "all" and not visible:
        raise HTTPException(403, "Agent 初筛结果仅超级管理员可查看")
    return groups(db, keyword, status, skip, limit, visible, agent_bucket)


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


@router.get("/name-merge/groups")
def read_name_merge_groups(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                           db: Session = Depends(get_db), user=Depends(require_super_admin)):
    from talent_name_merge_service import list_groups
    return list_groups(db, skip, limit)


@router.post("/name-merge/preview")
def preview_name_merge(payload: NameMergePreviewRequest, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    from talent_name_merge_service import preview_group
    result = preview_group(db, payload)
    result.pop("before_snapshot", None)
    result.pop("automatic_request", None)
    return result


@router.post("/name-merge/commit")
def commit_name_merge(payload: NameMergeCommitRequest, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    from talent_name_merge_service import commit_group
    try:
        return commit_group(db, payload, user)
    except Exception:
        db.rollback()
        raise


@router.get("/operations/{operation_id}")
def read_operation(operation_id: UUID, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    return operation_detail(db, operation_id)


@router.get("/operations/{operation_id}/original-data")
def read_original_data(operation_id: UUID, response: Response, person_id: UUID | None = None,
                       db: Session = Depends(get_db), user=Depends(require_super_admin)):
    from talent_retention_service import original_data
    response.headers["Cache-Control"] = "no-store"
    return original_data(db, operation_id, person_id)


@router.get("/operations/{operation_id}/original-data/export")
def download_original_data(operation_id: UUID, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    from talent_retention_service import export_original_data
    data = export_original_data(db, operation_id)
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="talent-original-data-{operation_id}.json"',
                             "Cache-Control": "no-store"})


@router.get("/operations/{operation_id}/original-data/attachments/{attachment_id}")
def download_original_attachment(operation_id: UUID, attachment_id: UUID,
                                 db: Session = Depends(get_db), user=Depends(require_super_admin)):
    from talent_retention_service import original_attachment
    path, item = original_attachment(db, operation_id, attachment_id)
    return FileResponse(path, media_type=item.get("content_type") or "application/octet-stream",
                        filename=item["original_name"], headers={"Cache-Control": "no-store"})


@router.post("/operations/{operation_id}/undo")
def undo_action(operation_id: UUID, db: Session = Depends(get_db), user=Depends(require_super_admin)):
    try:
        return undo(db, operation_id, user)
    except Exception:
        db.rollback()
        raise
