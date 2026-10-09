"""调试机隔离验收：独立源码副本、临时 PostgreSQL，不读取默认业务数据库。"""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile

PROJECT = Path(r'E:\xinshi_system')
INPUT = Path(__file__).resolve().parents[1]
FILES = [
    'referral_development_models.py', 'referral_development_schemas.py', 'referral_development_service.py',
    'routers/referral_development.py', 'data/migrations/20261008_referral_development.sql',
    'tests/test_referral_development.py', 'frontend/tests/referralDevelopment.test.mjs',
    'frontend/src/api/referralDevelopment.js', 'frontend/src/utils/referralDevelopment.js',
    'frontend/src/views/resource/ReferralDevelopment.vue',
    'frontend/src/views/resource/components/ReferralDetailContent.vue',
    'frontend/src/views/resource/components/ReferralImages.vue',
    'frontend/src/views/resource/components/ReferralRecordEditor.vue',
    'frontend/src/views/resource/components/ReferralEvidenceCell.vue', 'frontend/src/utils/referralImages.js',
    'frontend/tests/referralImages.test.mjs',
    'tools/verify_referral_development_ui.py',
]


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ui-only', action='store_true', help='仅重跑浏览器验收，要求当前源码的完整构建已通过')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if socket.gethostname().upper() != 'PC' or Path.cwd().resolve() != PROJECT:
        raise SystemExit('仅允许在本机 E:\\xinshi_system 执行')
    root = PROJECT / '.tmp/referral-verification-workspace'
    root.mkdir(parents=True, exist_ok=True)
    for path in PROJECT.glob('*.py'):
        shutil.copy2(path, root / path.name)
    for directory in ['routers', 'tests', 'frontend']:
        shutil.copytree(PROJECT / directory, root / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('node_modules', 'dist', '.git', '.env*', '__pycache__'))
    shutil.copytree(PROJECT / 'data/migrations', root / 'data/migrations', dirs_exist_ok=True)
    for relative in FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(INPUT / relative, target)
    # 对副本增量注册，不覆盖调试机中的其他功能。
    main = root / 'main.py'
    content = main.read_text(encoding='utf-8')
    if 'app.include_router(referral_development.router)' not in content:
        anchor = 'app.include_router(resource_development.router)'
        assert content.count(anchor) == 1
        main.write_text(content.replace(anchor, anchor + '\nfrom routers import referral_development\napp.include_router(referral_development.router)', 1), encoding='utf-8')
    route = root / 'frontend/src/router/index.js'
    content = route.read_text(encoding='utf-8')
    if "name: 'ReferralDevelopment'" not in content:
        anchor = "            path: 'resource-development',"
        assert content.count(anchor) == 1
        route.write_text(content.replace(anchor, "            path: 'referral-development',\n            name: 'ReferralDevelopment',\n            component: () => import('../views/resource/ReferralDevelopment.vue'),\n            meta: { title: '推荐拓展', roles: ['*'], permissions: ['talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate'] }\n          },\n          {\n" + anchor, 1), encoding='utf-8')
    nav = root / 'frontend/src/config/talentResourceViews.js'
    content = nav.read_text(encoding='utf-8')
    if "label: '推荐拓展'" not in content:
        assert content.count('])') == 1
        nav.write_text(content.replace('])', "  { label: '推荐拓展', path: '/resource-management/referral-development', permissions: ['talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate'] },\n])", 1), encoding='utf-8')
    modules = root / 'frontend/node_modules'
    if not modules.exists():
        subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(modules), str(PROJECT / 'frontend/node_modules')], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    out = root / '.tmp/referral-verification'
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix='pg-', dir=out))
    pg_root = Path(r'C:\Program Files\PostgreSQL')
    candidates = sorted(pg_root.glob('*/bin'), reverse=True)
    pg_bin = next((path for path in candidates if (path / 'initdb.exe').is_file() and (path / 'pg_ctl.exe').is_file()), None)
    if pg_bin is None:
        raise SystemExit('未找到本机 PostgreSQL 工具，不能回退到业务数据库')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]

    def command(*args, env=None, cwd=root, timeout=120, log_name=None):
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            output.seek(0); raw = output.read()
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            content = raw.decode('gbk', errors='replace')
        if log_name:
            (out / log_name).write_text(content, encoding='utf-8')
        shown = '\n'.join(line for line in content.splitlines() if 'built in' in line or 'error' in line.lower()) if log_name == 'build.log' else content[-10000:]
        print(shown, flush=True)
        result.check_returncode()
        return content

    identity = subprocess.check_output(['whoami.exe']).decode().strip()
    command('icacls.exe', data, '/grant', f'{identity}:(OI)(CI)F')
    command(pg_bin / 'initdb.exe', '-D', data, '-U', 'referral_test', '--auth=trust', '--encoding=UTF8', '--locale=C')
    command(pg_bin / 'pg_ctl.exe', '-D', data, '-l', data / 'server.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
    try:
        env = dict(os.environ, DATABASE_URL=f'postgresql+psycopg2://referral_test@127.0.0.1:{port}/postgres',
                   SECRET_KEY=secrets.token_urlsafe(48), RUN_RESOURCE_DEVELOPMENT_DB_TESTS='1', PYTHONIOENCODING='utf-8', APP_ENV='development',
                   LOCAL_SCHEMA_MIGRATIONS_ENABLED='false')
        print(f'验收环境：主机 PC，源码 {PROJECT}，提交 ' + subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=PROJECT).decode().strip()
              + f'，隔离数据库 127.0.0.1:{port}/postgres（用户 referral_test）', flush=True)
        setup = """
import main
from models import Base
from database import engine
from sqlalchemy import text
from pathlib import Path
assert engine.url.host == '127.0.0.1' and engine.url.username == 'referral_test'
with engine.begin() as connection:
    connection.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    connection.execute(text('CREATE SEQUENCE IF NOT EXISTS chat_message_sequence'))
Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if not t.name.startswith('referral_development_')])
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    sql=Path('data/migrations/20261008_referral_development.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(sql)
    connection.exec_driver_sql(sql)
    core_migration=Path('data/migrations/20261011_auto_talent_resource_code.sql')
    if core_migration.exists():
        connection.exec_driver_sql(core_migration.read_text(encoding='utf-8'))
engine.dispose()
print('推荐拓展迁移首次及重复执行通过')
"""
        command(sys.executable, '-c', setup, env=env, log_name='migration.log')
        if not args.ui_only:
            command(sys.executable, '-m', 'pytest', 'tests/test_referral_development.py', 'tests/test_resource_follow_up.py', '-q', '--tb=short', env=env, timeout=300, log_name='backend-tests.log')
            command('node', '--test', 'tests/referralDevelopment.test.mjs', 'tests/referralImages.test.mjs', cwd=root / 'frontend', env=env, log_name='frontend-tests.log')
            command('node', 'node_modules/vite/bin/vite.js', 'build', '--outDir', '../.tmp/referral-dist', '--emptyOutDir', cwd=root / 'frontend', env=env, timeout=300, log_name='build.log')
            command('node', 'tools/check-build-budget.mjs', '--dist-dir', '../.tmp/referral-dist', cwd=root / 'frontend', env=env, log_name='build-budget.log')
        elif not (root / '.tmp/referral-dist/index.html').exists():
            raise SystemExit('尚无完整构建，不能仅运行浏览器验收')
        command(sys.executable, 'tools/verify_referral_development_ui.py', env=env, timeout=300, log_name='ui-tests.log')
    finally:
        command(pg_bin / 'pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop')
    print(f'推荐拓展隔离验收完成；结果目录：{out}', flush=True)


if __name__ == '__main__':
    run()
