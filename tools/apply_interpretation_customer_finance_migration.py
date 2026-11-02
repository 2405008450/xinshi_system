"""仅创建口译客户财务及历史记录两张新表，可重复执行。"""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from interpretation_customer_finance import InterpretationCustomerFinance, InterpretationCustomerFinanceHistory
    for model in (InterpretationCustomerFinance, InterpretationCustomerFinanceHistory):
        model.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    from sqlalchemy import inspect, text
    tables = ['interpretation_customer_finance', 'interpretation_customer_finance_history']
    with engine.begin() as connection:
        print('tables_before=' + repr({name: inspect(connection).has_table(name) for name in tables}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
            print('tables_ready=' + repr({name: inspect(connection).has_table(name) for name in tables}))
