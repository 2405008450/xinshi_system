"""项目操作审计只读接口结构。"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectOperationAuditResponse(BaseModel):
    id: UUID
    project_type: str
    project_id: UUID
    order_no: str
    project_name: Optional[str] = None
    operation_type: str
    operation_source: str
    actor_user_id: Optional[UUID] = None
    actor_username_snapshot: Optional[str] = None
    actor_name_snapshot: Optional[str] = None
    project_snapshot: dict[str, Any]
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectOperationAuditListResponse(BaseModel):
    items: list[ProjectOperationAuditResponse]
    total: int
