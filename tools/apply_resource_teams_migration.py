"""团队资源显式迁移入口，仅允许本机数据库。"""
import socket
import subprocess
import sys
from pathlib import Path


def run():
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "PC" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在PC的 E:\\xinshi_system 执行")
    if Path(sys.executable).resolve() != root / ".venv/Scripts/python.exe":
        raise SystemExit("必须使用项目 .venv\\Scripts\\python.exe")
    sys.path.insert(0, str(root))
    from database import engine
    if engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("此迁移入口仅允许本机数据库，禁止迁移云端业务库")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    print(f"主机={socket.gethostname()} 项目={root} 提交={commit} 数据库={engine.url.host}:{engine.url.port}/{engine.url.database}")
    with engine.begin() as connection:
        for name in ("20261012_resource_teams.sql", "20261013_resource_team_contacts.sql", "20261013_resource_team_attachments.sql"):
            connection.exec_driver_sql((root / "data/migrations" / name).read_text(encoding="utf-8"))
    print("团队资源迁移完成（可重复执行）")


if __name__ == "__main__":
    run()
