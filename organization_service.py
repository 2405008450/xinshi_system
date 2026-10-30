"""组织名册；职务不授予权限，行政部成员按明确规则获得组织架构权限。"""
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
    people = db.query(AppUser).filter(AppUser.is_deleted.is_(False)).order_by(AppUser.full_name, AppUser.username).all()
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
        raise HTTPException(403, '仅行政部、ethan、jimmy 和超级管理员可管理组织架构')
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
    users = {u.id: u for u in db.query(AppUser).filter(AppUser.id.in_(requested), AppUser.is_deleted.is_(False)).all()}
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


def save_person_departments(db, user, user_id, payload):
    """原子调整个人全部部门，保留仍所属部门的职务。"""
    import department_service as departments
    if not departments.can_manage(db, user):
        raise HTTPException(403, '仅行政部、ethan、jimmy 和超级管理员可调整部门')
    if not ready(db) or not departments.ready(db):
        raise HTTPException(503, '组织架构存储尚未初始化')
    rows = db.query(Department).order_by(Department.id).with_for_update().all()
    catalog = {row.id: row for row in rows}
    person = db.query(AppUser).filter(AppUser.id == user_id, AppUser.is_deleted.is_(False)).with_for_update().first()
    if not person:
        raise HTTPException(404, '人员不存在')
    requested = set(payload.department_ids)
    if len(requested) != len(payload.department_ids) or not requested.issubset(catalog):
        raise HTTPException(422, '部门不存在或重复，请刷新后重新选择')
    if (requested and payload.primary_department_id not in requested) or (not requested and payload.primary_department_id):
        raise HTTPException(422, '主部门必须属于已选部门；未分部门时请清空主部门')
    links = db.query(DepartmentMember).filter_by(user_id=person.id).all()
    current = {link.department_id for link in links}
    canonical_primary = departments.alias_map(db).get(person.department, person.department) or None
    old_primary = next((row for row in rows if row.name == canonical_primary), None)
    if old_primary:
        current.add(old_primary.id)
    if current != set(payload.expected_department_ids) or canonical_primary != payload.expected_primary_department:
        raise HTTPException(409, '该人员的部门已被修改，请重新打开后调整')
    affected = current | requested
    if any(payload.revisions.get(dept_id) != catalog[dept_id].revision for dept_id in affected):
        raise HTTPException(409, '部门名册已被修改，请重新打开后调整')
    existing = {link.department_id: link for link in links}
    for dept_id, link in existing.items():
        if dept_id not in requested:
            db.delete(link)
    for dept_id in requested - existing.keys():
        db.add(DepartmentMember(department_id=dept_id, user_id=person.id, position=''))
    person.department = catalog[payload.primary_department_id].name if payload.primary_department_id else None
    person.updated_at = now().replace(tzinfo=None)
    for dept_id in affected:
        catalog[dept_id].revision += 1
        catalog[dept_id].updated_at = now()
        catalog[dept_id].updated_by = user.id
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
