"""项目操作审计只读接口结构。"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator
from annotation_progress_time import business_datetime


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
    previous_order_no: Optional[str] = None
    change_reason: Optional[str] = None
    project_snapshot: dict[str, Any]
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def normalize_audit_time(cls, value):
        return business_datetime(value)

    model_config = ConfigDict(from_attributes=True)


class ProjectOperationAuditListResponse(BaseModel):
    items: list[ProjectOperationAuditResponse]
    total: int
