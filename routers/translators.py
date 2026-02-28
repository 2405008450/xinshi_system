from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_translator, get_translators,
    create_translator, update_translator, delete_translator
)
from schemas import TranslatorCreate, TranslatorUpdate, TranslatorResponse

router = APIRouter(prefix="/translators", tags=["translators"])

@router.post("/", response_model=TranslatorResponse, status_code=status.HTTP_201_CREATED)
def create_translator_endpoint(translator: TranslatorCreate, db: Session = Depends(get_db)):
    return create_translator(db=db, translator=translator)

@router.get("/", response_model=List[TranslatorResponse])
def read_translators(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_translators(db, skip=skip, limit=limit)

@router.get("/{translator_id}", response_model=TranslatorResponse)
def read_translator(translator_id: UUID, db: Session = Depends(get_db)):
    db_translator = get_translator(db, translator_id=translator_id)
    if not db_translator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translator not found")
    return db_translator

@router.put("/{translator_id}", response_model=TranslatorResponse)
def update_translator_endpoint(translator_id: UUID, translator_update: TranslatorUpdate, db: Session = Depends(get_db)):
    db_translator = update_translator(db, translator_id=translator_id, translator_update=translator_update)
    if not db_translator:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translator not found")
    return db_translator

@router.delete("/{translator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_translator_endpoint(translator_id: UUID, db: Session = Depends(get_db)):
    success = delete_translator(db, translator_id=translator_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translator not found")
    return None
