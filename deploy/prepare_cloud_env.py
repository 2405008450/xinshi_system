"""从现有环境模板生成隔离的云端运行配置。"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


source = Path(".env.source")
target = Path(".env")
values = read_env(source)
values.update(
    {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "DB_USER": "postgres",
        "DB_PASSWORD": secrets.token_urlsafe(36),
        "DB_HOST": "postgres",
        "DB_PORT": "5432",
        "DB_NAME": "xinshi_system",
        "FRONTEND_PORT": "3000",
        "CORS_ALLOWED_ORIGINS": "",
        "AUTH_THROTTLE_HMAC_KEY": secrets.token_urlsafe(48),
        "AUTH_TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128,172.16.0.0/12",
        "VITE_OPENPATH_ALLOWED_ROOTS": "",
        "OPENPATH_ALLOWED_ROOTS": "",
    }
)

target.write_text(
    "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
    encoding="utf-8",
)
os.chmod(target, 0o600)
source.unlink()
