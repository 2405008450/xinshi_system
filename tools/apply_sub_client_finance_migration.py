"""仅创建子客户笔译财务设置表。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from sub_client_finance import SubClientFinancePreference
    SubClientFinancePreference.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    from sqlalchemy import inspect, text
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    with engine.begin() as connection:
        print('sub_client_finance_preference_before=', inspect(connection).has_table('sub_client_finance_preference'))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            apply_migration(connection)
            print('sub_client_finance_preference_ready=', inspect(connection).has_table('sub_client_finance_preference'))
