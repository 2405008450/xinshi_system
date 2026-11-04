"""仅创建标注、招聘客户财务修改记录附表，不修改既有表。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target

TABLES = ('project_customer_finance_history',)

def apply_migration(connection):
    from project_customer_finance import ProjectCustomerFinanceHistory
    ProjectCustomerFinanceHistory.__table__.create(connection, checkfirst=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    from sqlalchemy import inspect, text
    with engine.begin() as connection:
        print('tables_before=' + repr({name: inspect(connection).has_table(name) for name in TABLES}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
    if not args.check_only:
        print('tables_ready=' + ','.join(TABLES))
