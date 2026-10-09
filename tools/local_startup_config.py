"""输出启动检查所需的非敏感配置；不导入应用、不连接数据库。"""

import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def startup_config(values):
    if values.get("DATABASE_URL"):
        url = make_url(values["DATABASE_URL"])
    else:
        if not values.get("DB_PASSWORD"):
            raise ValueError("未配置 DB_PASSWORD 或 DATABASE_URL")
        url = URL.create(
            "postgresql+psycopg2",
            host=values.get("DB_HOST", "localhost"),
            port=int(values.get("DB_PORT", "5432")),
            database=values.get("DB_NAME", "xinshi_system"),
        )
    if values.get("LOCAL_SCHEMA_MIGRATIONS_ENABLED", "false").strip().lower() in {"1", "true", "yes"}:
        raise ValueError("常驻服务必须关闭 LOCAL_SCHEMA_MIGRATIONS_ENABLED；迁移请单独执行")
    return {
        "python": sys.executable,
        "database_driver": url.drivername,
        "database_host": url.host or "(本地文件/内存)",
        "database_port": url.port or (5432 if url.drivername.startswith("postgresql") else None),
        "database_name": url.database,
        "app_env": values.get("APP_ENV", "development"),
        "share_paths": [p.strip() for p in values.get("OPENPATH_ALLOWED_ROOTS", "").split(";") if p.strip()]
        or [r"\\Win-server\服务器资料7", r"\\Win-server\服务器资料4"],
    }


def main():
    # Windows 重定向默认编码可能是 GBK，固定 UTF-8 防止中文错误消息乱码。
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        # 与 database.py 一致：进程环境变量优先于根目录 .env。
        values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
        result = startup_config(values)
    except Exception:
        # URL 解析错误可能包含凭据，因此不能输出原始异常。
        print("启动配置无效：请检查数据库配置，并关闭 LOCAL_SCHEMA_MIGRATIONS_ENABLED。", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
