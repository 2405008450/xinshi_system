"""共享电脑端心跳租约；与聊天 WebSocket、应用进程独立。"""
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import DateTime, Integer, Boolean, Uuid, Index, inspect, select
from sqlalchemy.orm import Mapped, mapped_column
from models import Base
from chat_time import now

LEASE_SECONDS = 120


class ChatDesktopHeartbeat(Base):
    __tablename__ = 'chat_desktop_heartbeat'
    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    client_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index('ix_chat_desktop_heartbeat_seen', 'last_seen_at'),)


def ready(db):
    return inspect(db.connection()).has_table(ChatDesktopHeartbeat.__tablename__)


def record(db, user_id, client_id, sequence, active=True, moment=None):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    if not ready(db):
        return False
    table = ChatDesktopHeartbeat.__table__
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    statement = insert(table).values(user_id=user_id, client_id=client_id, sequence=sequence,
                                    active=active, last_seen_at=moment or now())
    db.execute(statement.on_conflict_do_update(
        index_elements=[table.c.user_id, table.c.client_id],
        set_={key: getattr(statement.excluded, key) for key in ('sequence', 'active', 'last_seen_at')},
        where=statement.excluded.sequence > table.c.sequence))
    db.commit()
    return True


def desktop_presence(db, user_ids, moment=None):
    # 未覆盖/从未上报的用户返回未知，不能把“没有证据”当作离线。
    result = {str(uid): None for uid in user_ids}
    if not user_ids or not ready(db):
        return result
    cutoff = (moment or now()) - timedelta(seconds=LEASE_SECONDS)
    table = ChatDesktopHeartbeat.__table__.c
    observed = db.execute(select(table.user_id).where(table.user_id.in_(user_ids)).distinct()).scalars()
    for uid in observed:
        result[str(uid)] = False
    online = db.execute(select(table.user_id).where(table.user_id.in_(user_ids),
        table.active.is_(True), table.last_seen_at > cutoff).distinct()).scalars()
    for uid in online:
        result[str(uid)] = True
    return result
