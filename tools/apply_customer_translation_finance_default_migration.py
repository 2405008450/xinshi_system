"""仅创建客户笔译财务默认设置表。"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from customer_statement_defaults import CustomerTranslationFinanceDefault

    CustomerTranslationFinanceDefault.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    from sqlalchemy import inspect, text

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    with engine.begin() as connection:
        table = 'customer_translation_finance_default'
        print(f'{table}: exists={inspect(connection).has_table(table)}')
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
            if not inspect(connection).has_table(table):
                raise RuntimeError(f'{table} 创建失败')
    if not args.check_only:
        print(f'{table}: ready')
