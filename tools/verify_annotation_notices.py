"""创建临时 PostgreSQL，验证附件并可运行真实构建的浏览器验收。"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在 PC 的项目目录运行隔离验收')
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT).decode().strip()
    print(f'PC | {ROOT} | Git {commit} | 数据库：本次临时 127.0.0.1/notices_test', flush=True)
    pg_bin = Path(r'C:\Program Files\PostgreSQL\17\bin')
    if not (pg_bin / 'initdb.exe').is_file():
        raise SystemExit('缺少本机 PostgreSQL，禁止回退到业务库')
    project_notices = '--projects' in sys.argv
    output = ROOT / '.tmp' / ('project-notices-qa' if project_notices else 'annotation-notices-qa')
    output.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix='pg-', dir=output))
    def port():
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            return probe.getsockname()[1]
    pg_port, ui_port = port(), port()
    def command(*args):
        with tempfile.TemporaryFile() as log:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=90)
            log.seek(0)
            content = log.read().decode('utf-8', errors='replace')
        if result.returncode:
            print(content)
            result.check_returncode()
        return content
    identity = command('whoami.exe').strip()
    command('icacls.exe', data, '/grant', f'{identity}:(OI)(CI)F')
    command(pg_bin / 'initdb.exe', '-D', data, '-U', 'notice_test', '--auth=trust', '--encoding=UTF8', '--locale=C')
    command(pg_bin / 'pg_ctl.exe', '-D', data, '-l', data / 'server.log', '-o', f'-h 127.0.0.1 -p {pg_port}', '-w', 'start')
    server = None
    try:
        command(pg_bin / 'createdb.exe', '-h', '127.0.0.1', '-p', pg_port, '-U', 'notice_test', 'notices_test')
        url = f'postgresql+psycopg2://notice_test@127.0.0.1:{pg_port}/notices_test'
        env = {**os.environ, 'DATABASE_URL': 'sqlite://', 'LOCAL_SCHEMA_MIGRATIONS_ENABLED': 'false',
               'PYTHONIOENCODING': 'utf-8', 'NOTICE_TEST_DATABASE_URL': url, 'COMPANY_TEST_DATABASE_URL': url}
        python = ROOT / '.venv/Scripts/python.exe'
        if '--ui-only' not in sys.argv:
            with (output / 'pytest.log').open('w', encoding='utf-8') as log:
                tests = subprocess.run([str(python), '-m', 'pytest', 'tests/test_annotation_notice_attachments.py',
                    'tests/test_annotation_notices.py', 'tests/test_company_management.py', 'tests/test_company_management_time.py',
                    *(['tests/test_project_notices.py'] if project_notices else []),
                    '-q', '--disable-warnings', '--maxfail=3'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            print((output / 'pytest.log').read_text(encoding='utf-8'), flush=True)
            if tests.returncode:
                return tests.returncode
        if '--ui' in sys.argv or '--ui-only' in sys.argv:
            env.update(DATABASE_URL=url, ANNOTATION_NOTICES_QA='1',
                ANNOTATION_NOTICE_UPLOAD_DIR=str(output / 'notice-uploads'),
                COMPANY_MANAGEMENT_UPLOAD_DIR=str(output / 'company-uploads'),
                NOTICE_UI_BASE=f'http://localhost:{ui_port}', NOTICE_UI_OUTPUT=str(output))
            if project_notices:
                env.update(PROJECT_NOTICES_QA='1', PROJECT_NOTICE_UPLOAD_DIR=str(output / 'project-uploads'))
            with (output / 'server.log').open('w', encoding='utf-8') as log:
                app_module = 'tools.project_notices_isolated_app:app' if project_notices else 'tools.notices_isolated_app:app'
                server = subprocess.Popen([str(python), '-m', 'uvicorn', app_module,
                    '--host', '127.0.0.1', '--port', str(ui_port)], cwd=ROOT, env=env, stdout=log,
                    stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                for _ in range(100):
                    if server.poll() is not None:
                        print((output / 'server.log').read_text(encoding='utf-8'))
                        raise RuntimeError('隔离服务启动失败')
                    try:
                        urlopen(f'http://localhost:{ui_port}/', timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.2)
                with (output / 'ui.log').open('w', encoding='utf-8') as ui_log:
                    ui_script = 'tools/verify_project_notices_ui.py' if project_notices else 'tools/verify_annotation_notices_ui.py'
                    ui = subprocess.run([str(python), ui_script], cwd=ROOT, env=env,
                        stdout=ui_log, stderr=subprocess.STDOUT)
                print((output / 'ui.log').read_text(encoding='utf-8'), flush=True)
                return ui.returncode
        return 0
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            server.wait(timeout=15)
        command(pg_bin / 'pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop')


if __name__ == '__main__':
    sys.exit(run())
