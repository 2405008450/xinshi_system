"""按明确指令创建口译项目部并追加指定人员及客户、销售人员，不移除原归属。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.apply_translation_requirement_migration import verify_target

NAME = '口译项目部'
FIXED = {'zixia', 'kuangjiao', 'ethan', 'williamzhao'}
ROLES = {'客户专员', '客户经理', '销售', '销售专员', '销售经理'}
DEPARTMENTS = {'客户部', '销售', '销售部'}


def selected_users(db):
    from sqlalchemy import exists, func, or_
    from models import AppUser, Role, UserRole
    from department_models import Department, DepartmentMember
    role_match = exists().where(UserRole.user_id == AppUser.id, UserRole.role_id == Role.id,
                                Role.role_name.in_(ROLES))
    member_match = exists().where(DepartmentMember.user_id == AppUser.id,
        DepartmentMember.department_id == Department.id,
        or_(Department.name.in_(DEPARTMENTS), DepartmentMember.position.in_(ROLES)))
    return db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False),
        or_(func.lower(AppUser.username).in_(FIXED), AppUser.department.in_(DEPARTMENTS),
            role_match, member_match)).order_by(func.lower(AppUser.username)).all()


def configure(db, expected_members=None, apply=False):
    from department_models import Department, DepartmentMember
    from chat_time import now
    departments = db.query(Department).order_by(Department.id)
    if apply:
        departments = departments.with_for_update()
    matches = [row for row in departments.all() if NAME.casefold() in
               {value.casefold() for value in [row.name, *(row.aliases or [])]}]
    if len(matches) > 1 or (matches and matches[0].name != NAME):
        raise ValueError('口译项目部名称存在别名冲突，停止写入')
    users = selected_users(db)
    usernames = {(row.username or '').lower() for row in users}
    if not FIXED.issubset(usernames):
        raise ValueError('紫霞、旷姣、Ethan、赵震锋未能全部匹配有效账号，停止写入')
    if expected_members is not None and usernames != set(expected_members):
        raise ValueError('待加入名单与已核对名单不一致，停止写入')
    department = matches[0] if matches else None
    existing = {uid for uid, in db.query(DepartmentMember.user_id).filter_by(department_id=department.id)} if department else set()
    missing = [row for row in users if row.id not in existing]
    result = dict(department=NAME, created=department is None, applied=apply,
                  added=[row.username for row in missing], total_selected=len(users),
                  members=[dict(username=row.username, name=row.full_name) for row in users])
    if apply:
        actor = next(row for row in users if row.username.lower() == 'williamzhao')
        stamp = now()
        if department is None:
            department = Department(name=NAME, aliases=[], revision=1, updated_by=actor.id,
                                    created_at=stamp, updated_at=stamp)
            db.add(department)
            db.flush()
        elif missing:
            department.revision += 1
            department.updated_by = actor.id
            department.updated_at = stamp
        db.add_all(DepartmentMember(department_id=department.id, user_id=row.id,
            position='', created_at=stamp, updated_at=stamp) for row in missing)
        db.flush()
    return result


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-members', help='已核对的账号，逗号分隔；执行写入时必填')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.expected_members:
        parser.error('写入前必须提供已核对的 expected-members')
    engine = verify_target(args)
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        if not args.apply:
            db.execute(text('SET TRANSACTION READ ONLY'))
        db.execute(text("SET LOCAL lock_timeout='5s'"))
        db.execute(text("SET LOCAL statement_timeout='30s'"))
        expected = args.expected_members.split(',') if args.expected_members else None
        result = configure(db, expected, args.apply)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    run()
