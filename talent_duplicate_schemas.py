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
    decision_pairs: list[tuple[UUID, UUID]] | None = Field(default=None, max_length=4950)
    agent_report_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_selection(self):
        if len(set(self.person_ids)) != len(self.person_ids):
            raise ValueError("不能重复选择同一档案")
        if self.action in {"merge", "keep"} and self.target_id not in self.person_ids:
            raise ValueError("请选择本次处理中的保留档案")
        if self.action in {"different", "defer"} and self.target_id is not None:
            raise ValueError("区分或暂缓操作不需要保留档案")
        if self.decision_pairs is not None:
            if self.action not in {"different", "defer"} or not self.decision_pairs:
                raise ValueError("只有区分或暂缓操作可以指定非空记录对")
            pairs = {tuple(sorted((str(a), str(b)))) for a, b in self.decision_pairs}
            if len(pairs) != len(self.decision_pairs) or any(a == b for a, b in self.decision_pairs):
                raise ValueError("记录对不能重复或指向同一档案")
            if {identifier for pair in self.decision_pairs for identifier in pair} != set(self.person_ids):
                raise ValueError("记录对必须且只能覆盖本次选中的档案")
        return self


class DuplicateReviewCommit(DuplicateReviewRequest):
    preview_token: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)


class NameMergePreviewRequest(BaseModel):
    group_key: str = Field(min_length=1, max_length=1000)
    group_version: str = Field(min_length=64, max_length=64)


class NameMergeCommitRequest(NameMergePreviewRequest):
    preview_token: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)
