from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_consultation, get_consultations,
    create_consultation, update_consultation, delete_consultation,
    create_translation_project, get_translation_projects
)
from schemas import ConsultationCreate, ConsultationUpdate, ConsultationResponse, TranslationProjectCreate, TranslationProjectResponse
from models import TranslationProject

router = APIRouter(prefix="/consultations", tags=["consultations"])


class CreateProjectFromConsultationRequest(BaseModel):
    project_name: str


@router.post("/", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
def create_consultation_endpoint(consultation: ConsultationCreate, db: Session = Depends(get_db)):
    return create_consultation(db=db, consultation=consultation)


@router.get("/", response_model=List[ConsultationResponse])
def read_consultations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_consultations(db, skip=skip, limit=limit)


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def read_consultation(consultation_id: UUID, db: Session = Depends(get_db)):
    db_consultation = get_consultation(db, consultation_id=consultation_id)
    if not db_consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return db_consultation


@router.put("/{consultation_id}", response_model=ConsultationResponse)
def update_consultation_endpoint(consultation_id: UUID, consultation_update: ConsultationUpdate, db: Session = Depends(get_db)):
    db_consultation = update_consultation(db, consultation_id=consultation_id, consultation_update=consultation_update)
    if not db_consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return db_consultation


@router.post("/{consultation_id}/create-project", response_model=TranslationProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_from_consultation(
    consultation_id: UUID,
    body: CreateProjectFromConsultationRequest,
    db: Session = Depends(get_db)
):
    """
    基于已成交的咨询记录，手动输入项目名称后创建翻译项目。
    避免重复：如果已存在以该咨询 ID 为 source 的项目，则返回已有项目。
    """
    db_consultation = get_consultation(db, consultation_id=consultation_id)
    if not db_consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询记录不存在")

    if db_consultation.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有已成交的咨询才能创建翻译项目")

    project_data = TranslationProjectCreate(
        project_name=body.project_name,
        client_id=db_consultation.client_id,
        customer_reception_time=db_consultation.consultation_time,
        created_by=db_consultation.editor_id,
    )

    new_project = create_translation_project(db, project_data)
    return new_project


@router.delete("/{consultation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consultation_endpoint(consultation_id: UUID, db: Session = Depends(get_db)):
    success = delete_consultation(db, consultation_id=consultation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return None
