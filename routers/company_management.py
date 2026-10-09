"""公司管理树形栏目、正文及检索 API。"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from company_management_attachment_service import (
    attachment_path, delete_attachment, get_attachment, list_attachments, save_attachment,
)

from annotation_notice_schemas import (
    AnnotationNoticeReorder,
    AnnotationNoticeSearchResponse,
    AnnotationNoticeSectionCreate,
    AnnotationNoticeSectionEdit,
    AnnotationNoticeSectionResponse,
    AnnotationNoticeSectionUpdate,
    AnnotationNoticeTreeNodeResponse,
)
from company_management_service import (
    create_company_management_section,
    delete_company_management_section,
    get_company_management_section,
    list_company_management_tree,
    reorder_company_management_sections,
    search_company_management_sections,
    update_company_management_content,
    update_company_management_structure,
)
from database import get_db
from models import AppUser
from routers.auth import get_current_user


router = APIRouter(
    prefix="/company-management",
    tags=["company_management"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/tree", response_model=list[AnnotationNoticeTreeNodeResponse])
def read_company_management_tree(db: Session = Depends(get_db)):
    return list_company_management_tree(db)


@router.get("/search", response_model=AnnotationNoticeSearchResponse)
def search_company_management(
    keyword: str = Query(..., min_length=1, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    normalized = keyword.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="请输入搜索关键词")
    return search_company_management_sections(db, normalized, skip, limit)


@router.post(
    "/sections", response_model=AnnotationNoticeSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation_notice(
    payload: AnnotationNoticeSectionCreate, db: Session = Depends(get_db)
):
    try:
        return create_company_management_section(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/sections/reorder", response_model=list[AnnotationNoticeTreeNodeResponse],
)
def reorder_company_management(payload: AnnotationNoticeReorder, db: Session = Depends(get_db)):
    try:
        return reorder_company_management_sections(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sections/{section_id}", response_model=AnnotationNoticeSectionResponse)
def read_annotation_notice(section_id: UUID, db: Session = Depends(get_db)):
    row = get_company_management_section(db, section_id)
    if row is None:
        raise HTTPException(status_code=404, detail="公司管理栏目不存在")
    return row


@router.patch(
    "/sections/{section_id}", response_model=AnnotationNoticeSectionResponse,
)
def edit_annotation_notice(
    section_id: UUID, payload: AnnotationNoticeSectionEdit, db: Session = Depends(get_db)
):
    row = update_company_management_structure(db, section_id, payload)
    if row is None:
        raise HTTPException(status_code=404, detail="公司管理栏目不存在")
    return row


@router.delete(
    "/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def remove_annotation_notice(section_id: UUID, db: Session = Depends(get_db)):
    try:
        if not delete_company_management_section(db, section_id):
            raise HTTPException(status_code=404, detail="公司管理栏目不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/sections/{section_id}/content", response_model=AnnotationNoticeSectionResponse,
)
def save_company_management_content(
    section_id: UUID,
    payload: AnnotationNoticeSectionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        row = update_company_management_content(db, section_id, payload, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="公司管理栏目不存在")
    return row



class CompanyAttachmentResponse(BaseModel):
    id: UUID
    section_id: UUID
    original_name: str
    file_size: int
    content_type: str
    uploaded_by: UUID | None
    uploaded_by_name: str | None
    uploaded_at: datetime


@router.get("/sections/{section_id}/attachments", response_model=list[CompanyAttachmentResponse])
def read_attachments(section_id: UUID, db: Session = Depends(get_db)):
    return list_attachments(db, section_id)


@router.post(
    "/sections/{section_id}/attachments", response_model=CompanyAttachmentResponse,
    status_code=201,
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


@router.delete("/sections/{section_id}/attachments/{attachment_id}", status_code=204)
def remove_attachment(section_id: UUID, attachment_id: UUID, db: Session = Depends(get_db)):
    delete_attachment(db, section_id, attachment_id)
