"""项目级客户经理与不可覆盖的调整记录；不修改客户档案。"""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint, Uuid, func, select
from sqlalchemy.orm import Session, object_session

from annotation_progress_time import business_datetime, business_now
from database import get_db
from models import AppUser, Base
from routers.auth import require_permission


class ProjectClientManagerChange(Base):
    __tablename__ = 'project_client_manager_change'
    __table_args__ = (
        UniqueConstraint('project_type', 'project_id', 'revision', name='uq_project_client_manager_revision'),
        Index('ix_project_client_manager_latest', 'project_type', 'project_id', 'revision'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    project_type = Column(String(30), nullable=False)
    project_id = Column(Uuid, nullable=False)
    revision = Column(Integer, nullable=False)
    previous_manager_id = Column(Uuid)
    previous_manager_name = Column(String(255))
    new_manager_id = Column(Uuid)
    new_manager_name = Column(String(255))
    actor_user_id = Column(Uuid)
    actor_name = Column(String(255))
    reason = Column(String(500), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


def latest(db, project_type, project_id):
    return db.query(ProjectClientManagerChange).filter_by(
        project_type=project_type, project_id=project_id,
    ).order_by(ProjectClientManagerChange.revision.desc()).first()


def manager_name_expression(project_type, project_id, fallback):
    """有新记录时采用项目经理快照；历史项目继续显示原客户档案值。"""
    row = ProjectClientManagerChange
    value = select(func.coalesce(row.new_manager_name, '')).where(
        row.project_type == project_type, row.project_id == project_id,
    ).order_by(row.revision.desc()).limit(1).correlate_except(row).scalar_subquery()
    return func.coalesce(value, fallback)


def attach(db, project_type, projects):
    if not projects:
        return
    row = ProjectClientManagerChange
    ranked = select(row.project_id, row.new_manager_id, row.new_manager_name,
        func.row_number().over(partition_by=row.project_id, order_by=row.revision.desc()).label('rank')
    ).where(row.project_type == project_type, row.project_id.in_([p.id for p in projects])).subquery()
    states = {item.project_id: item for item in db.execute(select(ranked).where(ranked.c.rank == 1))}
    for project in projects:
        state = states.get(project.id)
        project.__dict__['_project_client_manager'] = state
        project.client_manager_id = state.new_manager_id if state else None
        if project_type == 'translation' and state:
            project.client_manager = state.new_manager_name


def interpretation_manager_name(project, fallback):
    if '_project_client_manager' not in project.__dict__:
        db = object_session(project)
        if db:
            attach(db, 'interpretation', [project])
    state = project.__dict__.get('_project_client_manager')
    return state.new_manager_name if state else fallback


def apply(db, project_type, project, manager_id, reason, actor_id, *, creating=False):
    """调用方先锁项目；与项目保存处于同一事务，不单独提交。"""
    actor = db.get(AppUser, actor_id) if actor_id else None
    if creating and not manager_id:
        manager_id = actor_id
    manager = db.get(AppUser, manager_id) if manager_id else None
    previous = latest(db, project_type, project.id)
    old_id = previous.new_manager_id if previous else (
        project.client_manager_id if project_type == 'recruitment' else None)
    old_name = previous.new_manager_name if previous else (
        getattr(project, 'client_manager_name', None) if project_type == 'recruitment' else
        getattr(project, 'current_client_manager', None) if project_type == 'interpretation' else
        getattr(getattr(project, 'client', None), 'client_manager', None))
    if not creating and old_id == manager_id:
        return
    if manager_id and (not manager or not manager.is_active or manager.is_deleted) and (creating or manager_id != old_id):
        raise ValueError('请选择启用的客户经理')
    normalized = (reason or '').strip()
    if len(normalized) > 500:
        raise ValueError('客户经理调整原因不能超过500字')
    if (not creating or manager_id != actor_id) and not normalized:
        raise ValueError('请填写客户经理调整原因')
    db.add(ProjectClientManagerChange(
        project_type=project_type, project_id=project.id,
        revision=previous.revision + 1 if previous else 1,
        previous_manager_id=None if creating else old_id,
        previous_manager_name=None if creating else old_name,
        new_manager_id=manager_id, new_manager_name=(manager.full_name or manager.username) if manager else None,
        actor_user_id=actor_id, actor_name=(actor.full_name or actor.username) if actor else None,
        reason=normalized or '创建项目，默认由填写人担任客户经理', changed_at=business_now(),
    ))
    if project_type == 'recruitment':
        project.client_manager_id = manager_id
        project.client_manager_name_snapshot = (manager.full_name or manager.username) if manager else None


router = APIRouter(prefix='/project-client-managers', tags=['project_client_managers'],
                   dependencies=[Depends(require_permission('projects:read'))])


@router.get('/{project_type}/{project_id}/history')
def history(project_type: str, project_id: UUID,
            skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db)):
    from models import TranslationProject
    from interpretation_models import InterpretationProject
    from recruitment_models import RecruitmentProject
    from annotation_models import AnnotationProject
    model = {'translation': TranslationProject, 'interpretation': InterpretationProject,
             'recruitment': RecruitmentProject, 'annotation': AnnotationProject}.get(project_type)
    if not model or not db.get(model, project_id):
        raise HTTPException(404, '项目不存在')
    if project_type == 'annotation':
        from annotation_manager_change_service import list_annotation_manager_changes
        rows, total = list_annotation_manager_changes(db, project_id=project_id,
            manager_role='client_manager', skip=skip, limit=limit)
        return {'total': total, 'items': [dict(id=r.id, previous_manager_name=r.previous_manager_name,
            new_manager_name=r.new_manager_name, actor_name=r.actor_name_snapshot or r.actor_username_snapshot,
            reason=r.reason, changed_at=business_datetime(r.changed_at).isoformat()) for r in rows]}
    query = db.query(ProjectClientManagerChange).filter_by(project_type=project_type, project_id=project_id)
    total = query.count()
    rows = query.order_by(ProjectClientManagerChange.revision.desc()).offset(skip).limit(limit).all()
    return {'total': total, 'items': [dict(id=r.id, previous_manager_name=r.previous_manager_name,
        new_manager_name=r.new_manager_name, actor_name=r.actor_name, reason=r.reason,
        changed_at=business_datetime(r.changed_at).isoformat()) for r in rows]}
