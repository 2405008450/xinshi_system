"""显式、幂等创建居家资格及居家办公申请表，不改动既有表或排班记录。"""
import argparse
import socket
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from home_office_models import HomeOfficeQualification,HomeOfficeApplication,HomeOfficeAnnualUsage
    HomeOfficeQualification.__table__.create(connection,checkfirst=True)
    HomeOfficeApplication.__table__.create(connection,checkfirst=True)
    HomeOfficeAnnualUsage.__table__.create(connection,checkfirst=True)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    from tools.local_startup_config import startup_config
    from dotenv import dotenv_values
    import os
    startup_config({**dotenv_values(ROOT/'.env'),**os.environ})
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        existing={name:inspect(connection).has_table(name) for name in ('home_office_qualification','home_office_application','home_office_annual_usage')}
        if args.check_only:print(existing);return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('home_office_qualification / home_office_application / home_office_annual_usage: ready; existing tables and business records unchanged')


if __name__=='__main__':run()
