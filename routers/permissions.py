from fastapi import APIRouter, Depends

from permission_registry import PERMISSION_GROUPS
from routers.auth import require_permission
from schemas import PermissionGroup

router = APIRouter(
    prefix="/permissions",
    tags=["permissions"],
    dependencies=[Depends(require_permission("system:roles:read"))],
)


@router.get("/catalog", response_model=list[PermissionGroup])
def get_permission_catalog():
    return PERMISSION_GROUPS
