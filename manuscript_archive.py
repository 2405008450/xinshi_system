"""稿件安排共享路径的邮件压缩包生成。"""

from __future__ import annotations

import io
import datetime
import ntpath
import os
import re
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable, Optional

from mail_service import MailAttachment
from path_security import DANGEROUS_FILE_EXTENSIONS


MAX_MANUSCRIPT_ARCHIVE_SOURCE_BYTES = 50 * 1024 * 1024
MAX_MANUSCRIPT_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_MANUSCRIPT_MAIL_CONTENT_BYTES = 75 * 1024 * 1024
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_reparse_point(path: Path) -> bool:
    try:
        stat_result = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError(f"无法读取共享路径：{path}（{exc}）") from exc
    return bool(
        path.is_symlink()
        or getattr(stat_result, "st_file_attributes", 0)
        & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _iter_regular_files(root: Path) -> Iterable[tuple[Path, Path]]:
    if _is_reparse_point(root):
        raise ValueError(f"共享路径不能使用符号链接或目录联接：{root}")
    try:
        if root.is_file():
            yield root, Path(root.name)
            return
        if not root.is_dir():
            raise ValueError(f"共享路径不是文件或文件夹：{root}")
    except OSError as exc:
        raise ValueError(f"无法访问共享路径：{root}（{exc}）") from exc

    try:
        def raise_walk_error(error: OSError) -> None:
            raise error

        for current, directories, filenames in os.walk(
            root,
            followlinks=False,
            onerror=raise_walk_error,
        ):
            current_path = Path(current)
            directories.sort()
            for directory in sorted(directories):
                child = current_path / directory
                if _is_reparse_point(child):
                    raise ValueError(f"共享路径不能包含符号链接或目录联接：{child}")
            for filename in sorted(filenames):
                file_path = current_path / filename
                if _is_reparse_point(file_path):
                    raise ValueError(f"共享路径不能包含符号链接或目录联接：{file_path}")
                if not file_path.is_file():
                    continue
                yield file_path, file_path.relative_to(root)
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(f"读取共享文件夹失败：{root}（{exc}）") from exc


def resolve_selected_dispatch_file(root: Path, relative_path: str) -> Path:
    """在派稿根目录内解析一个相对文件，并拒绝穿越和重解析点。"""
    normalized = str(relative_path or "").strip().replace("\\", "/")
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or relative.is_absolute()
        or ":" in normalized
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError("派稿文件路径无效，请重新选择")
    if _is_reparse_point(root):
        raise ValueError(f"派稿根目录不能使用符号链接或目录联接：{root}")
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if _is_reparse_point(current):
            raise ValueError(f"派稿文件不能经过符号链接或目录联接：{relative.as_posix()}")
    try:
        if not candidate.is_file():
            raise ValueError(f"选中的派稿文件不存在：{relative.as_posix()}")
    except OSError as exc:
        raise ValueError(f"无法读取选中的派稿文件：{relative.as_posix()}（{exc}）") from exc
    if candidate.suffix.casefold() in DANGEROUS_FILE_EXTENSIONS:
        raise ValueError(f"禁止发送该文件类型：{candidate.name}")
    return candidate


def list_manuscript_directory(
    dispatch_path: str,
    relative_directory: str = "",
    *,
    limit: int = 500,
) -> dict:
    """按层枚举派稿目录，绝不接受客户端传入新的绝对根路径。"""
    root = Path((dispatch_path or "").strip())
    if not str(root):
        raise ValueError("请先填写项目派稿文路径")
    normalized = str(relative_directory or "").strip().replace("\\", "/")
    relative = PurePosixPath(normalized) if normalized else PurePosixPath()
    if relative.is_absolute() or ":" in normalized or any(part in {".", ".."} for part in relative.parts):
        raise ValueError("目录路径无效")
    target = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if _is_reparse_point(current):
            raise ValueError("不能浏览符号链接或目录联接")
    if _is_reparse_point(root) or not target.is_dir():
        raise ValueError("派稿目录不存在或无法访问")
    try:
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
    except OSError as exc:
        raise ValueError(f"无法读取派稿目录（{exc}）") from exc
    truncated = len(entries) > limit
    items = []
    for entry in entries[:limit]:
        child_relative = (relative / entry.name).as_posix()
        is_reparse = _is_reparse_point(entry)
        is_directory = entry.is_dir() if not is_reparse else False
        selectable = not is_directory and not is_reparse and entry.is_file()
        reason = None
        if is_reparse:
            reason = "不允许选择符号链接或目录联接"
        elif is_directory:
            selectable = False
        elif entry.suffix.casefold() in DANGEROUS_FILE_EXTENSIONS:
            selectable = False
            reason = "禁止发送该文件类型"
        elif not entry.is_file():
            selectable = False
            reason = "不是普通文件"
        stat = entry.stat() if selectable else None
        items.append({
            "relative_path": child_relative,
            "name": entry.name,
            "is_directory": is_directory,
            "file_size": stat.st_size if stat else None,
            "modified_at": datetime.datetime.fromtimestamp(stat.st_mtime) if stat else None,
            "selectable": selectable,
            "unavailable_reason": reason,
        })
    return {
        "relative_directory": relative.as_posix() if normalized else "",
        "items": items,
        "truncated": truncated,
    }


def _safe_archive_filename(stem: Optional[str]) -> str:
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (stem or "稿件资料").strip())
    normalized = normalized.strip(" .") or "稿件资料"
    return f"{normalized[:180]}-稿件资料.zip"


def build_manuscript_path_archive(
    dispatch_path: Optional[str],
    reference_path: Optional[str],
    *,
    filename_stem: Optional[str] = None,
    selected_dispatch_files: Optional[Iterable[str]] = None,
) -> MailAttachment:
    """将派稿文和参考文件路径合并为一个内存 ZIP 附件。"""
    sources = []
    seen_paths: set[str] = set()
    for label, raw_path in (("派稿文", dispatch_path), ("参考文件", reference_path)):
        normalized = (raw_path or "").strip()
        if not normalized:
            continue
        dedupe_key = ntpath.normcase(ntpath.normpath(normalized))
        if dedupe_key in seen_paths:
            continue
        seen_paths.add(dedupe_key)
        sources.append((label, Path(normalized)))

    if not sources:
        raise ValueError("请先填写派稿文路径或参考文件路径，再发送稿件")

    files: list[tuple[str, Path, Path]] = []
    source_bytes = 0
    selected_paths = list(selected_dispatch_files) if selected_dispatch_files is not None else None
    for label, root in sources:
        if label == "派稿文" and selected_paths is not None:
            source_files = (
                (resolve_selected_dispatch_file(root, relative_path), PurePosixPath(relative_path))
                for relative_path in selected_paths
            )
        else:
            source_files = _iter_regular_files(root)
        for file_path, relative_path in source_files:
            if file_path.suffix.casefold() in DANGEROUS_FILE_EXTENSIONS:
                raise ValueError(f"共享文件夹包含禁止发送的文件类型：{file_path.name}")
            try:
                source_bytes += file_path.stat().st_size
            except OSError as exc:
                raise ValueError(f"无法读取共享文件：{file_path}（{exc}）") from exc
            if source_bytes > MAX_MANUSCRIPT_ARCHIVE_SOURCE_BYTES:
                raise ValueError("共享文件原始总大小不能超过 50MB")
            files.append((label, file_path, relative_path))

    if not files:
        raise ValueError("派稿文路径和参考文件路径中没有可发送的文件")

    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(
            buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for label, file_path, relative_path in files:
                archive.write(file_path, (Path(label) / relative_path).as_posix())
    except OSError as exc:
        raise ValueError(f"打包共享文件失败：{exc}") from exc

    content = buffer.getvalue()
    if len(content) > MAX_MANUSCRIPT_ARCHIVE_BYTES:
        raise ValueError("共享文件压缩包不能超过 50MB")
    return MailAttachment(
        filename=_safe_archive_filename(filename_stem),
        content=content,
        content_type="application/zip",
    )


def validate_manuscript_mail_size(
    attachments: Iterable[MailAttachment],
    inline_images: Iterable[object] = (),
) -> None:
    total = sum(len(item.content) for item in attachments)
    total += sum(
        int(getattr(item, "file_size", 0) or len(getattr(item, "content", b"")))
        for item in inline_images
    )
    if total > MAX_MANUSCRIPT_MAIL_CONTENT_BYTES:
        raise ValueError("邮件附件与正文图片合计不能超过 75MB")
