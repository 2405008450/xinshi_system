"""按本次明确指令新增笔译项目部及五位成员；只追加归属，不改变原有部门。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.apply_translation_requirement_migration import verify_target

USERNAMES = ('thomas', 'shaofei', 'menghua', 'lixian', 'williamzhao')


def ensure(db):
    from annotation_progress_time import business_now
    from department_models import Department, DepartmentMember
    from models import AppUser
    from sqlalchemy import func
    rows = db.query(Department).order_by(Department.id).with_for_update().all()
    matches = [d for d in rows if '笔译项目部' in [d.name, *(d.aliases or [])]]
    if len(matches) > 1 or (matches and matches[0].name != '笔译项目部'):
        raise ValueError('目标名称存在别名冲突，请核对后处理')
    users = db.query(AppUser).filter(func.lower(AppUser.username).in_(USERNAMES), AppUser.is_active.is_(True), AppUser.is_deleted.is_(False)).all()
    by_name = {(u.username or '').lower(): u for u in users}
    if len(users) != 5 or set(by_name) != set(USERNAMES):
        raise ValueError('五位成员未能唯一匹配有效账号，停止写入')
    actor = by_name['williamzhao']
    department = matches[0] if matches else Department(name='笔译项目部', aliases=[], revision=1, updated_by=actor.id)
    if not matches:
        db.add(department); db.flush()
    current = {uid for uid, in db.query(DepartmentMember.user_id).filter_by(department_id=department.id)}
    added = []
    for name in USERNAMES:
        person = by_name[name]
        if person.id not in current:
            db.add(DepartmentMember(department_id=department.id, user_id=person.id, position=''))
            added.append(name)
    if added:
        department.revision += 1 if matches else 0
        department.updated_at = business_now()
        department.updated_by = actor.id
    db.flush()
    return dict(department='笔译项目部', added=added, members=[{'username':name,'name':by_name[name].full_name} for name in USERNAMES])


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    from sqlalchemy.orm import Session
    from sqlalchemy import text
    with Session(engine) as db:
        db.execute(text("SET LOCAL lock_timeout='5s'"))
        db.execute(text("SET LOCAL statement_timeout='30s'"))
        result = ensure(db)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps({'applied':args.apply, **result}, ensure_ascii=True))


if __name__ == '__main__':
    run()
