"""在局域网隔离目录执行回归；测试连接强制使用专用库和专用端口。"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--connection-config', required=True)
    parser.add_argument('--pg-bin', required=True)
    parser.add_argument('--scope', choices=['all', 'integration', 'ui'], default='all')
    args = parser.parse_args()
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5':
        parser.error('测试只能在局域网调试机运行')
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    root = Path(__file__).resolve().parents[1]
    config = Path(args.connection_config).resolve()
    assert Path('E:/xinshi_runtime/validation').resolve() in config.parents
    url = json.loads(config.read_text(encoding='utf-8'))['url']
    target = make_url(url)
    assert target.host == '127.0.0.1' and 15000 <= target.port <= 15999
    assert target.database.startswith('xinshi_form_regression_')
    cluster = config.parent
    pg_ctl = str(Path(args.pg_bin) / 'pg_ctl.exe')
    env = {**os.environ, 'DATABASE_URL': url, 'XINSHI_FORM_TEST_DATABASE_URL': url,
           'SECRET_KEY': 'isolated-form-test-secret-not-for-production', 'PYTHONIOENCODING': 'utf-8'}
    env.update(TALENT_NUMBERING_TEST_DATABASE_URL=url, RUN_RESOURCE_DEVELOPMENT_DB_TESTS='1', RUN_ANNOTATION_CHAT_DB_TESTS='1')
    results = []
    logs = root / 'form-regression-results'
    logs.mkdir(exist_ok=True)
    status = subprocess.run([pg_ctl, '-D', str(cluster / 'data'), 'status'], capture_output=True)
    started = status.returncode != 0
    try:
        if started:
            with (cluster / 'pg-ctl.log').open('ab') as log:
                subprocess.run([pg_ctl, '-D', str(cluster / 'data'), '-l', str(cluster / 'postgres.log'),
                                '-o', f'-h 127.0.0.1 -p {target.port}', '-w', 'start'],
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=90,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        engine = create_engine(url)
        with engine.begin() as db:
            marker = db.scalar(text("SELECT to_regclass('public.form_regression_marker')"))
            if marker is None:
                assert db.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")) == 0
                # 克隆失败时只允许在空的专用库恢复已读取的结构。
                db.exec_driver_sql((cluster / 'schema.sql').read_text(encoding='utf-8'))
                db.exec_driver_sql('CREATE TABLE public.form_regression_marker (purpose text NOT NULL)')
                db.exec_driver_sql("INSERT INTO public.form_regression_marker VALUES ('isolated_form_regression')")
            assert db.scalar(text('SELECT purpose FROM public.form_regression_marker')) == 'isolated_form_regression'
        engine.dispose()
        commands = []
        if args.scope == 'all':
            commands.extend([
                ('backend', [sys.executable, '-m', 'pytest', 'tests', '-q', '-rs', '--tb=short'], root),
                ('frontend', ['node', '--test', *map(str, (root / 'frontend/tests').glob('*.test.mjs'))], root / 'frontend'),
            ])
        if args.scope == 'integration':
            commands.append(('integration', [sys.executable, '-m', 'pytest', 'tests/test_form_postgres_regression.py', '-q', '--tb=short'], root))
        if args.scope in {'all', 'ui'}:
            commands.append(('trial-ui-mocked', [sys.executable, 'tools/verify_trial_form_ui.py'], root))
            commands.append(('trial-ui-live', [sys.executable, 'tools/verify_trial_form_live.py'], root))
            commands.append(('form-navigation-ui', [sys.executable, 'tools/verify_form_navigation_ui.py'], root))
        for name, command, cwd in commands:
            with (logs / f'{name}.log').open('wb') as output:
                result = subprocess.run(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=900)
            results.append({'suite': name, 'exitCode': result.returncode})
            print(f'{name}: {"PASS" if result.returncode == 0 else "FAIL"}', flush=True)
        (logs / 'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        return int(any(item['exitCode'] for item in results))
    finally:
        if started:
            subprocess.run([pg_ctl, '-D', str(cluster / 'data'), '-m', 'fast', '-w', 'stop'], capture_output=True, timeout=90)


if __name__ == '__main__':
    sys.exit(main())
