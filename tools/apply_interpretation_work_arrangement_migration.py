"""仅创建口译今日安排新表及其约束，不修改既有表或历史数据。"""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from interpretation_work_arrangement import InterpretationWorkDay
    InterpretationWorkDay.__table__.create(connection,checkfirst=True)


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        print('interpretation_work_day_before='+str(inspect(connection).has_table('interpretation_work_day')))
        if args.check_only:return
        apply_migration(connection)
    with engine.connect() as connection:
        print('interpretation_work_day_ready='+str(inspect(connection).has_table('interpretation_work_day')))


if __name__=='__main__':run()
