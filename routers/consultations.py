from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    count_consultations, get_consultation, get_consultations,
    create_consultation, update_consultation, delete_consultation,
    build_auto_project_name, create_translation_project, get_translation_projects
)
from schemas import ConsultationCreate, ConsultationUpdate, ConsultationResponse, TranslationProjectCreate, TranslationProjectResponse
from models import AppUser, TranslationProject
from routers.auth import get_current_user, require_module_access

router = APIRouter(prefix="/consultations", tags=["consultations"], dependencies=[Depends(require_module_access("consultations:read", "consultations:write"))])


class CreateProjectFromConsultationRequest(BaseModel):
    project_name: Optional[str] = None


CONSULTATION_CONFIRMED_STATUS = "success"
PROJECT_CONFIRMED_STATUS = "confirmed"


CONSULTATION_TASK_TYPE_LABELS = {
    "translation": "笔译项目",
    "interpretation": "口译项目",
    "recruitment": "招聘项目",
    "annotation": "标注项目",
    "dubbing": "配音项目",
    "subtitle": "字幕项目",
    "notarization": "公证项目",
    "certification": "认证项目",
    "equipment_rental": "其他项目",
    "other": "其他项目",
    "笔译": "笔译项目",
    "口译": "口译项目",
    "招聘": "招聘项目",
    "其他": "其他项目",
}


@router.post("/", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
def create_consultation_endpoint(consultation: ConsultationCreate, db: Session = Depends(get_db)):
    return create_consultation(db=db, consultation=consultation)


@router.get("/count")
def read_consultation_count(
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return {
        "total": count_consultations(
            db,
            consultation_code=consultation_code,
            client_name=client_name,
            status=status,
            consultation_date_start=consultation_date_start,
            consultation_date_end=consultation_date_end,
            consultation_method=consultation_method,
            consultation_type=consultation_type,
            client_source=client_source,
            customer_service_id=customer_service_id,
            sales_person_id=sales_person_id,
            follow_up_person_id=follow_up_person_id,
            follow_up_status=follow_up_status,
        )
    }


@router.get("/", response_model=List[ConsultationResponse])
def read_consultations(
    skip: int = 0, 
    limit: int = 100, 
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return get_consultations(
        db, 
        skip=skip, 
        limit=limit,
        consultation_code=consultation_code,
        client_name=client_name,
        status=status,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        consultation_method=consultation_method,
        consultation_type=consultation_type,
        client_source=client_source,
        customer_service_id=customer_service_id,
        sales_person_id=sales_person_id,
        follow_up_person_id=follow_up_person_id,
        follow_up_status=follow_up_status,
    )


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
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """
    基于已确认的咨询记录创建翻译项目。
    项目名称默认复用项目详情的“客户简称-日期-批次”命名规则。
    避免重复：同一条咨询只能生成一个翻译项目。
    """
    db_consultation = get_consultation(db, consultation_id=consultation_id)
    if not db_consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询记录不存在")

    if db_consultation.status != CONSULTATION_CONFIRMED_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有已确认的咨询才能生成项目详情")

    existing_project = (
        db.query(TranslationProject)
        .filter(TranslationProject.consultation_id == consultation_id)
        .first()
    )
    if existing_project:
        if existing_project.project_status in (None, "", "pending", "pending_confirmation"):
            existing_project.project_status = PROJECT_CONFIRMED_STATUS
            db.commit()
            db.refresh(existing_project)
        return existing_project

    project_name = (body.project_name or "").strip() or build_auto_project_name(
        getattr(db_consultation, "client_short_name", None)
    )
    if not project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="客户简称缺失，无法按规则生成项目名称",
        )

    project_data = TranslationProjectCreate(
        project_name=project_name,
        task_type=CONSULTATION_TASK_TYPE_LABELS.get(
            db_consultation.consultation_type,
            db_consultation.consultation_type,
        ),
        consultation_id=db_consultation.id,
        client_id=db_consultation.client_id,
        customer_reception_time=db_consultation.consultation_time,
        project_status=PROJECT_CONFIRMED_STATUS,
        created_by=current_user.id,
    )

    new_project = create_translation_project(db, project_data)
    return new_project


@router.delete("/{consultation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consultation_endpoint(consultation_id: UUID, db: Session = Depends(get_db)):
    success = delete_consultation(db, consultation_id=consultation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return None
