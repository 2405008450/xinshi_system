"""新增企微大群、人才所在地时区和可联系时段；不改历史记录。"""
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
    definitions = {
        'wecom_large_groups': 'TEXT',
        'residence_timezone': 'VARCHAR(12)',
        'contact_availability': "VARCHAR(30) CONSTRAINT ck_resource_person_contact_availability CHECK (contact_availability IS NULL OR contact_availability IN ('anytime', 'morning', 'afternoon', 'evening', 'weekday_daytime', 'weekend', 'appointment'))",
    }
    columns = {item['name'] for item in inspect(connection).get_columns('resource_person')}
    for name, definition in definitions.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE resource_person ADD COLUMN {name} {definition}'))
    updated = {item['name']: item for item in inspect(connection).get_columns('resource_person')}
    if not all(name in updated and updated[name]['nullable'] for name in definitions):
        raise RuntimeError('新增联系资料字段验证失败')
    constraints = inspect(connection).get_check_constraints('resource_person')
    if not any(item['name'] == 'ck_resource_person_contact_availability' for item in constraints):
        raise RuntimeError('可联系时段约束不符合预期，停止迁移')


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
            for name in ('wecom_large_groups', 'residence_timezone', 'contact_availability'):
                print(f'{name}_exists={name in names}')
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('人才联系资料字段已就绪；新增字段历史值为空，原有小群名称及业务记录不变')


if __name__ == '__main__':
    run()
