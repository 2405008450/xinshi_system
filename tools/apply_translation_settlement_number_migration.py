"""初始化笔译结算编号表与独立历史补号命令。"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target


def apply_migration(connection):
    from translation_settlement_number import TranslationSettlementNumber
    from translation_statement_number import TranslationStatementNumber
    for model in (TranslationSettlementNumber,TranslationStatementNumber):
        model.__table__.create(connection,checkfirst=True)


def backfill_payments(db):
    from models import TranslationProject
    from translation_settlement_number import apply, candidate_project_ids, ready
    if not ready(db):
        raise SystemExit('请先初始化笔译结算编号表')
    count=0
    cursor=None
    while True:
        query=candidate_project_ids(db)
        if cursor is not None:
            query=query.filter(TranslationProject.id>cursor)
        ids=[uid for (uid,) in query.order_by(TranslationProject.id).limit(500)]
        if not ids:
            return count
        for uid in ids:
            project=db.query(TranslationProject.id).filter_by(id=uid).with_for_update().first()
            if project:
                count+=apply(db,uid)
            # A retry skips issued identities and resumes safely.
            db.commit()
        cursor=ids[-1]


def backfill_statements(db):
    from customer_statement_workspace import StatementWorkspace,workspace
    from translation_statement_number import historical_boards,issue,ready
    if not ready(db):
        raise SystemExit('请先初始化笔译对账单编号表')
    count=0
    for (client_id,) in db.query(StatementWorkspace.client_id).order_by(StatementWorkspace.client_id).all():
        row=workspace(db,client_id,True)
        boards,dates=historical_boards(db,client_id)
        if row is not None:
            for board in row.payload['boards']:
                boards.setdefault(board['id'],board)
                dates.setdefault(board['id'],row.updated_at)
        count+=issue(db,client_id,boards.values(),dates)
        db.commit()
    return count


if __name__=='__main__':
    from sqlalchemy import inspect, text
    from sqlalchemy.orm import Session
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-only',action='store_true')
    mode.add_argument('--create-table',action='store_true')
    mode.add_argument('--backfill',action='store_true')
    args=parser.parse_args()
    engine=verify_target(args)
    if args.backfill:
        with Session(engine) as db:
            print(f'payment_numbers_issued={backfill_payments(db)}',flush=True)
            print(f'statement_numbers_issued={backfill_statements(db)}',flush=True)
    else:
        with engine.begin() as connection:
            print('translation_settlement_number_ready='+str(inspect(connection).has_table('translation_settlement_number')))
            print('translation_statement_number_ready='+str(inspect(connection).has_table('translation_statement_number')))
            if args.create_table:
                connection.execute(text("SET LOCAL lock_timeout='5s'"))
                apply_migration(connection)
        if args.create_table:
            print('created_or_already_exists=translation_settlement_number,translation_statement_number')
