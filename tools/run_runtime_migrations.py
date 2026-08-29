"""在维护窗口显式执行历史运行时迁移。常驻 API 进程不会调用本模块。"""

import os


def main() -> None:
    if os.getenv("RUN_STARTUP_SCHEMA_MIGRATIONS", "").strip().lower() not in {"1", "true", "yes"}:
        raise RuntimeError("必须显式设置 RUN_STARTUP_SCHEMA_MIGRATIONS=true")

    from main import ensure_runtime_tables

    ensure_runtime_tables()


if __name__ == "__main__":
    main()
