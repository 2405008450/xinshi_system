"""在调试机的临时 PostgreSQL 中验收资源开拓，绝不读取默认业务数据库配置。"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机运行')
    pg_bin = Path(r'C:\Program Files\PostgreSQL\18\bin')
    output_root = ROOT / '.tmp' / 'resource-status-postgres'
    output_root.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix='pg-', dir=output_root))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]

    def command(*args, env=None, timeout=90):
        # 使用文件承接输出，避免 PostgreSQL 子进程继承 SSH 管道。
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            output.seek(0)
            result.stdout = output.read()
        if result.returncode:
            print(result.stdout.decode('utf-8', errors='replace'))
            result.check_returncode()
        return result

    identity = command('whoami.exe').stdout.decode('utf-8').strip()
    command('icacls.exe', data, '/grant', f'{identity}:(OI)(CI)F')
    command(pg_bin / 'initdb.exe', '-D', data, '-U', 'resource_status_test', '--auth=trust', '--encoding=UTF8', '--locale=C')
    command(pg_bin / 'pg_ctl.exe', '-D', data, '-l', data / 'server.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
    try:
        environment = {**os.environ,
            'DATABASE_URL': f'postgresql+psycopg2://resource_status_test@127.0.0.1:{port}/postgres',
            'SECRET_KEY': 'isolated-resource-status-signing-key-not-for-production',
            'RUN_RESOURCE_DEVELOPMENT_DB_TESTS': '1', 'PYTHONIOENCODING': 'utf-8'}
        # 仅初始化临时库；编号触发器属于现有基础能力，不调用应用启动事件。
        setup = """
import main
from models import Base
from database import engine
from sqlalchemy import text
from pathlib import Path
assert engine.url.host == '127.0.0.1' and engine.url.username == 'resource_status_test'
with engine.begin() as connection:
    connection.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    connection.execute(text('CREATE SEQUENCE IF NOT EXISTS chat_message_sequence'))
Base.metadata.create_all(engine)
with engine.begin() as connection:
    connection.execute(text(Path('data/migrations/20261011_auto_talent_resource_code.sql').read_text(encoding='utf-8')))
engine.dispose()
"""
        command(sys.executable, '-c', setup, env=environment)
        log = output_root / 'tests.log'
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run([sys.executable, '-m', 'pytest', '.tmp/test_resource_status_acceptance_current.py', '-q', '--tb=short'],
                cwd=ROOT, env=environment, creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=output, stderr=subprocess.STDOUT, timeout=300)
        print(log.read_text(encoding='utf-8'))
        return result.returncode
    finally:
        command(pg_bin / 'pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop')


if __name__ == '__main__':
    sys.exit(run())
