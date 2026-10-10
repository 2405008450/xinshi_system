"""每日安排迁移：默认仅本机数据库，业务库须显式确认目标与提交并先备份。"""
import argparse
import csv
import hashlib
import json
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


def migrate_business_roles(engine, root, commit, backup_root):
    """仅增加岗位字段，相关表在同一事务内锁定、备份并核对原有内容。"""
    from sqlalchemy import text

    backup_root = backup_root.resolve()
    if backup_root == root or root in backup_root.parents:
        raise ValueError('业务备份必须保存在仓库外')
    sql_path = root / 'data/migrations/20261009_resource_arrangement_roles.sql'
    sql = sql_path.read_text(encoding='utf-8')
    statements = [s.strip() for s in '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--')).split(';') if s.strip()]
    if len(statements) != 3 or statements[0] != 'BEGIN' or statements[-1] != 'COMMIT' or not statements[1].startswith('ALTER TABLE resource_development_arrangement_cell'):
        raise ValueError('岗位增量迁移文件内容不符合预期')
    tables = ['resource_development_arrangement', 'resource_development_arrangement_cell']
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S+0800')
    directory = backup_root / f'resource-arrangement-roles-{stamp}-{uuid4().hex[:8]}'
    directory.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    sid = next(csv.reader(identity.splitlines()))[1]
    subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True, capture_output=True)

    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        existing = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('resource_development_arrangement','resource_development_arrangement_cell')")).scalars().all()
        if set(existing) != set(tables):
            raise ValueError('业务库缺少每日安排基础表；本入口只允许岗位增量迁移')
        connection.execute(text('LOCK TABLE resource_development_arrangement, resource_development_arrangement_cell IN ACCESS EXCLUSIVE MODE'))
        before = {name: connection.execute(text(f'SELECT row_to_json(t) FROM {name} t ORDER BY id')).scalars().all() for name in tables}
        columns = connection.execute(text("SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('resource_development_arrangement','resource_development_arrangement_cell') ORDER BY table_name,ordinal_position")).mappings().all()
        indexes = connection.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN ('resource_development_arrangement','resource_development_arrangement_cell')")).mappings().all()
        constraints = connection.execute(text("SELECT conrelid::regclass::text AS table_name,conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid IN ('resource_development_arrangement'::regclass,'resource_development_arrangement_cell'::regclass)")).mappings().all()
        existed = any(c['column_name'] == 'role_tags' for c in columns)
        backup = dict(database=dict(host=engine.url.host,port=engine.url.port,name=engine.url.database),git_commit=commit,
                      migration_sha256=hashlib.sha256(sql.encode('utf-8')).hexdigest(),created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                      tables=before,columns=[dict(c) for c in columns],indexes=[dict(i) for i in indexes],constraints=[dict(c) for c in constraints])
        payload = json.dumps(backup, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
        backup_file = directory / 'before.json'
        backup_file.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        if hashlib.sha256(backup_file.read_bytes()).hexdigest() != digest or json.loads(backup_file.read_text(encoding='utf-8')) != backup:
            raise ValueError('备份内容核验失败，未执行迁移')
        (directory / 'before.sha256').write_text(digest + '\n', encoding='utf-8')
        connection.execute(text(statements[1]))
        column = connection.execute(text("SELECT data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_development_arrangement_cell' AND column_name='role_tags'")).mappings().one()
        if column['data_type'] != 'json' or column['is_nullable'] != 'NO' or '[]' not in (column['column_default'] or ''):
            raise ValueError('岗位字段类型、非空约束或默认值不符合预期，回滚迁移')
        for name in tables:
            after = connection.execute(text(f'SELECT row_to_json(t) FROM {name} t ORDER BY id')).scalars().all()
            stripped = [{k:v for k,v in row.items() if existed or k != 'role_tags'} for row in after] if name.endswith('_cell') else after
            if stripped != before[name]:
                raise ValueError('原有业务内容发生变化，回滚迁移')
            if name.endswith('_cell') and not existed and any(row['role_tags'] != [] for row in after):
                raise ValueError('历史岗位默认值错误，回滚迁移')
    result = dict(applied=True,already_existed=existed,backup_verified=True,backup_sha256=digest,backup_file=str(backup_file),
                  database=backup['database'],git_commit=commit,rows={name:len(rows) for name,rows in before.items()},
                  completed_at=datetime.now(timezone(timedelta(hours=8))).isoformat())
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-business-target', help='仅在用户明确授权后填写：43.132.156.72:15432/xinshi_system')
    parser.add_argument('--expected-commit')
    parser.add_argument('--backup-root', type=Path, default=Path(r'E:\xinshi_runtime\backups'))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "PC" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在本机 E:\\xinshi_system 执行")
    sys.path.insert(0, str(root))
    from database import engine
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip()
    if args.confirm_business_target:
        target = (engine.url.host, engine.url.port, engine.url.database)
        if target != ('43.132.156.72',15432,'xinshi_system') or args.confirm_business_target != '43.132.156.72:15432/xinshi_system':
            raise SystemExit('显式确认的业务数据库目标与当前连接不一致')
        if not args.expected_commit or args.expected_commit != commit:
            raise SystemExit('必须指定与当前 HEAD 完全一致的 --expected-commit')
        migrate_business_roles(engine, root, commit, args.backup_root)
        return
    if engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("每日安排迁移只允许使用本机数据库")
    sql = (root / "data/migrations/20261008_resource_development_arrangements.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql((root / "data/migrations/20261009_resource_arrangement_roles.sql").read_text(encoding="utf-8"))
    print("每日安排迁移完成（可重复执行）")


if __name__ == "__main__":
    run()
