"""Create only the interpretation project settings table."""
import argparse
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from interpretation_settings import InterpretationProjectSettings

    InterpretationProjectSettings.__table__.create(connection, checkfirst=True)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    hostname = socket.gethostname()
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    if roots.get(hostname.lower()) != ROOT or Path.cwd().resolve() != ROOT:
        raise SystemExit('主机或项目目录不匹配')
    if Path(sys.executable).absolute() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('请使用项目虚拟环境')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')

    from database import engine
    from sqlalchemy import inspect, text

    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={hostname} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
        print(f'interpretation_project_settings_exists={inspect(connection).has_table("interpretation_project_settings")}')


if __name__ == '__main__':
    run()
