"""财务管理及项目表单共用报价单接口。"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from database import get_db
from routers.auth import require_permission
from models import TranslationProject
from annotation_progress_time import business_now
import translation_document_requirements as documents

router = APIRouter(prefix='/translation-quotations', tags=['笔译报价单'])


class QuotationWrite(BaseModel):
    revision: int = Field(ge=0)
    document: documents.QuotationDraft


@router.get('/{project_id}')
def read(project_id: UUID, db=Depends(get_db), actor=Depends(require_permission('projects:read'))):
    import crud
    project = crud.get_translation_project(db, project_id)
    if not project:
        raise HTTPException(404, '项目不存在')
    return documents.quotation(db, project)


@router.put('/{project_id}')
def write(project_id: UUID, payload: QuotationWrite, db=Depends(get_db), actor=Depends(require_permission('projects:write'))):
    project = db.query(TranslationProject).filter(TranslationProject.id == project_id,
        TranslationProject.annotation_migrated_at.is_(None)).with_for_update().first()
    if project is None:
        raise HTTPException(404, '项目不存在')
    current = documents.quotation(db, project)
    if current['revision'] != payload.revision:
        raise HTTPException(409, '报价单已被修改，请重新打开后编辑')
    try:
        documents.save(db, project, quotation_draft=payload.document, actor_id=actor.id)
        project.updated_at = business_now().replace(tzinfo=None)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '报价单已被修改，请重新打开后编辑')
    return documents.quotation(db, project)
