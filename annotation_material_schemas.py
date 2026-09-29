"""资料变更只随项目保存提交；同名文件仍有独立 ID。"""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class MaterialAddition(BaseModel):
    upload_id: UUID
    category: Literal['project', 'quotation', 'contract']
    file_id: UUID | None = None


class MaterialChanges(BaseModel):
    additions: list[MaterialAddition] = Field(default_factory=list, max_length=200)
    removed_file_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def unique_targets(self):
        uploads = [item.upload_id for item in self.additions]
        targets = [item.file_id for item in self.additions if item.file_id]
        if len(set(uploads)) != len(uploads) or len(set(targets)) != len(targets):
            raise ValueError('同一次保存不能重复使用暂存文件或更新同一文件')
        if set(targets) & set(self.removed_file_ids):
            raise ValueError('不能同时更新和移除同一文件')
        return self
