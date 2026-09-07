"""标注须知 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from annotation_notice_schemas import AnnotationNoticeSectionResponse, AnnotationNoticeSectionUpdate
from annotation_notice_service import list_annotation_notice_sections, update_annotation_notice_section
from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access


router = APIRouter(
    prefix="/annotation-notices",
    tags=["annotation_notices"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)


@router.get("", response_model=list[AnnotationNoticeSectionResponse])
def read_annotation_notices(db: Session = Depends(get_db)):
    return list_annotation_notice_sections(db)


@router.put(
    "/{section_key}",
    response_model=AnnotationNoticeSectionResponse,
    dependencies=[Depends(require_any_permission("projects:write"))],
)
def save_annotation_notice(
    section_key: str,
    payload: AnnotationNoticeSectionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    section = update_annotation_notice_section(db, section_key, payload, current_user.id)
    if section is None:
        raise HTTPException(status_code=404, detail="标注须知主题不存在")
    return section
