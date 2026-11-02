"""仅创建客户语种参考价、收费语种关联及参考价变更记录三张新表。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target
TABLES=('customer_translation_rate','translation_charge_direction','customer_translation_rate_history')


def apply_migration(connection):
    from customer_translation_rates import CustomerTranslationRate,TranslationChargeDirection,CustomerTranslationRateHistory
    for model in (CustomerTranslationRate,TranslationChargeDirection,CustomerTranslationRateHistory):model.__table__.create(connection,checkfirst=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('tables_before='+repr({table:inspect(connection).has_table(table) for table in TABLES}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"));apply_migration(connection)
            print('tables_ready='+','.join(TABLES))
