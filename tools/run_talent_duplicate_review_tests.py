"""启动独立本机 PostgreSQL 测试实例，绝不读取或连接业务数据库目标。"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != "PC" or ROOT != Path(r"E:\xinshi_system"):
        raise SystemExit("仅允许在 PC 的 E:\\xinshi_system 使用隔离数据库验收")
    python = ROOT / ".venv/Scripts/python.exe"
    binaries = Path(r"C:\Program Files\PostgreSQL\17\bin")
    scratch = ROOT / ".tmp" / ("talent-review-pg-" + uuid4().hex)
    scratch.mkdir(parents=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    def command(args):
        # Windows 后台 postgres 会继承管道，pg_ctl 已退出也可能让 communicate 永久等待。
        log_path = scratch / "control.log"
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags, timeout=60)
        if result.returncode:
            raise RuntimeError(log_path.read_text(encoding="utf-8", errors="replace"))
        return result
    data = scratch / "data"
    command([str(binaries / "initdb.exe"), "-D", str(data), "-U", "review_test", "--auth=trust", "--encoding=UTF8", "--locale=C"])
    command([str(binaries / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"])
    env = dict(os.environ, PYTHONUTF8="1", TALENT_DUPLICATE_TEST_DATABASE_URL=f"postgresql+psycopg2://review_test@127.0.0.1:{port}/postgres")
    try:
        print(json.dumps({"host": socket.gethostname(), "project": str(ROOT), "database": f"127.0.0.1:{port}/postgres（临时独立实例）", "artifacts": str(scratch)}, ensure_ascii=False), flush=True)
        test_log = scratch / "pytest.log"
        with test_log.open("w", encoding="utf-8") as output:
            result = subprocess.run([str(python), "-m", "pytest", "tests/test_talent_duplicate_review.py", "-q", *sys.argv[1:]], cwd=ROOT, env=env, creationflags=flags, stdout=output, stderr=subprocess.STDOUT)
        print(test_log.read_text(encoding="utf-8", errors="replace"), flush=True)
        return result.returncode
    finally:
        command([str(binaries / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"])


if __name__ == "__main__":
    raise SystemExit(run())
