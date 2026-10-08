"""渠道管理迁移及回归：仅在本机临时 PostgreSQL 执行，不读写业务数据库。"""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != "PC" or str(ROOT).lower() != r"e:\xinshi_system":
        raise SystemExit("仅允许在本机运行")
    pg_bin = Path(r"C:\Program Files\PostgreSQL\18\bin")
    out = ROOT / ".tmp" / "resource-channels-postgres"
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="pg-", dir=out))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]

    def command(*args, env=None, timeout=120):
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, creationflags=subprocess.CREATE_NO_WINDOW,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            output.seek(0); content = output.read().decode("utf-8", errors="replace")
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
tables = [table for table in Base.metadata.sorted_tables if table.name != 'resource_development_channel_member']
Base.metadata.create_all(engine, tables=tables)
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    sql = Path('data/migrations/20261008_resource_channels.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(sql)
    connection.exec_driver_sql(sql)
with engine.begin() as connection:
    row = connection.execute(text("SELECT name,category,code,description,revision,purpose,created_at,created_by FROM resource_development_option")).one()
    assert tuple(row) == ('历史平台','national','OLD','历史原说明',7,'',None,None)
    assert connection.execute(text('SELECT count(*) FROM resource_development_channel_member')).scalar() == 0
    connection.execute(text(Path('data/migrations/20261011_auto_talent_resource_code.sql').read_text(encoding='utf-8')))
engine.dispose()
with Session(engine) as session:
    data = load_talent_overview_data()
    # 最小目录基线使用语种；避免旧 HTTP 用例默认 language 类型与首个方言冲突。
    sync_overview_language_catalog(session, {"rows": [row for row in data["rows"] if row["language"] == "英语"]})
    session.commit()
print('渠道迁移首次及重复执行通过；历史平台标识、说明、版本和空创建信息保留')
"""
        command(sys.executable, "-c", setup, env=env)
        result = command(sys.executable, "-m", "pytest", "tests/test_resource_channels.py", "tests/test_resource_development.py",
                         "tests/test_resource_follow_up.py", "tests/test_resource_arrangements.py", "tests/test_resource_friend_daily.py",
                         "-q", "--tb=short", env=env, timeout=300)
        (out / "tests.log").write_text(result, encoding="utf-8")
    finally:
        command(pg_bin / "pg_ctl.exe", "-D", data, "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    run()
