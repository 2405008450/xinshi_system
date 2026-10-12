"""渠道管理迁移及回归：仅在本机临时 PostgreSQL 执行，不读写业务数据库。"""
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


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    if socket.gethostname().upper() != "PC" or str(ROOT).lower() != r"e:\xinshi_system":
        raise SystemExit("仅允许在本机运行")
    installed = shutil.which('initdb')
    candidates = ([Path(installed).parent] if installed else []) + sorted(Path(r'C:\Program Files\PostgreSQL').glob('*/bin'), reverse=True)
    pg_bin = next((p for p in candidates if (p / 'initdb.exe').is_file() and (p / 'pg_ctl.exe').is_file()), None)
    if pg_bin is None:
        raise SystemExit('缺少本机 PostgreSQL，禁止回退到业务数据库')
    out = ROOT / ".tmp" / "resource-channels-postgres"
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="pg-", dir=out))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]

    def command(*args, env=None, timeout=120):
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, creationflags=subprocess.CREATE_NO_WINDOW,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            output.seek(0); raw = output.read()
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("gbk", errors="replace")
        if content: print(content, flush=True)
        result.check_returncode()
        return content

    identity = subprocess.check_output(["whoami.exe"]).decode().strip()
    command("icacls.exe", data, "/grant", f"{identity}:(OI)(CI)F")
    command(pg_bin / "initdb.exe", "-D", data, "-U", "channel_test", "--auth=trust", "--encoding=UTF8", "--locale=C")
    command(pg_bin / "pg_ctl.exe", "-D", data, "-l", data / "server.log", "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
    try:
        env = dict(os.environ, DATABASE_URL=f"postgresql+psycopg2://channel_test@127.0.0.1:{port}/postgres",
                   SECRET_KEY=secrets.token_urlsafe(48), RUN_RESOURCE_DEVELOPMENT_DB_TESTS="1", PYTHONIOENCODING="utf-8")
        setup = """
import main
from models import Base
from database import engine
from sqlalchemy import text
from pathlib import Path
from sqlalchemy.orm import Session
from talent_overview_service import sync_overview_language_catalog, load_talent_overview_data
assert engine.url.host == '127.0.0.1' and engine.url.username == 'channel_test'
with engine.begin() as connection:
    connection.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    connection.execute(text('CREATE SEQUENCE IF NOT EXISTS chat_message_sequence'))
    connection.execute(text('''CREATE TABLE resource_development_option (
        id uuid PRIMARY KEY, kind varchar(20) NOT NULL, category varchar(20) NOT NULL DEFAULT '',
        name varchar(100) NOT NULL, code varchar(30) UNIQUE, description text NOT NULL DEFAULT '', revision integer NOT NULL DEFAULT 1,
        UNIQUE(kind,name))'''))
    connection.execute(text("INSERT INTO resource_development_option VALUES ('00000000-0000-0000-0000-000000000001','platform','national','历史平台','OLD','历史原说明',7)"))
tables = [table for table in Base.metadata.sorted_tables if table.name not in {'resource_development_channel_member', 'resource_channel_account_link'}]
Base.metadata.create_all(engine, tables=tables)
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    sql = Path('data/migrations/20261008_resource_channels.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(sql)
    connection.exec_driver_sql(sql)
    hierarchy = Path('data/migrations/20261012_resource_channel_accounts.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(hierarchy)
    connection.exec_driver_sql(hierarchy)
with engine.begin() as connection:
    row = connection.execute(text("SELECT name,category,code,description,revision,purpose,created_at,created_by FROM resource_development_option")).one()
    assert tuple(row) == ('历史平台','national','OLD','历史原说明',7,'',None,None)
    assert connection.execute(text('SELECT count(*) FROM resource_development_channel_member')).scalar() == 0
    assert connection.execute(text('SELECT count(*) FROM resource_channel_account_link')).scalar() == 0
    connection.execute(text(Path('data/migrations/20261011_auto_talent_resource_code.sql').read_text(encoding='utf-8')))
engine.dispose()
with Session(engine) as session:
    data = load_talent_overview_data()
    # 最小目录基线使用语种；避免旧 HTTP 用例默认 language 类型与首个方言冲突。
    sync_overview_language_catalog(session, {"rows": [row for row in data["rows"] if row["language"] == "英语"]})
    session.commit()
print('渠道迁移首次及重复执行通过；历史平台标识、说明、版本和空创建信息保留')
from tools.apply_resource_channel_accounts_migration import migrate_business_accounts
import tempfile
backup_root = Path(tempfile.mkdtemp(prefix='channel-migration-backup-'))
# 在隔离库验证显式迁移的备份、原数据校验及重复执行，不读取业务库。
migrate_business_accounts(engine, Path.cwd(), 'isolated-test', backup_root)
migrate_business_accounts(engine, Path.cwd(), 'isolated-test', backup_root)
"""
        command(sys.executable, "-c", setup, env=env)
        if '--ui-only' not in sys.argv:
            result = command(sys.executable, "-m", "pytest", "tests/test_resource_channels.py", "tests/test_resource_development.py",
                             "tests/test_resource_follow_up.py", "tests/test_resource_arrangements.py", "tests/test_resource_friend_daily.py",
                             "-q", "--tb=short", env=env, timeout=300)
            (out / "tests.log").write_text(result, encoding="utf-8")
        if '--ui' in sys.argv:
            command(sys.executable, '-c', UI_SEED, env=env)
            backend_port, frontend_port = free_port(), free_port()
            env.update(CHANNEL_RESOURCE_QA='1', PYTHONUTF8='1', LOCAL_SCHEMA_MIGRATIONS_ENABLED='false',
                       VITE_API_PROXY_TARGET=f'http://127.0.0.1:{backend_port}', CHANNEL_UI_BASE=f'http://localhost:{frontend_port}')
            children, logs = [], []
            try:
                for args, cwd, name in [
                    ([sys.executable, '-m', 'uvicorn', 'tools.channels_isolated_app:app', '--host', '127.0.0.1', '--port', str(backend_port)], ROOT, 'backend.log'),
                    (['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-channels-dist', '--host', '127.0.0.1', '--port', str(frontend_port), '--strictPort'], ROOT / 'frontend', 'frontend.log'),
                ]:
                    log = (out / name).open('w', encoding='utf-8'); logs.append(log)
                    children.append(subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
                for url in [f'http://127.0.0.1:{backend_port}/openapi.json', env['CHANNEL_UI_BASE']]:
                    for _ in range(100):
                        if any(process.poll() is not None for process in children):
                            raise RuntimeError('隔离进程已退出，请检查 backend.log 和 frontend.log')
                        try:
                            urlopen(url, timeout=1).close(); break
                        except Exception:
                            time.sleep(.2)
                    else:
                        raise RuntimeError(f'隔离服务未就绪：{url}')
                result = command(sys.executable, 'tools/verify_resource_channels_ui.py', env=env, timeout=300)
                (out / 'browser.log').write_text(result, encoding='utf-8')
            finally:
                for process in reversed(children):
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
                for log in logs: log.close()
    finally:
        command(pg_bin / "pg_ctl.exe", "-D", data, "-m", "fast", "-w", "stop")


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


UI_SEED = '''
import main
from uuid import UUID
from sqlalchemy.orm import Session
from database import engine
from models import AppUser
from resource_channel_schemas import ChannelWrite
from resource_channel_service import save_channel
assert engine.url.host == '127.0.0.1' and engine.url.username == 'channel_test'
with Session(engine) as db:
    people = [AppUser(id=UUID(int=i), username=f'channel_qa_{i}', full_name=name, is_active=True, password_hash='isolated-no-login')
              for i, name in [(101,'验收维护人'),(102,'验收使用人'),(103,'第二维护人')]]
    db.add_all(people); db.flush()
    def save(name, **fields):
        return save_channel(db, people[0], ChannelWrite(name=name, category='national', **fields))
    one = save('验收BOSS 1', description='账号独立原说明', maintainer_ids=[people[0].id], user_ids=[people[1].id])
    two = save('验收BOSS 2', maintainer_ids=[people[0].id, people[2].id], user_ids=[people[1].id])
    save('验收BOSS直聘', is_group=True, description='平台情况说明第一行\\n第二行\\n' * 100, account_ids=[one['id'],two['id']], account_revisions={one['id']:1,two['id']:1})
    save('验收智联', is_group=True)
    save('验收独立账号', maintainer_ids=[people[2].id])
    for i in range(21): save(f'验收平台{i:02d}')
    db.commit()
print('隔离浏览器数据已准备；原业务库未访问')
'''


if __name__ == "__main__":
    run()
