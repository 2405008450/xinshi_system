from datetime import datetime
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from database import get_db
from routers.auth import get_current_user
import meeting_service as service

router = APIRouter(prefix='/meetings', tags=['meetings'])
from meeting_reports import ActualWrite, confirm
import meeting_records as records

@router.get('/my-tasks')
def my_tasks(category: Literal['', 'project', 'non_project'] = '', keyword: str = Query('', max_length=300), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user)):
    return records.tasks(db, user, category, keyword, page, page_size)

@router.put('/tasks/{task_id}/status')
def task_status(task_id: UUID, data: records.StatusWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return records.status(db, user, task_id, data)

@router.put('/{meeting_id}/record')
def record(meeting_id: UUID, data: records.RecordWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return records.save(db, user, meeting_id, data)

@router.post('/{meeting_id}/confirm-actual')
def confirm_actual(meeting_id: UUID, data: ActualWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return confirm(db, user, meeting_id, data)

@router.get('/context')
def context(db=Depends(get_db), user=Depends(get_current_user)):
    return service.context(db)

@router.get('/availability')
def availability(start_at: datetime, end_at: datetime, db=Depends(get_db), user=Depends(get_current_user)):
    return service.availability(db, start_at, end_at)

@router.get('/summary')
def summary(db=Depends(get_db), user=Depends(get_current_user)):
    return service.summary(db, user)

@router.get('/client-options')
def clients(keyword: str = Query('', max_length=300), db=Depends(get_db), user=Depends(get_current_user)):
    from models import Client
    from search_matching import keyword_any
    rows = db.query(Client).filter(keyword_any([Client.client_name, Client.client_short_name], keyword)).order_by(Client.client_short_name, Client.id).limit(50).all()
    return [{'id': row.id, 'name': row.client_short_name or row.client_name} for row in rows]

@router.get('/project-options')
def projects(project_type: str, keyword: str = Query('', max_length=300), db=Depends(get_db), user=Depends(get_current_user)):
    from report_project_picker import search
    from fastapi import HTTPException
    if project_type not in ('笔译项目', '口译项目', '标注项目', '招聘项目'):
        raise HTTPException(422, '请选择四类项目之一')
    return search(db, project_type, keyword, 1, 50, period='all')

@router.get('')
def listing(keyword: str = Query('', max_length=300), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user)):
    return service.listing(db, user, keyword, page, page_size)

@router.post('')
def create(data: service.MeetingWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.create(db, user, data)

@router.get('/{meeting_id}')
def detail(meeting_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return service.detail(db, user, meeting_id)

@router.put('/{meeting_id}/receipt')
def receipt(meeting_id: UUID, data: service.ReceiptWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.receipt(db, user, meeting_id, data)

class SeenWrite(BaseModel):
    versions: dict[UUID, int] = Field(default_factory=dict, max_length=2000)

@router.post('/{meeting_id}/receipts-read')
def seen(meeting_id: UUID, data: SeenWrite, db=Depends(get_db), user=Depends(get_current_user)):
    service.read_receipts(db, user, meeting_id, data.versions)
    return {'ok': True}
