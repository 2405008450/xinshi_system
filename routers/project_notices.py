"""项目须知树形栏目、正文及检索 API。"""

from uuid import UUID
from typing import Literal

NoticeModule = Literal["translation", "interpretation", "recruitment"]

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from annotation_notice_schemas import (
    AnnotationNoticeAttachmentResponse,
    AnnotationNoticeReorder,
    AnnotationNoticeSearchResponse,
    AnnotationNoticeSectionCreate,
    AnnotationNoticeSectionEdit,
    AnnotationNoticeSectionResponse,
    AnnotationNoticeSectionUpdate,
    AnnotationNoticeTreeNodeResponse,
)
from project_notice_service import (
    create_section, delete_section, get_section, list_tree,
    reorder_sections, search_sections, update_content, update_structure,
)
from database import get_db
from project_notice_attachment_service import (
    attachment_path, delete_attachment, get_attachment, list_attachments, save_attachment,
)
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/project-notices/{module}",
    tags=["project_notices"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)
write_permission = [Depends(require_any_permission("projects:write"))]


@router.get("/tree", response_model=list[AnnotationNoticeTreeNodeResponse])
def read_project_notice_tree(module: NoticeModule, db: Session = Depends(get_db)):
    return list_tree(db, module)


@router.get("/search", response_model=AnnotationNoticeSearchResponse)
def search_project_notices(module: NoticeModule,
    keyword: str = Query(..., min_length=1, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    normalized = keyword.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="请输入搜索关键词")
    return search_sections(db, module, normalized, skip, limit)


@router.post(
    "/sections", response_model=AnnotationNoticeSectionResponse,
    status_code=status.HTTP_201_CREATED, dependencies=write_permission,
)
def create_project_notice(module: NoticeModule,
    payload: AnnotationNoticeSectionCreate, db: Session = Depends(get_db)
):
    try:
        return create_section(db, module, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/sections/reorder", response_model=list[AnnotationNoticeTreeNodeResponse],
    dependencies=write_permission,
)
def reorder_project_notices(module: NoticeModule, payload: AnnotationNoticeReorder, db: Session = Depends(get_db)):
    try:
        return reorder_sections(db, module, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sections/{section_id}", response_model=AnnotationNoticeSectionResponse)
def read_project_notice(module: NoticeModule, section_id: UUID, db: Session = Depends(get_db)):
    row = get_section(db, module, section_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目须知栏目不存在")
    return row


@router.patch(
    "/sections/{section_id}", response_model=AnnotationNoticeSectionResponse,
    dependencies=write_permission,
)
def edit_project_notice(module: NoticeModule,
    section_id: UUID, payload: AnnotationNoticeSectionEdit, db: Session = Depends(get_db)
):
    row = update_structure(db, module, section_id, payload)
    if row is None:
        raise HTTPException(status_code=404, detail="项目须知栏目不存在")
    return row


@router.delete(
    "/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=write_permission,
)
def remove_project_notice(module: NoticeModule, section_id: UUID, db: Session = Depends(get_db)):
    try:
        if not delete_section(db, module, section_id):
            raise HTTPException(status_code=404, detail="项目须知栏目不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/sections/{section_id}/content", response_model=AnnotationNoticeSectionResponse,
    dependencies=write_permission,
)
def save_project_notice_content(module: NoticeModule,
    section_id: UUID,
    payload: AnnotationNoticeSectionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        row = update_content(db, module, section_id, payload, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="项目须知栏目不存在")
    return row


@router.get("/sections/{section_id}/attachments", response_model=list[AnnotationNoticeAttachmentResponse])
def read_attachments(module: NoticeModule, section_id: UUID, db: Session = Depends(get_db)):
    return list_attachments(db, module, section_id)


@router.post(
    "/sections/{section_id}/attachments", response_model=AnnotationNoticeAttachmentResponse,
    status_code=status.HTTP_201_CREATED, dependencies=write_permission,
)
async def upload_attachment(module: NoticeModule,
    section_id: UUID, file: UploadFile = File(...),
    db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user),
):
    return await save_attachment(db, module, section_id, file, current_user.id)


@router.get("/sections/{section_id}/attachments/{attachment_id}")
def download_attachment(module: NoticeModule, section_id: UUID, attachment_id: UUID, db: Session = Depends(get_db)):
    row = get_attachment(db, module, section_id, attachment_id)
    path = attachment_path(module, row.storage_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="附件文件不存在")
    return FileResponse(
        path, filename=row.original_name, media_type="application/octet-stream",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.delete(
    "/sections/{section_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT, dependencies=write_permission,
)
def remove_attachment(module: NoticeModule, section_id: UUID, attachment_id: UUID, db: Session = Depends(get_db)):
    delete_attachment(db, module, section_id, attachment_id)


