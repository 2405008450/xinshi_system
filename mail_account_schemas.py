"""当前登录用户的个人 SMTP 邮箱接口数据结构。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class MailAccountWrite(BaseModel):
    authorization_code: str = Field(min_length=1, max_length=500)


class MailAccountStatus(BaseModel):
    email: Optional[EmailStr] = None
    is_bound: bool = False
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

