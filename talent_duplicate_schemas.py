"""核重操作契约，客户端只能选择服务端预览中的字段与原档案值。"""
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class DuplicateReviewRequest(BaseModel):
    action: Literal["different", "defer", "keep", "merge"]
    person_ids: list[UUID] = Field(min_length=2, max_length=100)
    target_id: UUID | None = None
    decisions: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_selection(self):
        if len(set(self.person_ids)) != len(self.person_ids):
            raise ValueError("不能重复选择同一档案")
        if self.action in {"merge", "keep"} and self.target_id not in self.person_ids:
            raise ValueError("请选择本次处理中的保留档案")
        if self.action in {"different", "defer"} and self.target_id is not None:
            raise ValueError("区分或暂缓操作不需要保留档案")
        return self


class DuplicateReviewCommit(DuplicateReviewRequest):
    preview_token: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)
