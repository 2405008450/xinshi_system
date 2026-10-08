"""调试机隔离PostgreSQL实例：迁移、行锁与公司管理事务验收，不连接业务数据库。"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机隔离验证目录运行')
    pg_bin = Path(r'C:\Program Files\PostgreSQL\18\bin')
    output_root = ROOT / '.tmp' / 'company-postgres'
    output_root.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix='pg-', dir=output_root))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    def command(*args):
        # pg_ctl启动的子进程可能继承管道句柄；使用文件避免communicate等待后台进程关闭管道。
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=90)
            output.seek(0)
            result.stdout = output.read()
        if result.returncode:
            print(result.stdout.decode('utf-8', errors='replace'))
            result.check_returncode()
        return result
    # initdb会移除管理员组权限，给当前用户SID显式授权，仅限本次临时数据目录。
    identity = command('whoami.exe').stdout.decode('utf-8').strip()
    command('icacls.exe', data, '/grant', f'{identity}:(OI)(CI)F')
    command(pg_bin / 'initdb.exe', '-D', data, '-U', 'material_test', '--auth=trust', '--encoding=UTF8', '--locale=C')
    command(pg_bin / 'pg_ctl.exe', '-D', data, '-l', data / 'server.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
    try:
        environment = {**os.environ, 'DATABASE_URL': 'sqlite://',
                       'SECRET_KEY': 'isolated-material-test-signing-key-not-for-production', 'PYTHONIOENCODING': 'utf-8',
                       'COMPANY_TEST_DATABASE_URL': f'postgresql+psycopg2://material_test@127.0.0.1:{port}/postgres'}
        with (ROOT / 'company-management-postgres-results.log').open('w', encoding='utf-8') as output:
            result = subprocess.run([r'E:\xinshi_system\.venv\Scripts\python.exe', '-m', 'pytest', 'tests/test_company_management.py', '-q', '--disable-warnings', '--maxfail=3'], cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
        print((ROOT / 'company-management-postgres-results.log').read_text(encoding='utf-8'))
        return result.returncode
    finally:
        command(pg_bin / 'pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop')


if __name__ == '__main__':
    sys.exit(run())
