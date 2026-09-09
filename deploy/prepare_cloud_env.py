"""从现有环境模板生成隔离的云端运行配置。

企业受控 UNC 根目录属于部署策略，不是云服务器上的挂载点。云端即使无法访问
这些共享目录，也必须保留管理员明确提供的白名单，供路径字段执行纯字符串校验。
"""

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


PATH_POLICY_KEYS = (
    "VITE_OPENPATH_ALLOWED_ROOTS",
    "OPENPATH_ALLOWED_ROOTS",
)


def prepare_cloud_env(
    source: Path = Path(".env.source"),
    target: Path = Path(".env"),
) -> dict[str, str]:
    values = read_env(source)
    path_policy = {key: values.get(key, "") for key in PATH_POLICY_KEYS}
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
            **path_policy,
        }
    )

    target.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
    os.chmod(target, 0o600)
    source.unlink()
    return values


if __name__ == "__main__":
    prepare_cloud_env()
