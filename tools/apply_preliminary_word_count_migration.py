"""仅创建预统计附属表，不修改既有字数表或费用。"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from preliminary_word_count import PreliminaryWordCountMetric
    PreliminaryWordCountMetric.__table__.create(connection,checkfirst=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('table_before='+str(inspect(connection).has_table('preliminary_word_count_metric')))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection);print('table_ready=preliminary_word_count_metric')
