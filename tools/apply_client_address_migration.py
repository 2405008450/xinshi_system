"""仅创建客户完整地址附表。"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target
def apply_migration(connection):
    from models import ClientAddress,SubClientAddress
    ClientAddress.__table__.create(connection,checkfirst=True)
    SubClientAddress.__table__.create(connection,checkfirst=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--confirm-target',required=True);p.add_argument('--expected-commit',required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args();engine=verify_target(a)
    from sqlalchemy import inspect,text
    with engine.begin() as c:
        print('client_address_before=',inspect(c).has_table('client_address'))
        if not a.check_only:
            c.execute(text("SET LOCAL lock_timeout='5s'"));apply_migration(c)
    if not a.check_only:print('client_address_ready=True')
