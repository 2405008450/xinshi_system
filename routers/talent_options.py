"""项目人员选择器接口。

该接口只返回项目安排所需的非敏感字段，项目人员无需获得完整人才总库权限。
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from resource_schemas import CapabilityType, TalentOptionResponse
from resource_service import get_talents
from routers.auth import require_module_access


router = APIRouter(
    prefix="/talent-options",
    tags=["talent_options"],
    dependencies=[Depends(require_module_access("projects:read", "projects:write"))],
)

ASSIGNABLE_TALENT_STATUSES = ("active", "standby")


@router.get("/", response_model=List[TalentOptionResponse])
def read_talent_options(
    capability_type: CapabilityType,
    keyword: str | None = None,
    limit: int = Query(500, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return get_talents(
        db,
        limit=limit,
        keyword=keyword,
        statuses=ASSIGNABLE_TALENT_STATUSES,
        capability_type=capability_type,
        capability_status="active",
    )
