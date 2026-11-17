"""显式新增人才编辑日志表，不修改或回填人才主表。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from talent_edit_audit import TalentEditLog
    TalentEditLog.__table__.create(connection, checkfirst=True)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True, help='已授权目标 host:port/database')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if socket.gethostname().lower() != 'pc' or ROOT != Path(r'E:\xinshi_system') or Path.cwd().resolve() != ROOT:
        raise SystemExit('主机或项目目录不匹配')
    if Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('必须使用项目虚拟环境')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')
    import main  # 只注册模型，不启动服务或自动迁移。
    import os
    from database import engine
    from sqlalchemy import inspect, text
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target:
        raise SystemExit('数据库目标不匹配')
    if os.getenv('LOCAL_SCHEMA_MIGRATIONS_ENABLED', '').lower() not in {'0', 'false', 'off', 'no'}:
        raise SystemExit('必须关闭启动自动迁移')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print('talent_edit_log_exists=' + str(inspect(connection).has_table('talent_edit_log')))
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
        indexes = {row['name'] for row in inspect(connection).get_indexes('talent_edit_log')}
        if not {'ix_talent_edit_log_person_time', 'ix_talent_edit_log_actor_time'} <= indexes:
            raise RuntimeError('日志索引不完整')
    print('人才编辑日志表及索引就绪；既有档案与历史数据未修改')


if __name__ == '__main__':
    run()
