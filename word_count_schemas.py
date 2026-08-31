"""多维字数统计接口 Schema。"""
from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


MetricType = Literal["words", "characters_no_spaces", "cjk_chars_korean_words", "foreign_words", "documents", "pages"]
EntityType = Literal["project", "suborder"]
EntityDimension = Literal["company", "customer", "translator_estimate"]
ArrangementDimension = Literal["planned", "actual"]


class WordCountValues(BaseModel):
    words: Optional[int] = Field(default=None, ge=0)
    characters_no_spaces: Optional[int] = Field(default=None, ge=0)
    cjk_chars_korean_words: Optional[int] = Field(default=None, ge=0)
    foreign_words: Optional[int] = Field(default=None, ge=0)
    documents: Optional[int] = Field(default=None, ge=0)
    pages: Optional[int] = Field(default=None, ge=0)


class WordCountCreateMatrix(BaseModel):
    company: WordCountValues = Field(default_factory=WordCountValues)
    customer: WordCountValues = Field(default_factory=WordCountValues)
    translator_estimate: WordCountValues = Field(default_factory=WordCountValues)


class TranslatorWordCountRow(BaseModel):
    arrangement_id: UUID
    dispatch_id: Optional[UUID] = None
    translator_id: UUID
    translator_name: str
    status: Optional[str] = None
    planned: WordCountValues = Field(default_factory=WordCountValues)
    actual: WordCountValues = Field(default_factory=WordCountValues)


class WordCountMatrixResponse(BaseModel):
    entity_type: EntityType
    entity_id: UUID
    company: WordCountValues = Field(default_factory=WordCountValues)
    customer: WordCountValues = Field(default_factory=WordCountValues)
    translator_estimate: WordCountValues = Field(default_factory=WordCountValues)
    translators: list[TranslatorWordCountRow] = Field(default_factory=list)


class WordCountCellChange(BaseModel):
    scope: Literal["entity", "translator"]
    dimension: str
    metric_type: MetricType
    value: Optional[int] = Field(default=None, ge=0)
    arrangement_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "entity":
            if self.dimension not in {"company", "customer", "translator_estimate"}:
                raise ValueError("项目级字数维度无效")
            if self.arrangement_id is not None:
                raise ValueError("项目级字数不能指定译员安排")
        else:
            if self.dimension not in {"planned", "actual"}:
                raise ValueError("译员字数维度无效")
            if self.arrangement_id is None:
                raise ValueError("译员字数必须指定安排记录")
        return self


class WordCountMatrixPatch(BaseModel):
    changes: list[WordCountCellChange] = Field(default_factory=list, max_length=500)
