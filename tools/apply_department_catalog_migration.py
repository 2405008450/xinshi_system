"""显式创建部门目录并导入现有部门名称；不修改人员和排班。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from sqlalchemy import select,insert
    from department_models import Department
    from department_service import DEFAULT_DEPARTMENTS
    from department_utils import DEPARTMENT_ALIASES,normalize_department
    from models import AppUser
    Department.__table__.create(connection,checkfirst=True)
    existing=set()
    for current,aliases in connection.execute(select(Department.name,Department.aliases)):
        existing.update([current,*(aliases or [])])
    names=list(dict.fromkeys([*DEFAULT_DEPARTMENTS,*[normalize_department(value) for value in connection.execute(select(AppUser.department).distinct()).scalars() if value and value.strip()]]))
    for name in names:
        if name not in existing:
            connection.execute(insert(Department).values(name=name,aliases=[old for old,current in DEPARTMENT_ALIASES.items() if current==name],revision=1))


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
            print(f'system_department_exists={inspect(connection).has_table("system_department")}');return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('department catalog ready; user and schedule data unchanged')


if __name__=='__main__':run()
