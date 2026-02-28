"""
工作流 Pydantic 校验模型
"""
from typing import Optional, Any
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- 请求模型 ---

class WorkflowInitRequest(BaseModel):
    """初始化工作流（创建项目后调用）"""
    translation_project_id: UUID


class SetDifficultyRequest(BaseModel):
    """客户专员设定难度并推进"""
    difficulty: str                          # simple / normal / complex
    file_editable: bool                      # 文件是否可编辑
    next_assignee_id: UUID                   # 下一阶段负责人
    note: Optional[str] = None               # 交接备注
    stage_data: Optional[dict] = None        # 当前阶段填写的进度数据
    operator_id: Optional[UUID] = None       # 操作人（后续可从 Token 解析）


class TransitionRequest(BaseModel):
    """完成当前阶段并推进到下一阶段"""
    next_assignee_id: Optional[UUID] = None  # 下一阶段负责人（最后一步到 completed 可为空）
    note: Optional[str] = None               # 交接备注
    stage_data: Optional[dict] = None        # 当前阶段填写的进度数据
    operator_id: Optional[UUID] = None       # 操作人


class RollbackRequest(BaseModel):
    """打回操作"""
    steps: int = 1                           # 打回几步（1=上一环节，2=上两环节）
    to_start: bool = False                   # 是否打回初始节点
    note: str                                # 打回原因（必填）
    operator_id: Optional[UUID] = None       # 操作人


class StageDataUpdateRequest(BaseModel):
    """更新当前阶段的进度数据（暂存）"""
    stage_data: dict                         # { fieldKey: value }


# --- 响应模型 ---

class WorkflowLogResponse(BaseModel):
    id: UUID
    operator_id: Optional[UUID] = None
    operator_name: Optional[str] = None
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    direction: Optional[str] = None
    description: Optional[str] = None
    note: Optional[str] = None
    next_assignee_id: Optional[UUID] = None
    next_assignee_name: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowStateResponse(BaseModel):
    id: UUID
    translation_project_id: UUID
    difficulty: Optional[str] = None
    file_editable: Optional[bool] = None
    current_stage_key: str
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    project_status: Optional[str] = None
    stage_notes: Optional[dict] = None
    stage_data: Optional[dict] = None
    logs: list[WorkflowLogResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MyTaskItem(BaseModel):
    """待我处理列表中的单条项目"""
    workflow_instance_id: UUID
    translation_project_id: UUID
    order_no: str
    project_name: str
    client_short_name: Optional[str] = None
    current_stage_key: str
    difficulty: Optional[str] = None
    project_status: Optional[str] = None

    class Config:
        from_attributes = True
