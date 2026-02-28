from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_client, get_clients,
    create_client, update_client, delete_client
)
from schemas import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/clients", tags=["clients"])

@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(client: ClientCreate, db: Session = Depends(get_db)):
    return create_client(db=db, client=client)

@router.get("/", response_model=List[ClientResponse])
def read_clients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_clients(db, skip=skip, limit=limit)

@router.get("/{client_id}", response_model=ClientResponse)
def read_client(client_id: UUID, db: Session = Depends(get_db)):
    db_client = get_client(db, client_id=client_id)
    if not db_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return db_client

@router.put("/{client_id}", response_model=ClientResponse)
def update_client_endpoint(client_id: UUID, client_update: ClientUpdate, db: Session = Depends(get_db)):
    db_client = update_client(db, client_id=client_id, client_update=client_update)
    if not db_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return db_client

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(client_id: UUID, db: Session = Depends(get_db)):
    success = delete_client(db, client_id=client_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return None
