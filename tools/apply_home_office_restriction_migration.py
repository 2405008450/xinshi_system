"""显式、幂等创建普通居家办公申请限制及年度额度调减表。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TABLE_NAMES = ('home_office_application_restriction', 'home_office_quota_reduction')


def apply_migration(connection):
    from home_office_models import HomeOfficeApplicationRestriction, HomeOfficeQuotaReduction

    HomeOfficeApplicationRestriction.__table__.create(connection, checkfirst=True)
    HomeOfficeQuotaReduction.__table__.create(connection, checkfirst=True)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    host = socket.gethostname()
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    if roots.get(host.lower()) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')

    from dotenv import dotenv_values
    from sqlalchemy import inspect, text
    from tools.local_startup_config import startup_config

    startup_config({**dotenv_values(ROOT / '.env'), **os.environ})
    from database import engine

    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={host} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            for table_name in TABLE_NAMES:
                print(f'{table_name}: {"存在" if inspect(connection).has_table(table_name) else "待创建"}')
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
        for table_name in TABLE_NAMES:
            if not inspect(connection).has_table(table_name):
                raise RuntimeError(f'未创建 {table_name}')
    for table_name in TABLE_NAMES:
        print(f'{table_name}: 已就绪')


if __name__ == '__main__':
    run()
