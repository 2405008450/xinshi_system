"""显式创建开发任务会话关联新表；可按用户指令移动并置顶现有技术沟通群。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from technical_task_conversations import TaskConversation
    TABLES = [TaskConversation.__table__]
    for table in TABLES: table.create(connection, checkfirst=True)


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--configure-general', action='store_true')
    parser.add_argument('--expected-general-revision', type=int)
    parser.add_argument('--actor-username', default='williamzhao')
    args = parser.parse_args()
    if {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}.get(socket.gethostname().lower()) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe': raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit: raise SystemExit('Git 提交不匹配')
    from dotenv import dotenv_values
    from tools.local_startup_config import startup_config
    startup_config({**dotenv_values(ROOT / '.env'), **os.environ})
    from database import engine
    from sqlalchemy import inspect, text
    from technical_task_conversations import TaskConversation
    TABLES = [TaskConversation.__table__]
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system': raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print({table.name: inspect(connection).has_table(table.name) for table in TABLES})
            from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryFolder as Folder
            from sqlalchemy import select
            from technical_task_conversations import GENERAL_NAME
            matches = connection.execute(select(Category.__table__.c.id,Category.__table__.c.revision).where(Category.__table__.c.name==GENERAL_NAME,Category.__table__.c.active.is_(True))).all()
            print('general_matches=',len(matches),'revisions=',[row.revision for row in matches])
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'")); connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
        if args.configure_general:
            if args.expected_general_revision is None: raise SystemExit('移动现有群必须明确核对版本')
            import main
            from sqlalchemy.orm import Session
            from models import AppUser
            from technical_task_conversations import configure_general
            with Session(bind=connection) as db:
                actor=db.query(AppUser).filter_by(username=args.actor_username,is_active=True,is_deleted=False).one()
                print(configure_general(db,actor=actor,expected_revision=args.expected_general_revision))
                db.commit()
    print('technical_task_conversation：已就绪；现有群移动及置顶仅在明确指定 --configure-general 时执行，原消息保持不变。')


if __name__ == '__main__': run()
