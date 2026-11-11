"""扩大旧译员兼容字段，完整接收人才总库的合法文本；不改写业务数据。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text
from tools.apply_translation_requirement_migration import verify_target

TARGET_WIDTHS = {
    'contact_info': 500, 'quality_score': 50, 'direction': 50,
    'languages': 500, 'gender': 20, 'height': 50, 'appearance': 255,
    'nationality': 100, 'ethnicity': 100, 'email1': 255, 'email2': 255,
    'resume_path': None,
}


def apply_migration(connection):
    if connection.dialect.name != 'postgresql':
        raise ValueError('此迁移只适用于 PostgreSQL')
    columns = {c['name']: c['type'] for c in inspect(connection).get_columns('translator')}
    changes = []
    for name, width in TARGET_WIDTHS.items():
        current = columns[name]
        length = getattr(current, 'length', None)
        if length is None or width is not None and length >= width:
            continue
        target = 'TEXT' if width is None else f'VARCHAR({width})'
        changes.append(f'ALTER COLUMN "{name}" TYPE {target}')
    if changes:
        connection.execute(text('ALTER TABLE translator ' + ', '.join(changes)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    with engine.begin() as connection:
        print({c['name']: str(c['type']) for c in inspect(connection).get_columns('translator') if c['name'] in TARGET_WIDTHS})
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
