"""笔译简单需求、状态变更及接收人明确回复；与通知在同一事务保存。"""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Session

from annotation_progress_time import business_datetime, business_now
from database import get_db
from department_models import Department, DepartmentMember
from models import AppNotification, AppUser, Base, TranslationProject
from routers.auth import get_current_user, require_module_access

STATUS_LABELS = {'simple_requirement': '简单需求', 'source_file_simple_requirement': '原文件+简单需求'}


class TranslationSimpleRequirement(Base):
    __tablename__ = 'translation_simple_requirement'
    __table_args__ = (
        UniqueConstraint('project_id', 'request_id', name='uq_translation_simple_requirement_request'),
        Index('ix_translation_simple_requirement_project_time', 'project_id', 'created_at', 'id'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    project_id = Column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), nullable=False)
    request_id = Column(Uuid, nullable=False)
    original_text = Column(String(2000), nullable=False)
    translated_text = Column(String(2000), nullable=False, default='')
    chargeable = Column(Boolean, nullable=False)
    previous_status = Column(String(50), nullable=True)
    saved_status = Column(String(50), nullable=False)
    actor_user_id = Column(Uuid, nullable=False)
    actor_name = Column(String(255), nullable=False)
    actor_username = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class TranslationSimpleRequirementRecipient(Base):
    __tablename__ = 'translation_simple_requirement_recipient'
    __table_args__ = (
        UniqueConstraint('requirement_id', 'user_id', name='uq_translation_simple_requirement_recipient'),
        Index('ix_translation_simple_requirement_recipient_user', 'user_id', 'received_at'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    requirement_id = Column(Uuid, ForeignKey('translation_simple_requirement.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Uuid, nullable=False)
    user_name = Column(String(255), nullable=False)
    notification_id = Column(Uuid, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True)
    reply = Column(String(500), nullable=True)


class RequirementCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    original_text: str = Field(min_length=1, max_length=2000)
    translated_text: str = Field(default='', max_length=2000)
    chargeable: StrictBool
    saved_status: str
    recipient_ids: list[UUID] = Field(min_length=1, max_length=100)
    expected_project_status: str | None
    expected_updated_at: datetime | None

    @field_validator('saved_status')
    @classmethod
    def valid_status(cls, value):
        from translation_requirement_dispatch import status_value
        return status_value(value)

    @field_validator('original_text', 'translated_text')
    @classmethod
    def trim_text(cls, value, info):
        value = value.strip()
        if info.field_name == 'original_text' and not value:
            raise ValueError('请填写原文')
        return value

    @field_validator('recipient_ids')
    @classmethod
    def unique_recipients(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('通知人不能重复')
        return value


class RequirementReply(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reply: str = Field(default='收到', min_length=1, max_length=500)

    @field_validator('reply')
    @classmethod
    def trim_reply(cls, value):
        if not value.strip():
            raise ValueError('请填写收到回复')
        return value.strip()


def project(db, project_id, lock=False):
    query = db.query(TranslationProject).filter(TranslationProject.id == project_id,
                                               TranslationProject.annotation_migrated_at.is_(None))
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, '笔译项目不存在')
    return row


def eligible_recipients(db):
    # 兼容主部门和跨部门归属；只允许当前部门中的有效账号。
    departments = db.query(Department).filter_by(name='笔译项目部').all()
    ids = [row.id for row in departments]
    names = {name for row in departments for name in [row.name, *(row.aliases or [])]}
    linked = db.query(DepartmentMember.user_id).filter(DepartmentMember.department_id.in_(ids))
    from sqlalchemy import or_
    return db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False),
        or_(AppUser.department.in_(names), AppUser.id.in_(linked))).order_by(AppUser.full_name, AppUser.username).all()


def recipient_options(db):
    users = eligible_recipients(db)
    preferred = [u for u in users if (u.username or '').casefold() == 'shaofei']
    if not preferred:
        preferred = [u for u in users if '少妃' in (u.full_name or '')]
    return {'items': [dict(id=u.id, name=u.full_name or u.username) for u in users],
            'default_recipient_ids': [preferred[0].id] if len(preferred) == 1 else []}


def serialize(db, row):
    from translation_requirement_dispatch import completion_states
    completed = completion_states(db, 'requirement', row.id)
    recipients = db.query(TranslationSimpleRequirementRecipient).filter_by(requirement_id=row.id).order_by(
        TranslationSimpleRequirementRecipient.user_name, TranslationSimpleRequirementRecipient.user_id).all()
    return dict(id=row.id, project_id=row.project_id, original_text=row.original_text,
        translated_text=row.translated_text, chargeable=row.chargeable, previous_status=row.previous_status,
        saved_status=row.saved_status, actor_name=row.actor_name, actor_username=row.actor_username,
        created_at=business_datetime(row.created_at).isoformat(), recipients=[dict(user_id=r.user_id,
            user_name=r.user_name, reply=r.reply, received_at=business_datetime(r.received_at).isoformat()
            if r.received_at else None, **completed.get(str(r.user_id), {})) for r in recipients])


def notification(db, recipient_id, title, content, row, moment, kind):
    item = AppNotification(id=uuid4(), recipient_user_id=recipient_id, title=title, content=content,
        notification_type=kind, related_project_id=row.project_id, related_project_type='translation',
        related_entity_id=row.id, is_read=False, created_at=moment.replace(tzinfo=None))
    db.add(item)
    return item


def publish(notifications):
    import logging
    from notification_ws import dispatch_personal_message
    from schemas import NotificationResponse
    for item in notifications:
        try:
            dispatch_personal_message(item.recipient_user_id, {'type': 'notification',
                'notification': NotificationResponse.model_validate(item).model_dump(mode='json')})
        except Exception:
            # 数据已提交；轮询仍可取得通知，不将实时派发失败误报为保存失败。
            logging.getLogger(__name__).warning('simple_requirement_realtime_delivery_deferred')


def create_requirement(db, project_id, payload, actor):
    parent = project(db, project_id, lock=True)
    existing = db.query(TranslationSimpleRequirement).filter_by(project_id=project_id, request_id=payload.request_id).first()
    if existing:
        data = serialize(db, existing)
        same = all(getattr(existing, field) == getattr(payload, field) for field in
                   ('original_text', 'translated_text', 'chargeable', 'saved_status'))
        if existing.actor_user_id != actor.id or not same or set(payload.recipient_ids) != {r['user_id'] for r in data['recipients']}:
            raise HTTPException(409, '保存请求已使用，请重新添加简单需求')
        return {'item': data, 'project_status': parent.project_status,
                'project_updated_at': business_datetime(parent.updated_at).isoformat() if parent.updated_at else None}
    if parent.project_status != payload.expected_project_status or business_datetime(parent.updated_at) != business_datetime(payload.expected_updated_at):
        raise HTTPException(409, '项目已被修改，请重新加载简单需求后再保存')
    users = {u.id: u for u in eligible_recipients(db)}
    if not set(payload.recipient_ids).issubset(users):
        raise HTTPException(422, '通知人须为笔译项目部的有效人员，请刷新后重选')
    moment = business_now()
    row = TranslationSimpleRequirement(id=uuid4(), project_id=project_id, request_id=payload.request_id,
        original_text=payload.original_text, translated_text=payload.translated_text, chargeable=payload.chargeable,
        previous_status=parent.project_status, saved_status=payload.saved_status, actor_user_id=actor.id,
        actor_name=actor.full_name or actor.username, actor_username=actor.username, created_at=moment)
    db.add(row)
    parent.project_status = payload.saved_status
    parent.updated_at = moment.replace(tzinfo=None)
    db.flush()
    notifications = []
    for uid in payload.recipient_ids:
        notice = notification(db, uid, f'{parent.order_no} · {STATUS_LABELS.get(payload.saved_status, "简单需求")}',
            f'{row.actor_name}发送了简单需求（{"收费" if row.chargeable else "不收费"}），请查看并回复收到及已完成回执。',
            row, moment, 'translation_simple_requirement')
        notifications.append(notice)
        db.add(TranslationSimpleRequirementRecipient(requirement_id=row.id, user_id=uid,
            user_name=users[uid].full_name or users[uid].username, notification_id=notice.id))
    db.commit()
    publish(notifications)
    return {'item': serialize(db, row), 'project_status': parent.project_status,
            'project_updated_at': business_datetime(parent.updated_at).isoformat()}


def list_requirements(db, project_id, skip=0, limit=10):
    parent = project(db, project_id)
    query = db.query(TranslationSimpleRequirement).filter_by(project_id=project_id)
    rows = query.order_by(TranslationSimpleRequirement.created_at.desc(), TranslationSimpleRequirement.id.desc()).offset(skip).limit(limit).all()
    total = query.count()
    return {'items': [serialize(db, r) for r in rows], 'total': total,
            'project_status': parent.project_status,
            'project_updated_at': business_datetime(parent.updated_at).isoformat() if parent.updated_at else None,
            'customer_deadline_time': business_datetime(parent.customer_deadline_time).isoformat() if parent.customer_deadline_time else None,
            'latest_requirement': serialize(db, query.order_by(TranslationSimpleRequirement.created_at.desc(), TranslationSimpleRequirement.id.desc()).first()) if total else None}


def detail(db, requirement_id, actor):
    row = db.get(TranslationSimpleRequirement, requirement_id)
    if not row:
        raise HTTPException(404, '简单需求不存在')
    is_recipient = db.query(TranslationSimpleRequirementRecipient).filter_by(requirement_id=row.id, user_id=actor.id).first()
    if row.actor_user_id != actor.id and not is_recipient:
        from permission_service import user_has_permission
        if not user_has_permission(db, actor.id, 'projects:read'):
            raise HTTPException(403, '仅发送人、通知接收人及有项目查看权限的人员可查看')
    parent = project(db, row.project_id)
    data = serialize(db, row)
    mine = next((person for person in data['recipients'] if person['user_id'] == actor.id), {})
    data.update(order_no=parent.order_no, project_name=parent.project_name,
                can_reply=bool(is_recipient and not is_recipient.received_at), current_status=parent.project_status,
                is_recipient=bool(is_recipient),
                can_complete=bool(is_recipient and is_recipient.received_at and not mine.get('completed_at')),
                my_completed_at=mine.get('completed_at'),
                customer_deadline_time=business_datetime(parent.customer_deadline_time).isoformat() if parent.customer_deadline_time else None)
    return data


def receive(db, requirement_id, payload, actor):
    # 不把通知已读当作收到；仅接收人本人可明确回复，重复点击不生成重复回复通知。
    target = db.query(TranslationSimpleRequirementRecipient).filter_by(
        requirement_id=requirement_id, user_id=actor.id).with_for_update().first()
    if not target:
        raise HTTPException(403, '仅所选通知人本人可回复收到')
    row = db.get(TranslationSimpleRequirement, requirement_id)
    parent = project(db, row.project_id)
    if target.received_at:
        return detail(db, row.id, actor)
    moment = business_now()
    target.received_at = moment
    target.reply = payload.reply
    # 仍保留首次发送时的姓名快照；回复仅由该账号本人产生。
    notice = notification(db, row.actor_user_id, f'{parent.order_no} · 收到回复',
        f'{target.user_name}回复：{payload.reply}', row, moment, 'translation_simple_requirement_receipt')
    original = db.get(AppNotification, target.notification_id)
    if original and original.recipient_user_id == actor.id and not original.is_read:
        original.is_read = True
        # 既有通知 read_at 为 UTC 无时区值；收到回复自身使用上方香港时区时间。
        original.read_at = moment.astimezone(timezone.utc).replace(tzinfo=None)
    db.commit()
    publish([notice])
    return detail(db, row.id, actor)


router = APIRouter(prefix='/translation-simple-requirements', tags=['translation_simple_requirements'])
access = require_module_access('projects:read', 'projects:write')


@router.get('/recipients', dependencies=[Depends(access)])
def options(db: Session = Depends(get_db)):
    return recipient_options(db)


@router.get('/projects/{project_id}', dependencies=[Depends(access)])
def history(project_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return list_requirements(db, project_id, skip, limit)


@router.post('/projects/{project_id}', dependencies=[Depends(access)])
def save(project_id: UUID, payload: RequirementCreate, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return create_requirement(db, project_id, payload, actor)


@router.get('/{requirement_id}')
def read(requirement_id: UUID, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return detail(db, requirement_id, actor)


@router.post('/{requirement_id}/received')
def confirm(requirement_id: UUID, payload: RequirementReply, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return receive(db, requirement_id, payload, actor)
