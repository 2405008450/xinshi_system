"""新增人才分级，存量档案初始化为待评定；不覆盖已评定数据。"""
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
    columns = inspect(connection).get_columns('resource_person')
    if not any(column['name'] == 'talent_grade' for column in columns):
        connection.execute(text(
            "ALTER TABLE resource_person ADD COLUMN talent_grade VARCHAR(20) NOT NULL DEFAULT 'pending' "
            "CONSTRAINT ck_resource_person_talent_grade CHECK (talent_grade IN ('S', 'A', 'B', 'C', 'pending'))"
        ))
    column = next(item for item in inspect(connection).get_columns('resource_person')
                  if item['name'] == 'talent_grade')
    constraints = inspect(connection).get_check_constraints('resource_person')
    if (column['nullable'] or not column.get('default')
            or 'pending' not in column['default']
            or not any(item['name'] == 'ck_resource_person_talent_grade' for item in constraints)):
        raise RuntimeError('人才分级字段、默认值或约束不符合预期，停止迁移')


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
            print('talent_grade_exists=' + str(any(item['name'] == 'talent_grade'
                  for item in inspect(connection).get_columns('resource_person'))))
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('resource_person.talent_grade 已就绪；新增字段时全部存量档案默认为待评定，已有评级不覆盖')


if __name__ == '__main__':
    run()
