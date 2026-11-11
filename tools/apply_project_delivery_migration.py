"""仅创建通用项目会话发送记录和邮件会话联动表，不改既有表及业务数据。"""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from project_delivery import TABLES
    for model in TABLES:model.__table__.create(connection,checkfirst=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();engine=verify_target(args)
    from sqlalchemy import inspect,text
    from project_delivery import TABLES
    with engine.begin() as connection:
        print('tables_before='+str({model.__tablename__:inspect(connection).has_table(model.__tablename__) for model in TABLES}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
            print('tables_ready='+','.join(model.__tablename__ for model in TABLES))
