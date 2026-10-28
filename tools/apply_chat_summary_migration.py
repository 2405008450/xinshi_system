"""为八类聊天总结增加结构化内容与关联范围；不重分类或删除历史记录。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from sqlalchemy import inspect,text
    from resource_issue_models import DevelopmentIssueAudience
    inspector=inspect(connection)
    if not inspector.has_table('resource_development_issue') or not inspector.has_table('system_department'):
        raise RuntimeError('需要先初始化开拓事项和部门目录')
    connection.execute(text("ALTER TABLE resource_development_issue ADD COLUMN IF NOT EXISTS summary_data JSON NOT NULL DEFAULT '{}'::json"))
    # 初始 SQL 使用内联 CHECK，PostgreSQL 自动命名的旧约束也必须移除。
    # 仅更新 ORM 命名约束会让新旧约束同时生效，新增四类仍无法保存。
    connection.execute(text('ALTER TABLE resource_development_issue DROP CONSTRAINT IF EXISTS resource_development_issue_category_check'))
    constraints=inspector.get_check_constraints('resource_development_issue')
    current=next((row['sqltext'] for row in constraints if row['name']=='ck_development_issue_category'),'')
    if not all(f"'{name}'" in current for name in ['request','decision','risk','standard']):
        connection.execute(text('ALTER TABLE resource_development_issue DROP CONSTRAINT IF EXISTS ck_development_issue_category'))
        connection.execute(text("ALTER TABLE resource_development_issue ADD CONSTRAINT ck_development_issue_category CHECK (category IN ('arrangement','request','idea','decision','execution','problem','risk','standard'))"))
    DevelopmentIssueAudience.__table__.create(connection,checkfirst=True)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    import main  # noqa: F401 只注册模型。
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:
            inspector=inspect(connection)
            constraints={row['name'] for row in inspector.get_check_constraints('resource_development_issue')}
            print(f'summary_data_exists={"summary_data" in {column["name"] for column in inspector.get_columns("resource_development_issue")}} audience_exists={inspector.has_table("resource_issue_audience")} legacy_category_constraint_exists={"resource_development_issue_category_check" in constraints}');return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('chat summary schema ready; historical records and notifications unchanged')


if __name__=='__main__':run()
