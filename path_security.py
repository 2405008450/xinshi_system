"""用户可编辑文件路径的安全边界。"""

from __future__ import annotations

import ntpath
import os


DANGEROUS_FILE_EXTENSIONS = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse",
    ".wsf", ".wsh", ".msi", ".msp", ".scr", ".cpl", ".lnk", ".url",
    ".hta", ".reg", ".dll",
}


def _normalize_unc(value: str) -> str:
    candidate = value.strip().replace("/", "\\")
    if not candidate.startswith("\\\\") or "\x00" in candidate:
        raise ValueError("仅允许规范化的 UNC 网络路径")
    segments = [segment for segment in candidate[2:].split("\\") if segment]
    if len(segments) < 2 or any(segment in {".", ".."} for segment in segments):
        raise ValueError("网络路径不能包含相对路径或路径穿越")
    return "\\\\" + "\\".join(segments)


def _allowed_roots() -> tuple[str, ...]:
    roots = []
    for raw_root in os.getenv("OPENPATH_ALLOWED_ROOTS", "").split(";"):
        if not raw_root.strip():
            continue
        roots.append(_normalize_unc(raw_root).rstrip("\\").casefold())
    return tuple(roots)


def validate_managed_path(value: str | None) -> str | None:
    """非 UNC 文本保持兼容；UNC 必须位于受控根目录且不得指向可执行文件。"""
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if not candidate.replace("/", "\\").startswith("\\\\"):
        return candidate

    normalized = _normalize_unc(candidate)
    lowered = normalized.casefold()
    roots = _allowed_roots()
    if not roots or not any(lowered == root or lowered.startswith(root + "\\") for root in roots):
        raise ValueError("网络路径不在企业允许的目录中")
    if ntpath.splitext(normalized)[1].casefold() in DANGEROUS_FILE_EXTENSIONS:
        raise ValueError("禁止保存可执行文件、脚本或快捷方式路径")
    return normalized
