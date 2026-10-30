from uuid import UUID
from fastapi import APIRouter, Depends
from database import get_db
from routers.auth import get_current_user
import development_feedback as service

router = APIRouter(prefix='/development-feedback', tags=['development_feedback'])


@router.get('')
def listing(db=Depends(get_db), user=Depends(get_current_user)):
    return service.catalog(db, user)


@router.post('/tasks/{task_id}/generate')
def generate(task_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return service.generate_sheet(db, user, task_id)


@router.post('/tasks/{task_id}/rows')
def create(task_id: UUID, payload: service.CreateFeedback, db=Depends(get_db), user=Depends(get_current_user)):
    return service.create(db, user, task_id, payload)


@router.get('/rows/{feedback_id}')
def detail(feedback_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return service.detail(db, user, feedback_id)


@router.patch('/rows/{feedback_id}')
def update(feedback_id: UUID, payload: service.PatchFeedback, db=Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, feedback_id, payload)


@router.post('/rows/{feedback_id}/opinions')
def opinion(feedback_id: UUID, payload: service.OpinionWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.add_opinion(db, user, feedback_id, payload)
