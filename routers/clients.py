import logging
from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_client, get_clients, count_clients,
    create_client, update_client, delete_client,
    get_sub_client, create_sub_client, update_sub_client, delete_sub_client
)
from schemas import ClientCreate, ClientUpdate, ClientResponse, SubClientCreate, SubClientUpdate, SubClientResponse
from routers.auth import require_module_access
from models import Client, SubClient
from field_filtering import ensure_filter_fields, ensure_filter_operators, parse_field_filters
from pagination_schemas import ClientOptionResponse, PageResponse, resolve_page_total

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(require_module_access("clients:read", "clients:write"))])
logger = logging.getLogger(__name__)

CLIENT_FILTER_FIELDS = {
    "client_code", "client_name", "client_short_name", "english_name", "english_short_name",
    "client_manager", "manager_contact", "field_level1", "field_level2", "country",
    "province", "city", "district", "client_status", "cooperation_start_date", "remarks",
}


def _field_filters(raw: Optional[str]):
    value = parse_field_filters(raw)
    ensure_filter_fields(value, CLIENT_FILTER_FIELDS)
    ensure_filter_operators(value, {field: ({"between"} if field == "cooperation_start_date" else {"in"} if field == "client_status" else {"contains"}) for field in CLIENT_FILTER_FIELDS})
    return value


@router.get("/options", response_model=List[ClientOptionResponse])
def read_client_options(
    keyword: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=50),
    db: Session = Depends(get_db),
):
    query = db.query(Client)
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(
            Client.client_code.ilike(pattern),
            Client.client_name.ilike(pattern),
            Client.client_short_name.ilike(pattern),
            Client.english_name.ilike(pattern),
            Client.english_short_name.ilike(pattern),
        ))
    rows = query.order_by(Client.updated_at.desc(), Client.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "client_code": row.client_code or "",
            "client_name": row.client_name or "",
            "client_short_name": row.client_short_name or row.client_name or "",
        }
        for row in rows
    ]

@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(
    client: ClientCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(Client).filter(Client.idempotency_key == idempotency_key).first()
        if existing:
            return get_client(db, existing.id)
    try:
        return create_client(db=db, client=client, idempotency_key=idempotency_key)
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(Client).filter(Client.idempotency_key == idempotency_key).first()
            if existing:
                return get_client(db, existing.id)
        logger.exception("创建客户时触发数据库约束")
        raise HTTPException(status_code=400, detail="客户数据不符合保存要求，请检查后重试")

@router.get("/", response_model=List[ClientResponse], deprecated=True)
def read_clients(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
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
    field_filters: Optional[str] = Query(None),
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
        frequent_first=frequent_first,
        field_filters=_field_filters(field_filters),
    )

@router.get("/count", deprecated=True)
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
    field_filters: Optional[str] = Query(None),
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
            field_filters=_field_filters(field_filters),
        )
    }


@router.get("/page", response_model=PageResponse[ClientResponse])
def read_client_page(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    client_code: Optional[str] = None,
    client_name: Optional[str] = None,
    client_short_name: Optional[str] = None,
    english_name: Optional[str] = None,
    client_manager: Optional[str] = None,
    manager_contact: Optional[str] = None,
    field_level1: Optional[str] = None,
    field_level2: Optional[str] = None,
    country: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    client_status: Optional[str] = None,
    cooperation_start_date_from: Optional[date] = None,
    cooperation_start_date_to: Optional[date] = None,
    frequent_first: bool = Query(False),
    field_filters: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = dict(
        client_code=client_code, client_name=client_name,
        client_short_name=client_short_name, english_name=english_name,
        client_manager=client_manager, manager_contact=manager_contact,
        field_level1=field_level1, field_level2=field_level2,
        country=country, province=province, city=city, district=district,
        client_status=client_status,
        cooperation_start_date_from=cooperation_start_date_from,
        cooperation_start_date_to=cooperation_start_date_to,
        field_filters=_field_filters(field_filters),
    )
    items = get_clients(
        db, skip=skip, limit=limit, frequent_first=frequent_first, **filters,
    )
    return {
        "items": items,
        "total": resolve_page_total(
            items, skip, lambda: count_clients(db, **filters),
        ),
    }

@router.get("/{client_id}", response_model=ClientResponse)
def read_client(client_id: UUID, db: Session = Depends(get_db)):
    db_client = get_client(db, client_id=client_id)
    if not db_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return db_client

@router.put("/{client_id}", response_model=ClientResponse)
def update_client_endpoint(client_id: UUID, client_update: ClientUpdate, db: Session = Depends(get_db)):
    try:
        db_client = update_client(db, client_id=client_id, client_update=client_update)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not db_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return db_client

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(client_id: UUID, db: Session = Depends(get_db)):
    try:
        success = delete_client(db, client_id=client_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="无法删除该客户：仍被咨询或项目引用，请先处理关联记录")
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return None

# --- Sub Client Endpoints ---

@router.post("/{client_id}/sub_clients", response_model=SubClientResponse, status_code=status.HTTP_201_CREATED)
def create_sub_client_endpoint(
    client_id: UUID,
    sub_client: SubClientCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if sub_client.parent_client_id != client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求路径中的客户标识与提交内容不一致")
    if idempotency_key:
        existing = db.query(SubClient).filter(
            SubClient.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_sub_client(db, existing.id)
    try:
        return create_sub_client(
            db=db, sub_client=sub_client, idempotency_key=idempotency_key,
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(SubClient).filter(
                SubClient.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_sub_client(db, existing.id)
        logger.exception("创建子客户时触发数据库约束")
        raise HTTPException(status_code=400, detail="子客户数据不符合保存要求，请检查后重试")

@router.put("/sub_clients/{sub_id}", response_model=SubClientResponse)
def update_sub_client_endpoint(sub_id: UUID, sub_client_update: SubClientUpdate, db: Session = Depends(get_db)):
    try:
        db_sub = update_sub_client(db, sub_id=sub_id, sub_update=sub_client_update)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not db_sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子客户不存在")
    return db_sub

@router.delete("/sub_clients/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_client_endpoint(sub_id: UUID, db: Session = Depends(get_db)):
    success = delete_sub_client(db, sub_id=sub_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子客户不存在")
    return None
