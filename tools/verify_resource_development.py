"""局域网调试机的迁移/回归入口，不连接生产环境。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()
    if socket.gethostname().upper() != "WIN-LOLJ8UHT2G5" or ROOT != Path(r"E:\xinshi_system"):
        raise SystemExit("仅允许在已核验的局域网调试机项目目录执行")
    from database import engine
    if args.migrate:
        from sqlalchemy import text
        sql = (ROOT / "data/migrations/20260924_resource_development.sql").read_text(encoding="utf-8")
        sql = sql.replace("BEGIN;", "").replace("COMMIT;", "")
        with engine.begin() as conn:
            conn.execute(text(sql))
        print("资源开拓迁移完成")
    env = dict(os.environ, RUN_RESOURCE_DEVELOPMENT_DB_TESTS="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_resource_development.py", "tests/test_resource_talents.py", "tests/test_talent_wechat_account.py", "-q", "--tb=short"], cwd=ROOT, env=env)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
