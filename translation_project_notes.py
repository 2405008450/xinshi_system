"""笔译项目简短记录：追加保存内容、业务时间及操作人快照。"""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Column, DateTime, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Session

from annotation_progress_time import business_datetime, business_now
from database import get_db
from models import AppUser, Base, TranslationProject
from routers.auth import get_current_user, require_module_access


class TranslationProjectNote(Base):
    __tablename__ = 'translation_project_note'
    __table_args__ = (
        UniqueConstraint('project_id', 'request_id', name='uq_translation_project_note_request'),
        Index('ix_translation_project_note_project_time', 'project_id', 'created_at', 'id'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    project_id = Column(Uuid, nullable=False)
    request_id = Column(Uuid, nullable=False)
    content = Column(String(200), nullable=False)
    actor_user_id = Column(Uuid, nullable=False)
    actor_name = Column(String(255), nullable=False)
    actor_username = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: str = Field(min_length=1, max_length=200)
    request_id: UUID

    @field_validator('content')
    @classmethod
    def trim_content(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('请填写记录内容')
        return value


def _project(db, project_id, *, lock=False):
    query = db.query(TranslationProject).filter(
        TranslationProject.id == project_id, TranslationProject.annotation_migrated_at.is_(None))
    if lock:
        query = query.with_for_update()
    if not query.first():
        raise HTTPException(404, '笔译项目不存在')


def serialize(row):
    return dict(id=row.id, content=row.content, actor_name=row.actor_name,
                actor_username=row.actor_username, created_at=business_datetime(row.created_at).isoformat())


def add_note(db, project_id, payload, actor):
    # 锁定业务行，串行处理同项目的重试及并发追加；不改动项目表单版本。
    _project(db, project_id, lock=True)
    existing = db.query(TranslationProjectNote).filter_by(project_id=project_id, request_id=payload.request_id).first()
    if existing:
        if existing.actor_user_id != actor.id or existing.content != payload.content:
            raise HTTPException(409, '保存请求已使用，请重新添加记录')
        return serialize(existing)
    row = TranslationProjectNote(project_id=project_id, request_id=payload.request_id,
        content=payload.content, actor_user_id=actor.id, actor_name=actor.full_name or actor.username,
        actor_username=actor.username, created_at=business_now())
    db.add(row)
    db.commit()
    return serialize(row)


def list_notes(db, project_id, skip=0, limit=10):
    _project(db, project_id)
    query = db.query(TranslationProjectNote).filter_by(project_id=project_id)
    total = query.count()
    rows = query.order_by(TranslationProjectNote.created_at.desc(), TranslationProjectNote.id.desc()).offset(skip).limit(limit).all()
    return {'items': [serialize(row) for row in rows], 'total': total}


router = APIRouter(prefix='/projects/translation', tags=['translation_project_notes'],
    dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])


@router.get('/{project_id}/short-notes')
def read_notes(project_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50),
               db: Session = Depends(get_db)):
    return list_notes(db, project_id, skip, limit)


@router.post('/{project_id}/short-notes')
def create_note(project_id: UUID, payload: NoteCreate, db: Session = Depends(get_db),
                current_user: AppUser = Depends(get_current_user)):
    return add_note(db, project_id, payload, current_user)
