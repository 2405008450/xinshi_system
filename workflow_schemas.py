"""
工作流 Pydantic 校验模型
"""
from datetime import datetime
from uuid import UUID
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from schemas import ProjectRoleAssignmentResponse


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
    role_code: str


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
    current_stage_role_code: Optional[str] = None
    current_stage_role_name: Optional[str] = None
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    group_assign_role: Optional[str] = None  # 同组指派时的目标角色名
    project_status: Optional[str] = None
    stage_notes: Optional[dict] = None
    stage_data: Optional[dict] = None
    effective_stages: list[WorkflowStageResponse] = []
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    logs: list[WorkflowLogResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowConfigResponse(BaseModel):
    all_stages: list[WorkflowStageResponse] = []


class MyTaskItem(BaseModel):
    """待我处理列表中的单条项目（母订单或子订单）"""

    workflow_instance_id: Optional[UUID] = None
    project_responsibility_id: Optional[UUID] = None
    source_kind: str = 'translation_workflow'
    project_type: str = 'translation'
    project_type_label: str = '笔译项目'
    project_id: Optional[UUID] = None
    detail_route_name: Optional[str] = None
    translation_project_id: Optional[UUID] = None
    sub_order_id: Optional[UUID] = None
    order_no: str
    project_name: str
    task_type: Optional[str] = None
    task_kind: str = 'workflow'
    sub_project_name: Optional[str] = None
    client_name: Optional[str] = None
    client_short_name: Optional[str] = None
    current_stage_key: str
    current_stage_role_code: Optional[str] = None
    current_stage_role_name: Optional[str] = None
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    group_assign_role: Optional[str] = None
    assignment_type: str = 'direct'
    difficulty: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    language_pair: Optional[str] = None
    entity_type: Optional[str] = 'project'   # 'project' | 'suborder'
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    transfer_mode: Optional[Literal['permanent', 'delegation']] = None
    delegation_id: Optional[UUID] = None
    original_assignee_id: Optional[UUID] = None
    original_assignee_name: Optional[str] = None
    delegation_end_at: Optional[datetime] = None
    delegation_overdue: bool = False

    class Config:
        from_attributes = True


class ManagedProjectItem(BaseModel):
    """项目经理在管理层负责的母项目。"""

    translation_project_id: Optional[UUID] = None
    project_responsibility_id: Optional[UUID] = None
    source_kind: str = 'translation_project'
    project_type: str = 'translation'
    project_type_label: str = '笔译项目'
    project_id: Optional[UUID] = None
    detail_route_name: Optional[str] = None
    order_no: str
    project_name: str
    task_type: Optional[str] = None
    client_short_name: Optional[str] = None
    project_status: Optional[str] = None
    difficulty: Optional[str] = None
    language_pair: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    current_assignee_id: Optional[UUID] = None
    current_assignee_name: Optional[str] = None
    group_assign_role: Optional[str] = None
    current_stage_role_code: Optional[str] = None
    current_stage_role_name: Optional[str] = None
    role_assignments: list[ProjectRoleAssignmentResponse] = Field(default_factory=list)
    project_manager_id: Optional[UUID] = None
    project_manager_name: Optional[str] = None


class ProjectReference(BaseModel):
    project_type: Literal['translation', 'interpretation', 'annotation', 'recruitment']
    project_id: UUID


class WorkItemReference(BaseModel):
    source_kind: Literal['translation_workflow', 'project_responsibility']
    source_id: UUID


class ProjectManagerHandoverCreate(BaseModel):
    translation_project_ids: list[UUID] = Field(default_factory=list, max_length=100)
    project_refs: list[ProjectReference] = Field(default_factory=list, max_length=100)
    target_manager_id: UUID
    reason: Optional[str] = Field(default=None, max_length=500)
    note: Optional[str] = Field(default=None, max_length=5000)


class ProjectManagerClaimRequest(BaseModel):
    translation_project_ids: list[UUID] = Field(default_factory=list, max_length=100)
    project_refs: list[ProjectReference] = Field(default_factory=list, max_length=100)


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
    workflow_instance_ids: list[UUID] = Field(default_factory=list, max_length=100)
    work_item_refs: list[WorkItemReference] = Field(default_factory=list, max_length=100)
    target_user_id: UUID
    handover_type: Literal['daily_shift', 'weekend_holiday', 'leave_time_off', 'other']
    reason_detail: Optional[str] = Field(default=None, max_length=500)
    transfer_mode: Literal['permanent', 'delegation'] = 'permanent'
    delegation_end_at: Optional[datetime] = None

    @model_validator(mode='after')
    def validate_transfer_mode(self):
        if self.transfer_mode == 'delegation' and self.delegation_end_at is None:
            raise ValueError('临时代办必须填写计划结束时间')
        if self.transfer_mode == 'permanent':
            self.delegation_end_at = None
        return self


class WorkflowClaimRequest(WorkflowTransferContent):
    workflow_instance_ids: list[UUID] = Field(default_factory=list, max_length=100)
    work_item_refs: list[WorkItemReference] = Field(default_factory=list, max_length=100)
    expected_assignee_ids: dict[UUID, UUID] = Field(default_factory=dict)


class WorkflowRolePoolClaimRequest(BaseModel):
    workflow_instance_ids: list[UUID] = Field(default_factory=list, max_length=100)
    work_item_refs: list[WorkItemReference] = Field(default_factory=list, max_length=100)


class WorkflowTransferUser(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None
    is_on_leave: bool = False
    leave_start: Optional[datetime] = None
    leave_end: Optional[datetime] = None
    assignment_disabled_reason: Optional[str] = None


class WorkflowEligibleUsersRequest(BaseModel):
    workflow_instance_ids: list[UUID] = Field(default_factory=list, max_length=100)
    work_item_refs: list[WorkItemReference] = Field(default_factory=list, max_length=100)


class WorkflowTransferResult(BaseModel):
    action: str
    transferred_count: int
    workflow_instance_ids: list[UUID]
    project_responsibility_ids: list[UUID] = Field(default_factory=list)


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
    transfer_mode: Literal['permanent', 'delegation'] = 'permanent'
    delegation_end_at: Optional[datetime] = None
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


class WorkflowDelegationReturnRequest(BaseModel):
    delegation_ids: list[UUID] = Field(min_length=1, max_length=100)
    note: Optional[str] = Field(default=None, max_length=500)
