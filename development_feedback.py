"""公司开发反馈：公开任务反馈表、单元格版本控制与具名意见历史。"""
from datetime import date
from typing import Literal
from uuid import UUID, uuid4
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Uuid, inspect, text
from sqlalchemy.orm import mapped_column
from models import Base, AppUser
from chat_time import now, api_time
import technical_development as tasks


class FeedbackSheet(Base):
    __tablename__ = 'development_feedback_sheet'
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), primary_key=True)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class Feedback(Base):
    __tablename__ = 'development_feedback'
    __table_args__ = (CheckConstraint("urgency IN ('低','中','高','紧急')"), CheckConstraint("status IN ('待处理','处理中','已解决','暂不处理')"))
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_id = mapped_column(Uuid, nullable=False, unique=True)
    task_id = mapped_column(Uuid, ForeignKey('development_feedback_sheet.task_id'), nullable=False, index=True)
    feedback_no = mapped_column(String(40), nullable=False, unique=True)
    submitted_on = mapped_column(Date, nullable=False)
    submitted_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    submitted_name = mapped_column(String(255), nullable=False)
    submitted_username = mapped_column(String(100), nullable=False)
    module = mapped_column(String(300), nullable=False, default='')
    content = mapped_column(Text, nullable=False, default='')
    urgency = mapped_column(String(10), nullable=False, default='中')
    attachments = mapped_column(Text, nullable=False, default='')
    status = mapped_column(String(20), nullable=False, default='待处理')
    assignee_id = mapped_column(Uuid, ForeignKey('app_user.id'))
    result = mapped_column(Text, nullable=False, default='')
    completed_on = mapped_column(Date)
    notes = mapped_column(Text, nullable=False, default='')
    revision = mapped_column(Integer, nullable=False, default=1)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class FeedbackOpinion(Base):
    __tablename__ = 'development_feedback_opinion'
    __table_args__ = (CheckConstraint("kind IN ('william','development')"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    feedback_id = mapped_column(Uuid, ForeignKey('development_feedback.id'), nullable=False, index=True)
    kind = mapped_column(String(20), nullable=False)
    content = mapped_column(Text, nullable=False)
    author_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    author_name = mapped_column(String(255), nullable=False)
    author_username = mapped_column(String(100), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [FeedbackSheet.__table__, Feedback.__table__, FeedbackOpinion.__table__]


class CreateFeedback(tasks.WriteModel):
    request_id: UUID


class PatchFeedback(tasks.WriteModel):
    revision: int = Field(ge=1)
    module: str = Field(default='', max_length=300)
    content: str = Field(default='', max_length=30000)
    urgency: Literal['低', '中', '高', '紧急'] = '中'
    attachments: str = Field(default='', max_length=30000)
    status: Literal['待处理', '处理中', '已解决', '暂不处理'] = '待处理'
    assignee_id: UUID | None = None
    result: str = Field(default='', max_length=30000)
    completed_on: date | None = None
    notes: str = Field(default='', max_length=30000)


class OpinionWrite(tasks.WriteModel):
    kind: Literal['william', 'development']
    content: str = Field(min_length=1, max_length=30000)
    expected_latest_id: UUID | None = None


def require_user(user):
    if not user or not user.is_active or user.is_deleted:
        raise HTTPException(403, '仅公司在职人员可使用开发反馈')


def permissions(db, user):
    require_user(user)
    return dict(william=(user.username or '').strip().lower() == 'williamzhao', development=tasks.can_enter(db, user))


def ready(db):
    return all(inspect(db.connection()).has_table(table.name) for table in TABLES)


def require_ready(db):
    if not ready(db):
        raise HTTPException(503, '开发反馈数据表尚未初始化')


def lock_creation(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(74260302)'))


def new_feedback(db, user, task_id, request_id):
    instant = now()
    prefix = f'FB-{instant:%y%m%d}-'
    # 所有分配持有同一事务锁；整数后缀避免超过999后按文字排序出错。
    numbers = db.query(Feedback.feedback_no).filter(Feedback.feedback_no.like(prefix + '%')).all()
    sequence = max((int(number.rsplit('-', 1)[1]) for number, in numbers), default=0) + 1
    row = Feedback(id=uuid4(), request_id=request_id, task_id=task_id, feedback_no=f'{prefix}{sequence:03d}', submitted_on=instant.date(), submitted_by=user.id, submitted_name=user.full_name or user.username, submitted_username=user.username, created_at=instant, updated_at=instant)
    db.add(row); db.flush()
    return row


def generate_sheet(db, user, task_id):
    tasks.require_user(user, db)
    require_ready(db)
    lock_creation(db)
    tasks.get_task(db, task_id)
    existing = db.get(FeedbackSheet, task_id)
    if existing:
        return dict(task_id=task_id, already_exists=True)
    db.add(FeedbackSheet(task_id=task_id, created_by=user.id)); db.flush()
    row = new_feedback(db, user, task_id, uuid4())
    db.commit()
    return dict(task_id=task_id, feedback_id=row.id, already_exists=False)


def serialize(row, names, access, user, opinions):
    value = {column.name: getattr(row, column.name) for column in Feedback.__table__.columns}
    value.update(assignee_name=names.get(row.assignee_id, ''), can_edit=(row.submitted_by == user.id or access['william'] or access['development']), opinions=[api_time({column.name: getattr(opinion, column.name) for column in FeedbackOpinion.__table__.columns}) for opinion in opinions])
    return api_time(value)


def catalog(db, user):
    access = permissions(db, user)
    if not ready(db):
        return dict(enabled=False, groups=[], access=access, assignees=[])
    names = dict(db.query(AppUser.id, AppUser.full_name).all())
    technical = tasks.people(db)['executors']
    feedback = db.query(Feedback).order_by(Feedback.created_at, Feedback.id).all()
    opinions = db.query(FeedbackOpinion).order_by(FeedbackOpinion.created_at.desc(), FeedbackOpinion.id).all()
    by_feedback = {}
    for opinion in opinions:
        by_feedback.setdefault(opinion.feedback_id, []).append(opinion)
    by_task = {}
    for row in feedback:
        by_task.setdefault(row.task_id, []).append(serialize(row, names, access, user, by_feedback.get(row.id, [])))
    from technical_task_management import numbers
    task_numbers = numbers(db)
    groups = [dict(task_id=task.id, task_name=task.name, task_no=task_numbers.get(task.id, ''), items=by_task.get(task.id, [])) for task, sheet, number in db.query(tasks.DevelopmentTask, FeedbackSheet, tasks.DevelopmentTaskNumber).join(FeedbackSheet, FeedbackSheet.task_id == tasks.DevelopmentTask.id).outerjoin(tasks.DevelopmentTaskNumber, tasks.DevelopmentTaskNumber.task_id == tasks.DevelopmentTask.id).order_by(FeedbackSheet.created_at, FeedbackSheet.task_id).all()]
    return dict(enabled=True, groups=groups, access=access, assignees=technical)


def detail(db, user, feedback_id):
    access = permissions(db, user)
    require_ready(db)
    row = db.get(Feedback, feedback_id)
    if not row: raise HTTPException(404, '反馈不存在')
    names = dict(db.query(AppUser.id, AppUser.full_name).all())
    opinions = db.query(FeedbackOpinion).filter_by(feedback_id=row.id).order_by(FeedbackOpinion.created_at.desc(), FeedbackOpinion.id).all()
    return serialize(row, names, access, user, opinions)


def create(db, user, task_id, payload):
    require_user(user); require_ready(db); lock_creation(db)
    if not db.get(FeedbackSheet, task_id): raise HTTPException(404, '开发反馈表不存在，请先由开发部门生成')
    previous = db.query(Feedback).filter_by(request_id=payload.request_id).first()
    if previous:
        if previous.submitted_by != user.id or previous.task_id != task_id: raise HTTPException(409, '请求标识已被使用')
        return detail(db, user, previous.id)
    row = new_feedback(db, user, task_id, payload.request_id)
    db.commit()
    return detail(db, user, row.id)


def locked_row(db, feedback_id):
    row = db.query(Feedback).filter_by(id=feedback_id).populate_existing().with_for_update().first()
    if not row: raise HTTPException(404, '反馈不存在')
    return row


def update(db, user, feedback_id, payload):
    access = permissions(db, user); require_ready(db)
    row = locked_row(db, feedback_id)
    if row.submitted_by != user.id and not (access['william'] or access['development']): raise HTTPException(403, '仅反馈人、William及开发部门可以编辑此反馈')
    if row.revision != payload.revision: raise HTTPException(409, '反馈已被其他人修改，请刷新后重试')
    changes = payload.model_dump(exclude_unset=True, exclude={'revision'})
    if changes.get('assignee_id') is not None and changes['assignee_id'] != row.assignee_id:
        if changes['assignee_id'] not in {item['id'] for item in tasks.people(db)['executors']}: raise HTTPException(422, '负责人必须为开发/IT部在职人员')
    for key, value in changes.items(): setattr(row, key, value)
    row.revision += 1; row.updated_at = now()
    db.commit()
    return detail(db, user, row.id)


def add_opinion(db, user, feedback_id, payload):
    access = permissions(db, user); require_ready(db)
    if not access[payload.kind]: raise HTTPException(403, '该意见仅允许对应人员填写')
    if not payload.content.strip(): raise HTTPException(422, '请填写意见内容')
    row = locked_row(db, feedback_id)
    latest = db.query(FeedbackOpinion).filter_by(feedback_id=row.id, kind=payload.kind).order_by(FeedbackOpinion.created_at.desc(), FeedbackOpinion.id).first()
    if (latest.id if latest else None) != payload.expected_latest_id: raise HTTPException(409, '意见已被更新，请查看最新记录后重试')
    db.add(FeedbackOpinion(feedback_id=row.id, kind=payload.kind, content=payload.content.strip(), author_id=user.id, author_name=user.full_name or user.username, author_username=user.username))
    db.commit()
    return detail(db, user, row.id)
