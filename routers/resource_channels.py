"""渠道资料接口，继承资源开拓读取权限。"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser
from resource_development_models import DevelopmentChannelMember
from routers.auth import get_current_user, require_any_permission
from resource_channel_schemas import ChannelWrite, ChannelDescriptionWrite
from resource_channel_service import list_channels, read_channel, save_channel, save_description

router = APIRouter(prefix="/channels")
write = Depends(require_any_permission("talents:write", "translators:write", "resource_development:delegate"))


@router.get("")
def read_list(keyword: str | None = Query(None, max_length=255), category: Literal["national", "local", "international"] | None = None,
              maintainer_ids: list[UUID] | None = Query(None, max_length=500), user_ids: list[UUID] | None = Query(None, max_length=500),
              skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return list_channels(db, keyword, category, maintainer_ids, user_ids, skip, limit)


@router.get("/people")
def read_people(db: Session = Depends(get_db)):
    # 筛选可检索仍被渠道引用的停用人员；新增分工继续只允许在职人员。
    rows = db.query(AppUser).filter(or_(AppUser.is_active.is_(True), AppUser.id.in_(db.query(DevelopmentChannelMember.user_id)))).order_by(AppUser.full_name, AppUser.username).all()
    return [{"id": str(person.id), "name": person.full_name or person.username, "is_active": person.is_active} for person in rows]


@router.get("/{platform_id}")
def read_detail(platform_id: UUID, db: Session = Depends(get_db)):
    return read_channel(db, platform_id)


def commit_channel(db, user, payload, platform_id=None):
    try:
        result = save_channel(db, user, payload, platform_id)
        db.commit()
        return result
    except IntegrityError as error:
        db.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint in {"uq_resource_channel_name_normalized", "resource_development_option_kind_name_key"}:
            raise HTTPException(409, "已有同名渠道，请使用现有渠道或修改名称") from error
        raise


@router.post("", dependencies=[write])
def create(payload: ChannelWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return commit_channel(db, user, payload)


@router.put("/{platform_id}", dependencies=[write])
def update(platform_id: UUID, payload: ChannelWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return commit_channel(db, user, payload, platform_id)


@router.put("/{platform_id}/description", dependencies=[write])
def update_description(platform_id: UUID, payload: ChannelDescriptionWrite, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = save_description(db, user, platform_id, payload.description, payload.revision)
    db.commit()
    return result
