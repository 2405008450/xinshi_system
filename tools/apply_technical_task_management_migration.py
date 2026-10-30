"""仅创建技术任务层级编号和删除记录新表，既有任务和原编号表不修改。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    import main  # 仅注册模型，不执行启动钩子。
    from sqlalchemy.orm import Session
    from technical_task_management import TABLES, initialize_numbers
    for table in TABLES: table.create(connection, checkfirst=True)
    with Session(bind=connection) as db:
        initialize_numbers(db)
        db.commit()


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}.get(socket.gethostname().lower()) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe': raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit: raise SystemExit('Git 提交不匹配')
    from dotenv import dotenv_values
    from tools.local_startup_config import startup_config
    startup_config({**dotenv_values(ROOT / '.env'), **os.environ})
    from database import engine
    from sqlalchemy import inspect, text
    from technical_task_management import TABLES
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system': raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print({table.name: inspect(connection).has_table(table.name) for table in TABLES}); return
        connection.execute(text("SET LOCAL lock_timeout='5s'")); connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('technical_task_hierarchy_number、technical_task_deletion：已就绪；仅初始化新增编号映射，既有任务和原编号表未修改。')


if __name__ == '__main__': run()
