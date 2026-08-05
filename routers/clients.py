from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_client, get_clients, count_clients,
    create_client, update_client, delete_client,
    get_sub_client, create_sub_client, update_sub_client, delete_sub_client
)
from schemas import ClientCreate, ClientUpdate, ClientResponse, SubClientCreate, SubClientUpdate, SubClientResponse
from routers.auth import require_module_access

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(require_module_access("clients:read", "clients:write"))])

@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(client: ClientCreate, db: Session = Depends(get_db)):
    return create_client(db=db, client=client)

@router.get("/", response_model=List[ClientResponse])
def read_clients(
    skip: int = 0,
    limit: int = 100,
    client_code: Optional[str] = Query(None),
    client_name: Optional[str] = Query(None),
    client_short_name: Optional[str] = Query(None),
    english_name: Optional[str] = Query(None),
    client_manager: Optional[str] = Query(None),
    manager_contact: Optional[str] = Query(None),
    field_level1: Optional[str] = Query(None),
    field_level2: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    client_status: Optional[str] = Query(None),
    cooperation_start_date_from: Optional[date] = Query(None),
    cooperation_start_date_to: Optional[date] = Query(None),
    frequent_first: bool = Query(False),
    db: Session = Depends(get_db)
):
    return get_clients(
        db,
        skip=skip,
        limit=limit,
        client_code=client_code,
        client_name=client_name,
        client_short_name=client_short_name,
        english_name=english_name,
        client_manager=client_manager,
        manager_contact=manager_contact,
        field_level1=field_level1,
        field_level2=field_level2,
        country=country,
        province=province,
        city=city,
        district=district,
        client_status=client_status,
        cooperation_start_date_from=cooperation_start_date_from,
        cooperation_start_date_to=cooperation_start_date_to,
        frequent_first=frequent_first
    )

@router.get("/count")
def read_client_count(
    client_code: Optional[str] = Query(None),
    client_name: Optional[str] = Query(None),
    client_short_name: Optional[str] = Query(None),
    english_name: Optional[str] = Query(None),
    client_manager: Optional[str] = Query(None),
    manager_contact: Optional[str] = Query(None),
    field_level1: Optional[str] = Query(None),
    field_level2: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    client_status: Optional[str] = Query(None),
    cooperation_start_date_from: Optional[date] = Query(None),
    cooperation_start_date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    return {
        "total": count_clients(
            db,
            client_code=client_code,
            client_name=client_name,
            client_short_name=client_short_name,
            english_name=english_name,
            client_manager=client_manager,
            manager_contact=manager_contact,
            field_level1=field_level1,
            field_level2=field_level2,
            country=country,
            province=province,
            city=city,
            district=district,
            client_status=client_status,
            cooperation_start_date_from=cooperation_start_date_from,
            cooperation_start_date_to=cooperation_start_date_to,
        )
    }

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

# --- Sub Client Endpoints ---

@router.post("/{client_id}/sub_clients", response_model=SubClientResponse, status_code=status.HTTP_201_CREATED)
def create_sub_client_endpoint(client_id: UUID, sub_client: SubClientCreate, db: Session = Depends(get_db)):
    if sub_client.parent_client_id != client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path ID and Body ID mismatch")
    return create_sub_client(db=db, sub_client=sub_client)

@router.put("/sub_clients/{sub_id}", response_model=SubClientResponse)
def update_sub_client_endpoint(sub_id: UUID, sub_client_update: SubClientUpdate, db: Session = Depends(get_db)):
    db_sub = update_sub_client(db, sub_id=sub_id, sub_update=sub_client_update)
    if not db_sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub client not found")
    return db_sub

@router.delete("/sub_clients/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_client_endpoint(sub_id: UUID, db: Session = Depends(get_db)):
    success = delete_sub_client(db, sub_id=sub_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub client not found")
    return None
