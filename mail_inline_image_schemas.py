"""邮件正文图片接口结构。"""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MailInlineImageResponse(BaseModel):
    id: UUID
    original_name: str
    content_type: str
    file_size: int
    width: int
    height: int


class InlineImagePayload(BaseModel):
    body_html: str | None = Field(default=None, max_length=100000)
    inline_image_ids: list[UUID] = Field(default_factory=list, max_length=5)

    @field_validator("inline_image_ids")
    @classmethod
    def unique_images(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("正文图片不能重复")
        return value
