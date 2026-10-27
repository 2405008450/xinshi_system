"""路径窗口的局部编辑与逐字段修改记录，不覆盖人才的其他资料。"""
from uuid import uuid4
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import mapped_column

from models import Base
from resource_models import ResourcePerson
from business_time import business_now, business_iso
from talent_privacy import RESOURCE_CONTACT_FIELDS

EditField = Literal['resource_code', 'full_name', 'ancestral_home', 'native_place', 'residence_address', 'resume_path',
                    'primary_phone', 'secondary_phone', 'primary_email', 'secondary_email', 'wechat', 'whatsapp',
                    'skype', 'line', 'other_contact', 'contact_info']


class TalentPathChange(Base):
    __tablename__ = 'talent_path_change'
    __table_args__ = (Index('ix_talent_path_change_person_time', 'person_id', 'created_at', 'id'),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    person_id = mapped_column(Uuid, ForeignKey('resource_person.id', ondelete='CASCADE'), nullable=False)
    actor_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    actor_name = mapped_column(String(255), nullable=False)
    changes = mapped_column(JSON, nullable=False)
    created_at = mapped_column(DateTime, nullable=False, default=business_now)


class TalentPathEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    changes: dict[EditField, str | None] = Field(min_length=1, max_length=16)
    expected_values: dict[EditField, str | None] = Field(max_length=16)

    @model_validator(mode='after')
    def validate_changes(self):
        if self.changes.keys() != self.expected_values.keys():
            raise ValueError('修改字段与原值字段必须一致')
        for key, value in self.changes.items():
            if value is not None:
                value = value.strip()
            if key in {'resource_code', 'full_name'} and not value:
                raise ValueError('人才编号和姓名不能为空')
            limit = getattr(ResourcePerson.__table__.c[key].type, 'length', None) or 20000
            if value is not None and len(value) > limit:
                raise ValueError(f'{key} 最多允许 {limit} 个字符')
            self.changes[key] = value.lower() if value and key.endswith('_email') else value or None
        return self


def save_path_fields(db, person_id, payload, actor, *, contacts_visible):
    from resource_service import (_record_talent_operation, _sync_legacy_translator, assert_writable,
                                  find_duplicate_talents, lock_account_writes)
    lock_account_writes(db)
    person = db.query(ResourcePerson).filter(ResourcePerson.id == person_id).with_for_update().first()
    if not person:
        raise HTTPException(404, '人才档案不存在')
    assert_writable(db, person)
    if not contacts_visible and set(payload.changes) & set(RESOURCE_CONTACT_FIELDS):
        raise HTTPException(403, '当前账号不能修改联系方式')
    changes = {}
    for key, value in payload.changes.items():
        original = getattr(person, key)
        if (original or '') != (payload.expected_values[key] or ''):
            raise HTTPException(409, '该字段已被其他人修改，请重新加载后核对；当前输入已保留')
        if (original or '') != (value or ''):
            changes[key] = {'before': original, 'after': value}
    if not changes:
        return person
    code = payload.changes.get('resource_code')
    if code and db.query(ResourcePerson.id).filter(ResourcePerson.resource_code == code, ResourcePerson.id != person_id).first():
        raise HTTPException(409, '人才编号已被使用，请填写其他编号')
    if {'primary_phone', 'primary_email'} & changes.keys():
        matches = find_duplicate_talents(db, phone=payload.changes.get('primary_phone'), email=payload.changes.get('primary_email'), exclude_id=person_id)
        if matches:
            raise HTTPException(409, '电话或邮箱与其他人才重复，请核实后再修改')
    for key, change in changes.items():
        setattr(person, key, change['after'])
    _record_talent_operation(person, actor)
    person.updated_at = business_now()
    db.add(TalentPathChange(person_id=person.id, actor_id=actor.id, actor_name=actor.full_name or actor.username,
                            changes=changes, created_at=business_now()))
    db.flush()
    _sync_legacy_translator(db, person)
    db.flush()
    return person


def path_history(db, person_id, *, skip, limit, contacts_visible):
    if not db.get(ResourcePerson, person_id):
        raise HTTPException(404, '人才档案不存在')
    query = db.query(TalentPathChange).filter_by(person_id=person_id)
    rows = query.order_by(TalentPathChange.created_at.desc(), TalentPathChange.id.desc()).offset(skip).limit(limit).all()
    items = []
    for row in rows:
        changes = {key: dict(value) for key, value in row.changes.items()}
        if not contacts_visible:
            for key, value in changes.items():
                if key in RESOURCE_CONTACT_FIELDS:
                    changes[key] = {side: '******' if text else None for side, text in value.items()}
        items.append({'id': str(row.id), 'actor_name': row.actor_name, 'created_at': business_iso(row.created_at), 'changes': changes})
    return {'items': items, 'total': query.count()}
