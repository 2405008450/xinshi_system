"""笔译子客户的单据与计费设置。"""
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Uuid, inspect

from annotation_progress_time import business_now
from models import Base, SubClient


class SubClientFinancePreference(Base):
    __tablename__ = 'sub_client_finance_preference'
    __table_args__ = (CheckConstraint("tax_mode IN ('incl_tax','excl_tax')", name='ck_sub_client_finance_tax_mode'),)

    sub_client_id = Column(Uuid, ForeignKey('sub_client.id', ondelete='CASCADE'), primary_key=True)
    quotation_required = Column(Boolean)
    statement_required = Column(Boolean)
    tax_mode = Column(String(16))
    revision = Column(Integer, nullable=False, default=0)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class PreferenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int
    quotation_required: bool | None = None
    statement_required: bool | None = None
    tax_mode: Literal['incl_tax','excl_tax'] | None = None


def ready(db):
    if 'sub_client_finance_ready' not in db.info:
        db.info['sub_client_finance_ready'] = inspect(db.connection()).has_table(SubClientFinancePreference.__tablename__)
    return db.info['sub_client_finance_ready']


def load(db, sub_client_ids):
    if not sub_client_ids or not ready(db):
        return {}
    rows = db.info.setdefault('sub_client_finance_preferences', {})
    missing = set(sub_client_ids) - rows.keys()
    if missing:
        rows.update(dict.fromkeys(missing))
        rows.update((row.sub_client_id, row) for row in db.query(SubClientFinancePreference).filter(
            SubClientFinancePreference.sub_client_id.in_(missing)))
    return rows


def values(sub_client, row):
    return {
        'sub_client_id': str(sub_client.id), 'client_id': str(sub_client.parent_client_id),
        'sub_client_code': sub_client.sub_client_code, 'sub_client_name': sub_client.client_short_name,
        'quotation_required': row.quotation_required if row else None,
        'statement_required': row.statement_required if row else None,
        'tax_mode': row.tax_mode if row else None, 'revision': row.revision if row else 0,
    }


def read(db, sub_client_id: UUID):
    sub_client = db.get(SubClient, sub_client_id)
    if sub_client is None:
        raise HTTPException(404, '子客户不存在')
    return values(sub_client, load(db, {sub_client_id}).get(sub_client_id))


def write(db, sub_client_id: UUID, changes, actor_id: UUID, *, revision=None):
    if not ready(db):
        raise HTTPException(503, '子客户财务设置尚未初始化')
    sub_client = db.query(SubClient).filter_by(id=sub_client_id).with_for_update().first()
    if sub_client is None:
        raise HTTPException(404, '子客户不存在')
    row = db.get(SubClientFinancePreference, sub_client_id, populate_existing=True)
    if revision is not None and revision != (row.revision if row else 0):
        raise HTTPException(409, '子客户财务设置已更新，请刷新后再修改')
    if row is None:
        row = SubClientFinancePreference(sub_client_id=sub_client_id, revision=0)
        db.add(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.revision += 1
    row.updated_by, row.updated_at = actor_id, business_now()
    db.info.setdefault('sub_client_finance_preferences', {})[sub_client_id] = row
    return values(sub_client, row)
