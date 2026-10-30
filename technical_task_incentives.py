"""完成日期、按时判定与开发奖励台账；历史追加，统计只使用当前评定。"""
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid, inspect
from sqlalchemy.orm import mapped_column
from models import Base, AppUser
from chat_time import now, api_time
import technical_development as tasks


class TaskCompletion(Base):
    __tablename__ = 'technical_task_completion'
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), primary_key=True)
    completed_on = mapped_column(Date)
    due_on = mapped_column(Date)
    executor_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    on_time = mapped_column(Boolean)
    revision = mapped_column(Integer, nullable=False, default=0)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class CompletionChange(Base):
    __tablename__ = 'technical_task_completion_change'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_id = mapped_column(Uuid, nullable=False, unique=True)
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), nullable=False, index=True)
    previous_date = mapped_column(Date)
    completed_on = mapped_column(Date)
    previous_due_on = mapped_column(Date)
    due_on = mapped_column(Date)
    previous_executor_id = mapped_column(Uuid, ForeignKey('app_user.id'))
    executor_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    on_time = mapped_column(Boolean)
    revision = mapped_column(Integer, nullable=False)
    reason = mapped_column(Text, nullable=False, default='')
    author_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    author_name = mapped_column(String(255), nullable=False)
    author_username = mapped_column(String(100), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class TaskIncentive(Base):
    __tablename__ = 'technical_task_incentive'
    __table_args__ = (UniqueConstraint('task_id', 'assessment_revision', 'sequence'), CheckConstraint('amount >= 0'), CheckConstraint("kind IN ('reward','deduction')"), CheckConstraint('sequence >= 1'))
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_id = mapped_column(Uuid, nullable=False, unique=True)
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), nullable=False, index=True)
    assessment_revision = mapped_column(Integer, nullable=False)
    sequence = mapped_column(Integer, nullable=False)
    executor_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    executor_name = mapped_column(String(255), nullable=False)
    kind = mapped_column(String(20), nullable=False)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    completed_on = mapped_column(Date, nullable=False)
    due_on = mapped_column(Date, nullable=False)
    reason = mapped_column(Text, nullable=False, default='')
    author_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    author_name = mapped_column(String(255), nullable=False)
    author_username = mapped_column(String(100), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [TaskCompletion.__table__, CompletionChange.__table__, TaskIncentive.__table__]


class DateWrite(tasks.WriteModel):
    request_id: UUID
    task_revision: int = Field(ge=1)
    completion_revision: int = Field(ge=0)
    completed_on: date | None = None
    reason: str = Field(default='', max_length=3000)


class AmountWrite(tasks.WriteModel):
    request_id: UUID
    completion_revision: int = Field(ge=1)
    expected_latest_id: UUID | None = None
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    reason: str = Field(default='', max_length=3000)


def ready(db):
    return all(inspect(db.connection()).has_table(table.name) for table in TABLES)


def require_ready(db):
    if not ready(db): raise HTTPException(503, '开发完成日期及奖励表尚未初始化')


def require_reader(db, user):
    from hr_access import can_manage_hr
    if not (tasks.can_enter(db, user) or can_manage_hr(db, user)): raise HTTPException(403, '仅开发/IT部及人事管理人员可查看')


def ledger_value(row):
    value = {column.name: getattr(row, column.name) for column in TaskIncentive.__table__.columns}
    value['amount'] = f'{row.amount:.2f}'
    return api_time(value)


def snapshot(state, ledger=None, enabled=True):
    return dict(completion_enabled=enabled, completed_on=state.completed_on if state else None, on_time=state.on_time if state else None, completion_revision=state.revision if state else 0, incentive=ledger_value(ledger) if ledger else None)


def snapshots(db):
    if not ready(db): return {}
    latest = {}
    for row in db.query(TaskIncentive).order_by(TaskIncentive.sequence.desc()).all(): latest.setdefault((row.task_id, row.assessment_revision), row)
    return {state.task_id: snapshot(state, latest.get((state.task_id, state.revision))) for state in db.query(TaskCompletion).all()}


def read(db, user, task_id):
    require_reader(db, user); require_ready(db)
    task = tasks.get_task(db, task_id, allow_deleted=True)
    state = db.get(TaskCompletion, task_id)
    ledger = db.query(TaskIncentive).filter_by(task_id=task_id, assessment_revision=state.revision).order_by(TaskIncentive.sequence.desc()).first() if state else None
    from technical_task_management import numbers
    task_no = numbers(db).get(task_id, '')
    changes = db.query(CompletionChange).filter_by(task_id=task_id).order_by(CompletionChange.revision.desc()).all()
    history = db.query(TaskIncentive).filter_by(task_id=task_id).order_by(TaskIncentive.created_at.desc(), TaskIncentive.sequence.desc()).all()
    import technical_task_allocations as collaboration
    is_group=task_id in collaboration.roots(db)
    return dict(task_id=task_id, task_no=task_no, task_name=task.name, executor_id=task.executor_id, due_on=api_time(task.due_at).date() if task.due_at else None, task_revision=task.revision, **snapshot(None if is_group else state, None if is_group else ledger), changes=[api_time({column.name: getattr(change, column.name) for column in CompletionChange.__table__.columns}) for change in changes], ledger_history=[{**ledger_value(row), 'effective': bool(not is_group and ledger and row.id == ledger.id)} for row in history])


def apply_date(db, user, task, completed_on, reason, request_id):
    state = db.get(TaskCompletion, task.id)
    due_on = api_time(task.due_at).date() if task.due_at else None
    if completed_on and not due_on: raise HTTPException(422, '请先填写预定完成时间，再填写完成日期')
    if not state:
        state = TaskCompletion(task_id=task.id, completed_on=None, due_on=due_on, executor_id=task.executor_id, revision=0)
        db.add(state)
    previous = (state.completed_on, state.due_on, state.executor_id)
    current = (completed_on, due_on, task.executor_id)
    if previous == current: return
    if state.completed_on is not None and completed_on != state.completed_on and not reason.strip(): raise HTTPException(422, '调整完成日期必须填写调整原因')
    state.completed_on, state.due_on, state.executor_id = current
    state.on_time = completed_on <= due_on if completed_on and due_on else None
    state.revision += 1; state.updated_at = now()
    db.add(CompletionChange(request_id=request_id, task_id=task.id, previous_date=previous[0], completed_on=completed_on, previous_due_on=previous[1], due_on=due_on, previous_executor_id=previous[2], executor_id=task.executor_id, on_time=state.on_time, revision=state.revision, reason=reason.strip() or '首次填写完成日期', author_id=user.id, author_name=user.full_name or user.username, author_username=user.username))
    db.flush()


def sync_task(db, user, task):
    if not ready(db): return
    import technical_task_allocations as collaboration
    if task.id in collaboration.roots(db): return
    state = db.get(TaskCompletion, task.id)
    if not state: return
    due_on = api_time(task.due_at).date() if task.due_at else None
    if state.completed_on and due_on is None: raise HTTPException(422, '已填写完成日期的任务不能清空预定完成时间')
    if state.due_on != due_on or state.executor_id != task.executor_id:
        apply_date(db, user, task, state.completed_on, '调整预定完成时间或执行人，重新评定', uuid4())


def save_date(db, user, task_id, payload):
    tasks.require_user(user, db); require_ready(db); tasks.lock_tree(db)
    from technical_task_allocations import require_individual
    require_individual(db,task_id)
    previous = db.query(CompletionChange).filter_by(request_id=payload.request_id).first()
    if previous:
        if previous.task_id != task_id or previous.author_id != user.id: raise HTTPException(409, '请求标识已使用')
        return read(db, user, task_id)
    task = tasks.get_task(db, task_id, payload.task_revision)
    state = db.get(TaskCompletion, task_id)
    if (state.revision if state else 0) != payload.completion_revision: raise HTTPException(409, '完成日期已更新，请刷新后重试')
    apply_date(db, user, task, payload.completed_on, payload.reason, payload.request_id)
    db.commit()
    return read(db, user, task_id)


def save_amount(db, user, task_id, payload):
    tasks.require_user(user, db); require_ready(db); tasks.lock_tree(db)
    from technical_task_allocations import require_individual
    require_individual(db,task_id)
    previous = db.query(TaskIncentive).filter_by(request_id=payload.request_id).first()
    if previous:
        if previous.task_id != task_id or previous.author_id != user.id: raise HTTPException(409, '请求标识已使用')
        return read(db, user, task_id)
    task = tasks.get_task(db, task_id)
    state = db.get(TaskCompletion, task_id)
    if not state or state.on_time is None: raise HTTPException(422, '请先填写完成日期及预定完成时间')
    if state.revision != payload.completion_revision: raise HTTPException(409, '按时完成评定已变化，请重新打开金额窗口')
    latest = db.query(TaskIncentive).filter_by(task_id=task_id, assessment_revision=state.revision).order_by(TaskIncentive.sequence.desc()).first()
    if (latest.id if latest else None) != payload.expected_latest_id: raise HTTPException(409, '金额已被更新，请查看最新记录后重试')
    if latest and latest.amount == payload.amount: return read(db, user, task_id)
    if latest and not payload.reason.strip(): raise HTTPException(422, '调整金额必须填写原因')
    executor = db.get(AppUser, task.executor_id)
    db.add(TaskIncentive(request_id=payload.request_id, task_id=task_id, assessment_revision=state.revision, sequence=(latest.sequence + 1 if latest else 1), executor_id=task.executor_id, executor_name=executor.full_name or executor.username, kind='reward' if state.on_time else 'deduction', amount=payload.amount.quantize(Decimal('.01')), completed_on=state.completed_on, due_on=state.due_on, reason=payload.reason.strip(), author_id=user.id, author_name=user.full_name or user.username, author_username=user.username))
    db.commit()
    return read(db, user, task_id)


def statistics(db, user):
    from hr_access import require_hr
    require_hr(db, user)
    if not ready(db): return dict(enabled=False, people=[], tasks=[], totals={})
    values = snapshots(db)
    names = {person.id: person.full_name or person.username for person in db.query(AppUser).all()}
    from technical_task_management import numbers as task_numbers
    numbers = task_numbers(db)
    import technical_task_allocations as collaboration
    group_ids=collaboration.roots(db)
    allocation_links=collaboration.executions(db)
    people, items = {}, []
    for task in db.query(tasks.DevelopmentTask).all():
        if task.id in group_ids: continue
        value = values.get(task.id)
        if not value: continue
        if task.id in allocation_links and not allocation_links[task.id].active and not value['incentive']: continue
        person = people.setdefault(task.executor_id, dict(executor_id=task.executor_id, executor_name=names.get(task.executor_id, '-'), reward_total=Decimal(0), deduction_total=Decimal(0), pending=0))
        ledger = value['incentive']
        if ledger: person['reward_total' if ledger['kind'] == 'reward' else 'deduction_total'] += Decimal(ledger['amount'])
        elif value['on_time'] is not None: person['pending'] += 1
        items.append(dict(task_id=task.id, task_no=numbers.get(task.id, ''), task_name=task.name, executor_name=person['executor_name'], due_on=api_time(task.due_at).date() if task.due_at else None, **value))
    totals = dict(reward_total=Decimal(0), deduction_total=Decimal(0), offset_total=Decimal(0), net_reward=Decimal(0), net_deduction=Decimal(0), pending=0)
    for person in people.values():
        person['offset_total'] = min(person['reward_total'], person['deduction_total'])
        person['net_reward'] = person['reward_total'] - person['offset_total']
        person['net_deduction'] = person['deduction_total'] - person['offset_total']
        for key in totals: totals[key] += person[key]
    def money(value): return {key: f'{amount:.2f}' if isinstance(amount, Decimal) else amount for key, amount in value.items()}
    return dict(enabled=True, people=[money(person) for person in people.values()], tasks=items, totals=money(totals))
