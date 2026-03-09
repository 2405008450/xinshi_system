from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_consultation, get_consultations,
    create_consultation, update_consultation, delete_consultation
)
from schemas import ConsultationCreate, ConsultationUpdate, ConsultationResponse

router = APIRouter(prefix="/consultations", tags=["consultations"])


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


@router.delete("/{consultation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consultation_endpoint(consultation_id: UUID, db: Session = Depends(get_db)):
    success = delete_consultation(db, consultation_id=consultation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return None
