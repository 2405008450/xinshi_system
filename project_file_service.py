"""项目文件共享路径读取服务。"""

from __future__ import annotations

import os
import ntpath
import stat
from pathlib import Path

from path_security import validate_managed_path


MAX_SOURCE_FILE_COUNT = 500
MAX_SOURCE_FILE_NAME_LENGTH = 255
IGNORED_SOURCE_FILE_NAMES = {".ds_store", "desktop.ini", "thumbs.db"}


def _should_ignore_source_file(name: str) -> bool:
    lowered = name.casefold()
    return lowered in IGNORED_SOURCE_FILE_NAMES or name.startswith("~$")


def _is_reparse_point(path: Path) -> bool:
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def collect_source_file_names(path: Path, *, limit: int = MAX_SOURCE_FILE_COUNT) -> list[str]:
    """读取文件或目录第一层的普通文件名称，不跟随符号链接。"""
    try:
        if _is_reparse_point(path):
            raise ValueError("原文路径不能使用符号链接或目录联接")
        if path.is_file():
            return [path.name]
        if not path.is_dir():
            raise ValueError("原文路径不存在或不是可读取的文件夹")

        names: list[str] = []
        with os.scandir(path) as entries:
            for entry in entries:
                if _should_ignore_source_file(entry.name):
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                if _is_reparse_point(Path(entry.path)):
                    continue
                names.append(entry.name)
                if len(names) > limit:
                    raise ValueError(f"原文目录文件数量超过 {limit} 个，请整理后重试")
        names.sort(key=str.casefold)
        if not names:
            raise ValueError("原文路径中没有可读取的文件")
        return names
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(f"读取原文路径失败：{exc}") from exc


def build_source_file_name(
    file_names: list[str],
    *,
    max_length: int = MAX_SOURCE_FILE_NAME_LENGTH,
) -> str:
    """原文目录只能读取一个文件，不拼接、汇总或截断扩展名。"""
    from translation_file_name_rules import normalize_single_file_name, MULTIPLE_MESSAGE
    if not file_names:
        raise ValueError("原文路径中没有可读取的文件")
    if len(file_names) != 1:
        raise ValueError(f"{MULTIPLE_MESSAGE}；原文目录中发现 {len(file_names)} 个文件，请指定单个文件路径")
    name = normalize_single_file_name(file_names[0])
    if len(name) > max_length:
        raise ValueError(f'文件名称不能超过 {max_length} 个字符，请先重命名原文件')
    return name


def inspect_project_source_path(storage_path: str) -> dict:
    """校验企业 UNC 白名单后读取原文路径中的文件名称。"""
    normalized = validate_managed_path(storage_path)
    if not normalized:
        raise ValueError("请先填写原文路径")
    if not normalized.startswith("\\\\"):
        raise ValueError("自动读取文件名称仅支持企业 UNC 网络路径")

    file_names = collect_source_file_names(Path(normalized))
    return {
        "storage_path": normalized,
        "file_names": file_names,
        "file_count": len(file_names),
        "source_file_name": build_source_file_name(file_names),
    }


def normalize_source_directory(storage_path: str) -> str:
    """仅接受企业白名单内的 UNC 目录文本；不触发网络读取。"""
    normalized = validate_managed_path(storage_path)
    if not normalized or not normalized.startswith("\\\\"):
        raise ValueError("请选择企业 UNC 共享文件夹路径")
    return normalized


def source_file_path(directory: str, name: str) -> str:
    from translation_file_name_rules import normalize_single_file_name
    name = normalize_single_file_name(name)
    return validate_managed_path(ntpath.join(normalize_source_directory(directory), name))


def list_sub_order_source_files(storage_path: str) -> dict:
    """只读枚举第一层文件，保留无效文件及其不可选原因。"""
    normalized = normalize_source_directory(storage_path)
    path = Path(normalized)
    try:
        if _is_reparse_point(path) or not (path.is_dir() or path.is_file()):
            raise ValueError("请选择可读取的文件夹，不能使用文件、符号链接或目录联接")
        names = collect_source_file_names(path)
        if path.is_file():
            normalized = ntpath.dirname(normalized)
    except OSError as exc:
        raise ValueError("共享文件夹不存在或没有读取权限") from exc
    files = []
    for name in names:
        reason = ""
        try:
            source_file_path(normalized, name)
        except ValueError as exc:
            reason = str(exc)
        files.append({"name": name, "path": ntpath.join(normalized, name),
                      "selectable": not reason, "reason": reason})
    return {"storage_path": normalized, "files": files}
