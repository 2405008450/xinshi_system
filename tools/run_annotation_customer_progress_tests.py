"""启动临时本机 PostgreSQL 验收客户进度，绝不读取业务数据库连接。"""

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
    scratch = ROOT / '.tmp' / ('customer-progress-pg-' + uuid4().hex)
    scratch.mkdir(parents=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    def command(args):
        with (scratch / 'control.log').open('w', encoding='utf-8') as output:
            result = subprocess.run(args, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
        if result.returncode:
            raise RuntimeError((scratch / 'control.log').read_text(encoding='utf-8', errors='replace'))
    data = scratch / 'data'
    command([str(binaries / 'initdb.exe'), '-D', str(data), '-U', 'customer_progress_test', '--auth=trust', '--encoding=UTF8', '--locale=C'])
    command([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-l', str(scratch / 'postgres.log'), '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'])
    url = f'postgresql+psycopg2://customer_progress_test@127.0.0.1:{port}/postgres'
    env = dict(os.environ, PYTHONUTF8='1', DATABASE_URL=url, CUSTOMER_PROGRESS_TEST_DATABASE_URL=url, LOCAL_SCHEMA_MIGRATIONS_ENABLED='false', SECRET_KEY='isolated-customer-progress-test-key')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
        print(f'主机 PC；项目 {ROOT}；Git {commit}；隔离库 127.0.0.1:{port}/postgres；输出 {scratch}', flush=True)
        with (scratch / 'pytest.log').open('w', encoding='utf-8') as output:
            result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'pytest', 'tests/test_annotation_customer_progress.py', 'tests/test_annotation_customer_progress_ui.py', '-q', '--tb=short', *sys.argv[1:]], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=300)
        print((scratch / 'pytest.log').read_text(encoding='utf-8', errors='replace'), flush=True)
        return result.returncode
    finally:
        command([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-m', 'fast', '-w', 'stop'])


if __name__ == '__main__':
    raise SystemExit(run())
