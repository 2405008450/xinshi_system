"""显式授权后扩展需求暂停约束；仓库外备份、事务校验，不修改业务记录。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-business-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-migration-sha256', required=True)
    parser.add_argument('--backup-root', type=Path, default=Path(r'E:\xinshi_runtime\backups'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if socket.gethostname().upper() != 'PC' or root != Path(r'E:\xinshi_system') or Path.cwd().resolve() != root:
        raise SystemExit('仅允许在 PC 的 E:\\xinshi_system 执行')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if args.expected_commit != commit:
        raise SystemExit('Git 提交与指定值不一致')
    migration = root / 'data/migrations/20261015_resource_request_pause.sql'
    sql_bytes = migration.read_bytes()
    sql_digest = hashlib.sha256(sql_bytes).hexdigest()
    if sql_digest != args.expected_migration_sha256:
        raise SystemExit('迁移文件 SHA-256 与已审阅值不一致')
    sys.path.insert(0, str(root))
    from database import engine
    from business_time import BUSINESS_TIMEZONE
    from datetime import datetime
    from sqlalchemy import text

    target = dict(host=engine.url.host, port=engine.url.port, name=engine.url.database)
    if target != dict(host='43.132.156.72', port=15432, name='xinshi_system') or args.confirm_business_target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标与本次显式授权不一致')
    backup_root = args.backup_root.resolve()
    if backup_root == root or root in backup_root.parents:
        raise SystemExit('备份必须保存在仓库外')
    now = lambda: datetime.now(BUSINESS_TIMEZONE)
    directory = backup_root / ('resource-request-pause-' + now().strftime('%Y%m%d-%H%M%S+0800-') + uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    sid = next(csv.reader(identity.splitlines()))[1]
    subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                   capture_output=True, check=True)

    def encode(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')

    def structure(connection):
        columns = connection.execute(text("SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_request' ORDER BY ordinal_position")).mappings().all()
        constraints = connection.execute(text("SELECT conname,contype,convalidated,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid='public.resource_request'::regclass ORDER BY conname")).mappings().all()
        indexes = connection.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='resource_request' ORDER BY indexname")).mappings().all()
        return dict(columns=[dict(row) for row in columns], constraints=[dict(row) for row in constraints], indexes=[dict(row) for row in indexes])

    backup_file = directory / 'before.json'
    result_file = directory / 'result.json'
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            actual = connection.execute(text("SELECT current_database() AS database, current_schema() AS schema, pg_is_in_recovery() AS recovery, current_setting('transaction_read_only') AS read_only")).mappings().one()
            if dict(actual) != dict(database='xinshi_system', schema='public', recovery=False, read_only='off'):
                raise RuntimeError('实际数据库身份或读写状态不符合预期')
            connection.execute(text('LOCK TABLE public.resource_request IN ACCESS EXCLUSIVE MODE'))
            before_rows = connection.execute(text('SELECT row_to_json(r) FROM public.resource_request r ORDER BY id')).scalars().all()
            before_schema = structure(connection)
            previous = next((row for row in before_schema['constraints'] if row['conname'] == 'ck_resource_request_demand_status'), None)
            if previous is None or previous['contype'] != 'c' or not previous['convalidated']:
                raise RuntimeError('缺少已验证的需求生命周期约束，停止迁移')
            backup = dict(database=target, git_commit=commit, created_at=now().isoformat(), migration_sha256=sql_digest,
                          structure=before_schema, rows=before_rows)
            payload = encode(backup)
            backup_file.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            if hashlib.sha256(backup_file.read_bytes()).hexdigest() != digest or json.loads(backup_file.read_text(encoding='utf-8')) != backup:
                raise RuntimeError('备份核验失败，停止迁移')
            (directory / 'before.sha256').write_text(digest + '\n', encoding='utf-8')
            (directory / migration.name).write_bytes(sql_bytes)
            # 回退只还原约束；若已有暂停记录，原约束校验会失败并回滚，禁止自动改写记录。
            original_constraint = previous['definition']
            rollback = 'BEGIN;\nALTER TABLE public.resource_request DROP CONSTRAINT ck_resource_request_demand_status;\nALTER TABLE public.resource_request ADD CONSTRAINT ck_resource_request_demand_status ' + original_constraint + ';\nCOMMIT;\n'
            (directory / 'rollback.sql').write_text(rollback, encoding='utf-8')
            connection.exec_driver_sql(sql_bytes.decode('utf-8'))
            after_rows = connection.execute(text('SELECT row_to_json(r) FROM public.resource_request r ORDER BY id')).scalars().all()
            after_schema = structure(connection)
            changed = next(row for row in after_schema['constraints'] if row['conname'] == 'ck_resource_request_demand_status')
            if not changed['convalidated'] or not all("'" + status + "'" in changed['definition'] for status in ['draft', 'confirmed', 'paused', 'cancelled']):
                raise RuntimeError('迁移后约束不符合预期，回滚')
            def other_constraints(schema):
                return [row for row in schema['constraints'] if row['conname'] != 'ck_resource_request_demand_status']
            if before_rows != after_rows or before_schema['columns'] != after_schema['columns'] or before_schema['indexes'] != after_schema['indexes'] or other_constraints(before_schema) != other_constraints(after_schema):
                raise RuntimeError('业务记录或其他结构发生变化，回滚')
        result = dict(applied=True, rows_unchanged=True, row_count=len(before_rows), backup_verified=True,
                      backup_sha256=digest, backup_file=str(backup_file), database=target, git_commit=commit,
                      migration_sha256=sql_digest, before_constraint=original_constraint, after_constraint=changed['definition'],
                      completed_at=now().isoformat())
        result_file.write_bytes(encode(result))
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        result_file.write_bytes(encode(dict(applied=False, error_type=type(exc).__name__, checked_at=now().isoformat())))
        raise
    finally:
        engine.dispose()


if __name__ == '__main__':
    run()
