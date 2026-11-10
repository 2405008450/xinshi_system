"""只创建客户开票资料、开票主体两张新表，并初始化三个主体的空白资料。"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target
TABLES=('organization_invoice_subject','client_invoice_profile','finance_invoice_settings','finance_invoice_request','finance_invoice_attachment')

def apply_migration(connection):
    from invoice_parties import OrganizationInvoiceSubject,ClientInvoiceProfile,SUBJECTS,InvoiceParty
    from invoice_workflow import InvoiceSettings,InvoiceRequest,InvoiceAttachment
    from annotation_progress_time import business_now
    for model in (OrganizationInvoiceSubject,ClientInvoiceProfile,InvoiceSettings,InvoiceRequest,InvoiceAttachment):model.__table__.create(connection,checkfirst=True)
    dialect=connection.dialect.name
    if dialect=='postgresql':from sqlalchemy.dialects.postgresql import insert
    elif dialect=='sqlite':from sqlalchemy.dialects.sqlite import insert
    else:raise ValueError('只支持 PostgreSQL 或隔离 SQLite')
    connection.execute(insert(InvoiceSettings).values(key='invoice',user_ids=None,revision=1,updated_at=business_now()).on_conflict_do_nothing(index_elements=['key']))
    for key,(_,name) in SUBJECTS.items():
        connection.execute(insert(OrganizationInvoiceSubject).values(key=key,data=InvoiceParty(title=name).model_dump(),revision=1,updated_at=business_now()).on_conflict_do_nothing(index_elements=['key']))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();engine=verify_target(args)
    from sqlalchemy import inspect,text
    with engine.begin() as connection:
        print('tables_before='+repr({name:inspect(connection).has_table(name) for name in TABLES}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"));apply_migration(connection)
    if not args.check_only:print('tables_ready='+','.join(TABLES)+'; subjects=3; invoice_details=待填写')
