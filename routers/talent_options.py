"""项目人员选择器接口。

该接口只返回项目安排所需的非敏感字段，项目人员无需获得完整人才总库权限。
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from resource_schemas import CapabilityType, TalentIdentityResponse, TalentOptionResponse
from resource_models import ResourcePerson
from resource_service import get_talents, _talent_query
from routers.auth import get_current_user, require_module_access
from talent_privacy import can_view_talent_contacts


router = APIRouter(
    prefix="/talent-options",
    tags=["talent_options"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)

ASSIGNABLE_TALENT_STATUSES = ("active", "standby")


@router.get("/identity", response_model=List[TalentIdentityResponse])
def read_talent_identity_options(
    keyword: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """全库按姓名、别名或编号搜索，只读取选择器需要的字段。"""
    return (
        _talent_query(db, keyword=keyword, include_contact_search=False)
        .with_entities(ResourcePerson.id, ResourcePerson.full_name, ResourcePerson.resource_code)
        .order_by(ResourcePerson.updated_at.desc(), ResourcePerson.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/", response_model=List[TalentOptionResponse])
def read_talent_options(
    capability_type: CapabilityType | None = None,
    keyword: str | None = None,
    limit: int = Query(500, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_talents(
        db,
        limit=limit,
        keyword=keyword,
        statuses=ASSIGNABLE_TALENT_STATUSES if capability_type else None,
        capability_type=capability_type,
        capability_status="active" if capability_type else None,
        include_contact_search=can_view_talent_contacts(db, current_user),
    )
