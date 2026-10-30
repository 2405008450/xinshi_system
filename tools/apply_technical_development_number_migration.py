"""只创建技术任务编号、报告重试凭证新表，并初始化新编号映射，不改原表。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    import main  # 注册项目全部关系模型，不运行启动钩子。
    from sqlalchemy.orm import Session
    from technical_development import DevelopmentTaskNumber, DevelopmentReportReceipt, DevelopmentTask, lock_tree, allocate_number
    for model in (DevelopmentTaskNumber, DevelopmentReportReceipt):
        model.__table__.create(connection, checkfirst=True)
    # 只向新增映射表初始化原任务的编号，不修改任务或原工作报告。
    with Session(bind=connection) as db:
        lock_tree(db)
        for row in db.query(DevelopmentTask).order_by(DevelopmentTask.created_at, DevelopmentTask.id):
            allocate_number(db, row.id, row.created_at)
        db.flush()
        db.commit()


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}.get(socket.gethostname().lower()) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')
    from dotenv import dotenv_values
    from tools.local_startup_config import startup_config
    startup_config({**dotenv_values(ROOT / '.env'), **os.environ})
    from database import engine
    from sqlalchemy import inspect, text
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print({name: inspect(connection).has_table(name) for name in ('technical_development_task_number', 'technical_development_report_receipt')})
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('技术任务编号与报告凭证新表就绪，原任务及原工作报告未修改。')


if __name__ == '__main__':
    run()
