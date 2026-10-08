"""仅在局域网项目、本机数据库执行每日安排增量迁移。"""
import socket
import sys
from pathlib import Path


def run():
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "PC" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在本机 E:\\xinshi_system 执行")
    sys.path.insert(0, str(root))
    from database import engine
    if engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("每日安排迁移只允许使用本机数据库")
    sql = (root / "data/migrations/20261008_resource_development_arrangements.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
    print("每日安排迁移完成（可重复执行）")


if __name__ == "__main__":
    run()
