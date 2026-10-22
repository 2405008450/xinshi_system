"""组织名册；部门职务不授予任何系统权限。"""
from sqlalchemy import inspect, or_, select
from fastapi import HTTPException
from models import AppUser
from department_models import Department, DepartmentMember
from department_utils import department_filter_values
from chat_time import now


def ready(db):
    return hasattr(db, 'connection') and inspect(db.connection()).has_table(DepartmentMember.__tablename__)


def department_condition(db, names):
    """兼容主部门及跨部门成员，用于人员筛选和部门通知。"""
    values = {value for name in names for value in department_filter_values(name, db)}
    primary = AppUser.department.in_(values)
    if not ready(db):
        return primary
    ids = select(DepartmentMember.user_id).join(Department, Department.id == DepartmentMember.department_id).where(Department.name.in_(values))
    return or_(primary, AppUser.id.in_(ids))


def directory(db, user):
    import department_service as departments
    result = departments.catalog(db, user)
    aliases = result['aliases']
    people = db.query(AppUser).order_by(AppUser.full_name, AppUser.username).all()
    links = db.query(DepartmentMember).all() if ready(db) else []
    by_id = {str(d['id']): d for d in result['items']}
    memberships = {}
    for link in links:
        dept = by_id.get(str(link.department_id))
        if dept:
            memberships.setdefault(str(link.user_id), {})[dept['name']] = dict(id=dept['id'], name=dept['name'], position=link.position)
    items = []
    for person in people:
        groups = memberships.get(str(person.id), {})
        primary = aliases.get(person.department, person.department)
        if primary and primary not in groups:
            dept = next((d for d in result['items'] if d['name'] == primary), None)
            if dept:
                groups[primary] = dict(id=dept['id'], name=primary, position='')
        items.append(dict(id=str(person.id), name=person.full_name or person.username, username=person.username,
                          active=person.is_active, primaryDepartment=primary, departments=list(groups.values())))
    result.update(membershipReady=ready(db), people=items)
    return result


def save_members(db, user, department_id, entries, revision):
    import department_service as departments
    if not departments.can_manage(db, user):
        raise HTTPException(403, '仅 ethan、jimmy 和超级管理员可管理组织架构')
    if not ready(db):
        raise HTTPException(503, '组织成员表尚未初始化')
    # 所有部门使用同一加锁顺序，防止同一人员跨部门编辑互相覆盖。
    rows = db.query(Department).order_by(Department.id).with_for_update().all()
    dept = next((d for d in rows if d.id == department_id), None)
    if not dept:
        raise HTTPException(404, '部门不存在')
    if revision != dept.revision:
        raise HTTPException(409, '名册已被修改，请刷新后重新编辑')
    requested = {entry.user_id: entry.position.strip() for entry in entries}
    if len(requested) != len(entries):
        raise HTTPException(422, '同一人员不能重复添加到同一部门')
    users = {u.id: u for u in db.query(AppUser).filter(AppUser.id.in_(requested)).all()}
    if len(users) != len(requested):
        raise HTTPException(422, '部分人员不存在，请刷新后重选')
    current = db.query(DepartmentMember).filter_by(department_id=dept.id).all()
    current_ids = {link.user_id for link in current}
    primary_users = db.query(AppUser).filter(AppUser.department.in_([dept.name, *(dept.aliases or [])])).all()
    removed = (current_ids | {u.id for u in primary_users}) - requested.keys()
    for link in current:
        if link.user_id in requested:
            link.position = requested[link.user_id]
            link.updated_at = now()
        else:
            db.delete(link)
    for uid in requested.keys() - current_ids:
        db.add(DepartmentMember(department_id=dept.id, user_id=uid, position=requested[uid]))
    db.flush()
    for person in primary_users:
        if person.id in removed:
            other = db.query(Department).join(DepartmentMember, DepartmentMember.department_id == Department.id).filter(DepartmentMember.user_id == person.id).order_by(Department.created_at, Department.id).first()
            person.department = other.name if other else None
    for person in users.values():
        if not person.department:
            person.department = dept.name
    dept.revision += 1
    dept.updated_at = now()
    dept.updated_by = user.id
    db.commit()
    publish(db)
    return directory(db, user)


def sync_primary(db, person, previous=None):
    """人员表更改主部门时保留其他部门；原主部门归属随主部门替换。"""
    if not ready(db):
        return
    db.flush()
    import department_service
    aliases = department_service.alias_map(db)
    old = aliases.get(previous, previous)
    if old and old != person.department:
        old_dept = db.query(Department).filter_by(name=old).first()
        if old_dept:
            db.query(DepartmentMember).filter_by(user_id=person.id, department_id=old_dept.id).delete()
    if person.department:
        dept = db.query(Department).filter_by(name=person.department).first()
        if dept and not db.get(DepartmentMember, (dept.id, person.id)):
            db.add(DepartmentMember(department_id=dept.id, user_id=person.id, position=''))


def publish(db):
    from notification_ws import broadcast_to_users
    broadcast_to_users([str(uid) for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True))], {'type': 'departments_changed'})
