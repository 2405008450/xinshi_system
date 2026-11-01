"""仅创建项目经理安排、安排接收人和简单需求操作事件表。"""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.apply_translation_requirement_migration import verify_target

TABLES = ('translation_requirement_dispatch', 'translation_requirement_dispatch_recipient', 'translation_requirement_event')


def apply_migration(connection):
    from translation_requirement_dispatch import RequirementDispatch, RequirementDispatchRecipient, RequirementEvent
    for model in (RequirementDispatch, RequirementDispatchRecipient, RequirementEvent):
        model.__table__.create(connection, checkfirst=True)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('tables_before='+repr({name:inspect(connection).has_table(name) for name in TABLES}))
        if args.check_only:return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('tables_ready='+','.join(TABLES))


if __name__=='__main__':run()
