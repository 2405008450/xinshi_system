"""简单需求的项目设置、项目经理安排及双回执；不扩展既有表结构。"""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Session

from annotation_progress_time import business_datetime, business_now
from database import get_db
from models import AppNotification, AppUser, Base
from routers.auth import get_current_user, require_module_access


class RequirementDispatch(Base):
    __tablename__ = 'translation_requirement_dispatch'
    __table_args__ = (
        UniqueConstraint('project_id', 'request_id', name='uq_translation_requirement_dispatch_request'),
        Index('ix_translation_requirement_dispatch_project_time', 'project_id', 'created_at', 'id'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    project_id = Column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), nullable=False)
    request_id = Column(Uuid, nullable=False)
    requirement_id = Column(Uuid, nullable=True)
    requirement_snapshot = Column(JSON, nullable=True)
    content = Column(String(10000), nullable=False)
    customer_deadline_time = Column(DateTime(timezone=True), nullable=True)
    actor_user_id = Column(Uuid, nullable=False)
    actor_name = Column(String(255), nullable=False)
    actor_username = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class RequirementDispatchRecipient(Base):
    __tablename__ = 'translation_requirement_dispatch_recipient'
    __table_args__ = (UniqueConstraint('dispatch_id', 'user_id', name='uq_translation_requirement_dispatch_recipient'),)
    id = Column(Uuid, primary_key=True, default=uuid4)
    dispatch_id = Column(Uuid, ForeignKey('translation_requirement_dispatch.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Uuid, nullable=False, index=True)
    user_name = Column(String(255), nullable=False)
    notification_id = Column(Uuid, nullable=False)


class RequirementEvent(Base):
    __tablename__ = 'translation_requirement_event'
    __table_args__ = (
        CheckConstraint("(subject_kind='project' AND event_kind='project_update') OR (subject_kind IN ('requirement','dispatch') AND event_kind IN ('received','completed'))", name='ck_translation_requirement_event_kind'),
        Index('ix_translation_requirement_event_subject', 'subject_kind', 'subject_id', 'event_kind', 'actor_user_id'),
        Index('ix_translation_requirement_event_project_time', 'project_id', 'created_at', 'id'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    project_id = Column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), nullable=False)
    subject_kind = Column(String(20), nullable=False)
    subject_id = Column(Uuid, nullable=False)
    event_kind = Column(String(20), nullable=False)
    event_key = Column(String(180), nullable=False, unique=True)
    actor_user_id = Column(Uuid, nullable=False)
    actor_name = Column(String(255), nullable=False)
    actor_username = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


def status_value(value):
    from translation_project_export_service import STATUS_LABELS
    aliases = {'pending': 'pending_confirmation', 'in_progress': 'confirmed', 'completed': 'sent_to_client', 'terminated': 'cancelled'}
    if value not in STATUS_LABELS:
        raise ValueError('请选择有效的笔译项目状态')
    return aliases.get(value, value)


class ProjectSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_updated_at: datetime | None
    project_status: str | None = None
    customer_deadline_time: datetime | None = None

    @field_validator('project_status')
    @classmethod
    def valid_status(cls, value):
        if value is None:
            raise ValueError('请选择项目状态')
        return status_value(value)

    @model_validator(mode='after')
    def has_change(self):
        if not self.model_fields_set.intersection({'project_status', 'customer_deadline_time'}):
            raise ValueError('请选择需要调整的项目状态或客户回稿时间')
        return self


class DispatchCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_updated_at: datetime | None
    requirement_id: UUID | None = None
    recipient_ids: list[UUID] = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=10000)

    @field_validator('content')
    @classmethod
    def trim_content(cls, value):
        if not value.strip():
            raise ValueError('请填写安排具体内容')
        return value.strip()

    @field_validator('recipient_ids')
    @classmethod
    def unique_people(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('被安排人不能重复')
        return value


class ReceiptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reply: str = Field(min_length=1, max_length=500)

    @field_validator('reply')
    @classmethod
    def trim_reply(cls, value):
        if not value.strip():
            raise ValueError('请填写回执内容')
        return value.strip()


def iso(value):
    return business_datetime(value).isoformat() if value else None


def project_meta(parent):
    return dict(item={'project_id': parent.id}, project_status=parent.project_status,
                project_updated_at=iso(parent.updated_at), customer_deadline_time=iso(parent.customer_deadline_time))


def require_version(parent, expected):
    if business_datetime(parent.updated_at) != business_datetime(expected):
        raise HTTPException(409, '项目已被修改，请关闭项目窗口后重新打开再操作')


def event(db, parent_id, subject_kind, subject_id, event_kind, key, actor, payload):
    row = RequirementEvent(id=uuid4(), project_id=parent_id, subject_kind=subject_kind, subject_id=subject_id,
        event_kind=event_kind, event_key=key, actor_user_id=actor.id, actor_name=actor.full_name or actor.username,
        actor_username=actor.username, payload=jsonable_encoder(payload), created_at=business_now())
    db.add(row)
    return row


def save_settings(db, project_id, payload, actor):
    from translation_simple_requirements import project
    parent = project(db, project_id, lock=True)
    key = f'settings:{project_id}:{payload.request_id}'
    values = {field: (iso(getattr(payload, field)) if field == 'customer_deadline_time' else getattr(payload, field))
              for field in ('project_status', 'customer_deadline_time') if field in payload.model_fields_set}
    previous = db.query(RequirementEvent).filter_by(event_key=key).first()
    if previous:
        if previous.actor_user_id != actor.id or previous.payload['values'] != values:
            raise HTTPException(409, '保存请求已使用，请重新操作')
        return previous.payload['result'] | {'changed_fields': list(values)}
    require_version(parent, payload.expected_updated_at)
    before = {'project_status': parent.project_status, 'customer_deadline_time': iso(parent.customer_deadline_time)}
    for field, value in values.items():
        setattr(parent, field, business_datetime(payload.customer_deadline_time).replace(tzinfo=None)
                if field == 'customer_deadline_time' and payload.customer_deadline_time else value)
    after = {'project_status': parent.project_status, 'customer_deadline_time': iso(parent.customer_deadline_time)}
    if before != after:
        parent.updated_at = business_now().replace(tzinfo=None)
    event(db, project_id, 'project', project_id, 'project_update', key, actor,
          {'values': values, 'before': before, 'after': after, 'result': project_meta(parent)})
    db.commit()
    return project_meta(parent) | {'changed_fields': list(values)}


def completion_states(db, kind, subject_id):
    return {str(row.actor_user_id): {'completed_at': iso(row.created_at), 'completed_reply': row.payload['reply']}
            for row in db.query(RequirementEvent).filter_by(subject_kind=kind, subject_id=subject_id, event_kind='completed')}


def receipt_states(db, dispatch_id):
    result = {}
    for row in db.query(RequirementEvent).filter_by(subject_kind='dispatch', subject_id=dispatch_id):
        prefix = 'received' if row.event_kind == 'received' else 'completed'
        result.setdefault(str(row.actor_user_id), {}).update({prefix + '_at': iso(row.created_at),
            'reply' if prefix == 'received' else 'completed_reply': row.payload['reply']})
    return result


def serialize_dispatch(db, row):
    receipts = receipt_states(db, row.id)
    recipients = db.query(RequirementDispatchRecipient).filter_by(dispatch_id=row.id).order_by(
        RequirementDispatchRecipient.user_name, RequirementDispatchRecipient.user_id).all()
    return dict(id=row.id, project_id=row.project_id, content=row.content, requirement_id=row.requirement_id,
        requirement_snapshot=row.requirement_snapshot, customer_deadline_time=iso(row.customer_deadline_time),
        actor_name=row.actor_name, actor_username=row.actor_username, created_at=iso(row.created_at), recipients=[
            dict(user_id=r.user_id, user_name=r.user_name, received_at=None, reply=None, completed_at=None,
                 completed_reply=None) | receipts.get(str(r.user_id), {}) for r in recipients])


def create_dispatch(db, project_id, payload, actor):
    import translation_simple_requirements as simple
    parent = simple.project(db, project_id, lock=True)
    existing = db.query(RequirementDispatch).filter_by(project_id=project_id, request_id=payload.request_id).first()
    if existing:
        data = serialize_dispatch(db, existing)
        if existing.actor_user_id != actor.id or existing.content != payload.content or existing.requirement_id != payload.requirement_id or set(payload.recipient_ids) != {r['user_id'] for r in data['recipients']}:
            raise HTTPException(409, '发送请求已使用，请重新发送安排')
        return data
    require_version(parent, payload.expected_updated_at)
    users = {u.id: u for u in simple.eligible_recipients(db)}
    if not set(payload.recipient_ids).issubset(users):
        raise HTTPException(422, '请选择笔译项目部的有效人员')
    requirement = db.get(simple.TranslationSimpleRequirement, payload.requirement_id) if payload.requirement_id else None
    if payload.requirement_id and (not requirement or requirement.project_id != project_id):
        raise HTTPException(422, '关联简单需求不属于当前项目或已被删除')
    moment = business_now()
    row = RequirementDispatch(id=uuid4(), project_id=project_id, request_id=payload.request_id,
        requirement_id=payload.requirement_id, requirement_snapshot=jsonable_encoder(simple.serialize(db, requirement)) if requirement else None,
        content=payload.content, customer_deadline_time=business_datetime(parent.customer_deadline_time),
        actor_user_id=actor.id, actor_name=actor.full_name or actor.username, actor_username=actor.username, created_at=moment)
    db.add(row); db.flush()
    notices = []
    for uid in payload.recipient_ids:
        notice = simple.notification(db, uid, f'{parent.order_no} · 项目经理安排',
            f'{row.actor_name}发送了项目安排，请查看并回复收到、已完成回执。', row, moment, 'translation_simple_dispatch')
        notices.append(notice)
        db.add(RequirementDispatchRecipient(dispatch_id=row.id, user_id=uid,
            user_name=users[uid].full_name or users[uid].username, notification_id=notice.id))
    db.commit(); simple.publish(notices)
    return serialize_dispatch(db, row)


def dispatch_detail(db, dispatch_id, actor):
    from translation_simple_requirements import project
    row = db.get(RequirementDispatch, dispatch_id)
    if not row:
        raise HTTPException(404, '项目经理安排不存在')
    target = db.query(RequirementDispatchRecipient).filter_by(dispatch_id=row.id, user_id=actor.id).first()
    if row.actor_user_id != actor.id and not target:
        from permission_service import user_has_permission
        if not user_has_permission(db, actor.id, 'projects:read'):
            raise HTTPException(403, '无权查看该安排')
    parent = project(db, row.project_id)
    data = serialize_dispatch(db, row)
    mine = next((r for r in data['recipients'] if r['user_id'] == actor.id), {})
    return data | dict(order_no=parent.order_no, project_name=parent.source_file_name or parent.project_name,
        current_status=parent.project_status, current_customer_deadline_time=iso(parent.customer_deadline_time),
        is_recipient=bool(target), can_reply=bool(target and not mine.get('received_at')),
        can_complete=bool(target and mine.get('received_at') and not mine.get('completed_at')),
        my_completed_at=mine.get('completed_at'))


def dispatch_receipt(db, dispatch_id, step, payload, actor):
    import translation_simple_requirements as simple
    target = db.query(RequirementDispatchRecipient).filter_by(dispatch_id=dispatch_id, user_id=actor.id).with_for_update().first()
    if not target:
        raise HTTPException(403, '仅被安排人本人可回复回执')
    row = db.get(RequirementDispatch, dispatch_id)
    parent = simple.project(db, row.project_id)
    key = f'receipt:dispatch:{dispatch_id}:{actor.id}:{step}'
    if db.query(RequirementEvent.id).filter_by(event_key=key).first():
        return dispatch_detail(db, dispatch_id, actor)
    if step == 'completed' and not db.query(RequirementEvent.id).filter_by(
            event_key=f'receipt:dispatch:{dispatch_id}:{actor.id}:received').first():
        raise HTTPException(409, '请先回复收到，再回复已完成回执')
    moment = business_now()
    event(db, row.project_id, 'dispatch', row.id, step, key, actor, {'reply': payload.reply})
    label = '收到' if step == 'received' else '已完成'
    notice = simple.notification(db, row.actor_user_id, f'{parent.order_no} · {label}回执',
        f'{target.user_name}回复{label}：{payload.reply}', row, moment, 'translation_simple_dispatch_receipt')
    original = db.get(AppNotification, target.notification_id)
    if original and original.recipient_user_id == actor.id and not original.is_read:
        original.is_read = True; original.read_at = moment.astimezone(timezone.utc).replace(tzinfo=None)
    db.commit(); simple.publish([notice])
    return dispatch_detail(db, dispatch_id, actor)


def complete_requirement(db, requirement_id, payload, actor):
    import translation_simple_requirements as simple
    target = db.query(simple.TranslationSimpleRequirementRecipient).filter_by(requirement_id=requirement_id,
        user_id=actor.id).with_for_update().first()
    if not target:
        raise HTTPException(403, '仅所选通知人本人可回复已完成回执')
    row = db.get(simple.TranslationSimpleRequirement, requirement_id)
    parent = simple.project(db, row.project_id)
    key = f'receipt:requirement:{requirement_id}:{actor.id}:completed'
    if db.query(RequirementEvent.id).filter_by(event_key=key).first():
        return simple.detail(db, requirement_id, actor)
    if not target.received_at:
        raise HTTPException(409, '请先回复收到，再回复已完成回执')
    event(db, row.project_id, 'requirement', row.id, 'completed', key, actor, {'reply': payload.reply})
    notice = simple.notification(db, row.actor_user_id, f'{parent.order_no} · 已完成回执',
        f'{target.user_name}回复已完成：{payload.reply}', row, business_now(), 'translation_simple_requirement_receipt')
    db.commit(); simple.publish([notice])
    return simple.detail(db, requirement_id, actor)


def project_activity(db, project_id, skip, limit, change_skip=0):
    from translation_simple_requirements import project
    project(db, project_id)
    dispatches = db.query(RequirementDispatch).filter_by(project_id=project_id)
    changes = db.query(RequirementEvent).filter_by(project_id=project_id, subject_kind='project')
    return dict(items=[serialize_dispatch(db, r) for r in dispatches.order_by(RequirementDispatch.created_at.desc(),
        RequirementDispatch.id.desc()).offset(skip).limit(limit)], total=dispatches.count(), changes=[dict(
            id=r.id, actor_name=r.actor_name, created_at=iso(r.created_at), **r.payload) for r in changes.order_by(
                RequirementEvent.created_at.desc(), RequirementEvent.id.desc()).offset(change_skip).limit(limit)], changes_total=changes.count())


router = APIRouter(prefix='/translation-simple-requirements', tags=['translation_simple_dispatch'])
access = require_module_access('projects:read', 'projects:write')


@router.patch('/projects/{project_id}/settings', dependencies=[Depends(access)])
def settings(project_id: UUID, payload: ProjectSettings, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return save_settings(db, project_id, payload, actor)


@router.get('/projects/{project_id}/dispatches', dependencies=[Depends(access)])
def activity(project_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50), change_skip: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return project_activity(db, project_id, skip, limit, change_skip)


@router.post('/projects/{project_id}/dispatches', dependencies=[Depends(access)])
def send(project_id: UUID, payload: DispatchCreate, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return create_dispatch(db, project_id, payload, actor)


@router.get('/dispatches/{dispatch_id}')
def read_dispatch(dispatch_id: UUID, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return dispatch_detail(db, dispatch_id, actor)


@router.post('/dispatches/{dispatch_id}/{step}')
def reply_dispatch(dispatch_id: UUID, step: Literal['received', 'completed'], payload: ReceiptInput,
                   db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return dispatch_receipt(db, dispatch_id, step, payload, actor)


@router.post('/{requirement_id}/completed')
def finish(requirement_id: UUID, payload: ReceiptInput, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return complete_requirement(db, requirement_id, payload, actor)
