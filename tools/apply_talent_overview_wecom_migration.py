"""本机企微群增量迁移：先在仓库外备份现有概览，再创建独立表。"""

import json
import socket
import sys
from datetime import datetime
from pathlib import Path


def run():
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "PC" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在本机 E:\\xinshi_system 执行")
    sys.path.insert(0, str(root))
    from database import engine
    if engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("只允许迁移本机数据库")
    backup = Path(r"E:\xinshi_runtime\backups") / ("talent-overview-wecom-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as connection:
        snapshot = connection.exec_driver_sql("SELECT row_to_json(s) FROM talent_overview_snapshot s WHERE id = 1").scalar()
    backup.write_text(json.dumps({"snapshot": snapshot, "fixture": json.loads((root / "data/talent_overview.json").read_text(encoding="utf-8"))}, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    sql = (root / "data/migrations/20261008_talent_overview_wecom.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
    print(f"概览备份：{backup}")
    print("企微大群迁移完成（可重复执行）")


if __name__ == "__main__":
    run()
