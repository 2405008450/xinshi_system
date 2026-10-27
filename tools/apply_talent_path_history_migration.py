"""显式创建路径窗口修改记录表，不修改已有表或历史记录。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from talent_path_edit import TalentPathChange
    TalentPathChange.__table__.create(connection, checkfirst=True)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower()) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')
    import main  # 注册模型，不运行启动钩子。
    import os
    from database import engine
    from sqlalchemy import inspect, text
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    if os.getenv('LOCAL_SCHEMA_MIGRATIONS_ENABLED', '').lower() not in {'0', 'false', 'off', 'no'}:
        raise SystemExit('必须关闭启动自动迁移')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print('talent_path_change_exists=' + str(inspect(connection).has_table('talent_path_change')))
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
        if not inspect(connection).has_table('talent_path_change'):
            raise RuntimeError('新表验证失败')
    print('talent_path_change ready; existing tables and historical data unchanged')


if __name__ == '__main__':
    run()
