"""在本机临时 PostgreSQL 验收迁移和回归；绝不使用默认业务库。"""
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机运行')
    initdb = shutil.which('initdb')
    candidates = [Path(initdb).parent] if initdb else []
    candidates.extend(sorted(Path(r'C:\Program Files\PostgreSQL').glob('*/bin'), reverse=True))
    pg_bin = next((p for p in candidates if (p/'initdb.exe').is_file() and (p/'pg_ctl.exe').is_file()), None)
    if pg_bin is None:
        raise SystemExit('本机缺少 PostgreSQL 验收工具，不能回退到业务数据库')
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
from models import Base, AppUser
from database import engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from pathlib import Path
from uuid import uuid4
from resource_development_models import DevelopmentOption
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
with Session(engine) as session:
    actor=AppUser(id=uuid4(),username='migration_smoke',password_hash='test-no-login',is_active=True)
    platform=DevelopmentOption(id=uuid4(),kind='platform',category='national',name='迁移验证账号')
    session.add_all([actor,platform]); session.flush()
    actor_id,platform_id=actor.id,platform.id
    day_id=session.execute(text('INSERT INTO resource_development_arrangement(work_date,created_by,updated_by) VALUES (:day,:actor,:actor) RETURNING id'),dict(day='2020-01-01',actor=actor_id)).scalar_one()
    session.execute(text("INSERT INTO resource_development_arrangement_cell(arrangement_id,platform_id,platform_name,owner_id,owner_name,remarks,completed,completed_by,completed_at) VALUES (:day,:platform,'迁移验证账号',:actor,'历史负责人','历史备注',true,:actor,CURRENT_TIMESTAMP)"),dict(day=day_id,platform=platform_id,actor=actor_id))
    session.commit()
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    roles_sql=Path('data/migrations/20261009_resource_arrangement_roles.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(roles_sql)
    connection.exec_driver_sql(roles_sql)
with engine.begin() as connection:
    row=connection.execute(text('SELECT role_tags,completed,owner_name,remarks FROM resource_development_arrangement_cell WHERE arrangement_id=:day'),dict(day=day_id)).one()
    assert tuple(row)==([],True,'历史负责人','历史备注'),row
    connection.execute(text('DELETE FROM resource_development_arrangement WHERE id=:day'),dict(day=day_id))
    connection.execute(text('DELETE FROM resource_development_option WHERE id=:platform'),dict(platform=platform_id))
    connection.execute(text('DELETE FROM app_user WHERE id=:actor'),dict(actor=actor_id))
    connection.execute(text(Path('data/migrations/20261011_auto_talent_resource_code.sql').read_text(encoding='utf-8')))
engine.dispose()
print('每日安排及岗位目标迁移首次执行及重复执行通过')
"""
        command(sys.executable,'-c',setup,env=env)
        results = command(sys.executable,'-m','pytest','tests/test_resource_arrangements.py','tests/test_resource_development.py',
                          'tests/test_resource_follow_up.py','tests/test_resource_request_daily_notes.py','-q','--tb=short',env=env,timeout=300)
        (out/'tests.log').write_text(results,encoding='utf-8')
    finally:
        command(pg_bin/'pg_ctl.exe','-D',data,'-m','fast','-w','stop')


if __name__ == '__main__':
    run()
