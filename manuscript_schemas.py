"""稿件安排模块的 API 数据结构。"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from workflow_schemas import ActiveProjectListResponse


EntityType = Literal["project", "suborder"]
ArrangementStatus = Literal["draft", "ready", "sent", "failed", "cancelled"]
DispatchStatus = Literal["draft", "ready", "partially_sent", "sent", "cancelled"]
MilestoneType = Literal["phase", "final"]
SettlementMethod = Literal["single", "monthly", "prepaid", "other"]


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


class ManuscriptArrangementContext(BaseModel):
    active_projects: ActiveProjectListResponse
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
    planned_word_count: Optional[int] = Field(default=None, ge=0)
    actual_word_count: Optional[int] = Field(default=None, ge=0)
    word_count_type: Optional[str] = Field(default=None, max_length=50)
    translation_scope: Optional[str] = Field(default=None, max_length=5000)
    settlement_method: Optional[SettlementMethod] = None
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
        custom = (self.custom_settlement_method or "").strip()
        if self.settlement_method == "other" and not custom:
            raise ValueError("结算方式选择“其他”时必须填写自定义结算方式")
        if self.settlement_method != "other":
            self.custom_settlement_method = None

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
    pass


class ManuscriptArrangementCreate(BaseModel):
    """旧单译员创建接口，内部会转换为单译员批次。"""

    entity_type: EntityType
    translation_project_id: UUID
    sub_order_id: Optional[UUID] = None
    translator_id: UUID
    planned_delivery_at: Optional[datetime] = None
    planned_word_count: Optional[int] = Field(default=None, ge=0)
    actual_word_count: Optional[int] = Field(default=None, ge=0)
    word_count_type: Optional[str] = Field(default=None, max_length=50)
    translation_scope: Optional[str] = Field(default=None, max_length=5000)
    settlement_method: Optional[SettlementMethod] = None
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
        if self.settlement_method == "other" and not (
            self.custom_settlement_method or ""
        ).strip():
            raise ValueError("结算方式选择“其他”时必须填写自定义结算方式")
        return self


class ManuscriptArrangementUpdate(BaseModel):
    planned_delivery_at: Optional[datetime] = None
    actual_word_count: Optional[int] = Field(default=None, ge=0)
    word_count_type: Optional[str] = Field(default=None, max_length=50)
    settlement_method: Optional[SettlementMethod] = None
    custom_settlement_method: Optional[str] = Field(default=None, max_length=100)
    translator_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    translator_total_price: Optional[Decimal] = Field(default=None, ge=0)
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_body: Optional[str] = Field(default=None, max_length=20000)
    remarks: Optional[str] = Field(default=None, max_length=5000)


class ManuscriptSettlementUpdate(BaseModel):
    actual_word_count: Optional[int] = Field(default=None, ge=0)
    word_count_type: Optional[str] = Field(default=None, max_length=50)
    settlement_method: Optional[SettlementMethod] = None
    custom_settlement_method: Optional[str] = Field(default=None, max_length=100)
    translator_unit_price: Optional[Decimal] = Field(default=None, ge=0)
    translator_total_price: Optional[Decimal] = Field(default=None, ge=0)
    remarks: Optional[str] = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_custom_method(self):
        if self.settlement_method == "other" and not (
            self.custom_settlement_method or ""
        ).strip():
            raise ValueError("结算方式选择“其他”时必须填写自定义结算方式")
        return self


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
    planned_word_count: Optional[int] = None
    actual_word_count: Optional[int] = None
    word_count_type: Optional[str] = None
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
    arrangements: list[ManuscriptArrangementResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ManuscriptBatchSendResponse(BaseModel):
    dispatch: ManuscriptDispatchResponse
    sent_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0


class ManuscriptMailStatus(BaseModel):
    mode: str
    configured: bool
    host: Optional[str] = None
    port: Optional[int] = None
    security: str
    sender_email: Optional[str] = None
    test_recipient_masked: Optional[str] = None
    detail: str
