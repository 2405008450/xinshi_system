"""显式授权的主题与开拓事项增量迁移；先备份，事务内验证原数据不变。"""
import argparse
import csv
import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
TARGET = '43.132.156.72:15432/xinshi_system'
MIGRATIONS = ('20261012_resource_development_issues.sql', '20261012_chat_topics.sql')
ORDERS = {'chat_project_message': 'id', 'resource_development_issue': 'id',
          'resource_development_issue_task': 'id', 'chat_topic': 'id',
          'chat_message_topic': 'message_id', 'chat_topic_audit': 'id'}


def transaction_body(source):
    lines = source.strip().splitlines()
    if lines[0].strip().upper() != 'BEGIN;' or lines[-1].strip().upper() != 'COMMIT;':
        raise ValueError('迁移文件缺少预期事务边界')
    return '\n'.join(lines[1:-1])


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--backup-root', type=Path, default=Path(r'E:\xinshi_runtime\backups'))
    args = parser.parse_args()
    if socket.gethostname().upper() != 'PC' or Path.cwd().resolve() != ROOT or ROOT != Path(r'E:\xinshi_system'):
        raise ValueError('主机或项目目录不匹配')
    if Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise ValueError('必须使用项目虚拟环境')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.expected_commit != commit or args.confirm_target != TARGET:
        raise ValueError('提交或显式授权目标不匹配')
    sys.path.insert(0, str(ROOT))
    from database import engine
    from sqlalchemy import text
    from business_time import business_now, business_iso
    if (engine.url.host, engine.url.port, engine.url.database) != ('43.132.156.72', 15432, 'xinshi_system'):
        raise ValueError('实际数据库连接与授权目标不匹配')
    backup_root = args.backup_root.resolve()
    if backup_root == ROOT or ROOT in backup_root.parents:
        raise ValueError('业务备份必须保存在仓库外')
    sources = {name: (ROOT / 'data/migrations' / name).read_text(encoding='utf-8') for name in MIGRATIONS}
    bodies = {name: transaction_body(source) for name, source in sources.items()}
    stamp = business_now().strftime('%Y%m%d-%H%M%S+0800')
    directory = backup_root / f'chat-topics-{stamp}-{uuid4().hex[:8]}'
    directory.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    sid = next(csv.reader(identity.splitlines()))[1]
    subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r',
                    f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True, capture_output=True)
    print(json.dumps(dict(host='PC', project=str(ROOT), git_commit=commit, target=TARGET,
                          backup_directory=str(directory)), ensure_ascii=False), flush=True)
    names = list(ORDERS)
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='60s'"))
        connection.execute(text("SET LOCAL timezone='Asia/Hong_Kong'"))
        connection.execute(text('SET LOCAL search_path=public'))
        if connection.execute(text('SELECT current_database()')).scalar_one() != 'xinshi_system':
            raise ValueError('实际数据库名错误')
        existing = set(connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=ANY(:names)"), {'names': names}).scalars())
        if 'chat_project_message' not in existing:
            raise ValueError('缺少既有聊天基础表')
        # SHARE 锁避免备份期间消息被修改，迁移不会改写历史消息正文。
        for name in sorted(existing):
            connection.execute(text(f'LOCK TABLE public."{name}" IN SHARE MODE'))
        before = {name: connection.execute(text(f'SELECT row_to_json(t) FROM public."{name}" t ORDER BY {ORDERS[name]}')).scalars().all() for name in sorted(existing)}
        columns = [dict(row) for row in connection.execute(text("SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(:names) ORDER BY table_name,ordinal_position"), {'names': names}).mappings()]
        indexes = [dict(row) for row in connection.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=ANY(:names) ORDER BY tablename,indexname"), {'names': names}).mappings()]
        constraints = [dict(row) for row in connection.execute(text("SELECT c.relname AS table_name,p.conname,pg_get_constraintdef(p.oid) AS definition FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(:names) ORDER BY c.relname,p.conname"), {'names': names}).mappings()]
        backup = dict(target=TARGET, git_commit=commit, created_at=business_iso(business_now()),
                      tables=before, missing_tables=sorted(set(names)-existing), columns=columns,
                      indexes=indexes, constraints=constraints,
                      migration_sha256={name: hashlib.sha256(source.encode('utf-8')).hexdigest() for name, source in sources.items()})
        encoded = json.dumps(backup, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
        backup_file = directory / 'before.json'
        backup_file.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        if hashlib.sha256(backup_file.read_bytes()).hexdigest() != digest or json.loads(backup_file.read_text(encoding='utf-8')) != backup:
            raise ValueError('备份校验失败')
        (directory / 'before.sha256').write_text(digest + '\n', encoding='utf-8')
        print(json.dumps(dict(backup_verified=True, backup_sha256=digest,
                              existing_rows={name: len(rows) for name, rows in before.items()}), ensure_ascii=False), flush=True)
        for name in MIGRATIONS:
            connection.exec_driver_sql(bodies[name])
            print('迁移 SQL 执行完成，等待事务验证：' + name, flush=True)
        # 核对所有旧行和旧字段；新增主题默认记录允许追加，旧内容不得被修改。
        for name, old_rows in before.items():
            old_fields = {row['column_name'] for row in columns if row['table_name'] == name}
            key = ORDERS[name]
            after = {str(row[key]): {field: value for field, value in row.items() if field in old_fields}
                     for row in connection.execute(text(f'SELECT row_to_json(t) FROM public."{name}" t ORDER BY {key}')).scalars()}
            if any(after.get(str(row[key])) != row for row in old_rows):
                raise ValueError('原有业务内容改变，回滚迁移')
            if name != 'chat_topic' and len(after) != len(old_rows):
                raise ValueError('原有表行数改变，回滚迁移')
        final_tables = set(connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=ANY(:names)"), {'names': names}).scalars())
        if final_tables != set(names):
            raise ValueError('迁移结果缺少预期表')
        final_columns = {row['column_name']: dict(row) for row in connection.execute(text("SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_development_issue'")).mappings()}
        if not {'topic_id', 'topic_path', 'client_request_id'} <= set(final_columns):
            raise ValueError('缺少主题或手工请求字段')
        if any(final_columns[name]['is_nullable'] != 'YES' for name in ('source_message_id', 'source_conversation_id')):
            raise ValueError('手工来源字段仍强制非空')
        builtin_keys = ['annotation', 'resource-development', 'platform', 'people', 'wechat', 'posting', 'university', 'other']
        builtin_count = connection.execute(text('SELECT count(*) FROM chat_topic WHERE builtin_key=ANY(:keys)'), {'keys': builtin_keys}).scalar_one()
        if builtin_count != 8:
            raise ValueError('内置主题目录不完整')
        final_indexes = set(connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename=ANY(:names)"), {'names': names}).scalars())
        if not {'uq_translation_chat_client', 'uq_issue_manual_request', 'uq_chat_topic_sibling_name'} <= final_indexes:
            raise ValueError('关键唯一索引缺失')
        counts = {name: connection.execute(text(f'SELECT count(*) FROM public."{name}"')).scalar_one() for name in names}
    report = dict(applied=True, target=TARGET, git_commit=commit, backup_file=str(backup_file),
                  backup_sha256=digest, existing_data_unchanged=True, builtin_topics=builtin_count,
                  table_counts=counts, migrations=list(MIGRATIONS), completed_at=business_iso(business_now()))
    (directory / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        # 不回显连接异常或连接字符串，避免泄露凭据。
        print('迁移未完成；事务内数据库变更已回滚。错误类型：' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
