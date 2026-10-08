"""资源小红书号增量迁移，仅允许在本机调试数据库执行。"""
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
        raise SystemExit("迁移仅允许连接本机数据库")
    sql = (root / "data/migrations/20261008_resource_development_xiaohongshu.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
    print("资源小红书号迁移完成（可重复执行）")


if __name__ == "__main__":
    run()
