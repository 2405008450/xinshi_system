from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    get_role, get_role_by_name, get_roles,
    create_role, update_role, delete_role
)
from schemas import RoleCreate, RoleUpdate, RoleResponse

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role_endpoint(role: RoleCreate, db: Session = Depends(get_db)):
    # 检查角色名是否已存在
    db_role = get_role_by_name(db, role_name=role.role_name)
    if db_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name already exists"
        )
    return create_role(db=db, role=role)


@router.get("/", response_model=List[RoleResponse])
def read_roles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    roles = get_roles(db, skip=skip, limit=limit)
    return roles


@router.get("/{role_id}", response_model=RoleResponse)
def read_role(role_id: UUID, db: Session = Depends(get_db)):
    db_role = get_role(db, role_id=role_id)
    if db_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    return db_role


@router.put("/{role_id}", response_model=RoleResponse)
def update_role_endpoint(
    role_id: UUID,
    role_update: RoleUpdate,
    db: Session = Depends(get_db)
):
    db_role = update_role(db, role_id=role_id, role_update=role_update)
    if db_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    return db_role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role_endpoint(role_id: UUID, db: Session = Depends(get_db)):
    success = delete_role(db, role_id=role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    return None
