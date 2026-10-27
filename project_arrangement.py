"""笔译项目人员安排与今日任务；完成任务和追加工作报告原子提交。"""
from datetime import date, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Uuid, inspect, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from chat_time import now, api_time
from models import Base, AppUser, TranslationProject
from task_models import DailyReport, DailyReportItem
from task_schemas import DailyReportItemInput, DailyReportSaveRequest
from work_report_dates import report_business_date
import work_report_access as access
import project_arrangement_history as history
import project_arrangement_instruction as instructions


class ProjectArrangement(Base):
    __tablename__ = 'translation_project_arrangement'
    __table_args__ = (
        CheckConstraint("status IN ('pending','in_progress','completed')", name='ck_translation_arrangement_status'),
        CheckConstraint('estimated_minutes BETWEEN 0 AND 1440 AND actual_minutes BETWEEN 0 AND 1440', name='ck_translation_arrangement_duration'),
        Index('ix_translation_arrangement_assignee_date', 'assignee_id', 'work_date'),
        Index('ix_translation_arrangement_project', 'project_id'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('translation_project.id', ondelete='CASCADE'))
    assignee_id: Mapped[UUID] = mapped_column(ForeignKey('app_user.id', ondelete='RESTRICT'))
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey('app_user.id', ondelete='RESTRICT'))
    content: Mapped[str] = mapped_column(Text)
    work_date: Mapped[date] = mapped_column(Date)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class AssignmentInput(BaseModel):
    assignee_id: UUID
    content: str = Field(min_length=1, max_length=10000)
    work_date: date


class AssignmentBatch(BaseModel):
    items: list[AssignmentInput] = Field(min_length=1, max_length=100)
    common_instruction: str | None = Field(default=None,max_length=10000)
    instruction_revision: int | None = Field(default=None,ge=0)


class TaskEdit(BaseModel):
    revision: int = Field(ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    estimated_minutes: int | None = Field(default=None, ge=0, le=1440)
    actual_minutes: int | None = Field(default=None, ge=0, le=1440)
    status: str | None = None


class TaskComplete(BaseModel):
    revision: int = Field(ge=1)
    item: DailyReportItemInput


def ready(db):
    return inspect(db.connection()).has_table(ProjectArrangement.__tablename__)


def require_ready(db):
    if not ready(db):
        raise HTTPException(503, '项目安排表尚未初始化，请联系管理员执行已审核的迁移')


def allowed_people(db, user):
    return access.sender_ids_for_rules(db, access.receiving_rules(db, user))


def serialize(db, row, include_sequence=True, include_instruction=True, instruction=None):
    person = db.get(AppUser, row.assignee_id)
    project = db.get(TranslationProject, row.project_id)
    result = api_time({key: getattr(row, key) for key in (
        'id', 'project_id', 'assignee_id', 'assigned_by', 'content', 'work_date',
        'estimated_minutes', 'actual_minutes', 'status', 'revision', 'created_at', 'updated_at', 'completed_at'
    )} | {'assignee_name': person.full_name or person.username if person else '-',
         'assigned_by_name': ((actor.full_name or actor.username) if (actor := db.get(AppUser, row.assigned_by)) else '-'),
         'order_no': project.order_no if project else '-', 'project_name': (project.source_file_name or project.project_name) if project else '-'})
    if include_sequence:
        result['execution_sequence'] = history.sequence(db, row.project_id)
        result['execution_step'] = next((item['step'] for item in result['execution_sequence'] if item['id'] == str(row.id)), None)
    if include_instruction:result.update(instruction if instruction is not None else instructions.read(db,row.project_id))
    return result


def serialize_many(db, rows):
    chains = {}
    briefs = {}
    result = []
    for row in rows:
        if row.project_id not in chains:
            chains[row.project_id] = history.sequence(db, row.project_id)
        chain = chains[row.project_id]
        if row.project_id not in briefs:briefs[row.project_id]=instructions.read(db,row.project_id)
        result.append(serialize(db, row, include_sequence=False,instruction=briefs[row.project_id]) | {'execution_sequence': chain, 'execution_step': next((item['step'] for item in chain if item['id'] == str(row.id)), None)})
    return result


def create_assignments(db, user, project_id, payload):
    require_ready(db)
    plan = history.lock_plan(db, project_id, user)
    before = history.snapshot(db, project_id, plan)
    rows = []
    for item in payload.items:
        person = db.get(AppUser, item.assignee_id)
        if not person or not person.is_active or person.is_deleted:
            raise HTTPException(422, '只能安排在职且启用的人员')
        if not item.content.strip():
            raise HTTPException(422, '请填写具体任务')
        row = ProjectArrangement(project_id=project_id, assigned_by=user.id,
                                 **item.model_dump(exclude={'content'}), content=item.content.strip())
        db.add(row)
        rows.append(row)
    db.flush()
    if payload.common_instruction is not None:
        instructions.write_locked(db,user,project_id,payload.common_instruction,payload.instruction_revision)
    plan.ordered_task_ids = [*plan.ordered_task_ids, *(str(row.id) for row in rows)]
    project = db.get(TranslationProject, project_id)
    if project.project_status in (None, 'initial_consultation', 'pending', 'pending_confirmation', 'confirmed', 'organized', 'in_progress', 'arranged'):
        project.project_status = 'arranged'
        project.updated_at = now().replace(tzinfo=None)
    history.append_history(db, plan, user, 'assign', before)
    db.commit()
    return serialize_many(db, rows)


def locked_task(db, task_id, revision, user):
    require_ready(db)
    project_id = db.query(ProjectArrangement.project_id).filter_by(id=task_id).scalar()
    if project_id is None:
        raise HTTPException(404, '任务不存在')
    history.lock_plan(db, project_id, user)
    row = db.query(ProjectArrangement).filter_by(id=task_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '任务不存在')
    if row.revision != revision:
        raise HTTPException(409, '任务已被修改，请刷新后重试')
    return row


def edit_task(db, user, task_id, payload, can_assign=False):
    row = locked_task(db, task_id, payload.revision, user)
    if row.assignee_id != user.id and not can_assign:
        raise HTTPException(403, '无权修改该任务')
    if row.status == 'completed':
        raise HTTPException(409, '任务已完成，请在工作报告中查看记录')
    plan = db.get(history.ArrangementPlan, row.project_id)
    before = history.snapshot(db, row.project_id, plan)
    values = payload.model_dump(exclude_none=True, exclude={'revision'})
    if 'status' in values and values['status'] not in ('pending', 'in_progress'):
        raise HTTPException(422, '完成任务须先填写并保存工作报告')
    if 'content' in values:
        values['content'] = values['content'].strip()
        if not values['content']:
            raise HTTPException(422, '请填写具体任务')
    for key, value in values.items():
        setattr(row, key, value)
    row.revision += 1
    row.updated_at = now()
    history.append_history(db, plan, user, 'edit', before)
    db.commit()
    return serialize(db, row)


def complete_task(db, user, task_id, payload):
    row = locked_task(db, task_id, payload.revision, user)
    if row.assignee_id != user.id:
        raise HTTPException(403, '仅任务本人可以完成任务并加入工作报告')
    if row.status == 'completed':
        raise HTTPException(409, '任务已完成，不可重复录入')
    plan = db.get(history.ArrangementPlan, row.project_id)
    before = history.snapshot(db, row.project_id, plan)
    item = payload.item.model_copy(deep=True)
    # 重新按完整工作报告规则校验，拒绝省略类型而绕过必填项。
    metadata = item.display_metadata or {}
    if metadata.get('report_types') != ['笔译项目']:
        raise HTTPException(422, '项目安排任务须按笔译项目填写报告')
    project = db.get(TranslationProject, row.project_id)
    item.source_type, item.source_id = 'manual', row.id
    metadata.update(source='project_arrangement', arrangement_id=str(row.id),
                    order_no=project.order_no, project_type='translation', _feedback_key=str(uuid4()))
    item.display_metadata = metadata
    from task_report_completion import append_report_item
    entry = append_report_item(db, user, item, 'project_arrangement', row.id)
    row.status, row.actual_minutes, row.report_item_id = 'completed', item.duration_minutes, entry.id
    row.completed_at = row.updated_at = now()
    row.revision += 1
    history.append_history(db, plan, user, 'complete', before)
    db.commit()
    return serialize(db, row)
