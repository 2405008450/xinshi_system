"""本机文字跟进增量迁移，可重复执行。"""
import socket
import sys
from pathlib import Path


def run():
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "PC" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在本机 E:\\xinshi_system 执行")
    sys.path.insert(0, str(root))
    from database import engine
    sql = (root / "data/migrations/20261008_resource_development_follow_up.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
    print("文字跟进迁移完成（可重复执行）")


if __name__ == "__main__":
    run()
