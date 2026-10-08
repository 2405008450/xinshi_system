"""在本机隔离源码/临时 PostgreSQL 中验收企微大群，绝不加载业务库。"""

import json
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON = r"E:\xinshi_system\.venv\Scripts\python.exe"


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', action='append', choices=['backend', 'frontend', 'build', 'ui'])
    suites = parser.parse_args().suite or ['backend', 'frontend', 'build', 'ui']
    if socket.gethostname().upper() != "PC" or "xinshi_validation" not in str(ROOT):
        raise SystemExit("只能在本机 xinshi_validation 隔离目录运行")
    pg_bin = Path(r"C:\Program Files\PostgreSQL\18\bin")
    data = Path(tempfile.mkdtemp(prefix="wecom-pg-", dir=ROOT))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    def command(*args):
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(list(map(str, args)), cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=120)
            output.seek(0)
            result.stdout = output.read()
        if result.returncode:
            print(result.stdout.decode("utf-8", errors="replace"))
            result.check_returncode()
        return result

    identity = command("whoami.exe").stdout.decode("utf-8").strip()
    command("icacls.exe", data, "/grant", f"{identity}:(OI)(CI)F")
    command(pg_bin / "initdb.exe", "-D", data, "-U", "wecom_test", "--auth=trust", "--encoding=UTF8", "--locale=C")
    command(pg_bin / "pg_ctl.exe", "-D", data, "-l", data / "server.log", "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
    try:
        environment = {**os.environ, "DATABASE_URL": f"postgresql+psycopg2://wecom_test@127.0.0.1:{port}/postgres",
                       "SECRET_KEY": "isolated-wecom-test-key-not-for-production", "PYTHONIOENCODING": "utf-8",
                       "RUN_TALENT_OVERVIEW_WECOM_DB_TESTS": "1", "XINSHI_POOL_DB_TEST": "1"}
        results = []
        for name, args, cwd in [
            ("prepare", [PYTHON, "tools/verify_talent_overview_wecom_ui.py", "--prepare"], ROOT),
            ("backend", [PYTHON, "-m", "pytest", "tests/test_talent_overview_wecom.py", "tests/test_talent_overview.py", "tests/test_talent_pool_statistics.py", "-q", "--tb=short"], ROOT),
            ("frontend", ["node", "--test", "tests/talentOverview.test.mjs", "tests/talentOverviewWecom.test.mjs"], ROOT / "frontend"),
            ("build", ["npm.cmd", "run", "build"], ROOT / "frontend"),
            ("ui", [PYTHON, "tools/verify_talent_overview_wecom_ui.py"], ROOT),
        ]:
            if name != 'prepare' and name not in suites:
                continue
            log_path = ROOT / f"wecom-{name}.log"
            with log_path.open("wb") as output:
                completed = subprocess.run(args, cwd=cwd, env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=600,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
            result = {"suite": name, "exit_code": completed.returncode}
            results.append(result)
            print(json.dumps(result), flush=True)
            if completed.returncode:
                print(log_path.read_text(encoding="utf-8", errors="replace")[-18000:], flush=True)
                if name == "prepare":
                    break
        (ROOT / "wecom-validation-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        return int(any(row["exit_code"] for row in results))
    finally:
        command(pg_bin / "pg_ctl.exe", "-D", data, "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    sys.exit(run())
