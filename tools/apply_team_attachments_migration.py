"""团队附件显式迁移；必须确认业务库与当前提交，先备份再执行。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
TARGET = '43.132.156.72:15432/xinshi_system'


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    args = parser.parse_args()
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system' or Path.cwd().resolve() != ROOT:
        raise ValueError('只能在 PC 的项目目录执行')
    if Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise ValueError('必须使用项目虚拟环境')
    sys.path.insert(0, str(ROOT))
    from database import engine
    from sqlalchemy import text
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.confirm_target != TARGET or args.expected_commit != commit or (engine.url.host, engine.url.port, engine.url.database) != ('43.132.156.72', 15432, 'xinshi_system'):
        raise ValueError('数据库目标或提交与授权信息不一致')
    now = lambda: datetime.now(timezone(timedelta(hours=8)))
    directory = Path.home() / '.codex/backups/xinshi_system' / ('team-attachments-' + now().strftime('%Y%m%d-%H%M%S-%f+0800'))
    directory.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    sid = next(csv.reader(identity.splitlines()))[1]
    subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True, capture_output=True)
    sql = (ROOT / 'data/migrations/20261013_resource_team_attachments.sql').read_text(encoding='utf-8')
    names = ['resource_team', 'resource_team_audit', 'resource_team_attachment']
    print(f'主机=PC 项目={ROOT} Git={commit} 数据库={TARGET}', flush=True)
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout='10s'"))
        connection.execute(text("SET LOCAL statement_timeout='60s'"))
        connection.execute(text("SET LOCAL search_path=public"))
        assert connection.execute(text('SELECT current_database()')).scalar() == 'xinshi_system'
        existing = list(connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=ANY(:names) ORDER BY table_name"), {'names': names}).scalars())
        if not {'resource_team', 'resource_team_audit'} <= set(existing):
            raise ValueError('缺少现有团队基础表')
        for table in existing:
            connection.execute(text(f'LOCK TABLE public.{table} IN ACCESS EXCLUSIVE MODE'))
        rows = {table: connection.execute(text(f'SELECT row_to_json(t) FROM public.{table} t ORDER BY id')).scalars().all() for table in existing}
        columns = [dict(row) for row in connection.execute(text("SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(:names) ORDER BY table_name,ordinal_position"), {'names': names}).mappings()]
        indexes = [dict(row) for row in connection.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=ANY(:names) ORDER BY tablename,indexname"), {'names': names}).mappings()]
        constraints = [dict(row) for row in connection.execute(text("SELECT c.relname AS table_name,p.conname,pg_get_constraintdef(p.oid) AS definition FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(:names) ORDER BY c.relname,p.conname"), {'names': names}).mappings()]
        backup = {'target': TARGET, 'git_commit': commit, 'created_at': now().isoformat(), 'tables': rows, 'columns': columns, 'indexes': indexes, 'constraints': constraints,
                  'missing_tables': sorted(set(names) - set(existing)), 'migration_sha256': hashlib.sha256(sql.encode('utf-8')).hexdigest()}
        encoded = json.dumps(backup, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
        backup_path = directory / 'before.json'; backup_path.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        if hashlib.sha256(backup_path.read_bytes()).hexdigest() != digest or json.loads(backup_path.read_text(encoding='utf-8')) != backup:
            raise ValueError('备份校验失败')
        (directory / 'before.sha256').write_text(digest + '\n', encoding='utf-8')
        print('团队相关数据及结构备份已校验：' + str(backup_path), flush=True)
        connection.exec_driver_sql(sql)
        for table, before in rows.items():
            after = connection.execute(text(f'SELECT row_to_json(t) FROM public.{table} t ORDER BY id')).scalars().all()
            if before != after:
                raise ValueError('迁移前后既有数据改变，事务回滚')
        final_columns = {row['column_name']: row['data_type'] for row in connection.execute(text("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_team_attachment'")).mappings()}
        if not {'id', 'team_id', 'original_name', 'storage_name', 'file_size', 'uploaded_by', 'uploaded_at'} <= final_columns.keys() or final_columns['uploaded_at'] != 'timestamp with time zone':
            raise ValueError('附件表结构不符合预期')
        validated = connection.execute(text("SELECT convalidated FROM pg_constraint WHERE conrelid='resource_team_attachment'::regclass AND conname='ck_resource_team_attachment_size'")).scalar()
        if validated is not True:
            raise ValueError('附件大小约束未生效')
    report = {'applied': True, 'completed_at': now().isoformat(), 'target': TARGET, 'git_commit': commit, 'backup': str(backup_path), 'backup_sha256': digest,
              'existing_data_unchanged': True, 'existing_counts': {table: len(values) for table, values in rows.items()}, 'migration': '20261013_resource_team_attachments.sql'}
    (directory / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print('迁移未完成，事务内修改已回滚；错误类型：' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
