"""人才概览与标注项目语种储备查询接口模型。"""

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


OVERVIEW_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$"


class TalentOverviewColumn(BaseModel):
    key: str
    label: str
    group: str
    width: int


class TalentOverviewRow(BaseModel):
    overview_key: str
    language: str
    aliases: list[str] = Field(default_factory=list)
    updated_at: Optional[date] = None
    counts: dict[str, Optional[int]]
    row_total: int


class TalentOverviewResponse(BaseModel):
    version: int
    revision: int = 1
    non_deduplicated: bool = True
    columns: list[TalentOverviewColumn]
    rows: list[TalentOverviewRow]
    column_totals: dict[str, int]
    grand_total: int
    updated_at: Optional[datetime] = None
    updated_by_name: Optional[str] = None


class TalentOverviewColumnWrite(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=OVERVIEW_KEY_PATTERN)
    label: str = Field(min_length=1, max_length=100)
    group: Literal["sheet", "wecom"]
    width: int = Field(default=120, ge=80, le=240)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("来源列名称不能为空")
        return value


class TalentOverviewRowWrite(BaseModel):
    overview_key: str = Field(min_length=1, max_length=80, pattern=OVERVIEW_KEY_PATTERN)
    language: str = Field(min_length=1, max_length=100)
    updated_at: Optional[date] = None
    counts: dict[str, Optional[int]]

    @field_validator("language")
    @classmethod
    def clean_language(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("语种/方言不能为空")
        return value

    @field_validator("counts")
    @classmethod
    def validate_counts(cls, value: dict[str, Optional[int]]):
        for count in value.values():
            if isinstance(count, bool) or (count is not None and count < 0):
                raise ValueError("人才数量只能为空或非负整数")
        return value


class TalentOverviewWrite(BaseModel):
    expected_revision: int = Field(ge=1)
    columns: list[TalentOverviewColumnWrite] = Field(min_length=1, max_length=100)
    rows: list[TalentOverviewRowWrite] = Field(min_length=1, max_length=500)


class TalentLanguageReserveLookupRequest(BaseModel):
    language_ids: list[UUID] = Field(default_factory=list, max_length=500)


class TalentLanguageReserveItem(BaseModel):
    language_id: UUID
    requested_label: Optional[str] = None
    matched: bool
    overview_key: Optional[str] = None
    overview_language: Optional[str] = None
    updated_at: Optional[date] = None
    total: Optional[int] = None
    non_deduplicated: bool = True
    match_type: Optional[str] = None


class TalentLanguageReserveLookupResponse(BaseModel):
    items: list[TalentLanguageReserveItem]
