"""在本机临时 PostgreSQL 验收迁移和回归；绝不使用默认业务库。"""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机运行')
    pg_bin = Path(r'C:\Program Files\PostgreSQL\18\bin')
    out = ROOT / '.tmp' / 'resource-arrangements-postgres'
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix='pg-', dir=out))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); port = probe.getsockname()[1]

    def command(*args, env=None, timeout=120):
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, creationflags=subprocess.CREATE_NO_WINDOW,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            output.seek(0); raw = output.read()
            try:
                content = raw.decode('utf-8')
            except UnicodeDecodeError:
                content = raw.decode('gbk',errors='replace')
        if content: print(content,flush=True)
        result.check_returncode()
        return content

    identity = subprocess.check_output(['whoami.exe']).decode().strip()
    command('icacls.exe',data,'/grant',f'{identity}:(OI)(CI)F')
    command(pg_bin/'initdb.exe','-D',data,'-U','arrangement_test','--auth=trust','--encoding=UTF8','--locale=C')
    command(pg_bin/'pg_ctl.exe','-D',data,'-l',data/'server.log','-o',f'-h 127.0.0.1 -p {port}','-w','start')
    try:
        env = dict(os.environ,DATABASE_URL=f'postgresql+psycopg2://arrangement_test@127.0.0.1:{port}/postgres',
                   SECRET_KEY=secrets.token_urlsafe(48),RUN_RESOURCE_DEVELOPMENT_DB_TESTS='1',PYTHONIOENCODING='utf-8')
        setup = """
import main
from models import Base
from database import engine
from sqlalchemy import text
from pathlib import Path
assert engine.url.host == '127.0.0.1' and engine.url.username == 'arrangement_test'
with engine.begin() as connection:
    connection.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    connection.execute(text('CREATE SEQUENCE IF NOT EXISTS chat_message_sequence'))
tables=[t for t in Base.metadata.sorted_tables if not t.name.startswith('resource_development_arrangement')]
Base.metadata.create_all(engine,tables=tables)
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    sql=Path('data/migrations/20261008_resource_development_arrangements.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(sql)
    connection.exec_driver_sql(sql)
with engine.begin() as connection:
    connection.execute(text(Path('data/migrations/20261011_auto_talent_resource_code.sql').read_text(encoding='utf-8')))
engine.dispose()
print('每日安排迁移首次执行及重复执行通过')
"""
        command(sys.executable,'-c',setup,env=env)
        results = command(sys.executable,'-m','pytest','tests/test_resource_arrangements.py','tests/test_resource_development.py',
                          'tests/test_resource_follow_up.py','tests/test_resource_request_daily_notes.py','-q','--tb=short',env=env,timeout=300)
        (out/'tests.log').write_text(results,encoding='utf-8')
    finally:
        command(pg_bin/'pg_ctl.exe','-D',data,'-m','fast','-w','stop')


if __name__ == '__main__':
    run()
