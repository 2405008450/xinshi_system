from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_, and_, literal
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_permission, require_module_access
from permission_service import user_has_permission
import project_arrangement as service
import project_arrangement_history as history
import personal_daily_task as personal
import report_project_picker as picker
import project_arrangement_instruction as instructions
import annotation_work_status as annotation_status
import annotation_daily_operations as operations
import interpretation_work_arrangement as interpretation_arrangement

router = APIRouter(prefix='/project-arrangements', tags=['project-arrangements'])


@router.get('/interpretation-status/{project_id}', dependencies=[Depends(require_permission('tasks:read'))])
def interpretation_arrangement_context(project_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return interpretation_arrangement.context(db,user,project_id)


@router.put('/interpretation-status/{project_id}', dependencies=[Depends(require_permission('tasks:read'))])
def interpretation_arrangement_save(project_id: UUID, payload: annotation_status.ArrangementWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return interpretation_arrangement.save(db,user,project_id,payload)


@router.get('/annotation-operations', dependencies=[Depends(require_permission('reports:read'))])
def annotation_operations(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return operations.context(db, user)


@router.post('/annotation-operations', dependencies=[Depends(require_permission('reports:read'))])
def create_annotation_operations(payload: operations.BatchWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return operations.create(db, user, payload)


@router.put('/annotation-operations/{task_id}', dependencies=[Depends(require_permission('reports:read'))])
def edit_annotation_operation(task_id: UUID, payload: operations.OperationEdit, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return operations.edit(db, user, task_id, payload)


@router.post('/annotation-operations/import-translation', dependencies=[Depends(require_permission('reports:read'))])
def import_translation_operations(payload: operations.ImportWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return operations.import_translation(db, user, payload)


@router.post('/annotation-operations/{task_id}/report', dependencies=[Depends(require_permission('reports:read'))])
def report_annotation_operation(task_id: UUID, payload: operations.RevisionWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return operations.add_report(db, user, task_id, payload)


@router.get('/annotation-status')
def annotation_status_context(project_id: UUID | None = None, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return annotation_status.context(db, user, project_id)


@router.put('/annotation-status/{project_id}')
def annotation_status_arrangement(project_id: UUID, payload: annotation_status.ArrangementWrite,
                                  db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return annotation_status.save_arrangement(db, user, project_id, payload)


@router.post('/annotation-status/{project_id}/submit')
def annotation_status_submit(project_id: UUID, payload: annotation_status.SubmissionWrite,
                            db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return annotation_status.submit(db, user, project_id, payload)


@router.post('/annotation-status-reminder')
def annotation_status_reminder(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return annotation_status.claim_reminder(db, user)


@router.put('/annotation-status-availability')
def annotation_status_availability(payload: annotation_status.AvailabilityWrite,
                                   db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return annotation_status.save_availability(db, user, payload)


@router.get('/annotation-managed')
def annotation_managed(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                       arrangement_scope: str = Query('today', pattern='^(today|not_today|all)$'),
                       db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from annotation_today_tasks import managed_projects
    return managed_projects(db, user, page, page_size, arrangement_scope)


@router.get('/project-search', dependencies=[Depends(require_permission('reports:read'))])
def project_search(project_type: str, keyword: str = '', page: int = Query(1,ge=1), page_size: int = Query(10,ge=1,le=100), period: str = 'week', client_keyword: str = '', direction_keyword: str = '', db: Session = Depends(get_db), user: AppUser = Depends(get_current_user), task_scope: bool = False):
    scope_filter=None
    if task_scope:
        if project_type!='口译项目':
            raise HTTPException(422,'该任务范围仅适用于口译项目')
        from my_project_tasks import interpretation_task_filter
        scope_filter=interpretation_task_filter(db,user)
        from sqlalchemy import and_
        scope_filter=and_(scope_filter,interpretation_arrangement.today_filter(db,user))
    return picker.search(db,project_type,keyword,page,page_size,period,client_keyword,direction_keyword,scope_filter=scope_filter)


@router.post('/personal', dependencies=[Depends(require_permission('reports:read'))])
def create_personal(payload: personal.TaskWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return personal.create(db,user,payload)


@router.patch('/personal/{task_id}')
def edit_personal(task_id: UUID, payload: service.TaskEdit, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return personal.edit(db,user,task_id,payload)


@router.post('/personal-batch', dependencies=[Depends(require_permission('reports:read'))])
def create_personal_batch(payload: personal.TasksWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return personal.create_many(db,user,payload)


@router.put('/personal/{task_id}', dependencies=[Depends(require_permission('reports:read'))])
def replace_personal(task_id: UUID, payload: personal.TaskUpdate, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return personal.replace(db,user,task_id,payload)


@router.post('/personal/{task_id}/complete', dependencies=[Depends(require_permission('reports:read'))])
def complete_personal(task_id: UUID, payload: service.TaskComplete, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return personal.complete(db,user,task_id,payload)


@router.get('/project/{project_id}/detail', dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])
def project_detail(project_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_ready(db)
    return history.detail(db, project_id, page, page_size)


@router.get('/project/{project_id}/orders', dependencies=[Depends(require_permission('projects:read'))])
def project_orders(project_id: UUID, db: Session = Depends(get_db)):
    from project_arrangement_targets import catalog
    return catalog(db, project_id)


@router.put('/project/{project_id}/order', dependencies=[Depends(require_permission('projects:write'))])
def project_order(project_id: UUID, payload: history.ReorderWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return history.reorder(db, user, project_id, payload)


@router.put('/project/{project_id}/instruction', dependencies=[Depends(require_permission('projects:write'))])
def project_instruction(project_id: UUID, payload: instructions.InstructionWrite, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_ready(db)
    return instructions.save(db,user,project_id,payload)


@router.get('/directory', dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])
def directory(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from organization_service import directory as catalog
    data = catalog(db, user)
    return {'ready': service.ready(db), 'people': [p for p in data['people'] if p['active']], 'departments': data['items']}


@router.get('/review-directory')
def review_directory(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    from organization_service import directory as catalog
    data = catalog(db, user)
    allowed = service.allowed_people(db, user)
    people = [p for p in data['people'] if UUID(p['id']) in allowed and p['active']]
    ids = {d['id'] for p in people for d in p['departments']}
    return {'people': people, 'departments': [d for d in data['items'] if d['id'] in ids]}


@router.get('')
def tasks(day: date, review: bool = False, person_id: UUID | None = None, department_id: UUID | None = None,
          project_ids: list[UUID] = Query(default=[]), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
          db: Session = Depends(get_db), user: AppUser = Depends(get_current_user), date_from: date | None = None, date_to: date | None = None, carryover: bool = True):
    if len(project_ids) > 100:
        raise HTTPException(422, '单次最多查询100个项目')
    if not service.ready(db):
        return {'ready': False, 'items': [], 'total': 0}
    query = db.query(service.ProjectArrangement)
    if project_ids:
        if not any(user_has_permission(db, user.id, permission) for permission in ('projects:read', 'projects:write')):
            raise HTTPException(403, '无权查看项目安排')
        query = query.filter(service.ProjectArrangement.project_id.in_(project_ids))
    else:
        ids = service.allowed_people(db, user) if review else {user.id}
        ids = service.access.filter_people_ids(db, ids, department_id)
        if person_id:
            ids.intersection_update({person_id})
        def dated(query,model):
            if date_from or date_to:
                start,end=date_from or date_to,date_to or date_from
                if start>end:raise HTTPException(422,'开始日期不能晚于结束日期')
                return query.filter(model.work_date>=start,model.work_date<=end)
            condition=model.work_date==day
            if carryover:condition=or_(condition,and_(model.work_date<day,model.status!='completed'))
            return query.filter(condition)
        query=dated(query.filter(service.ProjectArrangement.assignee_id.in_(ids)),service.ProjectArrangement)
        if personal.ready(db):
            own=dated(db.query(personal.PersonalDailyTask).filter(personal.PersonalDailyTask.user_id.in_(ids)),personal.PersonalDailyTask)
            operation_source = personal.PersonalDailyTask.report_row['display_metadata']['operation_source'].as_string()
            own = own.filter(or_(operation_source.is_(None), operation_source != operations.SOURCE))
            assigned=query.with_entities(service.ProjectArrangement.id.label('id'),literal('assigned').label('source'),service.ProjectArrangement.work_date.label('work_date'),service.ProjectArrangement.created_at.label('created_at'))
            own=own.with_entities(personal.PersonalDailyTask.id.label('id'),literal('personal').label('source'),personal.PersonalDailyTask.work_date.label('work_date'),personal.PersonalDailyTask.created_at.label('created_at'))
            combined=assigned.union_all(own);total=combined.count()
            selected=combined.order_by('work_date','created_at','id').offset((page-1)*page_size).limit(page_size).all()
            assignments=[db.get(service.ProjectArrangement,row.id) for row in selected if row.source=='assigned']
            mapped={str(row['id']):row for row in service.serialize_many(db,assignments)}
            items=[personal.serialize(db,db.get(personal.PersonalDailyTask,row.id)) if row.source=='personal' else mapped[str(row.id)]|{'source':'assigned'} for row in selected]
            return {'ready':True,'personal_ready':True,'items':items,'total':total}
    total = query.count()
    rows = query.order_by(service.ProjectArrangement.work_date, service.ProjectArrangement.created_at, service.ProjectArrangement.id).offset((page-1)*page_size).limit(page_size).all()
    return {'ready': True, 'items': service.serialize_many(db, rows), 'total': total}


@router.post('/project/{project_id}', dependencies=[Depends(require_permission('projects:write'))])
def assign(project_id: UUID, payload: service.AssignmentBatch, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.create_assignments(db, user, project_id, payload)


@router.patch('/{task_id}')
def edit(task_id: UUID, payload: service.TaskEdit, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.edit_task(db, user, task_id, payload, user_has_permission(db, user.id, 'projects:write'))


@router.delete('/{task_id}', dependencies=[Depends(require_permission('projects:write'))])
def remove(task_id: UUID, payload: service.TaskRemove, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.remove_task(db, user, task_id, payload, can_assign=True)


@router.post('/{task_id}/complete', dependencies=[Depends(require_permission('reports:read'))])
def complete(task_id: UUID, payload: service.TaskComplete, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.complete_task(db, user, task_id, payload)
