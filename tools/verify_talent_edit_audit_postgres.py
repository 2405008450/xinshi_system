"""本机临时 PostgreSQL：验证日志迁移及 100 万条模拟日志的索引查询。"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    if socket.gethostname().lower() != 'pc' or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('仅允许 PC 使用项目 .venv 验证')
    binary = shutil.which('pg_ctl.exe')
    if not binary:
        raise SystemExit('缺少本机 PostgreSQL，不得回退业务库')
    pg = Path(binary).parent
    output = ROOT / '.tmp/talent-edit-audit-postgres'
    output.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='postgres-', dir=output))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]

    def command(args, name):
        with (output / name).open('w', encoding='utf-8') as log:
            result = subprocess.run([str(arg) for arg in args], cwd=ROOT, stdout=log,
                                    stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=240)
        if result.returncode:
            print((output / name).read_text(encoding='utf-8', errors='replace'))
        result.check_returncode()

    command(['icacls.exe', directory, '/grant', subprocess.check_output(['whoami.exe'], text=True).strip() + ':(OI)(CI)F'], 'permissions.log')
    command([pg / 'initdb.exe', '-D', directory, '-U', 'audit_test', '--auth=trust', '--encoding=UTF8', '--locale=C'], 'initdb.log')
    command([pg / 'pg_ctl.exe', '-D', directory, '-l', directory / 'postgres.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'], 'start.log')
    try:
        command([pg / 'createdb.exe', '-h', '127.0.0.1', '-p', port, '-U', 'audit_test', 'talent_edit_audit_test'], 'createdb.log')
        from sqlalchemy import create_engine, text, inspect
        from tools.apply_talent_edit_audit_migration import apply_migration
        engine = create_engine(f'postgresql+psycopg2://audit_test@127.0.0.1:{port}/talent_edit_audit_test')
        try:
            with engine.begin() as connection:
                apply_migration(connection)
                apply_migration(connection)
                assert inspect(connection).get_columns('talent_edit_log')[-1]['type'].timezone
                connection.execute(text("""
                    INSERT INTO talent_edit_log
                    (id, person_id, resource_code, person_name, actor_account, actor_name, source, changes, created_at)
                    SELECT md5(n::text)::uuid, md5((n % 100000)::text)::uuid, 'TEST-' || (n % 100000),
                    'isolated-talent', 'isolated-editor', 'isolated-editor', 'manual',
                    '{"remarks":{"before":"old","after":"new"}}'::json,
                    TIMESTAMPTZ '2026-11-17 00:00:00+08' + n * INTERVAL '1 microsecond'
                    FROM generate_series(1, 1000000) AS n
                """))
                connection.execute(text('ANALYZE talent_edit_log'))
            with engine.connect() as connection:
                plan = '\n'.join(row[0] for row in connection.execute(text("""
                    EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM talent_edit_log
                    WHERE person_id=md5('42')::uuid ORDER BY created_at DESC, id DESC LIMIT 20
                """)))
                assert 'ix_talent_edit_log_person_time' in plan
                started = perf_counter()
                total = connection.scalar(text("SELECT count(*) FROM talent_edit_log WHERE person_id=md5('42')::uuid"))
                count_ms = (perf_counter() - started) * 1000
                assert total == 10
                result = dict(rows=1000000, simulated_people=100000, per_person=10, count_ms=round(count_ms, 2), plan=plan)
                (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(result, ensure_ascii=False))
        finally:
            engine.dispose()
    finally:
        command([pg / 'pg_ctl.exe', '-D', directory, '-m', 'fast', '-w', 'stop'], 'stop.log')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
