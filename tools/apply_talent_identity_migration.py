"""新增身份证号码与视力；不改历史记录。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from sqlalchemy import inspect, text
    columns = {item['name'] for item in inspect(connection).get_columns('resource_person')}
    for name, definition in {'identity_number': 'VARCHAR(50)', 'eyesight': 'VARCHAR(255)'}.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE resource_person ADD COLUMN {name} {definition}'))
    updated = {item['name'] for item in inspect(connection).get_columns('resource_person')}
    if not {'identity_number', 'eyesight'} <= updated:
        raise RuntimeError('身份与视力字段验证失败')


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    if (roots.get(socket.gethostname().lower()) != ROOT or Path.cwd().resolve() != ROOT
            or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe'):
        raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')
    from database import engine
    from sqlalchemy import inspect, text
    if os.getenv('LOCAL_SCHEMA_MIGRATIONS_ENABLED', '').lower() not in {'0', 'false', 'off', 'no'}:
        raise SystemExit('必须关闭启动自动迁移')
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            names = {item['name'] for item in inspect(connection).get_columns('resource_person')}
            for name in ('identity_number', 'eyesight'):
                print(f'{name}_exists={name in names}')
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('身份证号码与视力字段已就绪；历史值不变')


if __name__ == '__main__':
    run()
