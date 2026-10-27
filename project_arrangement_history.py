"""项目安排顺序与不可覆盖的变更快照；独立新表，不改写原任务结构。"""
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, Integer, JSON, String, Uuid, DateTime, Index, UniqueConstraint, inspect
from sqlalchemy.orm import Mapped, mapped_column
from chat_time import now, api_time
from models import Base, AppUser, TranslationProject


class ArrangementPlan(Base):
    __tablename__ = 'translation_arrangement_plan'
    project_id: Mapped[UUID] = mapped_column(ForeignKey('translation_project.id', ondelete='CASCADE'), primary_key=True)
    ordered_task_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class ArrangementHistory(Base):
    __tablename__ = 'translation_arrangement_history'
    __table_args__ = (UniqueConstraint('project_id', 'revision', name='uq_translation_arrangement_history_revision'), Index('ix_translation_arrangement_history_project_time', 'project_id', 'created_at'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('translation_project.id', ondelete='CASCADE'))
    revision: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[UUID] = mapped_column(Uuid)
    actor_name: Mapped[str] = mapped_column(String(255))
    before_snapshot: Mapped[dict] = mapped_column(JSON)
    after_snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReorderWrite(BaseModel):
    revision: int = Field(ge=0)
    task_ids: list[UUID] = Field(min_length=1, max_length=10000)


def ready(db):
    inspector = inspect(db.connection())
    return inspector.has_table(ArrangementPlan.__tablename__) and inspector.has_table(ArrangementHistory.__tablename__)


def ordered_tasks(db, project_id, plan=None):
    from project_arrangement import ProjectArrangement
    rows = db.query(ProjectArrangement).filter_by(project_id=project_id).order_by(ProjectArrangement.created_at, ProjectArrangement.id).all()
    if plan is None and ready(db):
        plan = db.get(ArrangementPlan, project_id)
    rank = {value: index for index, value in enumerate(plan.ordered_task_ids if plan else [])}
    return sorted(rows, key=lambda row: rank.get(str(row.id), len(rank)))


def snapshot(db, project_id, plan=None):
    from project_arrangement import serialize
    from project_arrangement_instruction import read
    project = db.get(TranslationProject, project_id)
    return jsonable_encoder({'project_status': project.project_status, **read(db,project_id),'tasks': [serialize(db, row, include_sequence=False,include_instruction=False) for row in ordered_tasks(db, project_id, plan)]})


def append_history(db, plan, user, operation, before):
    plan.revision += 1
    plan.updated_by, plan.updated_at = user.id, now()
    db.add(ArrangementHistory(project_id=plan.project_id, revision=plan.revision, operation=operation,
        actor_id=user.id, actor_name=user.full_name or user.username,
        before_snapshot=before, after_snapshot=snapshot(db, plan.project_id, plan), created_at=now()))


def lock_plan(db, project_id, user):
    if not ready(db):
        raise HTTPException(503, '项目安排顺序与历史存储尚未初始化')
    project = db.query(TranslationProject).filter_by(id=project_id).with_for_update().first()
    if not project:
        raise HTTPException(404, '项目不存在')
    plan = db.get(ArrangementPlan, project_id)
    if plan is None:
        tasks = ordered_tasks(db, project_id)
        plan = ArrangementPlan(project_id=project_id, ordered_task_ids=[str(row.id) for row in tasks], revision=0)
        db.add(plan); db.flush()
        if tasks:
            # 历史操作无法追溯，只标明首次快照，不伪造早期修改记录。
            append_history(db, plan, user, 'baseline', snapshot(db, project_id, plan))
    return plan


def sequence(db, project_id):
    rows = ordered_tasks(db, project_id)
    return [{'id': str(row.id), 'step': index+1, 'assignee_name': (person.full_name or person.username) if (person := db.get(AppUser, row.assignee_id)) else '-', 'status': row.status} for index, row in enumerate(rows)]


def detail(db, project_id, page=1, page_size=10):
    from project_arrangement import serialize
    from project_arrangement_instruction import read
    project = db.get(TranslationProject, project_id)
    if not project:
        raise HTTPException(404, '项目不存在')
    available = ready(db)
    plan = db.get(ArrangementPlan, project_id) if available else None
    history = db.query(ArrangementHistory).filter_by(project_id=project_id).order_by(ArrangementHistory.revision.desc()) if available else None
    actor = db.get(AppUser, plan.updated_by) if plan and plan.updated_by else None
    instruction=read(db,project_id)
    return api_time({'ready': available, **instruction,'revision': plan.revision if plan else 0, 'project_status': project.project_status,
        'updated_by_name': (actor.full_name or actor.username) if actor else None, 'updated_at': plan.updated_at if plan else None,
        'tasks': [serialize(db, row, include_sequence=False,instruction=instruction) for row in ordered_tasks(db, project_id, plan)],
        'history_total': history.count() if history is not None else 0,
        'history': [{key: getattr(row, key) for key in ('id', 'revision', 'operation', 'actor_name', 'created_at', 'before_snapshot', 'after_snapshot')} for row in history.offset((page-1)*page_size).limit(page_size).all()] if history is not None else []})


def reorder(db, user, project_id, payload):
    # 先比较已显示的版本，避免为已有任务首次补录快照时产生无意义冲突。
    plan = lock_plan(db, project_id, user)
    expected = plan.revision
    if expected != payload.revision and not (expected == 1 and payload.revision == 0 and db.query(ArrangementHistory).filter_by(project_id=project_id, operation='baseline').count() == 1):
        raise HTTPException(409, '项目安排已变化，请刷新后重新调整顺序')
    rows = ordered_tasks(db, project_id, plan)
    ids = [str(value) for value in payload.task_ids]
    if len(ids) != len(set(ids)) or set(ids) != {str(row.id) for row in rows}:
        raise HTTPException(409, '排序必须包含当前项目全部任务且不可重复，请刷新后重试')
    if ids != [str(row.id) for row in rows]:
        before = snapshot(db, project_id, plan)
        plan.ordered_task_ids = ids
        append_history(db, plan, user, 'reorder', before)
    db.commit()
    return detail(db, project_id)
