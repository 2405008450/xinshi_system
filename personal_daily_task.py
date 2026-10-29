"""未被安排工作的人员也能自行填写今日任务。"""
from datetime import date,datetime
from types import SimpleNamespace
from uuid import UUID,uuid4
import json
from decimal import Decimal,InvalidOperation
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import ForeignKey,Date,DateTime,Integer,JSON,String,Text,Uuid,CheckConstraint,Index,inspect
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from chat_time import now,api_time
from task_schemas import DailyReportItemInput
from task_report_completion import append_report_item
import report_project_picker as picker


class PersonalDailyTask(Base):
    __tablename__='personal_daily_task'
    __table_args__=(CheckConstraint("status IN ('pending','in_progress','completed')",name='ck_personal_daily_task_status'),
                   CheckConstraint('estimated_minutes BETWEEN 0 AND 1440 AND actual_minutes BETWEEN 0 AND 1440',name='ck_personal_daily_task_minutes'),Index('ix_personal_daily_task_user_date','user_id','work_date'))
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    user_id:Mapped[UUID]=mapped_column(ForeignKey('app_user.id',ondelete='CASCADE'))
    work_date:Mapped[date]=mapped_column(Date)
    report_row:Mapped[dict]=mapped_column(JSON)
    estimated_minutes:Mapped[int]=mapped_column(Integer,default=0)
    actual_minutes:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(20),default='pending')
    revision:Mapped[int]=mapped_column(Integer,default=1)
    report_item_id:Mapped[UUID|None]=mapped_column(Uuid,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class TaskRow(BaseModel):
    task_type:str=Field(min_length=1,max_length=50)
    task_name:str=Field(default='',max_length=255)
    progress_content:str=Field(min_length=1,max_length=10000)
    result_content:str|None=Field(default=None,max_length=10000)
    duration_minutes:int=Field(default=0,ge=0,le=1440)
    display_metadata:dict=Field(default_factory=dict)
    @model_validator(mode='after')
    def check(self):
        if not self.progress_content.strip():raise ValueError('请填写具体任务')
        types=self.display_metadata.get('report_types')
        if not isinstance(types,list) or not types or any(not isinstance(value,str) or not value.strip() for value in types):raise ValueError('请选择任务类型')
        from work_report_categories import DEFAULT_CATEGORIES
        allowed=set(DEFAULT_CATEGORIES)|set(DEFAULT_CATEGORIES['项目工作'])
        for value in types:
            parent,separator,name=value.partition('::')
            if value not in allowed and not (separator and parent in DEFAULT_CATEGORIES and name.strip() and len(name)<=80 and '::' not in name):raise ValueError('请选择有效任务类型')
        quantity=self.display_metadata.get('quantity')
        if quantity not in (None,''):
            try:numeric=Decimal(str(quantity))
            except InvalidOperation:raise ValueError('工作量须为非负数字')
            if isinstance(quantity,bool) or not numeric.is_finite() or numeric<0:raise ValueError('工作量须为非负数字')
            if not str(self.display_metadata.get('quantity_unit') or '').strip():raise ValueError('填写工作量后请选择单位')
        if 'screenshot://' in json.dumps(self.model_dump()).lower() or 'data:image/' in json.dumps(self.model_dump()).lower():raise ValueError('任务表单请填写文字，不支持截图')
        return self


class TaskWrite(BaseModel):
    work_date:date
    item:TaskRow


class TaskUpdate(TaskWrite):
    revision:int=Field(ge=1)


class TasksWrite(BaseModel):
    work_date:date
    items:list[TaskRow]=Field(min_length=1,max_length=100)


def ready(db):return inspect(db.connection()).has_table(PersonalDailyTask.__tablename__)


def normalize_row(db,user,item):
    from work_report_categories import validate_categories
    try:validate_categories(db,user,[SimpleNamespace(source_type='manual',display_metadata=item.display_metadata)])
    except PermissionError as error:raise HTTPException(403,str(error))
    except ValueError as error:raise HTTPException(422,str(error))
    data=item.model_dump();metadata=data['display_metadata']
    project_types=[value for value in metadata['report_types'] if value in picker.PROJECT_MODELS]
    if len(project_types)>1:raise HTTPException(422,'一项任务只能选择一种项目类型')
    if project_types:
        selected=picker.resolve(db,project_types[0],metadata.get('project_id'))
        data['task_name']=selected['project_name'][:255];metadata.update(order_no=selected['order_no'],project_id=selected['id'],selected_project_type=project_types[0],selected_project_name=selected['project_name'])
    elif any(value!='非项目工作' and not value.startswith('非项目工作::') for value in metadata['report_types']):
        if not metadata.get('order_no') or not data['task_name'].strip():raise HTTPException(422,'请填写订单号和项目名称')
    data.update(source_type='manual',source_id=None)
    return data


def serialize(db,row):
    from models import AppUser
    user=db.get(AppUser,row.user_id);item=row.report_row
    return api_time({'id':row.id,'source':'personal','assignee_id':row.user_id,'assignee_name':user.full_name or user.username,
        'order_no':item.get('display_metadata',{}).get('order_no',''),'project_name':item.get('task_name',''),'content':item['progress_content'],
        'work_date':row.work_date,'estimated_minutes':row.estimated_minutes,'actual_minutes':row.actual_minutes,'status':row.status,'revision':row.revision,
        'execution_sequence':[],'report_row':item,'updated_at':row.updated_at})


def create(db,user,payload):
    return create_many(db,user,TasksWrite(work_date=payload.work_date,items=[payload.item]))['items'][0]


def create_many(db,user,payload):
    if not ready(db):raise HTTPException(503,'自主任务表尚未初始化')
    # 所有行先完成关联项目和类型校验，再一次性保存，避免部分成功后重试重复创建。
    items=[normalize_row(db,user,item) for item in payload.items]
    rows=[]
    for item in items:
        # 每行是可以独立完成的任务，保留继承的项目值，移除表单内的父行引用。
        item['display_metadata'].pop('parent_item_key',None)
        rows.append(PersonalDailyTask(user_id=user.id,work_date=payload.work_date,report_row=item,estimated_minutes=item['duration_minutes']))
    try:
        db.add_all(rows);db.commit()
    except Exception:
        db.rollback();raise
    return {'items':[serialize(db,row) for row in rows]}


def locked(db,user,task_id,revision):
    if not ready(db):raise HTTPException(503,'自主任务表尚未初始化')
    # 与完成事务统一先锁用户，避免同一天多任务并发生成多份报告。
    from models import AppUser
    db.query(AppUser.id).filter_by(id=user.id).with_for_update().first()
    row=db.query(PersonalDailyTask).filter_by(id=task_id,user_id=user.id).with_for_update().first()
    if not row:raise HTTPException(404,'任务不存在或无权修改')
    if row.revision!=revision:raise HTTPException(409,'任务已被修改，请刷新重试')
    if row.status=='completed':raise HTTPException(409,'任务已完成')
    return row


def edit(db,user,task_id,payload):
    row=locked(db,user,task_id,payload.revision)
    values=payload.model_dump(exclude_none=True,exclude={'revision'})
    if values.get('status') not in (None,'pending','in_progress'):raise HTTPException(422,'完成任务须先填写工作报告')
    if 'content' in values:
        content=values.pop('content').strip()
        if not content:raise HTTPException(422,'请填写具体任务')
        row.report_row={**row.report_row,'progress_content':content}
    for key,value in values.items():setattr(row,key,value)
    row.revision+=1;row.updated_at=now();db.commit();return serialize(db,row)


def replace(db,user,task_id,payload):
    row=locked(db,user,task_id,payload.revision)
    item=normalize_row(db,user,payload.item)
    row.report_row=item;row.work_date=payload.work_date;row.estimated_minutes=item['duration_minutes'];row.revision+=1;row.updated_at=now()
    db.commit();return serialize(db,row)


def complete(db,user,task_id,payload):
    row=locked(db,user,task_id,payload.revision)
    item=payload.item.model_copy(deep=True)
    expected=row.report_row.get('display_metadata',{}).get('report_types',[])
    if (item.display_metadata or {}).get('report_types')!=expected:raise HTTPException(422,'完成时任务类型须与原任务一致')
    metadata={**(item.display_metadata or {})}
    stored=row.report_row.get('display_metadata',{})
    if stored.get('project_id'):
        selected=picker.resolve(db,stored['selected_project_type'],stored['project_id'])
        item.task_name=selected['project_name'][:255];metadata.update(order_no=selected['order_no'],project_id=selected['id'],selected_project_type=stored['selected_project_type'])
    item.display_metadata=metadata
    entry=append_report_item(db,user,item,'personal_daily_task',row.id)
    row.status='completed';row.actual_minutes=item.duration_minutes;row.report_item_id=entry.id;row.revision+=1;row.updated_at=now()
    db.commit();return serialize(db,row)
