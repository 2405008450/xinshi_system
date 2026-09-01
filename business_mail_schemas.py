"""内部项目邮件 API 数据结构。"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


ProjectMailType = Literal["translation", "interpretation", "annotation", "recruitment"]


class MailRecipientUser(BaseModel):
    user_id: UUID
    display_name: str
    email: str
    department: Optional[str] = None
    recipient_type: Literal["to", "cc"] = "to"


class MailRecipientGroupWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True
    user_ids: list[UUID] = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("邮件组名称不能为空")
        return value


class MailRecipientGroupResponse(MailRecipientGroupWrite):
    id: UUID
    members: list[MailRecipientUser] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectMailPolicyWrite(BaseModel):
    to_group_ids: list[UUID] = Field(default_factory=list)
    cc_group_ids: list[UUID] = Field(default_factory=list)


class ProjectMailPolicyResponse(ProjectMailPolicyWrite):
    project_type: ProjectMailType
    to_groups: list[MailRecipientGroupResponse] = Field(default_factory=list)
    cc_groups: list[MailRecipientGroupResponse] = Field(default_factory=list)


class BusinessMailPreviewRequest(BaseModel):
    project_type: ProjectMailType
    project_id: Optional[UUID] = None
    consultation_id: Optional[UUID] = None
    source: dict = Field(default_factory=dict)


class BusinessMailPreviewResponse(BaseModel):
    project_type: ProjectMailType
    order_no: Optional[str] = None
    project_name: Optional[str] = None
    to_users: list[MailRecipientUser]
    cc_users: list[MailRecipientUser]
    subject: str
    body: str
    body_html: Optional[str] = None
    inline_images: list[dict] = Field(default_factory=list)
    missing_fields: list[str]
    sender_mode: Literal["system", "personal"]
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_verified: bool = False
    can_send: bool
    blocking_reasons: list[str]


class BusinessMailSendRequest(BaseModel):
    project_type: ProjectMailType
    project_id: UUID
    consultation_id: Optional[UUID] = None
    source_kind: Literal["consultation_confirmation", "project_manual"]
    to_user_ids: list[UUID] = Field(min_length=1)
    cc_user_ids: list[UUID] = Field(default_factory=list)
    subject: str = Field(min_length=1, max_length=1000)
    body: str = Field(min_length=1, max_length=50000)
    body_html: Optional[str] = Field(default=None, max_length=100000)
    inline_image_ids: list[UUID] = Field(default_factory=list, max_length=5)
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("邮件主题不能为空")
        if "\r" in value or "\n" in value:
            raise ValueError("邮件主题不能包含换行")
        return value

    @field_validator("body", "idempotency_key")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class BusinessMailAttemptResponse(BaseModel):
    attempted_at: datetime
    sender_user_id: Optional[UUID] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    success: bool
    delivery_mode: Optional[str] = None
    error: Optional[str] = None


class BusinessMailResponse(BaseModel):
    id: UUID
    source_kind: str
    project_type: ProjectMailType
    consultation_id: Optional[UUID]
    project_id: Optional[UUID]
    subject: str
    body: str
    body_html: Optional[str] = None
    inline_images: list[dict] = Field(default_factory=list)
    status: str
    recipients: list[MailRecipientUser]
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    attempts: list[BusinessMailAttemptResponse] = Field(default_factory=list)
    send_error: Optional[str]
    delivery_mode: Optional[str]
    created_at: datetime
    send_attempted_at: Optional[datetime]
    sent_at: Optional[datetime]


class ProjectMailStatusResponse(BaseModel):
    mode: str
    project_sender_mode: str = "system"
    configured: bool
    host: Optional[str] = None
    port: Optional[int] = None
    security: str
    sender_email: Optional[str] = None
    test_recipient_masked: Optional[str] = None
    detail: str
