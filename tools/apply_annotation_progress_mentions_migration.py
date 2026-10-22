"""创建标注项目共用的进度默认@设置表，不修改既有聊天、进度和参与人。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from annotation_progress_chat import ProgressMentionDefaults
    ProgressMentionDefaults.__table__.create(connection, checkfirst=True)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':
        raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    import main
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print('defaults_table_exists=',inspect(connection).has_table('annotation_progress_mention_defaults'))
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('annotation progress mention defaults ready; existing records unchanged')


if __name__=='__main__':run()
