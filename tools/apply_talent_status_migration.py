"""显式扩展人才档案状态约束，不修改历史数据，不接入启动自动迁移。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from sqlalchemy import text
    from resource_models import TALENT_STATUSES
    if connection.dialect.name != 'postgresql':
        raise RuntimeError('此迁移只支持 PostgreSQL')
    values = ', '.join(f"'{value}'" for value in TALENT_STATUSES)
    connection.execute(text('ALTER TABLE resource_person DROP CONSTRAINT IF EXISTS ck_resource_person_status'))
    connection.execute(text('ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_status '
                            f'CHECK (status IN ({values}))'))


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
    from resource_models import TALENT_STATUSES
    if os.getenv('LOCAL_SCHEMA_MIGRATIONS_ENABLED', '').lower() not in {'0', 'false', 'off', 'no'}:
        raise SystemExit('必须关闭启动自动迁移')
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        constraints = inspect(connection).get_check_constraints('resource_person')
        current = next((item['sqltext'] for item in constraints if item['name'] == 'ck_resource_person_status'), None)
        print(f'ck_resource_person_status={current}')
        if args.check_only:
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
        updated = next(item['sqltext'] for item in inspect(connection).get_check_constraints('resource_person')
                       if item['name'] == 'ck_resource_person_status')
        if not all(f"'{value}'" in updated for value in TALENT_STATUSES):
            raise RuntimeError('状态约束验证失败，回滚迁移')
    print('resource_person 状态约束已更新；历史数据保持原值')


if __name__ == '__main__':
    run()
