"""账号归属增量迁移：默认只允许本机隔离数据库，不自动处理业务库。"""
import argparse
import csv
import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def migrate_business_accounts(engine, root, commit, backup_root):
    """先锁定并备份原资料，再增加空关系表；不自动猜测或写入账号归属。"""
    from sqlalchemy import text
    from business_time import business_now, business_iso

    backup_root = backup_root.resolve()
    if backup_root == root or root in backup_root.parents:
        raise ValueError('业务备份必须保存在仓库外')
    sql = (root / 'data/migrations/20261012_resource_channel_accounts.sql').read_text(encoding='utf-8')
    directory = backup_root / ('resource-channel-accounts-' + business_now().strftime('%Y%m%d-%H%M%S+0800') + '-' + uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    sid = next(csv.reader(identity.splitlines()))[1]
    subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True, capture_output=True)
    orders = {'resource_development_option': 'id', 'resource_development_channel_member': 'platform_id,user_id,role', 'resource_channel_account_link': 'account_id'}
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        existing = set(connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = ANY(:names)"), {'names': list(orders)}).scalars())
        if not {'resource_development_option', 'resource_development_channel_member'} <= existing:
            raise ValueError('缺少渠道基础表；本入口只允许账号归属增量迁移')
        connection.execute(text('LOCK TABLE ' + ','.join(sorted(existing)) + ' IN SHARE ROW EXCLUSIVE MODE'))
        before = {name: connection.execute(text(f'SELECT row_to_json(t) FROM {name} t ORDER BY {orders[name]}')).scalars().all() for name in sorted(existing)}
        columns = connection.execute(text("SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name = ANY(:names) ORDER BY table_name,ordinal_position"), {'names': list(existing)}).mappings().all()
        indexes = connection.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename = ANY(:names) ORDER BY tablename,indexname"), {'names': list(existing)}).mappings().all()
        backup = dict(database=dict(host=engine.url.host, port=engine.url.port, name=engine.url.database), git_commit=commit,
                      created_at=business_iso(business_now()), migration_sha256=hashlib.sha256(sql.encode('utf-8')).hexdigest(),
                      rows=before, columns=[dict(c) for c in columns], indexes=[dict(i) for i in indexes])
        payload = json.dumps(backup, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
        backup_file = directory / 'before.json'; backup_file.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        if hashlib.sha256(backup_file.read_bytes()).hexdigest() != digest or json.loads(backup_file.read_text(encoding='utf-8')) != backup:
            raise ValueError('备份校验失败，未执行迁移')
        (directory / 'before.sha256').write_text(digest + '\n', encoding='utf-8')
        connection.exec_driver_sql(sql)
        for name, rows in before.items():
            after = connection.execute(text(f'SELECT row_to_json(t) FROM {name} t ORDER BY {orders[name]}')).scalars().all()
            if rows != after:
                raise ValueError('原有渠道或归属数据发生变化，回滚迁移')
        if 'resource_channel_account_link' not in before and connection.execute(text('SELECT count(*) FROM resource_channel_account_link')).scalar() != 0:
            raise ValueError('新增关系表不为空，回滚迁移')
    result = dict(applied=True, backup_verified=True, backup_file=str(backup_file), backup_sha256=digest,
                  database=backup['database'], git_commit=commit, rows={name: len(rows) for name, rows in before.items()}, completed_at=business_iso(business_now()))
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-business-target')
    parser.add_argument('--expected-commit')
    parser.add_argument('--backup-root', type=Path, default=Path(r'E:\xinshi_runtime\backups'))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != "PC" or str(root).lower() != r"e:\xinshi_system":
        raise SystemExit("只能在 PC 的 E:\\xinshi_system 执行")
    if Path(sys.executable).resolve() != root / ".venv/Scripts/python.exe":
        raise SystemExit("必须使用项目虚拟环境解释器")
    sys.path.insert(0, str(root))
    from database import engine
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if args.confirm_business_target:
        if (engine.url.host, engine.url.port, engine.url.database) != ('43.132.156.72', 15432, 'xinshi_system') or args.confirm_business_target != '43.132.156.72:15432/xinshi_system':
            raise SystemExit('显式确认目标与实际业务库不一致')
        if args.expected_commit != commit:
            raise SystemExit('必须提供与当前 HEAD 完全一致的 --expected-commit')
        migrate_business_accounts(engine, root, commit, args.backup_root)
        return
    if engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("此入口仅允许本机数据库；业务库迁移需要单独明确授权及备份")
    print(f"主机={socket.gethostname()} 项目={root} 提交={commit} 数据库={engine.url.host}:{engine.url.port}/{engine.url.database}")
    sql = (root / "data/migrations/20261012_resource_channel_accounts.sql").read_text(encoding="utf-8")
    with engine.begin() as connection:
        connection.exec_driver_sql(sql)
    print("账号归属迁移完成；没有修改已有账号或业务数据")


if __name__ == "__main__":
    run()
