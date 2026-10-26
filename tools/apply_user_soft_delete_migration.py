"""显式新增人员逻辑删除字段，不删除或回填业务记录。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from sqlalchemy import text
    connection.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS is_deleted boolean NOT NULL DEFAULT false"))
    connection.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL"))


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    import main  # noqa: F401 仅注册模型，不执行启动迁移。
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print("deletion_columns=" + str({c["name"] for c in inspect(connection).get_columns("app_user")} & {"is_deleted", "deleted_at"}));return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('user deletion columns ready; existing business records unchanged')


if __name__=='__main__':run()
