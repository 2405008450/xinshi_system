"""平台账号每日统筹；候选读取实时需求，历史内容保存名称快照。"""
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from interpretation_models import InterpretationLanguage
from models import AppUser
from resource_development_models import DevelopmentArrangement as Day, DevelopmentArrangementCell as Cell, DevelopmentOption as Option
from resource_development_service import active_user, audit, can_delegate, lock_writes, snapshot, user_name
from resource_request_models import ResourceRequest
from resource_request_service import SOURCE_MODELS, _request_options, list_source_project_options


def target_key(target):
    return (target['kind'], str(target.get('request_id') or ''), str(target.get('language_id') or ''))


def project_key(project):
    return (project['source_type'], str(project['project_id']))


def get_day(db, work_date, locked=False):
    query = db.query(Day).filter_by(work_date=work_date)
    if locked:
        query = query.with_for_update().populate_existing()
    return query.one_or_none()


def get_cells(db, day):
    return db.query(Cell).filter_by(arrangement_id=day.id).order_by(Cell.platform_name, Cell.id).all() if day else []


def request_active(request):
    return bool(request and request.demand_status == 'confirmed' and request.request_status != 'cancelled')


def language_in_request(request, language_id):
    return bool(request and any(str(language_id) in {str(value) for value in item.language_ids} for item in request.items))


def source_snapshot(db, source_type, project_id):
    model, _field = SOURCE_MODELS[source_type]
    project = db.get(model, UUID(str(project_id)))
    if not project:
        return None
    return {'source_type': source_type, 'project_id': str(project.id),
            'order_no': project.order_no or '', 'project_name': project.project_name or '',
            'parent_project_id': str(getattr(project, 'parent_project_id', None) or '')}


def request_project(db, request):
    source = SOURCE_MODELS.get(request.source_type)
    if not source:
        return None
    project_id = getattr(request, source[1])
    return source_snapshot(db, request.source_type, project_id) if project_id else None


def target_status(db, target):
    if target['kind'] == 'internal':
        return True, ''
    if target['kind'] == 'manual':
        language = db.get(InterpretationLanguage, UUID(target['language_id']))
        return (True, '') if language and language.is_active else (False, '语种已停用')
    request = db.get(ResourceRequest, UUID(target['request_id']))
    if not request:
        return False, '需求已删除'
    if request.demand_status == 'cancelled' or request.request_status == 'cancelled':
        return False, '需求已取消'
    if not request_active(request):
        return False, '需求尚未发送'
    if not language_in_request(request, target['language_id']):
        return False, '需求语种已调整'
    language = db.get(InterpretationLanguage, UUID(target['language_id']))
    if not language or not language.is_active:
        return False, '语种已停用'
    return True, ''


def serialize_cell(db, cell, user):
    result = snapshot(cell)
    result['targets'] = []
    projects = {project_key(p): deepcopy(p) for p in cell.projects}
    for target in cell.targets:
        active, reason = target_status(db, target)
        result['targets'].append(deepcopy(target) | {'active': active, 'inactive_reason': reason})
        if target.get('project'):
            projects.setdefault(project_key(target['project']), deepcopy(target['project']))
    result['manual_projects'] = deepcopy(cell.projects)
    result['projects'] = list(projects.values())
    result['can_edit'] = can_delegate(db, user) or cell.owner_id == user.id
    return result


def read_arrangement(db, user, work_date, day=None):
    day = day or get_day(db, work_date)
    return {'work_date': work_date.isoformat(), 'revision': day.revision if day else 0,
            'remarks': day.remarks if day else '', 'updated_at': day.updated_at if day else None,
            'updated_by_name': user_name(db, day.updated_by) if day else '',
            'can_manage': can_delegate(db, user),
            'cells': [serialize_cell(db, cell, user) for cell in get_cells(db, day)]}


def list_arrangements(db, user, start=None, end=None, skip=0, limit=14):
    if start and end and start > end:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    query = db.query(Day)
    if start:
        query = query.filter(Day.work_date >= start)
    if end:
        query = query.filter(Day.work_date <= end)
    total = query.count()
    days = query.order_by(Day.work_date.desc()).offset(skip).limit(limit).all()
    return {'items': [read_arrangement(db, user, day.work_date, day) for day in days], 'total': total}


def arrangement_options(db, source_type=None, keyword=None):
    active_languages = {str(value) for (value,) in db.query(InterpretationLanguage.id).filter(InterpretationLanguage.is_active.is_(True))}
    requests = db.query(ResourceRequest).options(*_request_options()).filter(
        ResourceRequest.demand_status == 'confirmed', ResourceRequest.request_status != 'cancelled'
    ).order_by(ResourceRequest.requested_at.desc(), ResourceRequest.id).all()
    targets = []
    for request in requests:
        project = request_project(db, request)
        seen = set()
        for item in request.items:
            for language_id, label in zip(item.language_ids, item.language_labels):
                if str(language_id) in seen or str(language_id) not in active_languages:
                    continue
                seen.add(str(language_id))
                targets.append({'kind': 'request', 'request_id': str(request.id), 'language_id': str(language_id),
                                'label': label, 'request_no': request.request_no,
                                'source_name': request.source_project_name_snapshot, 'project': project})
    projects = []
    if source_type:
        if source_type not in SOURCE_MODELS:
            raise HTTPException(422, '不支持的项目类型')
        for project in list_source_project_options(db, source_type, keyword=keyword, limit=50):
            projects.append(source_snapshot(db, source_type, project['id']))
    return {'targets': targets, 'projects': projects}


def carry_preview(db, user, work_date):
    if not can_delegate(db, user):
        raise HTTPException(403, '沿用整日安排需要资源开拓代录权限')
    if get_day(db, work_date):
        raise HTTPException(409, '该日期已有安排，不能被沿用操作覆盖')
    source = db.query(Day).filter(Day.work_date < work_date).order_by(Day.work_date.desc()).first()
    if not source:
        raise HTTPException(404, '该日期之前没有可沿用的安排')
    draft = read_arrangement(db, user, source.work_date, source)
    warnings = []
    for cell in draft['cells']:
        owner = db.get(AppUser, UUID(cell['owner_id'])) if cell['owner_id'] else None
        if cell['owner_id'] and (not owner or not owner.is_active):
            warnings.append(f"{cell['platform_name']}：已跳过停用负责人 {cell['owner_name']}")
            cell['owner_id'], cell['owner_name'] = None, ''
        active_targets = []
        for target in cell['targets']:
            if target['active']:
                active_targets.append(target)
            else:
                warnings.append(f"{cell['platform_name']}：已跳过 {target['label']}（{target['inactive_reason']}）")
        cell['targets'] = active_targets
        manual_projects = []
        for project in cell['manual_projects']:
            if source_snapshot(db, project['source_type'], project['project_id']):
                manual_projects.append(project)
            else:
                warnings.append(f"{cell['platform_name']}：已跳过不存在的项目 {project['project_name']}")
        cell['manual_projects'] = manual_projects
        projects = {project_key(p): p for p in manual_projects}
        for target in active_targets:
            if target.get('project'):
                projects.setdefault(project_key(target['project']), target['project'])
        cell.update(projects=list(projects.values()), completed=False, completed_by=None,
                    completed_by_name='', completed_at=None, can_edit=True)
        cell.pop('id', None)
        cell.pop('arrangement_id', None)
    draft.update(work_date=work_date.isoformat(), revision=0, carried_from=source.work_date.isoformat(),
                 updated_at=None, updated_by_name='', warnings=warnings)
    return draft


def normalize_targets(db, payloads, existing):
    old = {target_key(t): t for t in existing}
    result = []
    for payload in payloads:
        value = payload.model_dump(mode='json')
        key = target_key(value)
        if key in old:
            # 已保存的失效来源可以保留，历史快照不能由前端伪造或覆盖。
            result.append(deepcopy(old[key]))
            continue
        if payload.kind == 'internal':
            result.append(value | {'label': '内部招聘'})
            continue
        language = db.get(InterpretationLanguage, payload.language_id)
        if not language or not language.is_active:
            raise HTTPException(422, '请选择在用的语种或方言')
        value['label'] = language.label
        if payload.kind == 'request':
            # 锁住需求行，避免校验通过到安排提交之间被另一事务取消。
            request = db.query(ResourceRequest).filter_by(id=payload.request_id).with_for_update().populate_existing().one_or_none()
            if not request_active(request) or not language_in_request(request, payload.language_id):
                raise HTTPException(409, '所选需求已取消或语种已调整，请刷新开拓方向后重试')
            value.update(request_no=request.request_no, source_name=request.source_project_name_snapshot,
                         project=request_project(db, request))
        result.append(value)
    return result


def normalize_projects(db, payloads, existing):
    old = {project_key(p): p for p in existing}
    result = []
    for payload in payloads:
        value = payload.model_dump(mode='json')
        key = project_key(value)
        if key in old:
            result.append(deepcopy(old[key]))
            continue
        project = source_snapshot(db, payload.source_type, payload.project_id)
        if not project:
            raise HTTPException(422, '关联项目不存在，请重新选择')
        result.append(project)
    return result


def check_day_revision(day, revision):
    if (day.revision if day else 0) != revision:
        raise HTTPException(409, '这一天已被其他人修改，请重新加载；当前草稿仍可保留')


def reset_completion(cell):
    cell.completed = False
    cell.completed_by = None
    cell.completed_by_name = ''
    cell.completed_at = None


def save_arrangement(db: Session, user, work_date, payload):
    lock_writes(db)
    day = get_day(db, work_date, locked=True)
    check_day_revision(day, payload.revision)
    manager = can_delegate(db, user)
    if not day and not manager:
        raise HTTPException(403, '新建整日安排需要资源开拓代录权限')
    if payload.carried_from:
        if not manager or day or payload.carried_from >= work_date or not get_day(db, payload.carried_from):
            raise HTTPException(409, '沿用来源或目标日期已发生变化，请重新加载')
    if payload.remarks is not None and not manager and payload.remarks != day.remarks:
        raise HTTPException(403, '每日备注仅由统筹人员维护')
    if not day:
        day = Day(work_date=work_date, remarks='', revision=1, created_by=user.id, updated_by=user.id)
        db.add(day)
        db.flush()
        before_day = None
    else:
        before_day = snapshot(day)
    cells = {str(c.platform_id): c for c in get_cells(db, day)}
    changed = before_day is None
    for value in payload.cells:
        cell = cells.get(str(value.platform_id))
        platform = db.get(Option, value.platform_id)
        if not platform or platform.kind != 'platform':
            raise HTTPException(422, '请选择有效的开拓平台账号')
        if not manager and (not cell or cell.owner_id != user.id or value.owner_id != cell.owner_id):
            raise HTTPException(403, '只能维护本人被分配的账号，不能转交负责人')
        if value.owner_id and (not cell or value.owner_id != cell.owner_id):
            owner = active_user(db, value.owner_id)
            owner_label = owner.full_name or owner.username
        else:
            owner_label = cell.owner_name if cell and value.owner_id else ''
        targets = normalize_targets(db, value.targets, cell.targets if cell else [])
        projects = normalize_projects(db, value.projects, cell.projects if cell else [])
        before = snapshot(cell) if cell else None
        if not cell:
            cell = Cell(arrangement_id=day.id, platform_id=platform.id, platform_name=platform.name,
                        owner_name='', targets=[], projects=[], remarks='', completed=False, completed_by_name='')
            db.add(cell)
        business_changed = (cell.owner_id != value.owner_id
                            or {target_key(t) for t in cell.targets} != {target_key(t) for t in targets}
                            or {project_key(p) for p in cell.projects} != {project_key(p) for p in projects})
        cell.owner_id, cell.owner_name = value.owner_id, owner_label
        cell.targets, cell.projects, cell.remarks = targets, projects, value.remarks
        if business_changed:
            reset_completion(cell)
        if before is None or before != snapshot(cell):
            audit(db, user, cell, 'create' if before is None else 'update', before)
            changed = True
    if payload.remarks is not None and payload.remarks != day.remarks:
        day.remarks = payload.remarks
        changed = True
    if changed:
        if before_day:
            day.revision += 1
        day.updated_by, day.updated_at = user.id, datetime.now()
        audit(db, user, day, 'carry' if payload.carried_from else ('update' if before_day else 'create'),
              (before_day or {}) | ({'carried_from': payload.carried_from.isoformat()} if payload.carried_from else {}))
    db.flush()
    return day


def complete_arrangement(db, user, work_date, platform_id, payload):
    lock_writes(db)
    day = get_day(db, work_date, locked=True)
    if not day:
        raise HTTPException(404, '请先保存每日安排')
    check_day_revision(day, payload.revision)
    cell = db.query(Cell).filter_by(arrangement_id=day.id, platform_id=platform_id).one_or_none()
    if not cell:
        raise HTTPException(404, '该账号尚未保存安排')
    if not can_delegate(db, user) and cell.owner_id != user.id:
        raise HTTPException(403, '只能修改本人被分配账号的完成状态')
    if payload.completed and not cell.owner_id:
        raise HTTPException(422, '请先分配负责人再标记完成')
    if cell.completed != payload.completed:
        before = snapshot(cell)
        if payload.completed:
            cell.completed, cell.completed_by = True, user.id
            cell.completed_by_name, cell.completed_at = user_name(db, user.id), datetime.now()
        else:
            reset_completion(cell)
        audit(db, user, cell, 'complete' if payload.completed else 'reopen', before)
        before_day = snapshot(day)
        day.revision += 1
        day.updated_by, day.updated_at = user.id, datetime.now()
        audit(db, user, day, 'update', before_day)
    db.flush()
    return day


def project_detail(db, source_type, project_id):
    if source_type not in SOURCE_MODELS:
        raise HTTPException(422, '不支持的项目类型')
    project = source_snapshot(db, source_type, project_id)
    if not project:
        raise HTTPException(404, '项目不存在')
    model, field = SOURCE_MODELS[source_type]
    row = db.get(model, project_id)
    requests = db.query(ResourceRequest).options(*_request_options()).filter(
        getattr(ResourceRequest, field) == project_id
    ).order_by(ResourceRequest.updated_at.desc()).all()
    return project | {'project_status': row.project_status,
                      'requirements': [{'request_no': r.request_no, 'demand_status': r.demand_status,
                                        'request_status': r.request_status,
                                        'languages': list(dict.fromkeys(label for item in r.items for label in item.language_labels))}
                                       for r in requests]}
