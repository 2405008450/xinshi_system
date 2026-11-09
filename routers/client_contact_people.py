from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Client, SubClient
from client_contact_people import names_for
from routers.auth import require_any_permission,get_current_user
from client_contact_privacy import can_view_client_contacts
from project_client_contact_details import contact_details

router=APIRouter(prefix='/client-contact-people',tags=['client_contact_people'],dependencies=[Depends(require_any_permission('clients:read','clients:write','projects:read','projects:write'))])


@router.get('/access')
def access(db:Session=Depends(get_db),user=Depends(get_current_user)):
    return {'can_view_contacts':can_view_client_contacts(db,user)}


@router.get('')
def options(client_id:UUID,sub_client_id:UUID|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owner=db.get(SubClient,sub_client_id) if sub_client_id else db.get(Client,client_id)
    if not owner:raise HTTPException(404,'客户不存在')
    if sub_client_id and owner.parent_client_id!=client_id:raise HTTPException(400,'子客户不属于当前客户')
    visible=can_view_client_contacts(db,user)
    people=contact_details(db,owner)
    if not visible:people=[{**person,'contact_method':''} for person in people]
    return {'contact_names':names_for(db,owner),'contact_people':people,'can_view_contacts':visible}
