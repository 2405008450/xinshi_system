"""仅创建笔译客户财务修改事件及事件明细两张新表。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target
TABLES=('translation_customer_finance_event','translation_customer_finance_event_item')


def apply_migration(connection):
    from translation_finance_audit import TranslationFinanceEvent,TranslationFinanceEventItem
    for model in (TranslationFinanceEvent,TranslationFinanceEventItem):model.__table__.create(connection,checkfirst=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('tables_before='+repr({table:inspect(connection).has_table(table) for table in TABLES}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"));apply_migration(connection);print('tables_ready='+','.join(TABLES))
