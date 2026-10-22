from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
import department_service as service

router=APIRouter(prefix='/departments',tags=['departments'])


class DepartmentWrite(BaseModel):
    name: str = Field(min_length=1,max_length=50)
    revision: int | None = Field(default=None,ge=1)

    @field_validator('name',mode='before')
    @classmethod
    def clean_name(cls,value):
        return value.strip() if isinstance(value,str) else value


class MemberWrite(BaseModel):
    user_id: UUID
    position: str = Field(default='', max_length=50)


class RosterWrite(BaseModel):
    revision: int = Field(ge=1)
    members: list[MemberWrite] = Field(max_length=2000)


@router.get('/organization')
def organization(db:Session=Depends(get_db),user=Depends(get_current_user)):
    from organization_service import directory
    return directory(db,user)


@router.put('/{department_id}/members')
def members(department_id:UUID,payload:RosterWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from organization_service import save_members
    return save_members(db,user,department_id,payload.members,payload.revision)


@router.get('')
def catalog(db:Session=Depends(get_db),user=Depends(get_current_user)):
    return service.catalog(db,user)


@router.post('')
def create(payload:DepartmentWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return service.save(db,user,payload.name)


@router.put('/{department_id}')
def update(department_id:UUID,payload:DepartmentWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return service.save(db,user,payload.name,department_id,payload.revision)
