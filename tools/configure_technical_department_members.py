"""按明确指令给 ethan、thomas 增加IT部成员关系，保留原部门及职务。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def configure(db, department_id, expected_revision, apply=False):
    from sqlalchemy import func
    from models import AppUser
    from department_models import Department, DepartmentMember
    from technical_development import TECHNICAL_DEPARTMENTS
    from chat_time import now
    dept = db.query(Department).filter_by(id=department_id).with_for_update().one()
    if dept.name not in TECHNICAL_DEPARTMENTS or dept.revision != expected_revision:
        raise RuntimeError('技术部门名称或版本不匹配')
    people = db.query(AppUser).filter(func.lower(AppUser.username).in_(['ethan', 'thomas']), AppUser.is_active.is_(True), AppUser.is_deleted.is_(False)).with_for_update().all()
    if {person.username.lower() for person in people} != {'ethan', 'thomas'} or len(people) != 2:
        raise RuntimeError('未找到唯一有效的 ethan、thomas 账号')
    missing = [person for person in people if not db.get(DepartmentMember, (dept.id, person.id))]
    result = dict(department=dept.name, revision=dept.revision, add=sorted(person.username for person in missing), existing_departments_preserved=True, applied=apply)
    if apply and missing:
        stamp = now()
        db.add_all(DepartmentMember(department_id=dept.id, user_id=person.id, position='', created_at=stamp, updated_at=stamp) for person in missing)
        dept.revision += 1; dept.updated_at = stamp; dept.updated_by = None
        db.flush()
    return result


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--department-id', type=UUID, required=True)
    parser.add_argument('--expected-revision', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
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
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    import main  # 仅注册全部ORM关系，不执行启动钩子。
    from sqlalchemy.orm import Session
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with Session(engine) as db:
        result = configure(db, args.department_id, args.expected_revision, args.apply)
        if args.apply: db.commit()
        else: db.rollback()
        print(result)


if __name__ == '__main__':
    run()
