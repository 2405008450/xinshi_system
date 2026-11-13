from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from client_contact_people import attach
from client_contact_privacy import can_view_client_contacts
from database import get_db
from models import Client, SubClient
from permission_service import user_has_permission
from routers.auth import get_current_user

router = APIRouter(prefix='/client-management-window', tags=['clients'])


def identity(row):
    is_sub = isinstance(row, SubClient)
    return {
        'client_id': row.parent_client_id if is_sub else row.id,
        'sub_client_id': row.id if is_sub else None,
        'name': row.client_name,
        'short_name': row.client_short_name,
        'code': row.sub_client_code if is_sub else row.client_code,
    }


def contact_preview(value, count):
    # 电话区号符号、空格等标点不占字母、汉字和数字的额度。
    return ''.join(char for char in str(value or '') if char.isalnum())[:count]


def contact_rows(row, full_access):
    return [
        {
            'name': person['name'] if full_access else contact_preview(person['name'], 1),
            'method': person['contact_method'] if full_access else contact_preview(person['contact_method'], 3),
            **({'description': person['description']} if full_access else {}),
        }
        for person in row.contact_people
    ]


@router.get('')
def read_window(
    response: Response,
    client_id: UUID | None = None,
    sub_client_id: UUID | None = None,
    short_name: str = Query('', max_length=255),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    response.headers['Cache-Control'] = 'private, no-store'
    if sub_client_id:
        row = db.get(SubClient, sub_client_id)
        if row and client_id and row.parent_client_id != client_id:
            raise HTTPException(404, '子客户不属于当前客户')
    elif client_id:
        row = db.get(Client, client_id)
    else:
        name = short_name.strip().lower()
        if not name:
            raise HTTPException(404, '未关联客户')
        matches = []
        for model in (Client, SubClient):
            matches.extend(db.query(model).filter(func.lower(func.trim(model.client_short_name)) == name).order_by(model.id).limit(20).all())
        if len(matches) > 1:
            return {'matches': [identity(match) for match in matches]}
        row = matches[0] if matches else None
    if not row:
        raise HTTPException(404, '未找到该客户')

    full_access = can_view_client_contacts(db, user)
    is_sub = isinstance(row, SubClient)
    attach(db, sub_clients=[row]) if is_sub else attach(db, clients=[row])
    parent = db.get(Client, row.parent_client_id) if is_sub else row
    return {
        **identity(row),
        'parent': identity(parent) if is_sub and parent else None,
        'children': [identity(child) for child in row.sub_clients] if not is_sub else [],
        'contacts': contact_rows(row, full_access),
        'full_access': full_access,
        'can_manage': full_access and (user_has_permission(db, user.id, 'clients:read') or user_has_permission(db, user.id, 'clients:write')),
    }
