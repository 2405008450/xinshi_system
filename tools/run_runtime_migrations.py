"""仅从本地开发环境显式执行历史运行时迁移。

常驻 API 进程不会调用本模块，云端部署也不提供迁移服务。
"""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

_TRUE_VALUES = {"1", "true", "yes"}


def require_local_migration_environment() -> None:
    """同时验证本地开发环境和一次性迁移授权。"""
    app_env = os.getenv("APP_ENV", "").strip().lower()
    migration_enabled = (
        os.getenv("LOCAL_SCHEMA_MIGRATIONS_ENABLED", "").strip().lower()
        in _TRUE_VALUES
    )
    if app_env != "development":
        raise RuntimeError(
            "数据库迁移只允许在 APP_ENV=development 的本地开发环境执行"
        )
    if not migration_enabled:
        raise RuntimeError(
            "必须在本地显式设置 LOCAL_SCHEMA_MIGRATIONS_ENABLED=true"
        )


def main() -> None:
    require_local_migration_environment()

    from main import run_runtime_migrations

    run_runtime_migrations()


if __name__ == "__main__":
    main()
