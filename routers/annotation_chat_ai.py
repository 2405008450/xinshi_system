from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, defer

import annotation_chat_ai as ai
import annotation_chat_service
import thoughts_ai_service
from annotation_chat_ai_models import AnnotationChatAnalysis as Job
from annotation_customer_progress_service import CustomerProgressUnavailable
from database import get_db
from models import AppUser
from routers.auth import get_current_user


router = APIRouter(prefix='/chat/annotation-ai', tags=['annotation_chat_ai'])


class RunRequest(BaseModel):
    period: Literal['day', 'week', 'month', 'all']
    auto_apply: bool = False
    all_visible: bool = False


def require_access(db, project_id, user):
    annotation_chat_service.require_project(db, project_id, user)
    ai.require_storage(db)


def get_job(db, project_id, job_id, *, lock=False):
    query = select(Job).where(Job.id == job_id, Job.project_id == project_id)
    job = db.scalar(query.with_for_update() if lock else query)
    if job is None:
        raise HTTPException(404, '分析记录不存在')
    return job


@router.post('/{project_id}/runs', status_code=202)
def start(project_id: UUID, payload: RunRequest, db: Session = Depends(get_db),
          user: AppUser = Depends(get_current_user)):
    return ai.enqueue_manual(db, project_id, user, payload.period, payload.auto_apply, payload.all_visible)


@router.get('/{project_id}/runs')
def history(project_id: UUID, skip: int = Query(0, ge=0), db: Session = Depends(get_db),
            user: AppUser = Depends(get_current_user)):
    require_access(db, project_id, user)
    rows = db.scalars(select(Job).options(defer(Job.results), defer(Job.imports)).where(Job.project_id == project_id)
                      .order_by(Job.created_at.desc(), Job.id.desc()).offset(skip).limit(21)).all()
    return {'items': [ai.public_job(row) for row in rows[:20]], 'has_more': len(rows) > 20,
            'enabled': thoughts_ai_service.enabled()}


@router.get('/{project_id}/runs/{job_id}')
def detail(project_id: UUID, job_id: UUID, db: Session = Depends(get_db),
           user: AppUser = Depends(get_current_user)):
    require_access(db, project_id, user)
    return ai.public_job(get_job(db, project_id, job_id), include_results=True)


@router.post('/{project_id}/runs/{job_id}/progress')
def add_progress(project_id: UUID, job_id: UUID, db: Session = Depends(get_db),
                 user: AppUser = Depends(get_current_user)):
    require_access(db, project_id, user)
    job = get_job(db, project_id, job_id, lock=True)
    try:
        count = ai.import_progress(db, job, user)
        db.commit()
    except (SQLAlchemyError, CustomerProgressUnavailable) as exc:
        db.rollback()
        raise HTTPException(503, '项目进度暂时无法保存') from exc
    return {'created': count, 'run': ai.public_job(job, include_results=True)}
