"""资料变更只随项目保存提交；同名文件仍有独立 ID。"""
from typing import Literal
from uuid import UUID
import unicodedata

from pydantic import BaseModel, Field, field_validator, model_validator


class MaterialFolderCreation(BaseModel):
    id: UUID
    parent_id: UUID | None = None
    name: str

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value or len(value) > 100 or value in {'.', '..'}:
            raise ValueError('文件夹名称不能为空、超过100字符或使用点号路径')
        if any(char in '/\\' or unicodedata.category(char) == 'Cc' for char in value):
            raise ValueError('文件夹名称不能包含路径分隔符或控制字符')
        return value


class MaterialAddition(BaseModel):
    upload_id: UUID
    category: Literal['project', 'quotation', 'contract']
    file_id: UUID | None = None
    folder_id: UUID | None = None

    @model_validator(mode='after')
    def project_folder_only(self):
        if self.folder_id is not None and self.category != 'project':
            raise ValueError('只有项目资料可以关联文件夹')
        return self


class MaterialChanges(BaseModel):
    additions: list[MaterialAddition] = Field(default_factory=list, max_length=200)
    removed_file_ids: list[UUID] = Field(default_factory=list, max_length=200)
    created_folders: list[MaterialFolderCreation] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def unique_targets(self):
        uploads = [item.upload_id for item in self.additions]
        targets = [item.file_id for item in self.additions if item.file_id]
        if len(set(uploads)) != len(uploads) or len(set(targets)) != len(targets):
            raise ValueError('同一次保存不能重复使用暂存文件或更新同一文件')
        if set(targets) & set(self.removed_file_ids):
            raise ValueError('不能同时更新和移除同一文件')
        folders = [item.id for item in self.created_folders]
        if len(set(folders)) != len(folders):
            raise ValueError('同一次保存不能重复创建同一文件夹')
        return self
