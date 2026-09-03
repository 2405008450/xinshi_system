"""项目操作审计只读接口。"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from project_audit_schemas import ProjectOperationAuditListResponse
from project_audit_service import list_project_operation_audits
from routers.auth import require_permission


router = APIRouter(
    prefix="/project-operation-audits",
    tags=["project_operation_audits"],
    dependencies=[Depends(require_permission("system:audit:read"))],
)


@router.get("/", response_model=ProjectOperationAuditListResponse)
def read_project_operation_audits(
    keyword: Optional[str] = None,
    project_type: Optional[Literal["translation", "interpretation", "annotation", "recruitment"]] = None,
    operation_type: Optional[Literal["create", "delete"]] = None,
    operator_keyword: Optional[str] = None,
    occurred_from: Optional[datetime] = None,
    occurred_to: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = list_project_operation_audits(
        db,
        keyword=keyword,
        project_type=project_type,
        operation_type=operation_type,
        operator_keyword=operator_keyword,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        skip=skip,
        limit=limit,
    )
    return {"items": items, "total": total}
