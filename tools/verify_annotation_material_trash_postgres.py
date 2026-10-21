"""PC 原生 PostgreSQL 临时实例，检查迁移幂等、Office 与回收站并发。"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or Path(sys.executable).resolve() != ROOT/'.venv/Scripts/python.exe':
        raise SystemExit('仅允许 PC 使用项目 .venv 验证')
    binary = shutil.which('pg_ctl.exe')
    if not binary: raise SystemExit('缺少本机 PostgreSQL，不得回退业务库')
    pg = Path(binary).parent
    output = ROOT/'.tmp/material-trash-postgres'; output.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='postgres-', dir=output))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    def command(args, name, env=None):
        with (output/name).open('w', encoding='utf-8') as log:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=240)
        if result.returncode: print((output/name).read_text(encoding='utf-8', errors='replace'))
        result.check_returncode()
    command(['icacls.exe', directory, '/grant', subprocess.check_output(['whoami.exe'],text=True).strip()+':(OI)(CI)F'], 'permissions.log')
    command([pg/'initdb.exe','-D',directory,'-U','material_test','--auth=trust','--encoding=UTF8','--locale=C'],'initdb.log')
    command([pg/'pg_ctl.exe','-D',directory,'-l',directory/'postgres.log','-o',f'-h 127.0.0.1 -p {port}','-w','start'],'start.log')
    try:
        command([pg/'createdb.exe','-h','127.0.0.1','-p',port,'-U','material_test','material_trash_test'],'createdb.log')
        env = dict(os.environ, MATERIAL_TEST_DATABASE_URL=f'postgresql+psycopg2://material_test@127.0.0.1:{port}/material_trash_test', PYTHONUTF8='1', LOCAL_SCHEMA_MIGRATIONS_ENABLED='false')
        command([sys.executable,'-m','pytest','tests/test_annotation_material_trash.py','tests/test_annotation_materials.py','tests/test_annotation_office.py','-q','--tb=short','--disable-warnings'],'pytest.log',env)
        print((output/'pytest.log').read_text(encoding='utf-8'))
    finally:
        command([pg/'pg_ctl.exe','-D',directory,'-m','fast','-w','stop'],'stop.log')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
