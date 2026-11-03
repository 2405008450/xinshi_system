"""仅创建收费项计价口径附属表。"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from translation_quantity_basis import TranslationChargeQuantityBasis
    TranslationChargeQuantityBasis.__table__.create(connection,checkfirst=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true');args=parser.parse_args();engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('table_before='+str(inspect(connection).has_table('translation_charge_quantity_basis')))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"));apply_migration(connection);print('table_ready=translation_charge_quantity_basis')
