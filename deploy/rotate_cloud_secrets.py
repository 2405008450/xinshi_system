"""轮换云端应用密钥，不输出任何密钥内容。"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


env_path = Path(".env")
replacements = {
    "SECRET_KEY": secrets.token_urlsafe(48),
    "AUTH_THROTTLE_HMAC_KEY": secrets.token_urlsafe(48),
}
output: list[str] = []
seen: set[str] = set()

for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
    if "=" not in raw_line or raw_line.lstrip().startswith("#"):
        output.append(raw_line)
        continue
    key = raw_line.split("=", 1)[0].strip()
    if key in replacements:
        output.append(f"{key}={replacements[key]}")
        seen.add(key)
    else:
        output.append(raw_line)

for key in replacements.keys() - seen:
    output.append(f"{key}={replacements[key]}")

temporary_path = env_path.with_suffix(".rotating")
temporary_path.write_text("\n".join(output) + "\n", encoding="utf-8")
os.chmod(temporary_path, 0o600)
os.replace(temporary_path, env_path)
