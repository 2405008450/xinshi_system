"""标注项目负责人变更日志接口结构。"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnnotationManagerChangeLogResponse(BaseModel):
    id: UUID
    source_request_id: Optional[UUID] = None
    project_id: UUID
    order_no: str
    project_name: Optional[str] = None
    manager_role: str
    previous_manager_id: Optional[UUID] = None
    previous_manager_name: Optional[str] = None
    new_manager_id: Optional[UUID] = None
    new_manager_name: Optional[str] = None
    change_mode: str
    reason: Optional[str] = None
    actor_user_id: Optional[UUID] = None
    actor_username_snapshot: Optional[str] = None
    actor_name_snapshot: Optional[str] = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnnotationManagerChangeLogListResponse(BaseModel):
    items: list[AnnotationManagerChangeLogResponse]
    total: int
