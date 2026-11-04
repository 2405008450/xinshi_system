"""母客户、子客户的统一客户类型；笔译项目实时读取并同步修改。"""
from typing import Literal
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, UniqueConstraint, inspect, or_
from sqlalchemy.orm import Mapped, mapped_column
from models import Base, Client, SubClient
from annotation_progress_time import business_now

CustomerType = Literal['个人客户', '企业客户', '行政/事业单位', '社会团体', '国际组织', 'NGO']


class ClientCustomerType(Base):
    __tablename__ = 'client_customer_type'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    client_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey('client.id', ondelete='CASCADE'))
    sub_client_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey('sub_client.id', ondelete='CASCADE'))
    customer_type: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now, onupdate=business_now)
    __table_args__ = (CheckConstraint(
        "customer_type IN ('个人客户','企业客户','行政/事业单位','社会团体','国际组织','NGO')",
        name='ck_client_customer_type'),
        CheckConstraint('(client_id IS NOT NULL AND sub_client_id IS NULL) OR (client_id IS NULL AND sub_client_id IS NOT NULL)', name='ck_customer_type_owner'),
        UniqueConstraint('client_id', name='uq_customer_type_client'),
        UniqueConstraint('sub_client_id', name='uq_customer_type_sub_client'),
    )


def ready(db):
    key = 'translation_project_customer_type_ready'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(ClientCustomerType.__tablename__)
    return db.info[key]


def _values(db, client_ids, sub_client_ids):
    if not ready(db) or (not client_ids and not sub_client_ids):
        return {}
    return {(row.client_id, row.sub_client_id): row.customer_type for row in db.query(ClientCustomerType).filter(or_(
        ClientCustomerType.client_id.in_(list(client_ids)), ClientCustomerType.sub_client_id.in_(list(sub_client_ids)))).all()}


def attach_clients(db, clients=(), sub_clients=()):
    sub_clients = [*sub_clients, *(sub for client in clients for sub in client.sub_clients)]
    values = _values(db, [row.id for row in clients], [row.id for row in sub_clients])
    for client in clients:
        client.customer_type = values.get((client.id, None))
    for sub in sub_clients:
        sub.customer_type = values.get((None, sub.id))


def attach(db, projects):
    values = _values(db, [row.client_id for row in projects if row.client_id], [row.sub_client_id for row in projects if row.sub_client_id]) if projects else {}
    for project in projects:
        project.customer_type = values.get((None, project.sub_client_id) if project.sub_client_id else (project.client_id, None))


def save_client(db, client, value):
    if not ready(db):
        if value is None:
            return
        from fastapi import HTTPException
        raise HTTPException(503, '客户类型存储尚未初始化')
    owners = dict(client_id=client.id if isinstance(client, Client) else None,
                  sub_client_id=client.id if isinstance(client, SubClient) else None)
    row = db.query(ClientCustomerType).filter_by(**owners).first()
    previous = row.customer_type if row else None
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(ClientCustomerType(**owners, customer_type=value))
    else:
        row.customer_type = value
    if previous != value:
        client.updated_at = business_now().replace(tzinfo=None)
    client.customer_type = value


def save(db, project, value):
    client = db.get(SubClient, project.sub_client_id) if project.sub_client_id else db.get(Client, project.client_id) if project.client_id else None
    if client is None:
        if value is not None:
            from fastapi import HTTPException
            raise HTTPException(422, '请先选择客户，再填写客户类型')
        return
    save_client(db, client, value)
    project.customer_type = value
