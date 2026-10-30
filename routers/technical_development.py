from uuid import UUID
from fastapi import APIRouter, Depends
from database import get_db
from routers.auth import get_current_user
import technical_development as service
import technical_development_report as reports
import technical_task_management as management

class SwapWrite(service.WriteModel):
    target_id: UUID
    revision: int
    target_revision: int

router = APIRouter(prefix='/technical-development', tags=['technical_development'])


@router.get('/access')
def access(db=Depends(get_db), user=Depends(get_current_user)):
    return dict(can_enter=service.can_enter(db, user))


@router.get('/people')
def people(db=Depends(get_db), user=Depends(get_current_user)):
    service.require_user(user, db)
    return service.people(db)


@router.get('/tasks')
def listing(db=Depends(get_db), user=Depends(get_current_user)):
    return service.list_tasks(db, user)


@router.post('/tasks')
def create(data: service.TaskCreate, db=Depends(get_db), user=Depends(get_current_user)):
    return service.create_task(db, user, data)


@router.get('/tasks/{task_id}')
def detail(task_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return service.detail(db, user, task_id)

@router.delete('/tasks/{task_id}')
def delete(task_id: UUID, revision: int, db=Depends(get_db), user=Depends(get_current_user)):
    return management.delete_task(db,user,task_id,revision)

@router.put('/tasks/{task_id}/swap')
def swap(task_id: UUID, data: SwapWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return management.swap_tasks(db,user,task_id,data)


@router.put('/tasks/{task_id}')
def update(task_id: UUID, data: service.TaskUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    return service.update_task(db, user, task_id, data)


@router.put('/tasks/{task_id}/parent')
def move(task_id: UUID, data: service.TaskMove, db=Depends(get_db), user=Depends(get_current_user)):
    return service.update_task(db, user, task_id, data)


@router.post('/tasks/{task_id}/progress')
def progress(task_id: UUID, data: service.ProgressWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.update_task(db, user, task_id, data)


@router.post('/tasks/{task_id}/feedback')
def feedback(task_id: UUID, data: service.FeedbackWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return service.add_feedback(db, user, task_id, data)


@router.get('/tasks/{task_id}/report')
def report_context(task_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    return reports.context(db, user, task_id)


@router.post('/tasks/{task_id}/report')
def add_report(task_id: UUID, data: reports.ReportWrite, db=Depends(get_db), user=Depends(get_current_user)):
    return reports.submit(db, user, task_id, data)
