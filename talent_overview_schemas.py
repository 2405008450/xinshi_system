"""人才概览与标注项目语种储备查询接口模型。"""

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


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
    non_deduplicated: bool = True
    columns: list[TalentOverviewColumn]
    rows: list[TalentOverviewRow]
    column_totals: dict[str, int]
    grand_total: int


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

