"""启动独立临时 PostgreSQL，只在本机测试聊天迁移与功能。"""
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在 PC 的 E:\\xinshi_system 验收')
    binaries = Path(r'C:\Program Files\PostgreSQL\17\bin')
    scratch = ROOT / '.tmp' / ('chat-pg-' + uuid4().hex)
    scratch.mkdir(parents=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    def command(args):
        with (scratch / 'control.log').open('w', encoding='utf-8') as output:
            result = subprocess.run(args, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        if result.returncode:
            raise RuntimeError((scratch / 'control.log').read_text(encoding='utf-8', errors='replace'))
    data = scratch / 'data'
    command([str(binaries / 'initdb.exe'), '-D', str(data), '-U', 'chat_test', '--auth=trust', '--encoding=UTF8', '--locale=C'])
    command([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-l', str(scratch / 'postgres.log'), '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'])
    env = dict(os.environ, PYTHONUTF8='1', DATABASE_URL=f'postgresql+psycopg2://chat_test@127.0.0.1:{port}/postgres',
        CHAT_TEST_DATABASE_URL=f'postgresql+psycopg2://chat_test@127.0.0.1:{port}/postgres', LOCAL_SCHEMA_MIGRATIONS_ENABLED='false', RUN_ANNOTATION_CHAT_DB_TESTS='1')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
        print(f'主机 PC；项目 {ROOT}；Git {commit}；隔离库 127.0.0.1:{port}/postgres；输出 {scratch}', flush=True)
        bootstrap = "import main; from database import engine; from models import Base; from sqlalchemy import text; c=engine.connect(); c.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm')); c.execute(text('CREATE SEQUENCE chat_message_sequence')); c.commit(); c.close(); Base.metadata.create_all(engine)"
        subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-c', bootstrap], cwd=ROOT, env=env, check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        with (scratch / 'pytest.log').open('w', encoding='utf-8') as output:
            result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'pytest', 'tests/test_chat_phase_one.py', 'tests/test_annotation_open_chat.py', 'tests/test_annotation_project_chat.py', 'tests/test_chat_history_search.py', 'tests/test_chat_attachment_storage.py', '-q', '--tb=short', *sys.argv[1:]], cwd=ROOT, env=env,
                stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=300)
        print((scratch / 'pytest.log').read_text(encoding='utf-8', errors='replace'), flush=True)
        return result.returncode
    finally:
        command([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-m', 'fast', '-w', 'stop'])


if __name__ == '__main__':
    raise SystemExit(run())
