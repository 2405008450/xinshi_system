"""稿件安排模块的 API 数据结构。"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from word_count_schemas import WordCountCreateMatrix, WordCountValues

EntityType = Literal["project", "suborder"]
ArrangementStatus = Literal["draft", "ready", "sent", "failed", "cancelled"]
DispatchStatus = Literal["draft", "ready", "partially_sent", "sent", "cancelled"]
MilestoneType = Literal["phase", "final"]
SettlementMethod = str


class ManuscriptTranslatorItem(BaseModel):
    id: UUID
    translator_code: Optional[str] = None
    translator_name: str
    cooperation_type: Optional[str] = None
    status: Optional[str] = None
    languages: Optional[str] = None
    translation_type: Optional[str] = None
    direction: Optional[str] = None
    quality_score: Optional[str] = None
    email1: Optional[str] = None
    email2: Optional[str] = None
    available_time_slot: Optional[str] = None
    daily_word_capacity: Optional[int] = None
    can_cloud_edit: Optional[bool] = None
    can_revision: Optional[bool] = None
    domain_skills: list = Field(default_factory=list)
    remarks: Optional[str] = None


class ManuscriptActiveProjectItem(BaseModel):
    """稿件安排页可选择的进行中母订单或子订单。"""

    workflow_instance_id: UUID
    entity_type: EntityType
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
    current_stage_role_code: Optional[str] = None
    current_stage_role_name: Optional[str] = None
    project_assistant_id: Optional[UUID] = None
    project_assistant_name: Optional[str] = None
    project_assistant_assignment_type: Literal["direct", "role_pool"] = "role_pool"
    can_manage_manuscript: bool = False
    manuscript_access_reason: Optional[str] = None
    project_manager_id: Optional[UUID] = None
    project_manager_name: Optional[str] = None
    project_status: Optional[str] = None
    customer_deadline_time: Optional[datetime] = None
    language_pair: Optional[str] = None
    file_type_secondary: Optional[str] = None
    priority: Optional[str] = None
    word_count_matrix: WordCountCreateMatrix = Field(default_factory=WordCountCreateMatrix)
    dispatch_path: Optional[str] = None
    # 保留旧字段供既有调用方读取；邮件发送统一使用 dispatch_path。
    network_file_path: Optional[str] = None
    reference_file_path_one: Optional[str] = None
    updated_at: Optional[datetime] = None


class ManuscriptActiveProjectListResponse(BaseModel):
    items: list[ManuscriptActiveProjectItem] = Field(default_factory=list)
    total: int = 0
    overdue_total: int = 0
    due_soon_total: int = 0


class ManuscriptArrangementContext(BaseModel):
    active_projects: ManuscriptActiveProjectListResponse
    translators: list[ManuscriptTranslatorItem] = Field(default_factory=list)


class ManuscriptMilestoneInput(BaseModel):
    milestone_type: MilestoneType = "phase"
    name: str = Field(min_length=1, max_length=100)
    sequence_no: int = Field(ge=1)
    planned_at: Optional[datetime] = None


class ManuscriptMilestoneResponse(ManuscriptMilestoneInput):
    id: UUID
    arrangement_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ManuscriptAssignmentInput(BaseModel):
    translator_id: UUID
    planned: WordCountValues = Field(default_factory=WordCountValues)
    actual: WordCountValues = Field(default_factory=WordCountValues)
    translation_scope: Optional[str] = Field(default=None, max_length=5000)
    settlement_method: Optional[SettlementMethod] = Field(default=None, max_length=100)
    custom_settlement_method: Optional[str] = Field(default=None, max_length=100)
    translator_unit_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )
    translator_total_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_body: Optional[str] = Field(default=None, max_length=20000)
    remarks: Optional[str] = Field(default=None, max_length=5000)
    milestones: list[ManuscriptMilestoneInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_settlement_and_milestones(self):
        sequence_numbers = [item.sequence_no for item in self.milestones]
        if len(sequence_numbers) != len(set(sequence_numbers)):
            raise ValueError("同一译员的交稿节点顺序不能重复")
        final_count = sum(
            1 for item in self.milestones if item.milestone_type == "final"
        )
        if final_count > 1:
            raise ValueError("同一译员只能设置一个全稿交付节点")

        dated = [
            item
            for item in sorted(self.milestones, key=lambda row: row.sequence_no)
            if item.planned_at is not None
        ]
        for previous, current in zip(dated, dated[1:]):
            if previous.planned_at > current.planned_at:
                raise ValueError("交稿节点时间必须按顺序递增")
        return self


class ManuscriptDispatchCreate(BaseModel):
    entity_type: EntityType
    translation_project_id: UUID
    sub_order_id: Optional[UUID] = None
    remarks: Optional[str] = Field(default=None, max_length=5000)
    arrangements: list[ManuscriptAssignmentInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dispatch(self):
        if self.entity_type == "suborder" and self.sub_order_id is None:
            raise ValueError("子订单稿件安排必须提供子订单 ID")
        if self.entity_type == "project" and self.sub_order_id is not None:
            raise ValueError("母订单稿件安排不能提供子订单 ID")
        translator_ids = [item.translator_id for item in self.arrangements]
        if len(translator_ids) != len(set(translator_ids)):
            raise ValueError("同一批次不能重复选择同一译员")
        if len(self.arrangements) > 1:
            for item in self.arrangements:
                if not (item.translation_scope or "").strip():
                    raise ValueError("多人派稿时，每位译员都必须填写需翻译部分")
        return self


class ManuscriptDispatchUpdate(ManuscriptDispatchCreate):
    expected_updated_at: Optional[datetime] = None


class ManuscriptArrangementCreate(BaseModel):
    """旧单译员创建接口，内部会转换为单译员批次。"""

    entity_type: EntityType
    translation_project_id: UUID
    sub_order_id: Optional[UUID] = None
    translator_id: UUID
    planned_delivery_at: Optional[datetime] = None
    planned: WordCountValues = Field(default_factory=WordCountValues)
    actual: WordCountValues = Field(default_factory=WordCountValues)
    translation_scope: Optional[str] = Field(default=None, max_length=5000)
    settlement_method: Optional[SettlementMethod] = Field(default=None, max_length=100)
    custom_settlement_method: Optional[str] = Field(default=None, max_length=100)
    translator_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    translator_total_price: Optional[Decimal] = Field(default=None, ge=0)
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_body: Optional[str] = Field(default=None, max_length=20000)
    remarks: Optional[str] = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_entity(self):
        if self.entity_type == "suborder" and self.sub_order_id is None:
            raise ValueError("子订单稿件安排必须提供子订单 ID")
        if self.entity_type == "project" and self.sub_order_id is not None:
            raise ValueError("母订单稿件安排不能提供子订单 ID")
        return self


class ManuscriptArrangementUpdate(BaseModel):
    planned_delivery_at: Optional[datetime] = None
    actual: Optional[WordCountValues] = None
    settlement_method: Optional[SettlementMethod] = Field(default=None, max_length=100)
    custom_settlement_method: Optional[str] = Field(default=None, max_length=100)
    translator_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    translator_total_price: Optional[Decimal] = Field(default=None, ge=0)
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_body: Optional[str] = Field(default=None, max_length=20000)
    remarks: Optional[str] = Field(default=None, max_length=5000)


class ManuscriptSettlementUpdate(BaseModel):
    actual: Optional[WordCountValues] = None
    settlement_method: Optional[SettlementMethod] = Field(default=None, max_length=100)
    custom_settlement_method: Optional[str] = Field(default=None, max_length=100)
    translator_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    translator_total_price: Optional[Decimal] = Field(default=None, ge=0)
    remarks: Optional[str] = Field(default=None, max_length=5000)

class ManuscriptArrangementResponse(BaseModel):
    id: UUID
    dispatch_id: Optional[UUID] = None
    entity_type: EntityType
    translation_project_id: UUID
    sub_order_id: Optional[UUID] = None
    translator_id: UUID
    order_no_snapshot: str
    project_name_snapshot: str
    translator_name_snapshot: str
    cooperation_type_snapshot: Optional[str] = None
    recipient_email: Optional[str] = None
    planned: WordCountValues = Field(default_factory=WordCountValues)
    actual: WordCountValues = Field(default_factory=WordCountValues)
    translation_scope: Optional[str] = None
    settlement_method: Optional[str] = None
    custom_settlement_method: Optional[str] = None
    translator_unit_price: Optional[Decimal] = None
    translator_total_price: Optional[Decimal] = None
    planned_delivery_at: Optional[datetime] = None
    manuscript_source_path: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    remarks: Optional[str] = None
    status: ArrangementStatus
    created_by: Optional[UUID] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    send_attempted_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivery_recipient: Optional[str] = None
    delivery_mode: Optional[str] = None
    smtp_message_id: Optional[str] = None
    send_error: Optional[str] = None
    milestones: list[ManuscriptMilestoneResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ManuscriptDispatchResponse(BaseModel):
    id: UUID
    entity_type: EntityType
    translation_project_id: UUID
    sub_order_id: Optional[UUID] = None
    order_no_snapshot: str
    project_name_snapshot: str
    status: DispatchStatus
    remarks: Optional[str] = None
    created_by: Optional[UUID] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    previous_order_status: Optional[str] = None
    project_assistant_id: Optional[UUID] = None
    project_assistant_name: Optional[str] = None
    project_assistant_assignment_type: Literal["direct", "role_pool"] = "role_pool"
    can_manage_manuscript: bool = False
    manuscript_access_reason: Optional[str] = None
    arrangements: list[ManuscriptArrangementResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ManuscriptBatchSendResponse(BaseModel):
    dispatch: ManuscriptDispatchResponse
    sent_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0


class ManuscriptMailPreview(BaseModel):
    """确认安排后展示，并与实际发送共用的邮件内容。"""

    arrangement_id: UUID
    recipient_email: Optional[str] = None
    subject: str
    body: str
    dispatch_path: Optional[str] = None
    reference_file_path_one: Optional[str] = None


class ManuscriptMailPathsUpdate(BaseModel):
    """更新稿件发送所引用的项目路径。"""

    dispatch_path: Optional[str] = Field(default=None, max_length=5000)
    reference_file_path_one: Optional[str] = Field(default=None, max_length=500)


class ManuscriptMailPathsResponse(ManuscriptMailPathsUpdate):
    translation_project_id: UUID
    project_file_id: UUID


class ManuscriptMailStatus(BaseModel):
    mode: str
    configured: bool
    host: Optional[str] = None
    port: Optional[int] = None
    security: str
    sender_email: Optional[str] = None
    test_recipient_masked: Optional[str] = None
    detail: str
