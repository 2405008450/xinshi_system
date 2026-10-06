"""局域网公司管理增量迁移。"""
import socket
import sys
from pathlib import Path

def run():
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "WIN-LOLJ8UHT2G5" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在局域网调试机 E:\\xinshi_system 执行")
    sys.path.insert(0, str(root))
    from database import engine
    sql = (root / "data/migrations/20261006_add_company_management.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
    print("公司管理迁移完成（可重复执行）")

if __name__ == "__main__":
    run()