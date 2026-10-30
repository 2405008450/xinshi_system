"""技术需求汇总到开发任务的稳定关联；项目名称只允许追加补充文字。"""
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, inspect
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now
from annotation_models import AnnotationProject
import technical_development as tasks
import technical_requirements as requirements


class RequirementTaskLink(Base):
    __tablename__ = 'technical_requirement_task_link'
    room_id = mapped_column(Uuid, ForeignKey('annotation_technical_room.room_id'), primary_key=True)
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), nullable=False, unique=True)
    base_name = mapped_column(String(300), nullable=False)
    suffix = mapped_column(String(80), nullable=False, default='')
    source_revision = mapped_column(Integer, nullable=False)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [RequirementTaskLink.__table__]


class SourceWrite(tasks.WriteModel):
    source_revision: int = Field(ge=1)
    task_revision: int | None = Field(default=None, ge=1)
    suffix: str = Field(default='', max_length=80)
    content: str = Field(default='', max_length=100000)
    arranger_id: UUID
    executor_id: UUID
    due_at: datetime | None = None
    adjustment: str = Field(default='', max_length=30000)
    notes: str = Field(default='', max_length=30000)
    allocations: list[tasks.ExecutorAllocation] | None = Field(default=None,min_length=1,max_length=100)


def ready(db): return inspect(db.connection()).has_table(RequirementTaskLink.__tablename__)


def snapshots(db):
    if not ready(db): return {}
    return {row.task_id: dict(room_id=row.room_id, base_name=row.base_name, suffix=row.suffix, source_revision=row.source_revision) for row in db.query(RequirementTaskLink).all()}


def joined_name(base, suffix): return base + (' · ' + suffix.strip() if suffix.strip() else '')


def protect_name(db, task_id, name, user):
    if not ready(db): return
    link = db.query(RequirementTaskLink).filter_by(task_id=task_id).first()
    if not link: return
    if name == link.base_name: suffix = ''
    elif name.startswith(link.base_name + ' · '): suffix = name[len(link.base_name) + 3:]
    else: raise HTTPException(422, '原项目名称不可编辑，只能在后面增加补充内容')
    if len(suffix) > 80: raise HTTPException(422, '任务名称补充内容最多80字')
    link.suffix = suffix; link.updated_at = now(); link.updated_by = user.id


def context(db, user, room_id):
    tasks.require_user(user, db)
    if not ready(db): raise HTTPException(503, '技术需求任务关联表尚未初始化')
    room = requirements.get_room(db, user, room_id)
    project = db.get(AnnotationProject, room.project_id)
    link = db.get(RequirementTaskLink, room_id)
    return dict(room_id=room_id, source_name=link.base_name if link else (project.project_name or project.order_no).strip(), source_revision=room.revision, requirements=room.requirements, task_id=link.task_id if link else None, task=tasks.detail(db, user, link.task_id) if link else None, default_executor_id=user.id, arranger_id=user.id)


def save(db, user, room_id, payload):
    tasks.require_user(user, db); tasks.require_ready(db)
    if not ready(db): raise HTTPException(503, '技术需求任务关联表尚未初始化')
    tasks.lock_tree(db)
    room = requirements.get_room(db, user, room_id, lock=True)
    if room.revision != payload.source_revision: raise HTTPException(409, '技术需求汇总已更新，请重新打开开发任务后确认内容')
    link = db.get(RequirementTaskLink, room_id)
    if link and payload.task_revision is None: raise HTTPException(409, '该汇总已生成开发任务，请重新打开后编辑')
    if not link and payload.task_revision is not None: raise HTTPException(409, '关联任务已变化，请重新打开')
    project = db.get(AnnotationProject, room.project_id)
    base = link.base_name if link else (project.project_name or project.order_no).strip()
    name = joined_name(base, payload.suffix)
    if len(name) > 300: raise HTTPException(422, '项目名称及补充内容合计不能超过300字')
    value = tasks.TaskWrite(name=name, **payload.model_dump(exclude={'source_revision', 'task_revision', 'suffix'}))
    existing = tasks.get_task(db, link.task_id, payload.task_revision) if link else None
    tasks.validate_people(db, value, existing)
    import technical_task_allocations as collaboration
    collaboration.validate(db,value.allocations,existing)
    instant = now()
    if existing:
        row = existing
        for field, item in value.model_dump(exclude={'allocations'}).items(): setattr(row, field, item)
        collaboration.apply(db,user,row,value.allocations)
        import technical_task_incentives as incentives
        incentives.sync_task(db, user, row)
        row.revision += 1; row.updated_by = user.id; row.updated_at = instant
        link.suffix = payload.suffix.strip(); link.source_revision = room.revision; link.updated_by = user.id; link.updated_at = instant
    else:
        row = tasks.DevelopmentTask(id=uuid4(), **value.model_dump(exclude={'allocations'}), created_by=user.id, updated_by=user.id, created_at=instant, updated_at=instant)
        db.add(row); db.flush(); tasks.allocate_number(db, row.id, instant)
        db.add(RequirementTaskLink(room_id=room_id, task_id=row.id, base_name=base, suffix=payload.suffix.strip(), source_revision=room.revision, created_by=user.id, updated_by=user.id))
        collaboration.apply(db,user,row,value.allocations)
    db.commit()
    return tasks.detail(db, user, row.id)
