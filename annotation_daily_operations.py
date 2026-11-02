"""标注今日具体操作，复用个人任务存储；完成与加入日报分开。"""
from typing import Literal
from datetime import date
from uuid import UUID
from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

import personal_daily_task as personal
import annotation_work_status as status
import project_arrangement as arrangements
import report_project_picker as picker
from annotation_today_tasks import EXCLUDED_STATUSES
from chat_time import now
from work_report_dates import report_business_date
from task_schemas import DailyReportItemInput
from task_report_completion import append_report_item

SOURCE = 'annotation_daily_operation'
Stage = Literal['pending', 'in_progress', 'performed']


class OperationWrite(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    estimated_minutes: int = Field(gt=0, le=1440, strict=True)

    @field_validator('content')
    @classmethod
    def text_only(cls, value):
        value = value.strip()
        if not value or 'screenshot://' in value.lower() or 'data:image/' in value.lower():
            raise ValueError('请填写文字具体操作')
        return value


class ProjectOperations(BaseModel):
    project_id: UUID | None = None
    operations: list[OperationWrite] = Field(min_length=1, max_length=100)


class BatchWrite(BaseModel):
    work_date: date
    project_type: Literal['标注项目', '口译项目', '招聘项目', '非项目任务'] = '标注项目'
    stage: Literal['pending', 'in_progress']
    projects: list[ProjectOperations] = Field(min_length=1, max_length=100)


class OperationEdit(OperationWrite):
    estimated_minutes: int = Field(ge=0, le=1440, strict=True)
    revision: int = Field(ge=1)
    stage: Stage
    actual_minutes: int | None = Field(default=None, ge=0, le=1440, strict=True)
    quantity: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    unit: str = Field(default='', max_length=50)

    @model_validator(mode='after')
    def quantity_unit(self):
        if self.quantity is not None and not self.unit.strip():
            raise ValueError('填写工作量后请选择单位')
        if self.unit.strip() == '其他':
            raise ValueError('请填写具体单位')
        return self


class RevisionWrite(BaseModel):
    revision: int = Field(ge=1)


class ImportWrite(BaseModel):
    work_date: date
    stage: Literal['pending', 'in_progress']


def require_ready(db):
    if not personal.ready(db):
        raise HTTPException(503, '任务表尚未初始化')


def own_query(db, user):
    return db.query(personal.PersonalDailyTask).filter(
        personal.PersonalDailyTask.user_id == user.id,
        personal.PersonalDailyTask.report_row['display_metadata']['operation_source'].as_string() == SOURCE,
    )


def serialize(db, row):
    result = personal.serialize(db, row)
    metadata = row.report_row['display_metadata']
    result.update(stage=metadata['operation_stage'], project_id=metadata.get('project_id'),
                  project_type='笔译项目' if metadata.get('linked_source') else metadata.get('report_types', ['标注项目'])[0],
                  quantity=metadata.get('quantity'), unit=metadata.get('quantity_unit', ''),
                  report_added=row.report_item_id is not None)
    source = linked_task(db, user_id=row.user_id, metadata=metadata)
    if source and source.report_item_id:
        result.update(report_added=True,stage='performed',actual_minutes=source.actual_minutes)
    return result


def context(db, user):
    require_ready(db)
    day = report_business_date(now())
    projects = status.context(db, user)
    rows = own_query(db, user).filter(personal.PersonalDailyTask.work_date == day).order_by(
        personal.PersonalDailyTask.created_at, personal.PersonalDailyTask.id).all()
    return {'work_date': day, 'projects': [row for row in projects.get('items', [])
            if row['arrangement_status'] == 'in_progress' and row['projectStatus'] not in EXCLUDED_STATUSES],
            'items': [serialize(db, row) for row in rows]}


def create(db, user, payload):
    require_ready(db)
    day = report_business_date(now())
    if payload.work_date != day:
        raise HTTPException(409, '工作报告日已变化，请重新打开今日安排')
    if sum(len(group.operations) for group in payload.projects) > 100:
        raise HTTPException(422, '每次最多新增100个具体操作')
    status.lock_user(db, user)
    allowed = {row['id'] for row in context(db, user)['projects']} if payload.project_type == '标注项目' else set()
    rows = []
    for group in payload.projects:
        if payload.project_type == '标注项目' and str(group.project_id) not in allowed:
            raise HTTPException(403, '只能选择本人今日进行中的标注项目')
        if payload.project_type == '非项目任务':
            identity = {'project_name': ''}
        else:
            if payload.project_type == '口译项目':
                from my_project_tasks import interpretation_task_filter
                from interpretation_work_arrangement import today_filter
                from models import Client, SubClient
                model,query=picker.query_projects(db,'口译项目')
                allowed_project=query.outerjoin(Client,model.client_id==Client.id).outerjoin(
                    SubClient,model.sub_client_id==SubClient.id).filter(model.id==group.project_id,
                    interpretation_task_filter(db,user),today_filter(db,user)).first()
                if not allowed_project:
                    raise HTTPException(403,'该口译项目不在本人的未取消、未结款任务范围内')
            identity = picker.resolve(db, payload.project_type, group.project_id)
        for operation in group.operations:
            item = personal.TaskRow(task_type='非项目工作' if payload.project_type=='非项目任务' else '项目工作', task_name=identity['project_name'],
                progress_content=operation.content, duration_minutes=operation.estimated_minutes,
                display_metadata={'report_types': ['非项目工作' if payload.project_type=='非项目任务' else payload.project_type], 'project_id': str(group.project_id) if group.project_id else None,
                    'operation_source': SOURCE, 'operation_stage': payload.stage})
            value = personal.normalize_row(db, user, item)
            rows.append(personal.PersonalDailyTask(user_id=user.id, work_date=day,
                report_row=value, estimated_minutes=operation.estimated_minutes, status=payload.stage))
    db.add_all(rows)
    db.commit()
    return {'items': [serialize(db, row) for row in rows]}


def locked(db, user, task_id):
    require_ready(db)
    status.lock_user(db, user)
    row = own_query(db, user).filter(personal.PersonalDailyTask.id == task_id).with_for_update().populate_existing().first()
    if not row:
        raise HTTPException(404, '操作不存在或无权访问')
    if row.work_date != report_business_date(now()):
        raise HTTPException(409, '工作报告日已变化，请重新打开今日安排')
    return row


def edit(db, user, task_id, payload):
    row = locked(db, user, task_id)
    if row.report_item_id:
        raise HTTPException(409, '已加入工作报告，请在工作报告中修改')
    source = linked_task(db, user.id, row.report_row['display_metadata'])
    if source and source.status == 'completed':
        raise HTTPException(409, '原任务已完成，请刷新后在工作报告中查看')
    if row.revision != payload.revision:
        raise HTTPException(409, '操作已变化，请刷新后重试')
    previous = row.report_row['display_metadata']['operation_stage']
    if previous == 'performed' and payload.stage != 'performed':
        raise HTTPException(409, '已进行任务不能退回，避免实际用时丢失')
    actual = payload.actual_minutes
    if payload.stage == 'performed' and previous != 'performed':
        actual = payload.estimated_minutes
    metadata = {**row.report_row['display_metadata'], 'operation_stage': payload.stage,
                'quantity': str(payload.quantity) if payload.quantity is not None else '',
                'quantity_unit': payload.unit.strip()}
    row.report_row = {**row.report_row, 'progress_content': payload.content,
                      'duration_minutes': payload.estimated_minutes, 'display_metadata': metadata}
    row.estimated_minutes = payload.estimated_minutes
    row.actual_minutes = actual or 0
    row.status = 'pending' if payload.stage == 'pending' else 'in_progress'
    row.revision += 1
    row.updated_at = now()
    db.commit()
    return serialize(db, row)


def add_report(db, user, task_id, payload):
    row = locked(db, user, task_id)
    # 重试同一请求也不重复生成报告行。
    if row.report_item_id:
        return serialize(db, row)
    if row.revision != payload.revision:
        raise HTTPException(409, '操作已变化，请刷新后重试')
    metadata = row.report_row['display_metadata']
    if metadata['operation_stage'] != 'performed':
        raise HTTPException(422, '请先将任务移至已进行任务')
    source = linked_task(db, user.id, metadata, lock=True)
    if source and source.report_item_id:
        row.report_item_id=source.report_item_id
        row.status='completed'
        row.revision+=1
        row.updated_at=now()
        db.commit()
        return serialize(db,row)
    report_type = '笔译项目' if metadata.get('linked_source') else metadata.get('report_types', ['标注项目'])[0]
    value = {**row.report_row, 'duration_minutes': row.actual_minutes,
             'display_metadata': {**metadata, 'personal_task_id':str(row.id)}}
    if report_type != '非项目工作':
        identity = picker.resolve(db,report_type,metadata['project_id'])
        if metadata.get('linked_source') == 'assigned':
            identity = arrangements.targets.identity(db,source)
        value.update(task_name=identity['project_name'][:255])
        value['display_metadata']['order_no']=identity['order_no']
    try:
        item = DailyReportItemInput.model_validate(value)
    except ValueError:
        raise HTTPException(422, '请填写实际花费时间、工作量和单位')
    if source:
        completion = arrangements.TaskComplete(revision=source.revision,item=item)
        if metadata['linked_source']=='assigned':
            arrangements.complete_task(db,user,source.id,completion,commit=False)
        else:
            personal.complete(db,user,source.id,completion,commit=False)
        row.report_item_id=source.report_item_id
    else:
        entry = append_report_item(db, user, item, 'personal_daily_task', row.id)
        row.report_item_id = entry.id
    row.status = 'completed'
    row.revision += 1
    row.updated_at = now()
    db.commit()
    return serialize(db, row)


def linked_task(db, user_id, metadata, lock=False):
    kind=metadata.get('linked_source')
    if not kind:
        return None
    model=arrangements.ProjectArrangement if kind=='assigned' else personal.PersonalDailyTask
    owner=model.assignee_id if kind=='assigned' else model.user_id
    if lock and kind=='assigned':
        project_id=db.query(model.project_id).filter(model.id==UUID(metadata['linked_task_id']),owner==user_id).scalar()
        if project_id is None:
            raise HTTPException(409,'原任务已删除或已转交，请刷新任务列表')
        arrangements.history.lock_plan(db,project_id,db.get(arrangements.AppUser,user_id))
    query=db.query(model).filter(model.id==UUID(metadata['linked_task_id']),owner==user_id)
    if lock:
        query=query.with_for_update().populate_existing()
    source=query.first()
    if not source and lock:
        raise HTTPException(409,'原任务已删除或已转交，请刷新任务列表')
    return source


def import_translation(db,user,payload):
    require_ready(db)
    day=report_business_date(now())
    if payload.work_date!=day:
        raise HTTPException(409,'工作报告日已变化，请重新打开状态汇报')
    status.lock_user(db,user)
    existing=own_query(db,user).filter(personal.PersonalDailyTask.work_date==day).all()
    mapped={(row.report_row['display_metadata'].get('linked_source'),row.report_row['display_metadata'].get('linked_task_id')):row for row in existing if row.report_row['display_metadata'].get('linked_source')}
    sources=[]
    if arrangements.ready(db):
        sources.extend(('assigned',row) for row in db.query(arrangements.ProjectArrangement).filter(
            arrangements.ProjectArrangement.assignee_id==user.id,arrangements.ProjectArrangement.status!='completed').order_by(arrangements.ProjectArrangement.id).with_for_update().all())
    for row in db.query(personal.PersonalDailyTask).filter(personal.PersonalDailyTask.user_id==user.id,personal.PersonalDailyTask.status!='completed').order_by(personal.PersonalDailyTask.id).with_for_update().all():
        metadata=row.report_row.get('display_metadata',{})
        if metadata.get('operation_source')!=SOURCE and '笔译项目' in metadata.get('report_types',[]):
            sources.append(('personal',row))
    added=0
    for kind,source in sources:
        key=(kind,str(source.id))
        if key in mapped:
            continue
        if kind=='assigned':
            identity=arrangements.targets.identity(db,source)
            value={'source_type':'manual','task_type':'项目工作','task_name':identity['project_name'],
                'progress_content':source.content,'duration_minutes':source.estimated_minutes,
                'display_metadata':{'report_types':['笔译项目'],'project_id':str(source.project_id),
                    'selected_project_type':'笔译项目','order_no':identity['order_no'],
                    'sub_order_id':identity.get('sub_order_id')}}
        else:
            value={**source.report_row,'display_metadata':dict(source.report_row['display_metadata'])}
        value['display_metadata'].update(operation_source=SOURCE,operation_stage=payload.stage,
            linked_source=kind,linked_task_id=str(source.id))
        row=personal.PersonalDailyTask(user_id=user.id,work_date=day,report_row=value,
            estimated_minutes=source.estimated_minutes,actual_minutes=source.actual_minutes,status=payload.stage)
        db.add(row)
        existing.append(row)
        mapped[key]=row
        added+=1
    db.commit()
    return {'items':[serialize(db,row) for row in existing], 'added':added, 'matched':len(sources)}
