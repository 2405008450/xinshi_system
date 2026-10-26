"""资源需求多版本、部分语种批次与发圈发帖通知回执结构初始化；不补发历史通知。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from sqlalchemy import text
    from resource_request_dispatch_models import ResourceRequestDispatch, ResourceRequestDispatchRecipient
    from resource_request_models import ResourceRequest
    connection.execute(text("ALTER TABLE resource_request ADD COLUMN IF NOT EXISTS request_content JSONB NOT NULL DEFAULT '{}'::jsonb"))
    connection.execute(text("ALTER TABLE resource_request ADD COLUMN IF NOT EXISTS partial_requested BOOLEAN NOT NULL DEFAULT false"))
    connection.execute(text("ALTER TABLE resource_request ADD COLUMN IF NOT EXISTS partial_sequence INTEGER NOT NULL DEFAULT 0"))
    connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_request_partial_batch ON resource_request (annotation_project_id, partial_sequence) WHERE partial_sequence > 0"))
    ResourceRequestDispatch.__table__.create(connection,checkfirst=True)
    ResourceRequestDispatchRecipient.__table__.create(connection,checkfirst=True)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            print('resource_request_content_exists=', 'request_content' in {row['name'] for row in inspect(connection).get_columns('resource_request')});return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"));apply_migration(connection)
    print('resource request versions and dispatch receipts ready; historical content retained; no notifications sent')


if __name__=='__main__':run()
