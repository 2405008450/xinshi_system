"""客户名称修改及删除留痕，与业务变更在同一事务中保存。"""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query
from sqlalchemy import Column, DateTime, Index, JSON, String, Uuid, or_
from models import Base, AppUser
from annotation_progress_time import business_now, business_datetime
from database import get_db
from routers.auth import get_current_user, require_permission
from search_matching import keyword_or, keyword_ilike


class ClientNameHistory(Base):
    __tablename__ = 'client_name_history'
    __table_args__ = (Index('ix_client_name_history_owner_time', 'client_id', 'occurred_at'),)
    id = Column(Uuid, primary_key=True, default=uuid4)
    client_id = Column(Uuid, nullable=False)
    parent_client_id = Column(Uuid)
    client_code = Column(String(100))
    operation = Column(String(20), nullable=False)
    before_names = Column(JSON, nullable=False)
    after_names = Column(JSON, nullable=False)
    actor_id = Column(Uuid)
    actor_name = Column(String(255), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


NAME_FIELDS = ('client_name', 'client_short_name', 'english_name', 'english_short_name')


def names(owner):
    return {field: getattr(owner, field, None) for field in NAME_FIELDS}


def record(db, owner, before, *, actor_id=None, deleted=False):
    after = {} if deleted else names(owner)
    if before == after:
        return
    actor = db.get(AppUser, actor_id) if actor_id else None
    db.add(ClientNameHistory(
        client_id=owner.id, parent_client_id=getattr(owner, 'parent_client_id', None),
        client_code=getattr(owner, 'sub_client_code', None) or getattr(owner, 'client_code', None),
        operation='delete' if deleted else 'rename', before_names=before, after_names=after,
        actor_id=actor_id, actor_name=(actor.full_name or actor.username) if actor else '系统',
        occurred_at=business_now(),
    ))


router = APIRouter(prefix='/name-history', tags=['客户名称记录'],
                   dependencies=[Depends(require_permission('clients:read'))])


@router.get('')
def read_history(client_id: UUID | None = None, keyword: str = Query('', max_length=200),
                 page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                 db=Depends(get_db), user=Depends(get_current_user)):
    query = db.query(ClientNameHistory)
    if client_id:
        query = query.filter(or_(ClientNameHistory.client_id == client_id,
                                 ClientNameHistory.parent_client_id == client_id))
    if keyword.strip():
        query = query.filter(keyword_or(lambda part: or_(
            keyword_ilike(ClientNameHistory.client_code, part),
            *(keyword_ilike(snapshot[field].as_string(), part)
              for snapshot in (ClientNameHistory.before_names, ClientNameHistory.after_names)
              for field in NAME_FIELDS),
        ), '%' + keyword.strip() + '%'))
    total = query.count()
    rows = query.order_by(ClientNameHistory.occurred_at.desc(), ClientNameHistory.id.desc()).offset(
        (page - 1) * page_size).limit(page_size).all()
    return {'total': total, 'items': [
        dict(id=str(row.id), client_code=row.client_code, sub_client=bool(row.parent_client_id),
             operation=row.operation, before=row.before_names, after=row.after_names,
             actor_name=row.actor_name, occurred_at=business_datetime(row.occurred_at).isoformat())
        for row in rows]}
