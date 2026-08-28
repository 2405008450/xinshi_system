"""乐观锁：用记录的 updated_at 作为版本条件，避免后保存的旧表单覆盖新值。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


VERSION_FIELD = "expected_updated_at"


class StaleUpdateError(Exception):
    """当前记录已被其他人更新。"""

    def __init__(self, message: str = "记录已被其他人更新，请刷新后重试"):
        super().__init__(message)


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


def parse_expected_updated_at(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _naive(value)
    text = str(value).strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _naive(parsed)


def assert_fresh(row, expected_updated_at: Any) -> None:
    """请求携带 expected_updated_at 时，必须与当前行版本一致。"""
    expected = parse_expected_updated_at(expected_updated_at)
    current = getattr(row, "updated_at", None)
    if expected is None or current is None:
        return
    if abs((_naive(current) - expected).total_seconds()) > 0.001:
        raise StaleUpdateError()
