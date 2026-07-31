"""
工作流 Pydantic 校验模型
"""
from datetime import datetime
from uuid import UUID
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- 请求模型 ---

class WorkflowInitRequest(BaseModel):
    """初始化工作流（创建项目后调用）"""

    translation_project_id: UUID


class SetDifficultyRequest(BaseModel):
    """客户专员设定难度并推进"""

    difficulty: str                          # simple / normal / complex
    file_editable: bool                      # 文件是否可编辑
    next_assignee_id: Optional[UUID] = None  # 下一阶段指定个人（与 group_assign_role 二选一）
    group_assign_role: Optional[str] = None  # 同组指派时的目标角色名
    note: Optional[str] = None               # 交接备注
    stage_data: Optional[dict] = None        # 当前阶段填写的进度数据
    operator_id: Optional[UUID] = None       # 操作人（后续可从 Token 解析）


class TransitionRequest(BaseModel):
    """完成当前阶段并推进到下一阶段"""

    next_assignee_id: Optional[UUID] = None  # 下一阶段指定个人（与 group_assign_role 二选一）
    group_assign_role: Optional[str] = None  # 同组指派时的目标角色名
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

class WorkflowStageResponse(BaseModel):
    key: str
    title: str
    role: str


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
    translation_project_id: Optional[UUID] = None
    sub_order_id: Optional[UUID] = None
    sub_order_no: Optional[str] = None       # 子订单号（仅子订单工作流时有值）
    difficulty: Optional[str] = None
    file_editable: Optional[bool] = None
    current_stage_key: str
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    group_assign_role: Optional[str] = None  # 同组指派时的目标角色名
    project_status: Optional[str] = None
    stage_notes: Optional[dict] = None
    stage_data: Optional[dict] = None
    effective_stages: list[WorkflowStageResponse] = []
    logs: list[WorkflowLogResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowConfigResponse(BaseModel):
    all_stages: list[WorkflowStageResponse] = []


class MyTaskItem(BaseModel):
    """待我处理列表中的单条项目（母订单或子订单）"""

    workflow_instance_id: UUID
    translation_project_id: Optional[UUID] = None
    sub_order_id: Optional[UUID] = None
    order_no: str
    project_name: str
    sub_project_name: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    current_stage_key: str
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    assignment_type: str = 'direct'
    difficulty: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    language_pair: Optional[str] = None
    entity_type: Optional[str] = 'project'   # 'project' | 'suborder'

    class Config:
        from_attributes = True


class ActiveProjectItem(BaseModel):
    """工作台中的进行中母订单或子订单。"""

    workflow_instance_id: UUID
    entity_type: Literal['project', 'suborder']
    translation_project_id: UUID
    sub_order_id: Optional[UUID] = None
    order_no: str
    project_name: str
    sub_project_name: Optional[str] = None
    client_short_name: Optional[str] = None
    current_stage_key: str
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    group_assign_role: Optional[str] = None
    project_manager_id: Optional[UUID] = None
    project_manager_name: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    language_pair: Optional[str] = None
    file_type_secondary: Optional[str] = None
    priority: Optional[str] = None
    word_count: Optional[int] = None
    expected_translator_stats_method: Optional[str] = None
    expected_translator_word_count: Optional[int] = None
    network_file_path: Optional[str] = None
    updated_at: Optional[datetime] = None


class ActiveProjectListResponse(BaseModel):
    items: list[ActiveProjectItem] = Field(default_factory=list)
    total: int = 0
    overdue_total: int = 0
    due_soon_total: int = 0


class ManagedProjectItem(BaseModel):
    """项目经理在管理层负责的母项目。"""

    translation_project_id: UUID
    order_no: str
    project_name: str
    client_short_name: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    project_manager_id: Optional[UUID] = None
    project_manager_name: Optional[str] = None


class ProjectManagerHandoverCreate(BaseModel):
    translation_project_ids: list[UUID] = Field(min_length=1, max_length=100)
    target_manager_id: UUID
    reason: Optional[str] = Field(default=None, max_length=500)
    note: Optional[str] = Field(default=None, max_length=5000)


class ProjectManagerHandoverDecisionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


class ProjectManagerHandoverResponse(BaseModel):
    id: UUID
    requester_id: Optional[UUID] = None
    requester_name: Optional[str] = None
    target_manager_id: UUID
    target_manager_name: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None
    status: str
    decision_note: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    projects: list[ManagedProjectItem] = Field(default_factory=list)


class WorkflowTransferContent(BaseModel):
    content: str = Field(default='', max_length=10000)
    content_json: Optional[dict] = None
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=9)


class WorkflowHandoverRequest(WorkflowTransferContent):
    workflow_instance_ids: list[UUID] = Field(min_length=1, max_length=100)
    target_user_id: UUID
    handover_type: Literal['daily_shift', 'weekend_holiday', 'leave_time_off', 'other']
    reason_detail: Optional[str] = Field(default=None, max_length=500)


class WorkflowClaimRequest(WorkflowTransferContent):
    workflow_instance_ids: list[UUID] = Field(min_length=1, max_length=100)
    expected_assignee_ids: dict[UUID, UUID]


class WorkflowTransferUser(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None


class WorkflowEligibleUsersRequest(BaseModel):
    workflow_instance_ids: list[UUID] = Field(min_length=1, max_length=100)


class WorkflowTransferResult(BaseModel):
    action: str
    transferred_count: int
    workflow_instance_ids: list[UUID]


class WorkflowHandoverAttachmentResponse(BaseModel):
    id: UUID
    original_name: str
    content_type: str
    file_size: int


class WorkflowHandoverRequestResponse(BaseModel):
    id: UUID
    requester_id: Optional[UUID] = None
    requester_name: Optional[str] = None
    target_user_id: UUID
    target_user_name: Optional[str] = None
    handover_type: str
    reason_detail: Optional[str] = None
    content: str
    content_json: Optional[dict] = None
    status: str
    decision_note: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    tasks: list[MyTaskItem] = Field(default_factory=list)
    attachments: list[WorkflowHandoverAttachmentResponse] = Field(default_factory=list)


class WorkflowHandoverDecisionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)
