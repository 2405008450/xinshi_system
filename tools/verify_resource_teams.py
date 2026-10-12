"""团队迁移、后端回归与真实浏览器联调，全部使用临时本机PostgreSQL。"""
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def available_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    if socket.gethostname().upper() != "PC" or str(ROOT).lower() != r"e:\xinshi_system" or Path(sys.executable).resolve() != ROOT / ".venv/Scripts/python.exe":
        raise SystemExit("仅允许PC使用项目虚拟环境执行")
    binary = shutil.which("pg_ctl.exe")
    if not binary:
        raise SystemExit("未找到本机PostgreSQL，请安装后重新验收")
    pg = Path(binary).parent
    output = ROOT / ".tmp/resource-teams-qa"
    output.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="postgres-", dir=output))
    pg_port, backend_port, frontend_port = [available_port() for _ in range(3)]
    flags = subprocess.CREATE_NO_WINDOW
    children, logs = [], []

    def command(*args, env=None, log_name=None, timeout=180):
        log_path = output / (log_name or "command.log")
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, creationflags=flags, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        content = log_path.read_text(encoding="utf-8", errors="replace")
        if result.returncode:
            print(content, flush=True)
        result.check_returncode()
        return content

    def start(args, env, cwd, log_name):
        log = (output / log_name).open("w", encoding="utf-8"); logs.append(log)
        process = subprocess.Popen([str(arg) for arg in args], cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        children.append(process)
        return process

    def ready(url):
        for _ in range(100):
            try:
                urlopen(url, timeout=1).close()
                return
            except Exception:
                time.sleep(.2)
        raise RuntimeError(f"隔离服务未就绪：{url}")

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    print(f"主机=PC 项目={ROOT} 提交={commit} 数据库=127.0.0.1:{pg_port}/teams_test（临时独立实例）", flush=True)
    identity = subprocess.check_output(["whoami.exe"]).decode().strip()
    command("icacls.exe", data, "/grant", f"{identity}:(OI)(CI)F", log_name="permissions.log")
    command(pg / "initdb.exe", "-D", data, "-U", "team_test", "--auth=trust", "--encoding=UTF8", "--locale=C", log_name="initdb.log")
    command(pg / "pg_ctl.exe", "-D", data, "-l", data / "postgres.log", "-o", f"-h 127.0.0.1 -p {pg_port}", "-w", "start", log_name="postgres-start.log")
    env = dict(os.environ, DATABASE_URL=f"postgresql+psycopg2://team_test@127.0.0.1:{pg_port}/teams_test", SECRET_KEY=secrets.token_urlsafe(48),
               PYTHONUTF8="1", RUN_TEAM_RESOURCE_DB_TESTS="1", TEAM_RESOURCE_QA="1", LOCAL_SCHEMA_MIGRATIONS_ENABLED="false",
               VITE_API_PROXY_TARGET=f"http://127.0.0.1:{backend_port}", TEAM_UI_BASE=f"http://localhost:{frontend_port}")
    try:
        command(pg / "createdb.exe", "-h", "127.0.0.1", "-p", pg_port, "-U", "team_test", "teams_test", log_name="createdb.log")
        setup = '''
import main
from pathlib import Path
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import engine
from models import AppUser
from team_resource_schemas import TeamWrite
from team_resource_service import save_team
assert engine.url.host == '127.0.0.1' and engine.url.database == 'teams_test'
AppUser.__table__.create(engine)
sql = Path('data/migrations/20261012_resource_teams.sql').read_text(encoding='utf-8')
with engine.begin() as connection:
    connection.exec_driver_sql(sql)
with Session(engine) as db:
    people = [AppUser(id=UUID(int=i), username=f'team_qa_{i}', full_name=name, is_active=active, password_hash='isolated-no-login')
              for i, name, active in [(101,'验收对接人',True),(102,'只读验收人',True),(103,'其他跟进人',True),(104,'历史停用人',False)]]
    db.add_all(people); db.flush()
    for i in range(24):
        row = save_team(db, people[0], TeamWrite(short_name=f'验收团队{i:02d}', full_name=f'验收公司全称{i:02d}', team_type='small_team', resource_types=['annotation','interpretation'],
                          contact_user_id=people[0].id, follow_up_user_id=people[2].id, contact_date='2026-10-12', introduction='团队介绍第一行\\n第二行', resource_situation='资源能力与规模\\n' * 120))
    db.commit()
with engine.begin() as connection:
    connection.exec_driver_sql(sql)
    assert connection.execute(text('SELECT count(*) FROM resource_team')).scalar() == 24
    assert connection.execute(text('SELECT count(*) FROM resource_team_audit')).scalar() == 24
print('迁移首次与重复执行通过，既有团队及审计保留')
'''
        print(command(sys.executable, "-c", setup, env=env, log_name="migration.log"), flush=True)
        if "--ui-only" not in sys.argv:
            print(command(sys.executable, "-m", "pytest", "tests/test_team_resources.py", "tests/test_talent_pool_statistics.py", "tests/test_talent_list_query.py", "-q", "--tb=short", env=env, log_name="pytest.log"), flush=True)
        start([sys.executable, "-m", "uvicorn", "tools.teams_isolated_app:app", "--host", "127.0.0.1", "--port", backend_port], env, ROOT, "backend.log")
        ready(f"http://127.0.0.1:{backend_port}/openapi.json")
        start(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", frontend_port, "--strictPort"], env, ROOT / "frontend", "frontend.log")
        ready(env["TEAM_UI_BASE"])
        print(command(sys.executable, "tools/verify_resource_teams_ui.py", env=env, log_name="browser.log", timeout=300), flush=True)
        print(f"团队资源隔离验收通过，报告与截图：{output}", flush=True)
    finally:
        for process in reversed(children):
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        for log in logs: log.close()
        command(pg / "pg_ctl.exe", "-D", data, "-m", "fast", "-w", "stop", log_name="postgres-stop.log")


if __name__ == "__main__":
    run()
