"""人才档案编辑差异：只追加历史，与业务数据使用同一事务。"""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import DateTime, Index, JSON, String, Uuid, inspect, select
from sqlalchemy.orm import mapped_column

from business_time import BUSINESS_TIMEZONE, business_iso
from models import Base


class TalentEditLog(Base):
    __tablename__ = 'talent_edit_log'
    __table_args__ = (
        Index('ix_talent_edit_log_person_time', 'person_id', 'created_at', 'id'),
        Index('ix_talent_edit_log_actor_time', 'actor_id', 'created_at'),
    )
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    # 独立保存标识及姓名快照；不级联删除历史，也不因账号删除丢失操作人。
    person_id = mapped_column(Uuid, nullable=False)
    resource_code = mapped_column(String(50))
    person_name = mapped_column(String(255), nullable=False)
    actor_id = mapped_column(Uuid)
    actor_account = mapped_column(String(255), nullable=False)
    actor_name = mapped_column(String(255), nullable=False)
    source = mapped_column(String(40), nullable=False)
    changes = mapped_column(JSON, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False)


IGNORED = {'id', 'person_id', 'created_at', 'updated_at', 'operated_by', 'operator_name',
           'operated_at', 'updated_by', 'revision', 'wechat_accounts_revision', 'idempotency_key',
           'legacy_translator_id'}
RELATIONS = ('capabilities', 'written_profile', 'interpretation_profile', 'annotation_profile',
             'annotation_language_skills', 'career_profile', 'education_experiences',
             'language_skills', 'certificates')


def _columns(row):
    values = {col.key: deepcopy(getattr(row, col.key))
              for col in inspect(type(row)).columns if col.key not in IGNORED}
    return jsonable_encoder({key: business_iso(value) if isinstance(value, datetime) else value
                             for key, value in values.items()})


def snapshot(db, person):
    """只在保存时读取一份档案；集合按业务顺序保存，不把新生成的明细 ID 当作修改。"""
    from talent_resume_profile import TalentResumeProfile
    from talent_settlement import TalentSettlement
    result = _columns(person)
    for key in RELATIONS:
        value = getattr(person, key)
        result[key] = [_columns(item) for item in value] if isinstance(value, list) else _columns(value) if value else None
    resume = db.get(TalentResumeProfile, person.id)
    result['resume_profile'] = deepcopy(resume.data) if resume else {}
    settlement = db.get(TalentSettlement, person.id)
    result['settlement'] = _columns(settlement) if settlement else None
    return result


def begin_edit(db, person, expected_updated_at=None):
    """在现有账号写锁内锁定主档，版本过期时拒绝整表单覆盖。"""
    from resource_models import ResourcePerson
    if not inspect(db.connection()).has_table(TalentEditLog.__tablename__):
        raise HTTPException(503, '编辑日志尚未启用，请先由管理员执行人才编辑日志建表迁移')
    db.execute(select(ResourcePerson.id).where(ResourcePerson.id == person.id).with_for_update())
    db.refresh(person)
    if expected_updated_at is not None and business_iso(person.updated_at) != business_iso(expected_updated_at):
        raise HTTPException(409, '该人才已被其他人修改，请重新打开并核对后保存；当前输入已保留')
    return snapshot(db, person)


def _diff(before, after, prefix=''):
    changes = {}
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(old, dict) and isinstance(new, dict):
            changes.update(_diff(old, new, path))
        elif old != new:
            changes[path] = {'before': old, 'after': new}
    return changes


def finish_edit(db, person, before, actor, source='manual'):
    changes = _diff(before, snapshot(db, person))
    if not changes:
        return
    db.add(TalentEditLog(
        person_id=person.id, resource_code=person.resource_code, person_name=person.full_name,
        actor_id=getattr(actor, 'id', None), actor_account=getattr(actor, 'username', None) or '系统',
        actor_name=(getattr(actor, 'full_name', None) or getattr(actor, 'username', None) or '系统'),
        source=source, changes=changes, created_at=datetime.now(BUSINESS_TIMEZONE),
    ))


def edit_history(db, person_id, *, skip=0, limit=20, contacts_visible=False):
    from resource_models import ResourcePerson
    from talent_privacy import RESOURCE_CONTACT_FIELDS
    if not inspect(db.connection()).has_table(TalentEditLog.__tablename__):
        raise HTTPException(503, '编辑日志尚未启用，请先由管理员执行人才编辑日志建表迁移')
    if not db.get(ResourcePerson, person_id):
        raise HTTPException(404, '人才档案不存在')
    query = db.query(TalentEditLog).filter(TalentEditLog.person_id == person_id)
    rows = query.order_by(TalentEditLog.created_at.desc(), TalentEditLog.id.desc()).offset(skip).limit(limit).all()
    items = []
    sensitive = {*RESOURCE_CONTACT_FIELDS, 'settlement', 'wechat_account', 'wechat_accounts', 'wechat_contact_state'}
    def redact(value):
        if isinstance(value, dict):
            return {key: '******' if key in sensitive else redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value
    for row in rows:
        changes = deepcopy(row.changes)
        if not contacts_visible:
            for key in changes:
                if any(part in sensitive for part in key.split('.')):
                    changes[key] = {'before': '******', 'after': '******'}
                else:
                    changes[key] = redact(changes[key])
        items.append(dict(id=str(row.id), actor_name=row.actor_name, actor_account=row.actor_account,
                          source=row.source, created_at=business_iso(row.created_at), changes=changes))
    return {'total': query.count(), 'items': items}
