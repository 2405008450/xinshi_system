"""仅创建简单需求统计来源表，不修改旧表及历史数据。"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target

def apply_migration(connection):
    import translation_simple_requirements
    from translation_simple_requirement_counts import SimpleRequirementWordCount
    SimpleRequirementWordCount.__table__.create(connection,checkfirst=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('table_exists='+str(inspect(connection).has_table('translation_simple_requirement_word_count')))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection);print('table_ready=translation_simple_requirement_word_count')
