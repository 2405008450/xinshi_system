"""个人思考 AI 接口，任务始终按登录用户隔离。"""
from uuid import UUID
from fastapi import APIRouter, Depends
from routers.auth import get_current_user
import thoughts_ai_service as service

router = APIRouter(prefix='/thoughts-ai', tags=['thoughts-ai'])


@router.get('/latest')
def latest(user=Depends(get_current_user)):
    return service.latest(user.id)


@router.post('/jobs', status_code=202)
def create(payload: service.ThoughtRequest, user=Depends(get_current_user)):
    return service.create(user.id, payload)


@router.post('/jobs/{job_id}/cancel')
def cancel(job_id: UUID, user=Depends(get_current_user)):
    return service.cancel(user.id, str(job_id))
