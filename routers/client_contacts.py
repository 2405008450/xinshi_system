import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
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
from routers.auth import require_module_access
from schemas import ClientContactCreate, ClientContactResponse, ClientContactUpdate
from models import ClientContact

router = APIRouter(prefix="/client-contacts", tags=["client-contacts"], dependencies=[Depends(require_module_access("clients:read", "clients:write"))])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ClientContactResponse, status_code=status.HTTP_201_CREATED)
def create_client_contact_endpoint(
    contact: ClientContactCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(ClientContact).filter(
            ClientContact.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_client_contact(db, existing.id)
    try:
        return create_client_contact(
            db=db, contact=contact, idempotency_key=idempotency_key,
        )
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(ClientContact).filter(
                ClientContact.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_client_contact(db, existing.id)
        logger.exception("创建客户联系人时触发数据库约束")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="联系人数据不符合保存要求，请检查后重试")
    except DatabaseError:
        db.rollback()
        logger.exception("创建客户联系人时数据库异常")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="联系人保存失败，请稍后重试")


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户联系人不存在")
    return db_contact


@router.put("/{contact_id}", response_model=ClientContactResponse)
def update_client_contact_endpoint(contact_id: UUID, contact_update: ClientContactUpdate, db: Session = Depends(get_db)):
    db_contact = update_client_contact(db, contact_id=contact_id, contact_update=contact_update)
    if db_contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户联系人不存在")
    return db_contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_contact_endpoint(contact_id: UUID, db: Session = Depends(get_db)):
    success = delete_client_contact(db, contact_id=contact_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户联系人不存在")
    return None
