"""仅创建笔译目录订单元数据表，不修改已有订单表。"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target

def apply_migration(connection):
    from translation_folder_orders import TranslationOrderFolder, TranslationFolderImportLog
    TranslationOrderFolder.__table__.create(connection,checkfirst=True)
    TranslationFolderImportLog.__table__.create(connection,checkfirst=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('tables_exist='+str({name:inspect(connection).has_table(name) for name in ['translation_order_folder','translation_folder_import_log']}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
            print('tables_ready=translation_order_folder,translation_folder_import_log')
