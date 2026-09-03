"""个人工作日报邮件接口数据结构。"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class DailyReportMailAccountWrite(BaseModel):
    authorization_code: str = Field(min_length=1, max_length=500)


class DailyReportMailAccountStatus(BaseModel):
    email: Optional[EmailStr] = None
    is_bound: bool = False
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DailyReportMailPolicyWrite(BaseModel):
    to_group_ids: list[UUID] = Field(default_factory=list)
    cc_group_ids: list[UUID] = Field(default_factory=list)


class DailyReportMailPolicyResponse(DailyReportMailPolicyWrite):
    user_id: UUID
    user_name: str
    email: Optional[EmailStr] = None
    is_active: bool
    mail_account_bound: bool = False
    mail_account_verified: bool = False


class DailyReportMailRecipientView(BaseModel):
    user_id: Optional[UUID] = None
    display_name: str
    email: EmailStr
    recipient_type: Literal["to", "cc"]


class DailyReportMailRow(BaseModel):
    order_no: str = Field(default="", max_length=255)
    task_name: str = Field(default="", max_length=255)
    client_name: str = Field(default="", max_length=255)
    task_type: str = Field(default="", max_length=50)
    progress_content: str = Field(default="", max_length=10000)
    result_content: str = Field(default="", max_length=10000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    source_label: str = Field(default="", max_length=100)


class DailyReportMailPreviewResponse(BaseModel):
    report_id: UUID
    report_date: str
    sender_name: str
    sender_email: Optional[EmailStr] = None
    subject: str
    rows: list[DailyReportMailRow]
    supplemental_note: Optional[str] = None
    inline_image_html: Optional[str] = None
    inline_images: list[dict] = Field(default_factory=list)
    signature_html: Optional[str] = None
    signature_text: Optional[str] = None
    to_users: list[DailyReportMailRecipientView]
    cc_users: list[DailyReportMailRecipientView]
    can_send: bool
    blocking_reasons: list[str]
    delivery_mode: str
    test_recipient_masked: Optional[str] = None


class DailyReportMailSendRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=1000)
    rows: list[DailyReportMailRow]
    supplemental_note: Optional[str] = Field(default=None, max_length=10000)
    inline_image_html: Optional[str] = Field(default=None, max_length=50000)
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


class DailyReportMailDeliveryResponse(BaseModel):
    id: UUID
    report_id: UUID
    sender_name: str
    sender_email: EmailStr
    subject: str
    rows: list[DailyReportMailRow]
    supplemental_note: Optional[str] = None
    inline_images: list[dict] = Field(default_factory=list)
    recipients: list[DailyReportMailRecipientView]
    status: str
    delivery_mode: Optional[str] = None
    send_error: Optional[str] = None
    created_at: datetime
    send_attempted_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
