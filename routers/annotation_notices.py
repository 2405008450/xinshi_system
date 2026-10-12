"""标注须知树形栏目、正文及检索 API。"""

from uuid import UUID

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
from annotation_notice_service import (
    create_annotation_notice_section,
    delete_annotation_notice_section,
    get_annotation_notice_section,
    list_annotation_notice_sections,
    list_annotation_notice_tree,
    reorder_annotation_notice_sections,
    search_annotation_notice_sections,
    update_annotation_notice_content,
    update_annotation_notice_section,
    update_annotation_notice_structure,
)
from database import get_db
from annotation_notice_attachment_service import (
    attachment_path, delete_attachment, get_attachment, list_attachments, save_attachment,
)
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/annotation-notices",
    tags=["annotation_notices"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)
write_permission = [Depends(require_any_permission("projects:write"))]


@router.get("/tree", response_model=list[AnnotationNoticeTreeNodeResponse])
def read_annotation_notice_tree(db: Session = Depends(get_db)):
    return list_annotation_notice_tree(db)


@router.get("/search", response_model=AnnotationNoticeSearchResponse)
def search_annotation_notices(
    keyword: str = Query(..., min_length=1, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    normalized = keyword.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="请输入搜索关键词")
    return search_annotation_notice_sections(db, normalized, skip, limit)


@router.post(
    "/sections", response_model=AnnotationNoticeSectionResponse,
    status_code=status.HTTP_201_CREATED, dependencies=write_permission,
)
def create_annotation_notice(
    payload: AnnotationNoticeSectionCreate, db: Session = Depends(get_db)
):
    try:
        return create_annotation_notice_section(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/sections/reorder", response_model=list[AnnotationNoticeTreeNodeResponse],
    dependencies=write_permission,
)
def reorder_annotation_notices(payload: AnnotationNoticeReorder, db: Session = Depends(get_db)):
    try:
        return reorder_annotation_notice_sections(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sections/{section_id}", response_model=AnnotationNoticeSectionResponse)
def read_annotation_notice(section_id: UUID, db: Session = Depends(get_db)):
    row = get_annotation_notice_section(db, section_id)
    if row is None:
        raise HTTPException(status_code=404, detail="标注须知栏目不存在")
    return row


@router.patch(
    "/sections/{section_id}", response_model=AnnotationNoticeSectionResponse,
    dependencies=write_permission,
)
def edit_annotation_notice(
    section_id: UUID, payload: AnnotationNoticeSectionEdit, db: Session = Depends(get_db)
):
    row = update_annotation_notice_structure(db, section_id, payload)
    if row is None:
        raise HTTPException(status_code=404, detail="标注须知栏目不存在")
    return row


@router.delete(
    "/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=write_permission,
)
def remove_annotation_notice(section_id: UUID, db: Session = Depends(get_db)):
    try:
        if not delete_annotation_notice_section(db, section_id):
            raise HTTPException(status_code=404, detail="标注须知栏目不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/sections/{section_id}/content", response_model=AnnotationNoticeSectionResponse,
    dependencies=write_permission,
)
def save_annotation_notice_content(
    section_id: UUID,
    payload: AnnotationNoticeSectionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        row = update_annotation_notice_content(db, section_id, payload, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="标注须知栏目不存在")
    return row


@router.get("/sections/{section_id}/attachments", response_model=list[AnnotationNoticeAttachmentResponse])
def read_attachments(section_id: UUID, db: Session = Depends(get_db)):
    return list_attachments(db, section_id)


@router.post(
    "/sections/{section_id}/attachments", response_model=AnnotationNoticeAttachmentResponse,
    status_code=status.HTTP_201_CREATED, dependencies=write_permission,
)
async def upload_attachment(
    section_id: UUID, file: UploadFile = File(...),
    db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user),
):
    return await save_attachment(db, section_id, file, current_user.id)


@router.get("/sections/{section_id}/attachments/{attachment_id}")
def download_attachment(section_id: UUID, attachment_id: UUID, db: Session = Depends(get_db)):
    row = get_attachment(db, section_id, attachment_id)
    path = attachment_path(row.storage_name)
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
def remove_attachment(section_id: UUID, attachment_id: UUID, db: Session = Depends(get_db)):
    delete_attachment(db, section_id, attachment_id)


# 兼容旧版平铺读取和按固定 section_key 保存正文。
@router.get("", response_model=list[AnnotationNoticeSectionResponse])
def read_annotation_notices(db: Session = Depends(get_db)):
    return list_annotation_notice_sections(db)


@router.put(
    "/{section_key}", response_model=AnnotationNoticeSectionResponse,
    dependencies=write_permission,
)
def save_annotation_notice(
    section_key: str,
    payload: AnnotationNoticeSectionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        section = update_annotation_notice_section(db, section_key, payload, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if section is None:
        raise HTTPException(status_code=404, detail="标注须知主题不存在")
    return section
