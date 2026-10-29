"""新增人才口译和笔译综合表现字段，保留原标注评价及所有历史数据。"""
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
        'interpretation_rating': 'INTEGER CONSTRAINT ck_resource_person_interpretation_rating CHECK (interpretation_rating IS NULL OR interpretation_rating BETWEEN 1 AND 6)',
        'interpretation_rating_note': 'TEXT',
        'interpretation_domains': 'TEXT',
        'written_translation_score': 'INTEGER CONSTRAINT ck_resource_person_written_translation_score CHECK (written_translation_score IS NULL OR written_translation_score BETWEEN 1 AND 10)',
        'written_translation_evaluation': 'TEXT',
    }
    columns = {item['name'] for item in inspect(connection).get_columns('resource_person')}
    for name, definition in definitions.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE resource_person ADD COLUMN {name} {definition}'))
    updated = {item['name']: item for item in inspect(connection).get_columns('resource_person')}
    if not all(name in updated and updated[name]['nullable'] for name in definitions):
        raise RuntimeError('综合表现字段验证失败')
    constraints = {item['name'] for item in inspect(connection).get_check_constraints('resource_person')}
    if not {'ck_resource_person_interpretation_rating', 'ck_resource_person_written_translation_score'} <= constraints:
        raise RuntimeError('综合表现取值约束验证失败')


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
            columns = {item['name'] for item in inspect(connection).get_columns('resource_person')}
            for name in ('interpretation_rating', 'interpretation_rating_note', 'interpretation_domains', 'written_translation_score', 'written_translation_evaluation'):
                print(f'{name}_exists={name in columns}')
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('口译、笔译综合表现字段已就绪；原总体评分、具体评价及全部历史值保持不变')


if __name__ == '__main__':
    run()
