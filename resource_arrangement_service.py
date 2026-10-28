"""平台账号每日统筹；候选读取实时需求，历史内容保存名称快照。"""
from search_matching import keyword_ilike, keyword_or
from copy import deepcopy
from hashlib import sha256
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Text, cast, or_
from sqlalchemy.orm import Session, load_only, selectinload

from interpretation_models import InterpretationLanguage
from models import AppUser, Client, SubClient
from resource_development_models import DevelopmentArrangement as Day, DevelopmentArrangementCell as Cell, DevelopmentOption as Option
from resource_development_service import active_user, can_delegate, require_daily_editor, lock_writes, snapshot, user_name
from recruitment_models import RecruitmentProject
from resource_arrangement_audit import audit, cell_operations, cell_history
from resource_request_models import ResourceRequest
from resource_request_service import SOURCE_MODELS, _request_options
from business_time import business_now, business_iso


def target_key(target):
    return (target['kind'], str(target.get('request_id') or ''), str(target.get('language_id') or ''),
            str(target.get('project_id') or ''))


def cell_owners(cell):
    """兼容迁移前的单负责人记录，并保留当时的姓名快照。"""
    if cell.owners:
        return deepcopy(cell.owners)
    return [{'id': str(cell.owner_id), 'name': cell.owner_name}] if cell.owner_id else []


def can_complete_cell(db, user, cell):
    owners = cell_owners(cell)
    return bool(user.is_active and owners and (str(user.id) in {owner['id'] for owner in owners}
                                               or can_delegate(db, user)))


def target_content_key(target):
    return (*target_key(target), tuple(sorted(item['key'] for item in target.get('scope', []))),
            target.get('arrangement_note') or '')


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


def arrangement_project_options(db, source_type, keyword=None, active_only=False):
    """候选批量带出各订单自己的语言；子订单不从名称推断或沿用母订单语言。"""
    model, _field = SOURCE_MODELS[source_type]
    columns = [model.id, model.order_no, model.project_name, model.updated_at]
    relation = getattr(model, 'language_items' if source_type == 'annotation' else 'language_directions', None)
    if source_type == 'annotation':
        columns.append(model.parent_project_id)
    if source_type == 'translation':
        columns.append(model.language_pair)
    query = db.query(model).options(load_only(*columns))
    if source_type == 'recruitment' and active_only:
        query = query.filter(~model.project_status.in_(('closed', 'cancelled')))
    direction_model = relation.property.mapper.class_ if relation is not None else None
    if relation is not None:
        direction_load = selectinload(relation).load_only(direction_model.source_language_id, direction_model.target_language_id)
        query = query.options(direction_load)
        if hasattr(direction_model, 'extra_languages'):
            query = query.options(direction_load.selectinload(direction_model.extra_languages))
    if source_type == 'translation':
        query = query.filter(model.annotation_migrated_at.is_(None))
    if keyword and keyword.strip():
        pattern = '%' + keyword.strip() + '%'
        query = query.outerjoin(Client, model.client_id == Client.id).outerjoin(SubClient, model.sub_client_id == SubClient.id)
        matches = [keyword_ilike(model.order_no, pattern), keyword_ilike(model.project_name, pattern),
                   keyword_ilike(Client.client_short_name, pattern), keyword_ilike(SubClient.client_short_name, pattern)]
        if relation is not None:
            language_ids = db.query(InterpretationLanguage.id).filter(keyword_ilike(InterpretationLanguage.label, pattern))
            directions = [direction_model.source_language_id.in_(language_ids), direction_model.target_language_id.in_(language_ids)]
            if hasattr(direction_model, 'extra_languages'):
                extra_model = direction_model.extra_languages.property.mapper.class_
                directions.append(direction_model.extra_languages.any(extra_model.language_id.in_(language_ids)))
            matches.append(relation.any(or_(*directions)))
        else:
            matches.append(keyword_ilike(model.language_pair, pattern))
        query = query.filter(or_(*matches))
    projects = query.order_by(model.updated_at.desc(), model.id.desc()).limit(50).all()
    ids_by_project = {}
    for project in projects:
        items = getattr(project, relation.key) if relation is not None else []
        ids_by_project[project.id] = [[value for value in [item.source_language_id, item.target_language_id,
            *(extra.language_id for extra in getattr(item, 'extra_languages', []))] if value] for item in items]
    ids = {value for directions in ids_by_project.values() for direction in directions for value in direction}
    labels = dict(db.query(InterpretationLanguage.id, InterpretationLanguage.label).filter(InterpretationLanguage.id.in_(ids)).all()) if ids else {}
    result = []
    for project in projects:
        languages = [' → '.join(labels[value] for value in direction if value in labels) for direction in ids_by_project[project.id]]
        if source_type == 'translation':
            languages = [value.strip() for value in (project.language_pair or '').replace('；', ';').split(';')]
        result.append({'source_type': source_type, 'project_id': str(project.id), 'order_no': project.order_no or '',
                       'project_name': project.project_name or '',
                       'parent_project_id': str(getattr(project, 'parent_project_id', None) or ''),
                       'languages': list(dict.fromkeys(value for value in languages if value))})
    return result


def request_project(db, request):
    source = SOURCE_MODELS.get(request.source_type)
    if not source:
        return None
    project_id = getattr(request, source[1])
    return source_snapshot(db, request.source_type, project_id) if project_id else None


def request_scope_options(db, request):
    """按项目原有语言项及其地区生成选项，不交叉拼接语言和城市。"""
    source = SOURCE_MODELS.get(request.source_type)
    project_id = getattr(request, source[1], None) if source else None
    project = db.get(source[0], project_id) if project_id else None
    rows = []
    if project and request.source_type == 'annotation' and project.language_items:
        for item in project.language_items:
            ids = [str(value) for value in (item.source_language_id, item.target_language_id) if value]
            labels = [item.source_language_label]
            if item.target_language_id:
                labels.append(item.target_language_label)
            for region in item.regions or [{}]:
                rows.append((str(item.id), ids, ' → '.join(labels), region))
    else:
        from resource_request_service import get_resource_request_source_prefill
        prefill = get_resource_request_source_prefill(db, request.source_type, project_id) if project else None
        items = prefill['items'] if prefill else request.items
        for index, item in enumerate(items):
            if isinstance(item, dict):
                ids = item.get('language_ids') or [item.get('source_language_id'), item.get('target_language_id')]
            else:
                ids = item.language_ids
            ids = [str(value) for value in ids if value]
            languages = [db.get(InterpretationLanguage, UUID(value)) for value in ids]
            label = ' → '.join(language.label for language in languages if language)
            # 招聘工作地点是该项目所有语言方向的共同约束。
            regions = [{'city': project.work_location}] if project and request.source_type == 'recruitment' else [{}]
            if project and request.source_type == 'interpretation':
                regions = [{'city': location} for location in project.locations or []] or [{}]
            for region in regions:
                rows.append((str(index), ids, label, region))
    result = {}
    for item_id, ids, language, region in rows:
        place = {key: str(region.get(key) or '').strip() for key in ('city', 'district', 'street')}
        identity = [request.source_type, str(project_id or request.id), item_id, ids, place]
        key = sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        result[key] = {'key': key, 'language_ids': ids, 'language_label': language or '未配置语种', **place,
                       'label': f"{language or '未配置语种'} · {' / '.join(v for v in place.values() if v) or '未配置城市'}"}
    return list(result.values())


def request_scope_target(db, request, payload, existing=None):
    """只接受选择标识；快照由服务端生成，旧客户端遗漏字段时保留原值。"""
    target = deepcopy(existing) if existing else request_project_target(db, request)
    explicit_scope = payload.selected_scope_keys is not None
    if explicit_scope or not existing:
        options = {item['key']: item for item in request_scope_options(db, request)}
        keys = payload.selected_scope_keys if explicit_scope else list(options)
        if len(keys) != len(set(keys)) or (options and not keys) or any(key not in options for key in keys):
            raise HTTPException(409, '项目语言或城市已变化，请重新加载并选择安排内容')
        target['scope'] = [options[key] for key in keys]
    if payload.arrangement_note is not None or not existing:
        target['arrangement_note'] = (payload.arrangement_note or '').strip()
    return target


def request_project_target(db, request):
    project = request_project(db, request)
    if request.source_type in SOURCE_MODELS and not project:
        raise HTTPException(409, '来源项目不存在，请检查需求')
    return {'kind': 'request_project', 'request_id': str(request.id), 'language_id': None,
            'label': project['project_name'] if project else request.other_source_name or request.source_project_name_snapshot or request.request_no,
            'request_no': request.request_no, 'source_name': request.source_project_name_snapshot,
            'project': project}


def request_arrangements(db, request_ids):
    """批量反查本页需求，来源以需求 ID 为准，同项目不同需求互不混淆。"""
    ids = {str(value) for value in request_ids}
    result = {value: [] for value in ids}
    if not ids:
        return result
    from resource_channel_service import arrangement_platforms
    definitions = {p['id']: p for p in arrangement_platforms(db)}
    query = db.query(Cell, Day.work_date).join(Day, Day.id == Cell.arrangement_id).filter(
        or_(*(cast(Cell.targets, Text).contains(value) for value in ids))
    ).order_by(Day.work_date.desc(), Cell.platform_name, Cell.id)
    for cell, work_date in query:
        definition = definitions.get(str(cell.platform_id), {})
        matches = {str(t.get('request_id')) for t in cell.targets if t.get('request_id')} & ids
        for request_id in matches:
            result[request_id].append({'work_date': work_date.isoformat(), 'platform_id': str(cell.platform_id),
                                      'platform_name': definition.get('parent_name') or definition.get('name') or cell.platform_name,
                                      'account_name': cell.platform_name if definition.get('parent_id') else '单账号',
                                      'owner_name': '、'.join(owner['name'] for owner in cell_owners(cell)),
                                      'owners': cell_owners(cell), 'completed': cell.completed,
                                      'active': all(target_status(db, t)[0] for t in cell.targets if str(t.get('request_id')) == request_id)})
    return result


def request_summary(db, request, arrangements):
    project = request_project(db, request)
    return {'id': str(request.id), 'request_no': request.request_no, 'source_type': request.source_type,
            'order_no': project['order_no'] if project else request.source_order_no_snapshot or '',
            'project_name': project['project_name'] if project else request.other_source_name or request.source_project_name_snapshot or '',
            'project': project, 'request_detail': request.request_detail or '',
            'languages': list(dict.fromkeys(label for item in request.items for label in item.language_labels)),
            'request_status': request.request_status, 'demand_status': request.demand_status,
            'arrangements': arrangements}


def list_arrangement_requests(db, keyword=None, skip=0, limit=5):
    query = db.query(ResourceRequest).options(*_request_options()).filter(
        ResourceRequest.demand_status == 'confirmed', ResourceRequest.request_status != 'cancelled')
    if keyword and keyword.strip():
        pattern = '%' + keyword.strip() + '%'
        fields = [ResourceRequest.request_no, ResourceRequest.source_order_no_snapshot,
                  ResourceRequest.source_project_name_snapshot, ResourceRequest.other_source_name]
        for model, field in SOURCE_MODELS.values():
            query = query.outerjoin(model, getattr(ResourceRequest, field) == model.id)
            fields.extend([model.order_no, model.project_name])
        query = query.filter(keyword_or(lambda _search_part: or_(*(keyword_ilike(field, _search_part) for field in fields)), pattern))
    total = query.count()
    requests = query.order_by(ResourceRequest.requested_at.desc(), ResourceRequest.id).offset(skip).limit(limit).all()
    arrangements = request_arrangements(db, [r.id for r in requests])
    return {'items': [request_summary(db, r, arrangements[str(r.id)]) for r in requests], 'total': total}


def arrangement_request_detail(db, request_id):
    request = db.query(ResourceRequest).options(*_request_options()).filter_by(id=request_id).one_or_none()
    if not request:
        raise HTTPException(404, '需求不存在')
    return request_summary(db, request, request_arrangements(db, [request_id])[str(request_id)]) | {
        'scope_options': request_scope_options(db, request),
    }


def assign_request(db, user, request_id, work_date, payload):
    from resource_development_schemas import ArrangementWrite
    from resource_channel_service import arrangement_platforms
    require_daily_editor(user)
    lock_writes(db)
    day = get_day(db, work_date, locked=True)
    check_day_revision(day, payload.revision)
    request = db.query(ResourceRequest).options(*_request_options()).filter_by(id=request_id).with_for_update().populate_existing().one_or_none()
    if not request_active(request):
        raise HTTPException(409, '需求已暂停、已取消或尚未发送，请刷新后重试')
    request_project_target(db, request)
    cells = {str(c.platform_id): c for c in get_cells(db, day)}
    selected = {str(value) for value in payload.platform_ids}
    linked = {key for key, cell in cells.items() if any(str(t.get('request_id')) == str(request_id) for t in cell.targets)}
    definitions = {p['id']: p for p in arrangement_platforms(db)}
    for key in selected:
        definition = definitions.get(key)
        if not definition or definition['kind'] != 'platform' or (definition.get('has_accounts') and key not in linked):
            raise HTTPException(422, '请选择有效的具体平台账号')
    if not day and not selected:
        raise HTTPException(422, '请至少选择一个平台账号')
    writes = []
    for key in sorted(selected | linked):
        cell = cells.get(key)
        targets = deepcopy(cell.targets) if cell else []
        if key in selected:
            existing = next((t for t in targets if t['kind'] == 'request_project' and str(t.get('request_id')) == str(request_id)), None)
            updated = request_scope_target(db, request, payload, existing)
            if existing:
                targets = [updated if t is existing else t for t in targets]
            else:
                targets.append(updated)
        else:
            targets = [t for t in targets if str(t.get('request_id')) != str(request_id)]
        if len(targets) > 100:
            raise HTTPException(422, '该账号的开拓方向已达100项，请先整理已有安排')
        writes.append({'platform_id': key, 'owner_ids': [owner['id'] for owner in cell_owners(cell)] if cell else [],
                       'targets': [target_write(t) for t in targets],
                       'role_tags': cell.role_tags if cell else [],
                       'projects': [{k: p[k] for k in ('source_type', 'project_id')} for p in cell.projects] if cell else [],
                       'remarks': cell.remarks if cell else ''})
    # 先携带快照进入统一保存路径，由统一归一化再次核对选项。
    return save_arrangement(db, user, work_date, ArrangementWrite(revision=payload.revision, cells=writes))


def target_write(target):
    value = {k: target.get(k) for k in ('kind', 'request_id', 'language_id', 'project_id')}
    if 'scope' in target:
        value['selected_scope_keys'] = [item['key'] for item in target['scope']]
    if 'arrangement_note' in target:
        value['arrangement_note'] = target['arrangement_note']
    return value


def target_status(db, target):
    if target['kind'] == 'internal':
        return True, ''
    if target['kind'] == 'recruitment_project':
        project = db.get(RecruitmentProject, UUID(target['project_id']))
        if not project:
            return False, '招聘项目已删除'
        if project.project_status in {'closed', 'cancelled'}:
            return False, '招聘项目已关闭或取消'
        return True, ''
    if target['kind'] == 'manual':
        language = db.get(InterpretationLanguage, UUID(target['language_id']))
        return (True, '') if language and language.is_active else (False, '语种已停用')
    request = db.get(ResourceRequest, UUID(target['request_id']))
    if not request:
        return False, '需求已删除'
    if request.demand_status == 'cancelled' or request.request_status == 'cancelled':
        return False, '需求已取消'
    if request.demand_status == 'paused':
        return False, '需求已暂停'
    if not request_active(request):
        return False, '需求尚未发送'
    if target['kind'] == 'request_project':
        if request.source_type in SOURCE_MODELS and not request_project(db, request):
            return False, '来源项目已删除'
        if 'scope' in target:
            current = {item['key'] for item in request_scope_options(db, request)}
            if any(item['key'] not in current for item in target['scope']):
                return False, '项目语言或城市已调整'
        return True, ''
    if not language_in_request(request, target['language_id']):
        return False, '需求语种已调整'
    language = db.get(InterpretationLanguage, UUID(target['language_id']))
    if not language or not language.is_active:
        return False, '语种已停用'
    return True, ''


def serialize_cell(db, cell, user, operations=None):
    result = snapshot(cell)
    result['owners'] = cell_owners(cell)
    result['owner_ids'] = [owner['id'] for owner in result['owners']]
    result['owner_name'] = '、'.join(owner['name'] for owner in result['owners'])
    result['can_complete'] = can_complete_cell(db, user, cell)
    result['targets'] = []
    projects = {project_key(p): deepcopy(p) for p in cell.projects}
    for target in cell.targets:
        active, reason = target_status(db, target)
        displayed = deepcopy(target) | {'active': active, 'inactive_reason': reason}
        if target['kind'] == 'request_project':
            displayed['scope_recorded'] = 'scope' in target
            request = db.get(ResourceRequest, UUID(target['request_id']))
            if 'scope' not in displayed:
                displayed['scope'] = request_scope_options(db, request) if request else []
            displayed.setdefault('arrangement_note', '')
        result['targets'].append(displayed)
        if target.get('project'):
            projects.setdefault(project_key(target['project']), deepcopy(target['project']))
    result['manual_projects'] = deepcopy(cell.projects)
    result['projects'] = list(projects.values())
    result['can_edit'] = bool(user.is_active)
    result['operations'] = operations or {'created': None, 'edited': None, 'status': None}
    return result


def read_arrangement(db, user, work_date, day=None):
    day = day or get_day(db, work_date)
    cells = get_cells(db, day)
    operations = cell_operations(db, cells)
    return {'work_date': work_date.isoformat(), 'revision': day.revision if day else 0,
            'remarks': day.remarks if day else '', 'updated_at': business_iso(day.updated_at) if day else None,
            'updated_by_name': user_name(db, day.updated_by) if day else '',
            'can_manage': bool(user.is_active),
            'cells': [serialize_cell(db, cell, user, operations.get(cell.id)) for cell in cells]}


def arrangement_history(db, work_date, platform_id, skip=0, limit=20):
    day = get_day(db, work_date)
    cell = db.query(Cell).filter_by(arrangement_id=day.id, platform_id=platform_id).one_or_none() if day else None
    if not cell:
        raise HTTPException(404, '该账号尚未保存安排')
    return cell_history(db, cell, skip, limit)


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


def arrangement_options(db, source_type=None, keyword=None, recruitment_keyword=None):
    active_languages = {str(value) for (value,) in db.query(InterpretationLanguage.id).filter(InterpretationLanguage.is_active.is_(True))}
    requests = db.query(ResourceRequest).options(*_request_options()).filter(
        ResourceRequest.demand_status == 'confirmed', ResourceRequest.request_status != 'cancelled'
    ).order_by(ResourceRequest.requested_at.desc(), ResourceRequest.id).all()
    targets, request_projects = [], []
    for request in requests:
        project = request_project(db, request)
        request_projects.append(request_project_target(db, request) | {'demand_status': request.demand_status})
        seen = set()
        for item in request.items:
            for language_id, label in zip(item.language_ids, item.language_labels):
                if str(language_id) in seen or str(language_id) not in active_languages:
                    continue
                seen.add(str(language_id))
                targets.append({'kind': 'request', 'request_id': str(request.id), 'language_id': str(language_id),
                                'label': label, 'request_no': request.request_no, 'demand_status': request.demand_status,
                                'source_name': request.source_project_name_snapshot, 'project': project})
    projects = []
    if source_type:
        if source_type not in SOURCE_MODELS:
            raise HTTPException(422, '不支持的项目类型')
        projects = arrangement_project_options(db, source_type, keyword)
    recruitment_projects = (arrangement_project_options(db, 'recruitment', recruitment_keyword, active_only=True)
                            if recruitment_keyword is not None else [])
    return {'targets': targets, 'request_projects': request_projects, 'projects': projects,
            'recruitment_projects': recruitment_projects}


def carry_preview(db, user, work_date):
    require_daily_editor(user)
    if get_day(db, work_date):
        raise HTTPException(409, '该日期已有安排，不能被沿用操作覆盖')
    source = db.query(Day).filter(Day.work_date < work_date).order_by(Day.work_date.desc()).first()
    if not source:
        raise HTTPException(404, '该日期之前没有可沿用的安排')
    draft = read_arrangement(db, user, source.work_date, source)
    warnings = []
    for cell in draft['cells']:
        active_owners = []
        for previous in cell['owners']:
            owner = db.get(AppUser, UUID(previous['id']))
            if owner and owner.is_active:
                active_owners.append(previous)
            else:
                warnings.append(f"{cell['platform_name']}：已跳过停用负责人 {previous['name']}")
        cell['owners'] = active_owners
        cell['owner_ids'] = [owner['id'] for owner in active_owners]
        cell['owner_id'] = active_owners[0]['id'] if active_owners else None
        cell['owner_name'] = '、'.join(owner['name'] for owner in active_owners)
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
                    completed_by_name='', completed_at=None, can_edit=True,
                    operations={'created': None, 'edited': None, 'status': None})
        cell.pop('id', None)
        cell.pop('arrangement_id', None)
    draft.update(work_date=work_date.isoformat(), revision=0, carried_from=source.work_date.isoformat(),
                 updated_at=None, updated_by_name='', warnings=warnings)
    return draft


def normalize_targets(db, payloads, existing):
    old = {target_key(t): t for t in existing}
    result = []
    for payload in payloads:
        value = payload.model_dump(mode='json', exclude={'selected_scope_keys', 'arrangement_note'})
        key = target_key(value)
        if key in old:
            # 已保存的失效来源可以保留，历史快照不能由前端伪造或覆盖。
            previous = old[key]
            scope_unchanged = payload.selected_scope_keys is None or payload.selected_scope_keys == [item['key'] for item in previous.get('scope', [])]
            note_unchanged = payload.arrangement_note is None or payload.arrangement_note == previous.get('arrangement_note', '')
            if payload.kind != 'request_project' or (scope_unchanged and note_unchanged):
                result.append(deepcopy(previous))
                continue
            request = db.query(ResourceRequest).filter_by(id=payload.request_id).with_for_update().populate_existing().one_or_none()
            if not request_active(request):
                raise HTTPException(409, '需求已暂停、已取消或尚未发送，请刷新后重试')
            result.append(request_scope_target(db, request, payload, previous))
            continue
        if payload.kind == 'internal':
            result.append(value | {'label': '内部招聘'})
            continue
        if payload.kind == 'recruitment_project':
            project = db.get(RecruitmentProject, payload.project_id)
            if not project or project.project_status in {'closed', 'cancelled'}:
                raise HTTPException(409, '所选招聘项目已关闭、取消或删除，请刷新开拓方向后重试')
            project_snapshot = source_snapshot(db, 'recruitment', payload.project_id)
            project_option = next((item for item in arrangement_project_options(db, 'recruitment', project.order_no)
                                   if item['project_id'] == str(project.id)), None)
            project_snapshot['languages'] = project_option['languages'] if project_option else []
            result.append(value | {'label': project.project_name or '未命名招聘项目',
                                   'project': project_snapshot})
            continue
        if payload.kind == 'request_project':
            request = db.query(ResourceRequest).filter_by(id=payload.request_id).with_for_update().populate_existing().one_or_none()
            if not request_active(request):
                raise HTTPException(409, '所选需求已暂停、已取消或尚未发送，请刷新后重试')
            result.append(request_scope_target(db, request, payload))
            continue
        language = db.get(InterpretationLanguage, payload.language_id)
        if not language or not language.is_active:
            raise HTTPException(422, '请选择在用的语种或方言')
        value['label'] = language.label
        if payload.kind == 'request':
            # 锁住需求行，避免校验通过到安排提交之间被另一事务取消。
            request = db.query(ResourceRequest).filter_by(id=payload.request_id).with_for_update().populate_existing().one_or_none()
            if not request_active(request) or not language_in_request(request, payload.language_id):
                raise HTTPException(409, '所选需求已暂停、已取消或语种已调整，请刷新开拓方向后重试')
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
    require_daily_editor(user)
    if payload.carried_from:
        if day or payload.carried_from >= work_date or not get_day(db, payload.carried_from):
            raise HTTPException(409, '沿用来源或目标日期已发生变化，请重新加载')
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
        previous_owners = cell_owners(cell) if cell else []
        if value.owner_ids is not None:
            selected_ids = [str(owner_id) for owner_id in value.owner_ids]
        elif 'owner_id' in value.model_fields_set:
            selected_ids = [str(value.owner_id)] if value.owner_id else []
            if len(previous_owners) > 1:
                raise HTTPException(409, '该账号已有多位负责人，请刷新页面后使用新版表单编辑')
        else:
            selected_ids = [owner['id'] for owner in previous_owners]
        previous_by_id = {owner['id']: owner for owner in previous_owners}
        owners = []
        for selected_id in selected_ids:
            if selected_id in previous_by_id:
                owners.append(previous_by_id[selected_id])
            else:
                person = active_user(db, UUID(selected_id))
                owners.append({'id': selected_id, 'name': person.full_name or person.username})
        targets = normalize_targets(db, value.targets, cell.targets if cell else [])
        automatic_keys = {project_key(target['project']) for target in targets
                          if target['kind'] == 'recruitment_project' and target.get('project')}
        projects = [project for project in normalize_projects(db, value.projects, cell.projects if cell else [])
                    if project_key(project) not in automatic_keys]
        # 老客户端未传岗位字段时保留已有内容，显式空数组才表示清空。
        role_tags = value.role_tags if 'role_tags' in value.model_fields_set else (cell.role_tags if cell else [])
        before = snapshot(cell) if cell else None
        if not cell:
            cell = Cell(arrangement_id=day.id, platform_id=platform.id, platform_name=platform.name,
                        owner_name='', targets=[], role_tags=[], projects=[], remarks='', completed=False, completed_by_name='')
            db.add(cell)
        business_changed = ({owner['id'] for owner in cell_owners(cell)} != {owner['id'] for owner in owners}
                            or {target_content_key(t) for t in cell.targets} != {target_content_key(t) for t in targets}
                            or set(cell.role_tags) != set(role_tags)
                            or {project_key(p) for p in cell.projects} != {project_key(p) for p in projects})
        cell.owners = owners
        cell.owner_id = UUID(owners[0]['id']) if owners else None
        cell.owner_name = owners[0]['name'] if owners else ''
        cell.targets, cell.projects, cell.remarks = targets, projects, value.remarks
        cell.role_tags = list(role_tags)
        if business_changed:
            reset_completion(cell)
        if before is None or before != snapshot(cell):
            audit(db, user, cell, 'create' if before is None else 'update', before, carried_from=payload.carried_from)
            changed = True
    if payload.remarks is not None and payload.remarks != day.remarks:
        day.remarks = payload.remarks
        changed = True
    if changed:
        if before_day:
            day.revision += 1
        day.updated_by, day.updated_at = user.id, business_now()
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
    require_daily_editor(user)
    if payload.completed and not cell_owners(cell):
        raise HTTPException(422, '请先分配负责人再标记完成')
    if not can_complete_cell(db, user, cell):
        raise HTTPException(403, '仅该账号负责人或统筹人员可确认完成')
    if cell.completed != payload.completed:
        before = snapshot(cell)
        if payload.completed:
            cell.completed, cell.completed_by = True, user.id
            cell.completed_by_name, cell.completed_at = user_name(db, user.id), business_now()
        else:
            reset_completion(cell)
        audit(db, user, cell, 'complete' if payload.completed else 'reopen', before)
        before_day = snapshot(day)
        day.revision += 1
        day.updated_by, day.updated_at = user.id, business_now()
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
    arrangements = request_arrangements(db, [r.id for r in requests])
    return project | {'project_status': row.project_status,
                      'arrangements': [item | {'request_no': r.request_no}
                                       for r in requests
                                       for item in arrangements[str(r.id)]],
                      'requirements': [{'request_no': r.request_no, 'demand_status': r.demand_status,
                                        'request_status': r.request_status,
                                        'languages': list(dict.fromkeys(label for item in r.items for label in item.language_labels))}
                                       for r in requests]}
