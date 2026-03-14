from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session

from crud import (
    count_client_contacts,
    create_client_contact,
    delete_client_contact,
    get_client_contact,
    get_client_contacts,
    update_client_contact,
)
from database import get_db
from routers.auth import get_current_user
from schemas import ClientContactCreate, ClientContactResponse, ClientContactUpdate

router = APIRouter(prefix="/client-contacts", tags=["client-contacts"], dependencies=[Depends(get_current_user)])


@router.post("/", response_model=ClientContactResponse, status_code=status.HTTP_201_CREATED)
def create_client_contact_endpoint(contact: ClientContactCreate, db: Session = Depends(get_db)):
    try:
        return create_client_contact(db=db, contact=contact)
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database integrity error: {error_msg}")
    except DatabaseError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {error_msg}")


@router.get("/", response_model=List[ClientContactResponse])
def read_client_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_client_contacts(db, skip=skip, limit=limit)


@router.get("/count")
def read_client_contact_count(db: Session = Depends(get_db)):
    return {"total": count_client_contacts(db)}


@router.get("/{contact_id}", response_model=ClientContactResponse)
def read_client_contact(contact_id: UUID, db: Session = Depends(get_db)):
    db_contact = get_client_contact(db, contact_id=contact_id)
    if db_contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client contact not found")
    return db_contact


@router.put("/{contact_id}", response_model=ClientContactResponse)
def update_client_contact_endpoint(contact_id: UUID, contact_update: ClientContactUpdate, db: Session = Depends(get_db)):
    db_contact = update_client_contact(db, contact_id=contact_id, contact_update=contact_update)
    if db_contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client contact not found")
    return db_contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_contact_endpoint(contact_id: UUID, db: Session = Depends(get_db)):
    success = delete_client_contact(db, contact_id=contact_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client contact not found")
    return None
