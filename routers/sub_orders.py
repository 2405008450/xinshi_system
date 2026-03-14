from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import get_db
from crud import (
    get_sub_order, get_sub_orders_by_project, get_all_sub_orders,
    create_sub_order, update_sub_order, delete_sub_order
)
from schemas import TranslationSubOrderCreate, TranslationSubOrderUpdate, TranslationSubOrderResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/sub-orders", tags=["sub-orders"], dependencies=[Depends(get_current_user)])


@router.post("/", response_model=TranslationSubOrderResponse, status_code=status.HTTP_201_CREATED)
def create_sub_order_endpoint(sub_order: TranslationSubOrderCreate, db: Session = Depends(get_db)):
    try:
        return create_sub_order(db=db, sub_order=sub_order)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据库约束错误: {error_msg}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=List[TranslationSubOrderResponse])
def read_all_sub_orders(skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    return get_all_sub_orders(db, skip=skip, limit=limit)


@router.get("/project/{project_id}", response_model=List[TranslationSubOrderResponse])
def read_sub_orders_by_project(project_id: UUID, db: Session = Depends(get_db)):
    """获取指定母订单下的所有子订单"""
    return get_sub_orders_by_project(db, parent_project_id=project_id)


@router.get("/{sub_order_id}", response_model=TranslationSubOrderResponse)
def read_sub_order(sub_order_id: UUID, db: Session = Depends(get_db)):
    db_sub = get_sub_order(db, sub_order_id=sub_order_id)
    if db_sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子订单不存在")
    return db_sub


@router.put("/{sub_order_id}", response_model=TranslationSubOrderResponse)
def update_sub_order_endpoint(
    sub_order_id: UUID,
    sub_order_update: TranslationSubOrderUpdate,
    db: Session = Depends(get_db)
):
    db_sub = update_sub_order(db, sub_order_id=sub_order_id, sub_order_update=sub_order_update)
    if db_sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子订单不存在")
    return db_sub


@router.delete("/{sub_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_order_endpoint(sub_order_id: UUID, db: Session = Depends(get_db)):
    success = delete_sub_order(db, sub_order_id=sub_order_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子订单不存在")
    return None
