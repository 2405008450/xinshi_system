"""工作台项目与安排任务统一查询，权限沿用各业务模块，先筛选再分页。"""
from fastapi import HTTPException
from sqlalchemy import Date, Integer, String, Uuid, and_, cast, exists, func, literal, null, or_

from annotation_models import AnnotationProject
from annotation_work_arrangement import latest_status_expression
from annotation_work_status_models import AnnotationWorkDay
from chat_time import api_time
from models import AppUser, Client, SubClient, TranslationProject, TranslationSubOrder
from my_project_tasks import LABELS, MODELS, project_query
from search_matching import keyword_any
from workflow_models import ProjectWorkbenchResponsibility
from work_report_dates import report_business_date
import personal_daily_task as personal
import project_arrangement as arrangements


GROUPS = ('translation', 'interpretation', 'annotation', 'recruitment')
REPORT_TYPES = {'translation': '笔译项目', 'interpretation': '口译项目', 'annotation': '标注项目', 'recruitment': '招聘项目'}
FILTER_FIELDS = {'project_type', 'order_no', 'project_name', 'client_name', 'content',
                 'task_status', 'arrangement_status', 'work_date', 'estimated_minutes', 'actual_minutes',
                 'customer_requirements', 'common_instruction', 'execution_sequence'}


def dated(query, model, day, date_from, date_to):
    if date_from or date_to:
        start, end = date_from or date_to, date_to or date_from
        if start > end:
            raise HTTPException(422, '开始日期不能晚于结束日期')
        return query.filter(model.work_date.between(start, end))
    return query.filter(or_(model.work_date == day, and_(model.work_date < day, model.status != 'completed')))


def projected(query, model, group, *, source='project', task=None, order=None, name=None, content=None):
    if group == 'other':
        project_id, status = null().cast(Uuid), literal('')
    else:
        project_id, status = model.id, func.coalesce(model.project_status, '')
    if name is None:
        name = func.coalesce(model.source_file_name, model.project_name, '') if group == 'translation' else model.project_name
    return query.with_entities(
        (task.id if task is not None else model.id).label('id'),
        literal(source).label('source'), literal(group).label('project_type'),
        project_id.label('project_id'),
        (order if order is not None else model.order_no).label('order_no'),
        func.coalesce(name, '').label('project_name'),
        func.coalesce(SubClient.client_short_name, SubClient.client_name, Client.client_short_name, Client.client_name, '').label('client_name'),
        func.coalesce(SubClient.client_name, Client.client_name, '').label('client_full_name'),
        func.coalesce(content if content is not None else literal(''), '').label('content'),
        status.label('project_status'),
        (task.status if task is not None else literal('')).label('task_status'),
        (task.work_date if task is not None else null().cast(Date)).label('work_date'),
        (task.estimated_minutes if task is not None else null().cast(Integer)).label('estimated_minutes'),
        (task.actual_minutes if task is not None else null().cast(Integer)).label('actual_minutes'),
    )


def catalog(db, user, day, date_from, date_to):
    sources = []
    if arrangements.ready(db):
        task = arrangements.ProjectArrangement
        model = TranslationProject
        query = db.query(task).join(model, model.id == task.project_id).outerjoin(
            Client, Client.id == model.client_id).outerjoin(SubClient, SubClient.id == model.sub_client_id)
        query = dated(query.filter(task.assignee_id == user.id), task, day, date_from, date_to)
        order, name = model.order_no, func.coalesce(model.source_file_name, model.project_name)
        if arrangements.targets.ready(db):
            target = arrangements.targets.ArrangementOrderTarget
            query = query.outerjoin(target, target.arrangement_id == task.id).outerjoin(
                TranslationSubOrder, TranslationSubOrder.id == target.sub_order_id)
            order = func.coalesce(TranslationSubOrder.sub_order_no, target.order_no, model.order_no)
            name = func.coalesce(TranslationSubOrder.sub_project_name, target.project_name, name)
        sources.append(projected(query, model, 'translation', source='assigned', task=task,
                                 order=order, name=name, content=task.content))
    if personal.ready(db):
        task = personal.PersonalDailyTask
        metadata = task.report_row['display_metadata']
        source = metadata['operation_source'].as_string()
        base = dated(db.query(task).filter(task.user_id == user.id, or_(
            source.is_(None), source != 'annotation_daily_operation')), task, day, date_from, date_to)
        selected_type = func.coalesce(metadata['selected_project_type'].as_string(), metadata['report_types'][0].as_string(), '')
        for group in (*GROUPS, 'other'):
            if group == 'other':
                query = base.filter(selected_type.notin_(list(REPORT_TYPES.values())))
                # 无项目类型的自主任务保持可见。
                query = query.outerjoin(Client, literal(False)).outerjoin(SubClient, literal(False))
                model = task
            else:
                model = MODELS[group]
                project_key = func.replace(cast(model.id, String), '-', '')
                query = base.filter(selected_type == REPORT_TYPES[group]).outerjoin(
                    model, project_key == func.replace(metadata['project_id'].as_string(), '-', '')
                ).outerjoin(Client, Client.id == model.client_id).outerjoin(SubClient, SubClient.id == model.sub_client_id)
            sources.append(projected(query, model, group, source='personal', task=task,
                                     order=func.coalesce(metadata['order_no'].as_string(), ''),
                                     name=task.report_row['task_name'].as_string(),
                                     content=task.report_row['progress_content'].as_string()))
    task_rows = sources[0].union_all(*sources[1:]).subquery() if sources else None
    projects = []
    for group in GROUPS:
        model, query = project_query(db, user, group)
        if task_rows is not None:
            query = query.filter(~exists().where(task_rows.c.project_type == group, task_rows.c.project_id == model.id))
        content = getattr(model, 'task_description', literal(''))
        projects.append(projected(query, model, group, content=content))
    return projects[0].union_all(*projects[1:], *sources).subquery()


def search(db, user, day, *, keyword='', filters=None, statuses=None, page=1, page_size=20,
           date_from=None, date_to=None):
    from sqlalchemy import inspect

    base = catalog(db, user, day, date_from, date_to)
    query = db.query(base)
    annotation_state = literal('')
    if inspect(db.connection()).has_table(AnnotationWorkDay.__tablename__):
        annotation_state = func.coalesce(latest_status_expression(user.id, report_business_date(), base.c.project_id), 'in_progress')
    from sqlalchemy import case
    arrangement_state = case((base.c.project_type == 'annotation', annotation_state), else_=literal(''))
    query = query.add_columns(arrangement_state.label('arrangement_status'))
    options = {}
    for group, status in db.query(base.c.project_type, base.c.project_status).distinct():
        options.setdefault(group, set())
        if status:
            options[group].add(status)
    if keyword:
        query = query.filter(keyword_any([base.c.order_no, base.c.project_name, base.c.client_name, base.c.client_full_name, base.c.content], keyword))
    for key, value in (filters or {}).items():
        if key not in FILTER_FIELDS:
            raise HTTPException(422, '不支持该筛选字段')
        if value in (None, '', []):
            continue
        if not isinstance(value, (str, int, list)) or isinstance(value, bool):
            raise HTTPException(422, '筛选条件须为文字或选项列表')
        if isinstance(value, list) and not all(isinstance(item, str) for item in value):
            raise HTTPException(422, '筛选选项格式不正确')
        if key == 'execution_sequence':
            if not arrangements.ready(db):
                query = query.filter(False)
                continue
            task = arrangements.ProjectArrangement
            project_ids = db.query(task.project_id).join(AppUser, AppUser.id == task.assignee_id).filter(
                keyword_any([AppUser.full_name, AppUser.username, task.content], str(value)))
            query = query.filter(base.c.source == 'assigned', base.c.project_id.in_(project_ids))
            continue
        if key == 'customer_requirements':
            project_ids = db.query(TranslationProject.id).filter(keyword_any([
                TranslationProject.customer_requirement_professional, TranslationProject.customer_requirement_special,
            ], str(value)))
            query = query.filter(base.c.project_type == 'translation', base.c.project_id.in_(project_ids))
            continue
        if key == 'common_instruction':
            instruction = arrangements.instructions.ArrangementInstruction
            project_ids = db.query(instruction.project_id).filter(keyword_any([instruction.content], str(value)))
            query = query.filter(base.c.project_type == 'translation', base.c.project_id.in_(project_ids)) if arrangements.instructions.ready(db) else query.filter(False)
            continue
        column = arrangement_state if key == 'arrangement_status' else base.c[key]
        if isinstance(value, list):
            query = query.filter(column.in_(value))
        elif key in ('estimated_minutes', 'actual_minutes'):
            try:
                minutes = int(value)
            except (ValueError, TypeError):
                raise HTTPException(422, '用时筛选须填写分钟数')
            query = query.filter(column == minutes)
        elif key == 'client_name':
            query = query.filter(keyword_any([base.c.client_name, base.c.client_full_name], str(value)))
        else:
            query = query.filter(keyword_any([cast(column, String)], str(value)))
    active_statuses = {key: values for key, values in (statuses or {}).items() if values}
    for group, values in active_statuses.items():
        if group not in GROUPS or not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise HTTPException(422, '项目状态筛选格式不正确')
        query = query.filter(or_(base.c.project_type != group, base.c.project_status.in_(values)))
    total = query.count()
    selected = query.order_by(base.c.source != 'project', base.c.work_date, base.c.order_no.desc(), base.c.id).offset((page - 1) * page_size).limit(page_size).all()
    # 只读取当前页任务的可编辑信息与执行顺序。
    assigned_ids = [row.id for row in selected if row.source == 'assigned']
    assigned = arrangements.serialize_many(db, db.query(arrangements.ProjectArrangement).filter(
        arrangements.ProjectArrangement.id.in_(assigned_ids)).all()) if assigned_ids else []
    assigned = {str(row['id']): row for row in assigned}
    items = []
    for row in selected:
        item = dict(row._mapping)
        if row.source == 'assigned':
            item.update(assigned[str(row.id)])
            item['status'] = row.task_status
        elif row.source == 'personal':
            item.update(personal.serialize(db, db.get(personal.PersonalDailyTask, row.id)))
        item['row_key'] = f'{row.source}:{row.project_type}:{row.id}'
        item['project_type_label'] = LABELS.get(row.project_type, '非项目任务')
        if row.project_type == 'translation' and row.source != 'assigned' and row.project_id:
            project = db.get(TranslationProject, row.project_id)
            item.update(customer_requirement_professional=project.customer_requirement_professional,
                        customer_requirement_special=project.customer_requirement_special,
                        **arrangements.instructions.read(db, row.project_id))
        if row.project_type == 'annotation':
            project = db.get(AnnotationProject, row.project_id)
            item['can_arrange_annotation'] = db.query(ProjectWorkbenchResponsibility.id).filter_by(
                annotation_project_id=row.project_id, role_code='project_manager', assignee_id=user.id
            ).first() is not None
            item['annotation_summary'] = {
                'id': str(project.id), 'orderNo': project.order_no, 'projectName': project.project_name,
                'projectStatus': project.project_status, 'taskDescription': project.task_description,
            } if project else None
        items.append(item)
    return api_time({'items': items, 'total': total, 'project_types': [
        {'value': group, 'label': LABELS.get(group, '非项目任务'), 'statuses': sorted(values)}
        for group, values in options.items()
    ]})
