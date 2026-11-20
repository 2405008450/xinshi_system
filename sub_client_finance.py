"""笔译子客户的单据与计费设置。"""
from copy import deepcopy
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Uuid, inspect

from annotation_progress_time import business_now
from models import Base, SubClient
from translation_document_requirements import DocumentNotes


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
    statement_subject_key: Literal['guangzhou','shenzhen','shanghai'] | None = None
    model_config = ConfigDict(extra='forbid')
    revision: int
    quotation_required: bool | None = None
    statement_required: bool | None = None
    invoice_required: bool | None = None
    document_notes: DocumentNotes | None = None
    tax_mode: Literal['incl_tax','excl_tax'] | None = None


PERIOD_PARTIES = 'sub_client_settlement_parties'
DOCUMENT_SETTINGS = 'sub_client_document_settings'


def document_settings(payload, sub_client_id):
    return (payload or {}).get(DOCUMENT_SETTINGS, {}).get(str(sub_client_id), {})


def settings_payload(db, client_id):
    from customer_statement_workspace import StatementWorkspace

    cached = db.info.get('settlement_workspace_payloads', {})
    if client_id in cached:
        return cached[client_id]
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return {}
    row = db.get(StatementWorkspace, client_id)
    return row.payload if row else {}


def write_preferences(db, sub_client_id, changes, user, revision):
    from customer_statement_workspace import workspace, empty_payload, save

    extra = {key: changes.pop(key) for key in ('invoice_required', 'document_notes', 'statement_subject_key') if key in changes}
    if not extra:
        return write(db, sub_client_id, changes, user.id, revision=revision)
    child = db.get(SubClient, sub_client_id)
    if child is None:
        raise HTTPException(404, '子客户不存在')
    client_id = child.parent_client_id
    workspace_row = workspace(db, client_id, lock=True)
    before = deepcopy(workspace_row.payload if workspace_row else empty_payload())
    previous = document_settings(before, sub_client_id)
    updated = {**previous, **extra}
    result = write(db, sub_client_id, changes, user.id, revision=revision)
    payload = deepcopy(before)
    payload.setdefault(DOCUMENT_SETTINGS, {})[str(sub_client_id)] = updated
    if 'statement_subject_key' in extra:
        from statement_subject_sync import apply
        apply(db,payload,extra['statement_subject_key'],sub_client_id)
    save(db, user, client_id, workspace_row, before, payload, '修改子客户单据设置', {
        'sub_client_id': str(sub_client_id), 'before': previous, 'after': updated,
    }, commit=False)
    db.info.setdefault('settlement_workspace_payloads', {})[client_id] = payload
    return {**result, **updated}


class PeriodPartyWrite(BaseModel):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    period: int | None = Field(default=None, ge=1)
    party: Literal['client', 'sub_client']
    expected_party: Literal['client', 'sub_client']


def period_party(payload, sub_client_id, month, period):
    if not isinstance(period, (int, type(None))):
        return 'sub_client'
    return (payload or {}).get(PERIOD_PARTIES, {}).get(str(sub_client_id), {}).get(
        f'{month}:{period or 0}', 'sub_client')


def read_period_party(db, sub_client, month, period):
    from customer_statement_workspace import StatementWorkspace

    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return 'sub_client'
    row = db.get(StatementWorkspace, sub_client.parent_client_id)
    return period_party(row.payload if row else None, sub_client.id, month, period)


def write_period_party(db, sub_client_id, data, user):
    from customer_statement_workspace import workspace, empty_payload, save

    sub_client = db.get(SubClient, sub_client_id)
    if sub_client is None:
        raise HTTPException(404, '子客户不存在')
    client_id = sub_client.parent_client_id
    row = workspace(db, client_id, lock=True)
    before = deepcopy(row.payload if row else empty_payload())
    current = period_party(before, sub_client_id, data.month, data.period)
    if current != data.expected_party:
        raise HTTPException(409, '该账期的结算对象已修改，请刷新后重试')
    if data.party == current:
        return {'party': current, 'client_id': str(client_id)}
    payload = deepcopy(before)
    parties = payload.setdefault(PERIOD_PARTIES, {})
    child_periods = parties.setdefault(str(sub_client_id), {})
    key = f'{data.month}:{data.period or 0}'
    if data.party == 'client':
        child_periods[key] = 'client'
    else:
        child_periods.pop(key, None)
        if not child_periods:
            parties.pop(str(sub_client_id))
    save(db, user, client_id, row, before, payload, '调整子客户账期结算对象', {
        'sub_client_id': str(sub_client_id), 'month': data.month, 'period_number': data.period,
        'before': current, 'after': data.party,
    })
    return {'party': data.party, 'client_id': str(client_id)}


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
    preferences = values(sub_client, load(db, {sub_client_id}).get(sub_client_id))
    from statement_subject_sync import read as read_subject
    return {**preferences, **document_settings(settings_payload(db, sub_client.parent_client_id), sub_client_id),
            'statement_subject_key':read_subject(db,sub_client.parent_client_id,sub_client_id)}


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
