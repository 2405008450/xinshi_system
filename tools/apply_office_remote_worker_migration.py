"""仅创建居家办公人员登记表及其约束。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from office_management import OfficeRemoteWorker

    OfficeRemoteWorker.__table__.create(connection, checkfirst=True)


def run():
    from sqlalchemy import inspect, text
    from office_management import OfficeRemoteWorker

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    table = OfficeRemoteWorker.__tablename__
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table('app_user'):
            raise SystemExit('缺少人员表 app_user')
        print(f'{table}_before={inspector.has_table(table)}')
        if args.check_only:
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    with engine.connect() as connection:
        if not inspect(connection).has_table(table):
            raise SystemExit(f'{table} 创建后校验失败')
        print(f'{table}_ready=True')


if __name__ == '__main__':
    run()
