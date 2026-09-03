"""邮件富文本中可复用的安全属性校验。"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit


_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$")
_RGB_COLOR = re.compile(
    r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})"
    r"(?:\s*,\s*(?:0(?:\.\d+)?|1(?:\.0+)?))?\s*\)$",
    re.IGNORECASE,
)


def safe_css_color(value: str) -> Optional[str]:
    color = (value or "").strip()
    if _HEX_COLOR.fullmatch(color):
        return color.lower()
    match = _RGB_COLOR.fullmatch(color)
    if match and all(0 <= int(channel) <= 255 for channel in match.groups()[:3]):
        return re.sub(r"\s+", "", color.lower())
    return None


def safe_mail_href(value: str) -> Optional[str]:
    href = (value or "").strip()
    if not href or "\r" in href or "\n" in href:
        return None
    scheme = urlsplit(href).scheme.lower()
    return href if scheme in {"http", "https", "mailto"} else None
