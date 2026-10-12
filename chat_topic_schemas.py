from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class TopicCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    parent_id: UUID | None = None
    description: str = Field(default='', max_length=500)
    sort_order: int = Field(default=0, ge=0, le=100000)


class TopicUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default='', max_length=500)
    sort_order: int = Field(ge=0, le=100000)
    active: bool


class MessageTopicWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic_id: UUID | None = None
    revision: int = Field(ge=0)
