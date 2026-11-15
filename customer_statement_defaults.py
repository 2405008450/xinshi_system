"""客户对账单默认值：只作为未人工设置项目的读取规则，不批量覆盖项目。"""
from sqlalchemy import Boolean, Column,DateTime,ForeignKey,String,Uuid,CheckConstraint, inspect
from fastapi import HTTPException
from models import Base,SubClient
from annotation_progress_time import business_now


class CustomerStatementDefault(Base):
    __tablename__='customer_statement_default'
    __table_args__=(CheckConstraint("choice IN ('required','not_required','unknown')",name='ck_customer_statement_default_choice'),)
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
    choice=Column(String(20),nullable=False,default='unknown')
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class CustomerTranslationFinanceDefault(Base):
    __tablename__ = 'customer_translation_finance_default'
    __table_args__ = (CheckConstraint("payment_method IN ('individual','statement','monthly')"),)
    client_id = Column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), primary_key=True)
    payment_method = Column(String(20))
    quotation_required = Column(Boolean)
    invoice_required = Column(Boolean)


def finance_defaults_ready(db):
    key = 'customer_translation_finance_default_ready'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(CustomerTranslationFinanceDefault.__tablename__)
    return db.info[key]


def write_finance_defaults(db, client_id, values):
    if not finance_defaults_ready(db):
        raise HTTPException(503, '客户笔译财务设置尚未初始化')
    row = db.get(CustomerTranslationFinanceDefault, client_id, populate_existing=True)
    if row is None:
        if all(value is None for value in values.values()):
            return
        row = CustomerTranslationFinanceDefault(client_id=client_id)
        db.add(row)
    for field, value in values.items():
        setattr(row, field, value)


def defaults_for_projects(db,projects):
    sub_ids={row.sub_client_id for row in projects if row.sub_client_id and not row.client_id}
    parents=dict(db.query(SubClient.id,SubClient.parent_client_id).filter(SubClient.id.in_(sub_ids)).all()) if sub_ids else {}
    owners={row.id:row.client_id or parents.get(row.sub_client_id) for row in projects}
    client_ids = {key for key in owners.values() if key}
    choices=dict(db.query(CustomerStatementDefault.client_id,CustomerStatementDefault.choice).filter(CustomerStatementDefault.client_id.in_(client_ids)).all())
    finance = {row.client_id: row for row in db.query(CustomerTranslationFinanceDefault).filter(
        CustomerTranslationFinanceDefault.client_id.in_(client_ids))} if client_ids and finance_defaults_ready(db) else {}
    return {key:(choices.get(owner,'unknown'), finance.get(owner)) for key,owner in owners.items()}
