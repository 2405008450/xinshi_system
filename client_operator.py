"""客户首次录入操作人的独立留存；历史回溯保留咨询来源，不代表字段修改历史。"""
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid, inspect
from sqlalchemy.orm import Mapped, mapped_column

from models import Base
from annotation_progress_time import business_now


class ClientOperator(Base):
    __tablename__ = 'client_operator'
    client_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), primary_key=True)
    operator_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    consultation_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey('consultation.id', ondelete='SET NULL'))
    consultation_code: Mapped[str | None] = mapped_column(String(50))
    recorded_at = mapped_column(DateTime(timezone=True), nullable=False, default=business_now)


def ready(db):
    if 'client_operator_ready' not in db.info:
        db.info['client_operator_ready'] = inspect(db.connection()).has_table('client_operator')
    return db.info['client_operator_ready']


def record(db, client_id, actor, source, consultation=None):
    """只在实际创建客户的事务内写入，后续编辑不覆盖首次录入人。"""
    if actor is None or not ready(db):
        return
    db.add(ClientOperator(
        client_id=client_id, operator_user_id=actor.id,
        operator_name=actor.full_name or actor.username, source=source,
        consultation_id=consultation.id if consultation else None,
        consultation_code=consultation.consultation_code if consultation else None,
    ))


def attach_clients(db, clients):
    values = {}
    if clients and ready(db):
        values = {row.client_id: row for row in db.query(ClientOperator).filter(
            ClientOperator.client_id.in_([client.id for client in clients])).all()}
    for client in clients:
        row = values.get(client.id)
        client.operator_name = row.operator_name if row else None
        client.operator_source = row.source if row else None
        client.operator_consultation_code = row.consultation_code if row else None
