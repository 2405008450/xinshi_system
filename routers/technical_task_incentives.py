from uuid import UUID
from fastapi import APIRouter, Depends
from database import get_db
from routers.auth import get_current_user
import technical_task_incentives as service

router = APIRouter(prefix='/technical-development', tags=['technical_task_incentives'])


@router.get('/tasks/{task_id}/completion')
def read(task_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return service.read(db, user, task_id)


@router.put('/tasks/{task_id}/completion')
def date(task_id: UUID, payload: service.DateWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.save_date(db, user, task_id, payload)


@router.post('/tasks/{task_id}/incentive')
def amount(task_id: UUID, payload: service.AmountWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.save_amount(db, user, task_id, payload)


@router.get('/incentives')
def statistics(db=Depends(get_db), user=Depends(get_current_user)):
    return service.statistics(db, user)
