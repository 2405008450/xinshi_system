"""仅在局域网项目执行增量迁移，不修改现有业务记录。"""
import socket
import sys
from pathlib import Path


def run():
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "WIN-LOLJ8UHT2G5" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在局域网调试机 E:\\xinshi_system 执行")
    sys.path.insert(0, str(root))
    from dotenv import load_dotenv
    load_dotenv(root / ".env")
    from database import engine
    from sqlalchemy import text
    sql = (root / "data/migrations/20261014_add_annotation_child_orders.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        before = connection.execute(text("SELECT count(*) FROM annotation_project")).scalar_one()
        connection.exec_driver_sql(sql)
        after = connection.execute(text("SELECT count(*) FROM annotation_project")).scalar_one()
        if before != after:
            raise RuntimeError("迁移前后记录数量发生变化，请检查")
        print(f"迁移完成，标注项目记录数量保持 {after} 条")


if __name__ == "__main__":
    run()
