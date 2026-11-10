"""来源分析和客户来源接口：分别沿用咨询、客户模块的读取权限。"""
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import customer_source_analysis as service
from database import get_db
from routers.auth import require_permission

router = APIRouter(tags=['customer-source-analysis'])
Dimension = Literal['source', 'method', 'type', 'keyword', 'status', 'type_status', 'type_confirmed', 'source_confirmed']


@router.get('/data-analysis/customer-sources', dependencies=[Depends(require_permission('consultations:read'))])
def source_summary(
    dimension: Dimension = 'source',
    granularity: Literal['day', 'week', 'month'] = 'day',
    start: Optional[date] = None, end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return service.summary(db, granularity, start=start, end=end, dimension=dimension)


@router.get('/data-analysis/customer-sources/records', dependencies=[Depends(require_permission('consultations:read'))])
def source_records(
    dimension: Dimension = 'source',
    start: Optional[date] = None, end: Optional[date] = None,
    source: Optional[str] = Query(None, max_length=1000),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.records(db, start=start, end=end, source=source, page=page, page_size=page_size, dimension=dimension)


@router.get('/clients/{client_id}/sources', dependencies=[Depends(require_permission('clients:read'))])
def client_source_summary(
    client_id: UUID, granularity: Literal['day', 'week', 'month'] = 'day',
    start: Optional[date] = None, end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return service.summary(db, granularity, client_id, start, end)


@router.get('/clients/{client_id}/sources/records', dependencies=[Depends(require_permission('clients:read'))])
def client_source_records(
    client_id: UUID, start: Optional[date] = None, end: Optional[date] = None,
    source: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.records(db, client_id, start, end, source, page, page_size)
