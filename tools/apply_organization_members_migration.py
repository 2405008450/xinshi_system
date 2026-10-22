"""显式创建跨部门成员表并导入现有主部门；保留人员、权限和排班。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


ANNOTATION_ROSTER = {
    '客户经理': ['huangmeng', 'weihao', 'litao'],
    '高级项目经理': ['ethan', 'thomas'],
    '项目经理': ['zhongyu', 'jingling', 'yilin', 'liufeng', 'zhengran', 'zhenzhong'],
    '项目助理': ['cuizhen', 'shaojie', 'wanjun', 'yuqi', 'yingqi', 'shuting'],
}


def apply_migration(connection, initialize_annotation=False):
    from sqlalchemy import select, insert
    from department_models import Department, DepartmentMember
    from models import AppUser
    from department_utils import normalize_department
    DepartmentMember.__table__.create(connection,checkfirst=True)
    departments={name:uid for uid,name in connection.execute(select(Department.id,Department.name))}
    existing=set(connection.execute(select(DepartmentMember.department_id,DepartmentMember.user_id)).all())
    for uid,name in connection.execute(select(AppUser.id,AppUser.department)):
        key=(departments.get(normalize_department(name)),uid)
        if key[0] and key not in existing:
            connection.execute(insert(DepartmentMember).values(department_id=key[0],user_id=uid,position=''))
            existing.add(key)
    if initialize_annotation and '标注项目部' not in departments:
        import uuid
        roster = {username: position for position, usernames in ANNOTATION_ROSTER.items() for username in usernames}
        people = connection.execute(select(AppUser.id, AppUser.username, AppUser.full_name, AppUser.is_active).where(AppUser.username.in_(roster))).all()
        if len(people) != len(roster) or any(not p.full_name or not p.is_active for p in people):
            raise RuntimeError('初始化名单存在缺失、重复或停用账号，停止操作')
        department_id = uuid.uuid4()
        connection.execute(insert(Department).values(id=department_id, name='标注项目部', aliases=[], revision=1))
        for person in people:
            connection.execute(insert(DepartmentMember).values(department_id=department_id, user_id=person.id, position=roster[person.username]))


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--initialize-annotation',action='store_true')
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
            print(f'system_department_member_exists={inspect(connection).has_table("system_department_member")}');return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection, args.initialize_annotation)
    print('organization memberships ready; primary departments, permissions and schedules unchanged')


if __name__=='__main__':run()
