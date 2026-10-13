"""启动可供浏览器验收的隔离服务；仅连接本机临时 PostgreSQL，不替换日常服务。"""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / '.tmp' / 'annotation-live-local'
PG = Path(r'C:\Program Files\PostgreSQL\17\bin')
STATE = OUTPUT / 'state.json'


def command(*args, env=None):
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(list(map(str, args)), cwd=ROOT, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                stdout=output, stderr=subprocess.STDOUT, timeout=90)
        output.seek(0)
        log = output.read().decode('utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(log)
    return log


def start():
    if STATE.exists():
        raise SystemExit('已存在隔离验收状态，请先核对并停止上轮服务。')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix='pg-', dir=OUTPUT))
    identity = command('whoami.exe').strip()
    command('icacls.exe', data, '/grant', f'{identity}:(OI)(CI)F')
    command(PG / 'initdb.exe', '-D', data, '-U', 'annotation_test', '--auth=trust', '--encoding=UTF8', '--locale=C')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    command(PG / 'pg_ctl.exe', '-D', data, '-l', data / 'server.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
    database_name = 'xinshi_annotation_validation_' + secrets.token_hex(4)
    command(PG / 'createdb.exe', '-h', '127.0.0.1', '-p', port, '-U', 'annotation_test', database_name)
    database_url = f'postgresql+psycopg2://annotation_test@127.0.0.1:{port}/{database_name}'
    environment = {**os.environ, 'DATABASE_URL': database_url,
                   'LOCAL_SCHEMA_MIGRATIONS_ENABLED': 'false',
                   'ANNOTATION_MATERIAL_STORAGE_MODE': 'disabled',
                   'SECRET_KEY': secrets.token_hex(32), 'PYTHONUTF8': '1',
                   'VITE_API_PROXY_TARGET': 'http://127.0.0.1:9800'}
    os.environ.update(environment)
    state = {'data': str(data), 'database_url': database_url, 'database_name': database_name,
             'username': 'annotation_local_test', 'password': secrets.token_urlsafe(24),
             'backend_port': 9800, 'frontend_port': 9300, 'pids': [],
             'host': socket.gethostname(), 'project': str(ROOT),
             'commit': command('git', 'rev-parse', 'HEAD').strip(),
             'time': datetime.now(timezone(timedelta(hours=8))).isoformat()}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        # 导入只注册模型；结构仅在新建的临时实例内创建。
        import main  # noqa: F401
        from database import engine
        from sqlalchemy import text
        from sqlalchemy.orm import Session
        from models import Base, AppUser, Role, UserRole, Client
        from interpretation_models import InterpretationLanguage
        from routers.auth import hash_password
        from annotation_models import AnnotationArea
        from annotation_schemas import AnnotationProjectCreate
        import annotation_service as service
        with engine.begin() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
            conn.execute(text('CREATE SEQUENCE IF NOT EXISTS chat_message_sequence'))
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = AppUser(username=state['username'], password_hash=hash_password(state['password']), full_name='本地隔离验收')
            role = Role(role_name='admin')
            client = Client(client_code='LOCAL-ANNOTATION', client_name='本地隔离验收客户', client_short_name='隔离验收')
            languages = [InterpretationLanguage(label=label) for label in ['英语', '日语']]
            areas = [AnnotationArea(label=label, name_key=label) for label in ['北美片区', '欧洲片区']]
            db.add_all([user, role, client, *languages, *areas]); db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id)); db.commit()
            root = service.create_annotation_project(db, AnnotationProjectCreate(
                project_name='本地三级订单验收', client_id=client.id, potential_demand='100',
                project_types=['audio_annotation'], task_description='隔离测试任务',
                language_items=[{'source_language_id': language.id} for language in languages],
            ), user.id)
            child = service.get_annotation_projects(db, parent_project_id=root.id, limit=10)[0]
            leaf = service.create_annotation_children(db, child.id, [AnnotationProjectCreate(
                project_name='北美验收任务', task_description='隔离测试任务', project_types=['audio_annotation'],
                area_id=areas[0].id, language_items=[{'source_language_id': child.language_items[0].source_language_id}],
            )], user.id, secrets.token_hex(16))[0]
            state.update(root_id=str(root.id), child_id=str(child.id), leaf_id=str(leaf.id))
        engine.dispose()
        for component, service_port in [('Backend', 9800), ('Frontend', 9300)]:
            args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    str(ROOT / 'deploy/start_local.ps1'), '-Service', component, '-ValidationPort', str(service_port)]
            (OUTPUT / f'{component.lower()}-check.log').write_text(command(*args, '-CheckOnly', env=environment), encoding='utf-8')
            with (OUTPUT / f'{component.lower()}.log').open('w', encoding='utf-8') as output:
                process = subprocess.Popen(args, cwd=ROOT, env=environment,
                                           creationflags=subprocess.CREATE_NO_WINDOW,
                                           stdout=output, stderr=subprocess.STDOUT)
            state['pids'].append(process.pid)
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with urlopen('http://127.0.0.1:9300/api/health/db', timeout=2) as response:
                    if json.load(response)['status'] == 'ok':
                        break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError('隔离服务未通过代理及数据库健康检查，请查看 .tmp/annotation-live-local 日志。')
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: state[key] for key in ['host', 'project', 'commit', 'time', 'database_name', 'backend_port', 'frontend_port']}, ensure_ascii=False))
    except BaseException:
        stop()
        raise


def stop():
    state = json.loads(STATE.read_text(encoding='utf-8'))
    data = Path(state['data']).resolve()
    if data.parent != OUTPUT.resolve() or not data.name.startswith('pg-'):
        raise SystemExit('临时数据库目录校验失败，停止清理。')
    for pid in state['pids']:
        command('taskkill.exe', '/PID', pid, '/T', '/F')
    command(PG / 'pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop')
    STATE.unlink()


def restart_backend():
    from sqlalchemy.engine import make_url
    state = json.loads(STATE.read_text(encoding='utf-8'))
    url = make_url(state['database_url'])
    if url.host != '127.0.0.1' or not url.database.startswith('xinshi_annotation_validation_'):
        raise SystemExit('只允许重启本轮隔离数据库的后端。')
    pid = state['pids'][0]
    # 确认仍是本轮启动的 PowerShell，避免状态文件中的 PID 被其他进程复用。
    command('powershell.exe', '-NoProfile', '-Command',
                    f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}'; if($p.CommandLine -notlike '*start_local.ps1*Backend*9800*'){{exit 1}}")
    environment = {**os.environ, 'DATABASE_URL': state['database_url'],
                   'SECRET_KEY': secrets.token_hex(32), 'PYTHONUTF8': '1',
                   'LOCAL_SCHEMA_MIGRATIONS_ENABLED': 'false', 'ANNOTATION_MATERIAL_STORAGE_MODE': 'disabled'}
    args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(ROOT / 'deploy/start_local.ps1'), '-Service', 'Backend', '-ValidationPort', '9800', '-Reload']
    command(*args, '-CheckOnly', env=environment)
    command('taskkill.exe', '/PID', pid, '/T', '/F')
    with (OUTPUT / 'backend-restarted.log').open('w', encoding='utf-8') as output:
        process = subprocess.Popen(args, cwd=ROOT, env=environment,
                                   creationflags=subprocess.CREATE_NO_WINDOW,
                                   stdout=output, stderr=subprocess.STDOUT)
    state['pids'][0] = process.pid
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print('隔离后端已按本机入口重启并启用热更新；临时账号需重新登录。')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system') or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('仅允许在 PC 项目目录使用项目 .venv Python 运行。')
    if '--stop' in sys.argv:
        stop()
    elif '--restart-backend' in sys.argv:
        restart_backend()
    else:
        start()
