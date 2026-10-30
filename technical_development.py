"""技术开发任务、三级层级与追加式进度/反馈记录。"""
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, inspect, text, func
from sqlalchemy.orm import mapped_column

from models import Base, AppUser
from task_models import DailyReport
from chat_time import now, api_time, BUSINESS_TIMEZONE
from organization_service import department_condition


class DevelopmentTask(Base):
    __tablename__ = 'technical_development_task'
    __table_args__ = (CheckConstraint('progress >= 0 AND progress <= 100'),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    parent_id = mapped_column(Uuid, ForeignKey('technical_development_task.id', ondelete='RESTRICT'), index=True)
    name = mapped_column(String(300), nullable=False)
    content = mapped_column(Text, nullable=False, default='')
    arranger_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    executor_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    due_at = mapped_column(DateTime(timezone=True))
    progress = mapped_column(Integer, nullable=False, default=0)
    progress_updated_at = mapped_column(DateTime(timezone=True))
    adjustment = mapped_column(Text, nullable=False, default='')
    notes = mapped_column(Text, nullable=False, default='')
    revision = mapped_column(Integer, nullable=False, default=1)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class DevelopmentProgress(Base):
    __tablename__ = 'technical_development_progress'
    __table_args__ = (CheckConstraint('percentage >= 1 AND percentage <= 100'),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id', ondelete='CASCADE'), nullable=False, index=True)
    percentage = mapped_column(Integer, nullable=False)
    previous_percentage = mapped_column(Integer, nullable=False)
    reason = mapped_column(Text, nullable=False, default='')
    content = mapped_column(Text, nullable=False, default='')
    author_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    author_name = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class DevelopmentFeedback(Base):
    __tablename__ = 'technical_development_feedback'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id', ondelete='CASCADE'), nullable=False, index=True)
    content = mapped_column(Text, nullable=False)
    author_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    author_name = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class DevelopmentTaskNumber(Base):
    __tablename__ = 'technical_development_task_number'
    __table_args__ = (UniqueConstraint('number_date', 'sequence'), CheckConstraint('sequence >= 1'))
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id', ondelete='CASCADE'), primary_key=True)
    task_no = mapped_column(String(40), nullable=False, unique=True)
    number_date = mapped_column(Date, nullable=False)
    sequence = mapped_column(Integer, nullable=False)


class DevelopmentReportReceipt(Base):
    __tablename__ = 'technical_development_report_receipt'
    request_id = mapped_column(Uuid, primary_key=True)
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), nullable=False)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    report_id = mapped_column(Uuid, ForeignKey(DailyReport.id), nullable=False)
    item_key = mapped_column(Uuid, nullable=False, unique=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [DevelopmentTask.__table__, DevelopmentProgress.__table__, DevelopmentFeedback.__table__, DevelopmentTaskNumber.__table__, DevelopmentReportReceipt.__table__]


class WriteModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ExecutorAllocation(WriteModel):
    executor_id: UUID
    content: str = Field(min_length=1,max_length=100000)
    due_at: datetime | None = None

    @field_validator('content')
    @classmethod
    def content_required(cls,value):
        if not value.strip(): raise ValueError('请填写每位执行人的分工')
        return value.strip()

    @field_validator('due_at')
    @classmethod
    def business_time(cls,value):
        return None if value is None else value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)


class TaskWrite(WriteModel):
    name: str = Field(min_length=1, max_length=300)
    content: str = Field(default='', max_length=100000)
    arranger_id: UUID
    executor_id: UUID
    due_at: datetime | None = None
    adjustment: str = Field(default='', max_length=30000)
    notes: str = Field(default='', max_length=30000)
    allocations: list[ExecutorAllocation] | None = Field(default=None,min_length=1,max_length=100)

    @model_validator(mode='after')
    def distinct_allocations(self):
        if self.allocations:
            ids=[item.executor_id for item in self.allocations]
            if len(ids)!=len(set(ids)) or ids[0]!=self.executor_id: raise ValueError('分工执行人不能重复，且必须与选择的执行人一致')
        return self

    @field_validator('name')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('请填写任务名称')
        return value.strip()

    @field_validator('due_at')
    @classmethod
    def business_time(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)


class TaskCreate(TaskWrite):
    parent_id: UUID | None = None


class TaskUpdate(TaskWrite):
    revision: int = Field(ge=1)


class TaskMove(WriteModel):
    parent_id: UUID | None = None
    revision: int = Field(ge=1)


class ProgressWrite(WriteModel):
    percentage: int = Field(ge=1, le=100, strict=True)
    content: str = Field(default='', max_length=30000)
    reason: str = Field(default='', max_length=3000)
    revision: int = Field(ge=1)


class FeedbackWrite(WriteModel):
    content: str = Field(min_length=1, max_length=30000)

    @field_validator('content')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('请填写反馈意见')
        return value.strip()


TECHNICAL_DEPARTMENTS = ['开发部', '开发/IT部', '技术部', 'IT部']


def can_enter(db, user):
    return bool(user and user.is_active and not user.is_deleted and db.query(AppUser.id).filter(AppUser.id == user.id, department_condition(db, TECHNICAL_DEPARTMENTS)).first())


def require_user(user, db):
    if not can_enter(db, user):
        raise HTTPException(403, '仅开发/IT部在职成员可以使用技术开发')


def ready(db):
    return all(inspect(db.connection()).has_table(table.name) for table in TABLES)


def require_ready(db):
    if not ready(db):
        raise HTTPException(503, '技术开发数据表尚未初始化')


def people(db):
    users = db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False)).all()
    priority = {'赵震锋': 0, '运坚': 1}
    users.sort(key=lambda u: (priority.get(u.full_name or u.username, 2), u.full_name or u.username, str(u.id)))
    technical = {u.id for u in db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False), department_condition(db, TECHNICAL_DEPARTMENTS)).all()}
    return dict(arrangers=[dict(id=u.id, name=u.full_name or u.username) for u in users], executors=[dict(id=u.id, name=u.full_name or u.username) for u in users if u.id in technical])


def validate_people(db, data, existing=None):
    options = people(db)
    for field, key, message in [('arranger_id', 'arrangers', '请选择公司在职人员'), ('executor_id', 'executors', '执行人必须为技术部在职人员')]:
        value = getattr(data, field)
        # 保留原有历史人员；改选时必须符合当前目录。
        if existing is not None and value == getattr(existing, field):
            continue
        if value not in {item['id'] for item in options[key]}:
            raise HTTPException(422, message)


def lock_tree(db):
    # 所有树写入统一串行，避免并发互相移入导致环或超过三级。
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(74260301)'))


def allocate_number(db, task_id, instant):
    """调用方持有树锁；日期按UTC+8，唯一约束兜底并发。"""
    existing = db.get(DevelopmentTaskNumber, task_id)
    if existing:
        from technical_task_management import assign_number
        assign_number(db, task_id)
        return existing.task_no
    day = api_time(instant).date()
    sequence = (db.query(func.max(DevelopmentTaskNumber.sequence)).filter_by(number_date=day).scalar() or 0) + 1
    value = f'DT-{day:%y%m%d}-{sequence:03d}'
    from technical_task_management import numbers
    used = set(numbers(db).values()) | {value for value, in db.query(DevelopmentTaskNumber.task_no)}
    suffix = sequence
    while value in used:
        suffix += 1
        value = f'DT-{day:%y%m%d}-{suffix:03d}'
    db.add(DevelopmentTaskNumber(task_id=task_id, task_no=value, number_date=day, sequence=sequence))
    db.flush()
    from technical_task_management import assign_number
    assign_number(db, task_id)
    return value


def get_task(db, task_id, revision=None, allow_deleted=False):
    row = db.get(DevelopmentTask, task_id, populate_existing=True)
    if row is None:
        raise HTTPException(404, '任务不存在')
    from technical_task_management import is_deleted
    if not allow_deleted and is_deleted(db, task_id):
        raise HTTPException(410, '任务已删除，仅保留历史记录')
    if revision is not None and row.revision != revision:
        raise HTTPException(409, '任务已被其他人修改，请刷新后重试')
    return row


def validate_parent(rows, task_id, parent_id):
    parents = {row.id: row.parent_id for row in rows}
    if parent_id is not None and parent_id not in parents:
        raise HTTPException(404, '上级任务不存在')
    parents[task_id] = parent_id
    for start in parents:
        seen = set()
        current = start
        while current is not None:
            if current in seen:
                raise HTTPException(422, '不能将任务移入自身或其子任务')
            seen.add(current)
            if len(seen) > 3:
                raise HTTPException(422, '任务最多三级，请先调整下属任务')
            current = parents.get(current)


def serialize_task(row, names, numbers):
    result = {column.name: getattr(row, column.name) for column in DevelopmentTask.__table__.columns}
    result.update(task_no=numbers.get(row.id, ''), arranger_name=names.get(row.arranger_id, '已离职人员'), executor_name=names.get(row.executor_id, '已离职人员'))
    return api_time(result)


def list_tasks(db, user):
    require_user(user, db)
    if not ready(db):
        return dict(enabled=False, items=[])
    names = {u.id: u.full_name or u.username for u in db.query(AppUser).all()}
    rows = db.query(DevelopmentTask).order_by(DevelopmentTask.created_at, DevelopmentTask.id).all()
    from technical_task_management import numbers as task_numbers, deleted_ids
    numbers = task_numbers(db)
    import technical_task_incentives as incentives
    completions = incentives.snapshots(db)
    default_completion = incentives.snapshot(None, enabled=incentives.ready(db))
    import technical_task_allocations as collaboration
    groups, hidden = collaboration.snapshot(db,names,completions)
    hidden |= deleted_ids(db)
    import technical_requirement_tasks as sources
    source_values = sources.snapshots(db)
    return dict(enabled=True, items=[{**serialize_task(row, names, numbers), **completions.get(row.id, default_completion), 'source': source_values.get(row.id), **groups.get(row.id,{})} for row in rows if row.id not in hidden])


def detail(db, user, task_id):
    require_user(user, db)
    require_ready(db)
    row = get_task(db, task_id, allow_deleted=True)
    names = {u.id: u.full_name or u.username for u in db.query(AppUser).all()}
    from technical_task_management import numbers, deleted_ids
    result = serialize_task(row, names, numbers(db))
    result['deleted'] = task_id in deleted_ids(db)
    import technical_requirement_tasks as sources
    result['source'] = sources.snapshots(db).get(task_id)
    import technical_task_incentives as incentives
    if incentives.ready(db):
        value = incentives.read(db, user, task_id)
        result.update({key: value[key] for key in ['completion_enabled', 'completed_on', 'on_time', 'completion_revision', 'incentive']})
    else:
        result.update(incentives.snapshot(None, enabled=False))
    for key, model in [('progress_history', DevelopmentProgress), ('feedback', DevelopmentFeedback)]:
        result[key] = [api_time({column.name: getattr(item, column.name) for column in model.__table__.columns}) for item in db.query(model).filter_by(task_id=task_id).order_by(model.created_at.desc(), model.id).all()]
    import technical_task_allocations as collaboration
    groups,_=collaboration.snapshot(db,names,incentives.snapshots(db))
    result.update(groups.get(task_id,{}))
    return result


def create_task(db, user, data):
    require_user(user, db)
    require_ready(db)
    lock_tree(db)
    validate_people(db, data)
    task_id = uuid4()
    import technical_task_allocations as collaboration
    if data.parent_id in collaboration.executions(db): raise HTTPException(422,'分工执行记录不能作为任务层级的上级')
    if data.parent_id is not None: get_task(db,data.parent_id)
    from technical_task_management import active_tasks
    validate_parent(active_tasks(db), task_id, data.parent_id)
    instant = now()
    import technical_task_allocations as collaboration
    collaboration.validate(db,data.allocations)
    row=DevelopmentTask(id=task_id, **data.model_dump(exclude={'allocations'}), created_by=user.id, updated_by=user.id, created_at=instant, updated_at=instant)
    db.add(row)
    db.flush()
    allocate_number(db, task_id, instant)
    collaboration.apply(db,user,row,data.allocations)
    db.commit()
    return detail(db, user, task_id)


def update_task(db, user, task_id, data):
    require_user(user, db)
    require_ready(db)
    lock_tree(db)
    row = get_task(db, task_id, data.revision)
    import technical_task_allocations as collaboration
    execution=collaboration.executions(db).get(task_id)
    if execution and (not execution.active or not isinstance(data,ProgressWrite)): raise HTTPException(422,'请在原任务的分工窗口中维护此执行记录')
    if isinstance(data, TaskMove):
        if data.parent_id in collaboration.executions(db): raise HTTPException(422,'分工执行记录不能作为任务层级的上级')
        if data.parent_id is not None: get_task(db,data.parent_id)
        from technical_task_management import active_tasks
        validate_parent(active_tasks(db), task_id, data.parent_id)
        old_parent = row.parent_id
        row.parent_id = data.parent_id
        if old_parent != data.parent_id:
            db.flush()
            from technical_task_management import renumber_subtree
            renumber_subtree(db,task_id)
    elif isinstance(data, ProgressWrite):
        if data.percentage < row.progress and not data.reason.strip():
            raise HTTPException(422, '进度回退必须填写修改原因')
        previous = row.progress
        row.progress = data.percentage
        row.progress_updated_at = now()
        db.add(DevelopmentProgress(task_id=task_id, percentage=data.percentage, previous_percentage=previous, reason=data.reason.strip(), content=data.content.strip(), author_id=user.id, author_name=user.full_name or user.username, created_at=row.progress_updated_at))
    else:
        validate_people(db, data, row)
        import technical_requirement_tasks as sources
        sources.protect_name(db, row.id, data.name, user)
        import technical_task_allocations as collaboration
        collaboration.validate(db,data.allocations,row)
        for field, value in data.model_dump(exclude={'revision','allocations'}).items():
            setattr(row, field, value)
        collaboration.apply(db,user,row,data.allocations)
        import technical_task_incentives as incentives
        incentives.sync_task(db, user, row)
    row.revision += 1
    row.updated_by = user.id
    row.updated_at = now()
    db.commit()
    return detail(db, user, task_id)


def add_feedback(db, user, task_id, data):
    require_user(user, db)
    require_ready(db)
    lock_tree(db)
    get_task(db, task_id)
    db.add(DevelopmentFeedback(task_id=task_id, content=data.content, author_id=user.id, author_name=user.full_name or user.username))
    db.commit()
    return detail(db, user, task_id)
