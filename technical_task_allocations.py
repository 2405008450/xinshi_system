"""多人分工以独立执行记录承载，复用每人的日期、进度、奖励台账。"""
from uuid import uuid4
from datetime import datetime,time
from fastapi import HTTPException
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid, inspect
from sqlalchemy.orm import mapped_column
from models import Base, AppUser
from chat_time import now, api_time, BUSINESS_TIMEZONE
import technical_development as tasks


class TaskCollaboration(Base):
    __tablename__ = 'technical_task_collaboration'
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), primary_key=True)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class TaskAllocation(Base):
    __tablename__ = 'technical_task_allocation'
    __table_args__ = (UniqueConstraint('root_task_id', 'executor_id'),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    root_task_id = mapped_column(Uuid, ForeignKey('technical_task_collaboration.task_id'), nullable=False, index=True)
    execution_task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), nullable=False, unique=True)
    executor_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    active = mapped_column(Boolean, nullable=False, default=True)
    position = mapped_column(Integer, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [TaskCollaboration.__table__, TaskAllocation.__table__]
def ready(db): return all(inspect(db.connection()).has_table(table.name) for table in TABLES)
def roots(db): return {uid for uid, in db.query(TaskCollaboration.task_id)} if ready(db) else set()
def executions(db): return {row.execution_task_id: row for row in db.query(TaskAllocation)} if ready(db) else {}


def require_individual(db, task_id):
    if not ready(db): return
    if db.get(TaskCollaboration, task_id): raise HTTPException(422, '多人任务请在分工窗口中分别填写每人的完成日期和金额')
    link = db.query(TaskAllocation).filter_by(execution_task_id=task_id).first()
    if link and not link.active: raise HTTPException(409, '此分工已停用，仅保留历史记录')


def snapshot(db, names, completion_values):
    if not ready(db): return {}, set()
    from technical_task_management import numbers
    number = numbers(db)
    hidden, grouped = set(), {uid: [] for uid in roots(db)}
    for link, row in db.query(TaskAllocation, tasks.DevelopmentTask).join(tasks.DevelopmentTask, tasks.DevelopmentTask.id == TaskAllocation.execution_task_id).order_by(TaskAllocation.position, TaskAllocation.id):
        hidden.add(row.id)
        if link.active:
            grouped[link.root_task_id].append(dict(executor_id=link.executor_id, executor_name=names.get(link.executor_id, '-'), task_id=row.id, task_no=number.get(row.id,''), content=row.content, due_at=api_time(row.due_at), revision=row.revision, progress=row.progress, **completion_values.get(row.id, dict(completed_on=None,on_time=None,completion_revision=0,incentive=None))))
    return {uid: dict(has_allocations=True, allocations=items, executor_ids=[item['executor_id'] for item in items], executor_name='、'.join(item['executor_name'] for item in items), completed_on=None,on_time=None,incentive=None) for uid,items in grouped.items()}, hidden


def validate(db, payload, existing=None):
    if payload is None: return
    if not ready(db): raise HTTPException(503, '多人分工表尚未初始化')
    eligible = {person['id'] for person in tasks.people(db)['executors']}
    historical = {row.executor_id for row in db.query(TaskAllocation).filter_by(root_task_id=existing.id,active=True)} if existing else set()
    if any(item.executor_id not in eligible | historical for item in payload): raise HTTPException(422, '分工执行人必须为开发/IT部在职人员')


def new_execution(db, user, root, executor_id, content, due_at):
    person = db.get(AppUser, executor_id)
    stamp = now()
    row = tasks.DevelopmentTask(id=uuid4(), name=f'{root.name[:260]} · {person.full_name or person.username}'[:300], content=content, arranger_id=root.arranger_id, executor_id=executor_id, due_at=due_at, adjustment='',notes='',created_by=user.id,updated_by=user.id,created_at=stamp,updated_at=stamp)
    db.add(row); db.flush(); tasks.allocate_number(db,row.id,stamp)
    return row


def apply(db, user, root, payload):
    if payload is None:
        if ready(db) and db.get(TaskCollaboration,root.id):
            active=db.query(TaskAllocation).filter_by(root_task_id=root.id,active=True).order_by(TaskAllocation.position).first()
            if active and root.executor_id != active.executor_id: raise HTTPException(422,'请通过多人分工窗口调整执行人')
        return
    validate(db,payload,root)
    import technical_task_incentives as incentives
    first = db.get(TaskCollaboration,root.id) is None
    if first:
        db.add(TaskCollaboration(task_id=root.id,created_by=user.id));db.flush()
    links = {row.executor_id:row for row in db.query(TaskAllocation).filter_by(root_task_id=root.id)}
    legacy = db.get(incentives.TaskCompletion,root.id) if first and incentives.ready(db) else None
    legacy_amount = db.query(incentives.TaskIncentive).filter_by(task_id=root.id,assessment_revision=legacy.revision).order_by(incentives.TaskIncentive.sequence.desc()).first() if legacy else None
    wanted={item.executor_id for item in payload}
    # 已完成的原单人记录保留归属：拆分时承接到原执行人，不重复计入总额。
    if legacy and legacy.completed_on and legacy.executor_id not in wanted:
        execution=new_execution(db,user,root,legacy.executor_id,root.content,datetime.combine(legacy.due_on,time(23,59,59),BUSINESS_TIMEZONE))
        link=TaskAllocation(root_task_id=root.id,execution_task_id=execution.id,executor_id=legacy.executor_id,active=False,position=1000)
        db.add(link);links[legacy.executor_id]=link
    for position,item in enumerate(payload):
        link=links.get(item.executor_id)
        if link:
            execution=tasks.get_task(db,link.execution_task_id)
            person=db.get(AppUser,item.executor_id)
            name=f'{root.name[:260]} · {person.full_name or person.username}'[:300]
            if execution.content != item.content or api_time(execution.due_at) != api_time(item.due_at) or execution.arranger_id != root.arranger_id or execution.name != name:
                execution.name=name;execution.content=item.content;execution.due_at=item.due_at;execution.arranger_id=root.arranger_id;execution.revision+=1;execution.updated_by=user.id;execution.updated_at=now()
                incentives.sync_task(db,user,execution)
            link.active=True;link.position=position;link.updated_at=now()
        else:
            execution=new_execution(db,user,root,item.executor_id,item.content,item.due_at)
            link=TaskAllocation(root_task_id=root.id,execution_task_id=execution.id,executor_id=item.executor_id,active=True,position=position)
            db.add(link);links[item.executor_id]=link
    for uid,link in links.items():
        if uid not in wanted: link.active=False;link.updated_at=now()
    db.flush()
    if legacy and legacy.completed_on:
        link=links[legacy.executor_id]
        execution=tasks.get_task(db,link.execution_task_id)
        if not execution.due_at: raise HTTPException(422,'原执行人已有完成记录，分工预定完成时间不能为空')
        if execution.due_at:
            incentives.apply_date(db,user,execution,legacy.completed_on,'由原单人任务拆分继承完成日期',uuid4())
            state=db.get(incentives.TaskCompletion,execution.id)
            if legacy_amount and state.on_time == legacy.on_time and state.due_on == legacy.due_on:
                db.add(incentives.TaskIncentive(request_id=uuid4(),task_id=execution.id,assessment_revision=state.revision,sequence=1,executor_id=execution.executor_id,executor_name=legacy_amount.executor_name,kind=legacy_amount.kind,amount=legacy_amount.amount,completed_on=state.completed_on,due_on=state.due_on,reason=f'承接原单人任务金额，原记录 {legacy_amount.id}',author_id=user.id,author_name=user.full_name or user.username,author_username=user.username))
    db.flush()
