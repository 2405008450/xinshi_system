"""仅创建每位客户联系人的联系方式与说明附表，不修改既有表。"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target
def apply_migration(connection):
    from client_contact_people import ClientContactPersonDetail
    ClientContactPersonDetail.__table__.create(connection,checkfirst=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--confirm-target',required=True);p.add_argument('--expected-commit',required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args();engine=verify_target(a)
    from sqlalchemy import inspect,text
    with engine.begin() as c:
        print('contact_detail_before=',inspect(c).has_table('client_contact_person_detail'))
        if not a.check_only:
            c.execute(text("SET LOCAL lock_timeout='5s'"));apply_migration(c)
    if not a.check_only:print('contact_detail_ready=True')
