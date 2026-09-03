"""当前登录用户的个人 SMTP 邮箱接口数据结构。"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class MailAccountWrite(BaseModel):
    authorization_code: str = Field(min_length=1, max_length=500)


class MailAccountStatus(BaseModel):
    email: Optional[EmailStr] = None
    is_bound: bool = False
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserMailProfileWrite(BaseModel):
    recipient_display_name: Optional[str] = Field(default=None, max_length=255)
    signature_html: Optional[str] = Field(default=None, max_length=20000)
    signature_enabled: bool = False

    @field_validator("recipient_display_name", "signature_html")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        value = value.strip() if value else None
        return value or None

    @field_validator("recipient_display_name")
    @classmethod
    def validate_display_name(cls, value: Optional[str]) -> Optional[str]:
        if value and ("\r" in value or "\n" in value):
            raise ValueError("邮件显示名不能包含换行")
        return value

    @model_validator(mode="after")
    def validate_enabled_signature(self):
        if self.signature_enabled and not self.signature_html:
            raise ValueError("启用签名前请先填写签名内容")
        return self


class UserMailProfileResponse(UserMailProfileWrite):
    user_id: UUID
    signature_text: Optional[str] = None
    updated_at: Optional[datetime] = None
