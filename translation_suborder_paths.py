"""预览并一次替换同一笔译项目内子订单的路径前缀。"""

import hashlib
import json
import ntpath
import re

from fastapi import HTTPException
from pydantic import BaseModel, Field

from annotation_progress_time import business_now
from models import TranslationProject, TranslationSubOrder
from path_security import validate_managed_path
from translation_folder_orders import TranslationOrderFolder, ready as folder_metadata_ready


class SubOrderPathReplacement(BaseModel):
    old_root: str = Field(min_length=1, max_length=502)
    new_root: str = Field(min_length=1, max_length=502)
    preview_token: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


def absolute_path(value):
    path = str(value or '').strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1].strip()
    path = path.replace('/', '\\')
    if not (re.match(r'^[a-zA-Z]:\\', path) or re.match(r'^\\\\[^\\]+\\[^\\]+', path)):
        return None
    if re.search(r'[<>:"|?*\x00-\x1f]', path[2:]) or any(
        part in {'.', '..'} for part in path.split('\\')
    ):
        return None
    return ntpath.normpath(path)


def replace_root(path, old_root, new_root):
    normalized = absolute_path(path)
    if not normalized:
        return None
    prefix = old_root.rstrip('\\') + '\\'
    if ntpath.normcase(normalized.rstrip('\\')) == ntpath.normcase(old_root.rstrip('\\')):
        replacement = new_root
    elif ntpath.normcase(normalized).startswith(ntpath.normcase(prefix)):
        replacement = ntpath.join(new_root, normalized[len(prefix):])
    else:
        return None
    if replacement == path:
        return None
    if len(replacement) > 500:
        raise ValueError('替换后的路径超过 500 个字符，请缩短新根路径')
    return validate_managed_path(replacement)


def replace_project_suborder_paths(db, project_id, payload):
    old_root = absolute_path(payload.old_root)
    new_root = absolute_path(payload.new_root)
    if not old_root or not new_root:
        raise ValueError('请输入带盘符或 UNC 的完整根路径')
    if old_root == new_root:
        raise ValueError('请填写不同的新根路径')
    validate_managed_path(new_root)

    applying = payload.preview_token is not None
    project_query = db.query(TranslationProject.id).filter_by(id=project_id)
    if applying:
        project_query = project_query.with_for_update()
    if project_query.first() is None:
        raise HTTPException(404, '母订单不存在')

    query = db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.sub_order_no)
    if applying:
        query = query.with_for_update()
    rows = query.all()
    changes = []
    for row in rows:
        replacement = replace_root(row.network_file_path, old_root, new_root)
        if replacement:
            changes.append((row, replacement))

    metadata_changes = []
    if changes and folder_metadata_ready(db):
        folders = db.query(TranslationOrderFolder).filter(
            TranslationOrderFolder.sub_order_id.in_([row.id for row, _ in changes])
        ).order_by(TranslationOrderFolder.sub_order_id)
        if applying:
            folders = folders.with_for_update()
        for folder in folders:
            replacement = replace_root(folder.root_path, old_root, new_root)
            if replacement:
                relative = folder.relative_path
                root_name, separator, rest = relative.partition('/')
                new_root_name = ntpath.basename(replacement.rstrip('\\/'))
                if new_root_name and ntpath.normcase(root_name) == ntpath.normcase(ntpath.basename(folder.root_path.rstrip('\\/'))):
                    relative = new_root_name + separator + rest
                metadata_changes.append((folder, replacement, relative))

    preview = [
        {'order_no': row.sub_order_no, 'old_path': row.network_file_path, 'new_path': replacement}
        for row, replacement in changes
    ]
    snapshot = [str(project_id), old_root, new_root, preview, [
        (str(folder.sub_order_id), folder.root_path, folder.relative_path, replacement, relative)
        for folder, replacement, relative in metadata_changes
    ]]
    token = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False).encode()).hexdigest()
    if applying:
        if token != payload.preview_token:
            raise HTTPException(409, '子订单路径已变化，请重新预览后再保存')
        if changes:
            updated_at = business_now().replace(tzinfo=None)
            for row, replacement in changes:
                row.network_file_path = replacement
                row.updated_at = updated_at
            for folder, replacement, relative in metadata_changes:
                folder.root_path = replacement
                folder.relative_path = relative
            db.commit()
    return {
        'preview_token': token,
        'changes': preview,
        'changed_count': len(changes),
        'unchanged_count': len(rows) - len(changes),
    }
