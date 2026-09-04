"""稿件安排共享路径的邮件压缩包生成。"""

from __future__ import annotations

import io
import ntpath
import os
import re
import zipfile
from pathlib import Path
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


def _safe_archive_filename(stem: Optional[str]) -> str:
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (stem or "稿件资料").strip())
    normalized = normalized.strip(" .") or "稿件资料"
    return f"{normalized[:180]}-稿件资料.zip"


def build_manuscript_path_archive(
    dispatch_path: Optional[str],
    reference_path: Optional[str],
    *,
    filename_stem: Optional[str] = None,
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
    for label, root in sources:
        for file_path, relative_path in _iter_regular_files(root):
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
