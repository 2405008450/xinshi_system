"""笔译项目统一进度记录，状态更新复用既有项目业务校验。"""
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, inspect
from database import get_db
from models import Base, TranslationProject, AppUser
from annotation_progress_time import business_datetime, business_now
from routers.auth import get_current_user, require_module_access, require_any_permission

STATUSES=frozenset({'cost_calculation','initial_consultation','simple_requirement','source_file_simple_requirement','pending_confirmation','confirmed','organized','arranged','translator_assigned','sent_to_translator','translator_returned','special_checked','typeset','special_checked_typeset','reviewed','sent_to_client','client_feedback','feedback_sent_to_client','cancelled','partially_cancelled','paused'})


class TranslationProjectProgress(Base):
    __tablename__='translation_project_progress'
    __table_args__=(UniqueConstraint('project_id','request_id',name='uq_translation_project_progress_request'),Index('ix_translation_project_progress_time','project_id','effective_on'))
    id=Column(Uuid,primary_key=True,default=uuid4)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False)
    request_id=Column(Uuid,nullable=False)
    from_status=Column(String(50))
    to_status=Column(String(50),nullable=False)
    note=Column(Text,nullable=False)
    actor_id=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    actor_name=Column(String(255),nullable=False)
    effective_on=Column(DateTime(timezone=True),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class ProgressWrite(BaseModel):
    project_status:str=Field(min_length=1,max_length=50)
    change_note:str=Field(min_length=1,max_length=10000)
    effective_on:datetime
    expected_updated_at:datetime | None = None
    request_id:UUID

    @field_validator('change_note')
    @classmethod
    def trim_note(cls,value):
        value=value.strip()
        if not value:raise ValueError('请填写进度/说明')
        return value

    @field_validator('effective_on')
    @classmethod
    def normalize_time(cls,value):return business_datetime(value)


def project(db,project_id,lock=False):
    query=db.query(TranslationProject).filter(TranslationProject.id==project_id,TranslationProject.annotation_migrated_at.is_(None))
    value=(query.with_for_update() if lock else query).first()
    if not value:raise HTTPException(404,'笔译项目不存在')
    if not inspect(db.connection()).has_table(TranslationProjectProgress.__tablename__):raise HTTPException(503,'笔译项目进度表尚未初始化')
    return value


def report(db,project_id):
    value=project(db,project_id)
    records=db.query(TranslationProjectProgress).filter_by(project_id=project_id).order_by(TranslationProjectProgress.effective_on.desc(),TranslationProjectProgress.created_at.desc()).all()
    return dict(project_status=value.project_status,updated_at=business_datetime(value.updated_at).isoformat() if value.updated_at else None,items=[dict(id=row.id,from_status=row.from_status,to_status=row.to_status,change_note=row.note,effective_on=business_datetime(row.effective_on).isoformat(),changed_by_name=row.actor_name) for row in records])


def save(db,project_id,payload,actor):
    value=project(db,project_id,lock=True)
    if payload.project_status!=value.project_status and payload.project_status not in STATUSES:
        raise HTTPException(422,'不支持的笔译项目状态')
    previous=db.query(TranslationProjectProgress).filter_by(project_id=project_id,request_id=payload.request_id).first()
    if previous:
        if previous.actor_id!=actor.id or previous.to_status!=payload.project_status or previous.note!=payload.change_note or business_datetime(previous.effective_on)!=payload.effective_on:
            raise HTTPException(409,'保存请求已用于其他内容，请重新打开项目进度')
        return report(db,project_id)
    from concurrency import assert_fresh
    assert_fresh(value,payload.expected_updated_at)
    from_status=value.project_status
    db.add(TranslationProjectProgress(project_id=project_id,request_id=payload.request_id,from_status=from_status,to_status=payload.project_status,note=payload.change_note,effective_on=payload.effective_on,actor_id=actor.id,actor_name=actor.full_name or actor.username))
    if from_status!=payload.project_status:
        from schemas import TranslationProjectUpdate
        from crud import update_translation_project
        # 进度行与状态在同一事务提交；继续沿用状态变更的继承、结款等既有规则。
        update_translation_project(db,project_id,TranslationProjectUpdate(project_status=payload.project_status,expected_updated_at=payload.expected_updated_at),actor_user_id=actor.id)
    else:db.commit()
    return report(db,project_id)


router=APIRouter(prefix='/projects/translation',tags=['translation_project_progress'],dependencies=[Depends(require_module_access('projects:read','projects:write'))])
@router.get('/{project_id}/progress')
def read_progress(project_id:UUID,db=Depends(get_db)):return report(db,project_id)

@router.post('/{project_id}/progress',dependencies=[Depends(require_any_permission('projects:write'))])
def write_progress(project_id:UUID,payload:ProgressWrite,db=Depends(get_db),actor:AppUser=Depends(get_current_user)):
    try:return save(db,project_id,payload,actor)
    except Exception:
        db.rollback()
        raise
