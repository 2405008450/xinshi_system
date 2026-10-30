from fastapi import HTTPException
from sqlalchemy import inspect, func
from sqlalchemy.exc import IntegrityError
from models import AppUser, WorkSchedule
from department_models import Department
from department_utils import DEPARTMENT_ALIASES, normalize_department
from permission_registry import SUPER_ROLE_NAMES
from chat_time import now

DEFAULT_DEPARTMENTS = ['项目经理', 'IT部', '项目部', '客户部', 'HR部', '排版', '其他', '销售']


def can_manage(db, user):
    if not user or not user.is_active or user.is_deleted:
        return False
    if (user.username or '').strip().casefold() in {'ethan', 'jimmy'}:
        return True
    from hr_access import can_manage_hr
    if can_manage_hr(db,user):return True
    from crud import get_user_roles_with_role_names
    from permission_service import user_has_permission
    return not SUPER_ROLE_NAMES.isdisjoint(get_user_roles_with_role_names(db, user.id)) or user_has_permission(db,user.id,'system:organization:write')


def ready(db):
    return hasattr(db,'connection') and inspect(db.connection()).has_table(Department.__tablename__)


def alias_map(db):
    result = dict(DEPARTMENT_ALIASES)
    if ready(db):
        for row in db.query(Department).all():
            for alias in row.aliases or []:
                result[alias] = row.name
            result[row.name] = row.name
    return result


def canonical_name(db, value):
    if value is None:
        return None
    value = value.strip()
    normalized = alias_map(db).get(value, normalize_department(value))
    if normalized and ready(db) and not db.query(Department.id).filter_by(name=normalized).first():
        raise HTTPException(422,'部门不存在，请先由有权限的账号在部门管理中新增')
    return normalized


def rename_fields(value, aliases):
    """仅替换结构化部门字段，不改任务、备注等自由文本。"""
    if isinstance(value, list):
        return [rename_fields(item, aliases) for item in value]
    if isinstance(value, dict):
        return {key: aliases.get(item.strip(), item) if key in {'dept', 'department'} and isinstance(item, str)
                else rename_fields(item, aliases) for key, item in value.items()}
    return value


def catalog(db, user):
    from organization_service import ready as memberships_ready
    from department_models import DepartmentMember
    available = ready(db)
    rows = db.query(Department).order_by(Department.created_at, Department.id).all() if available else []
    counts = dict(db.query(AppUser.department, func.count(AppUser.id)).filter(AppUser.is_deleted.is_(False)).group_by(AppUser.department).all())
    members = {row.id: set() for row in rows}
    names = {name: row.id for row in rows for name in [row.name, *(row.aliases or [])]}
    if available:
        for uid, name in db.query(AppUser.id, AppUser.department).filter(AppUser.is_deleted.is_(False)):
            if name in names:
                members[names[name]].add(uid)
        if memberships_ready(db):
            for department_id, uid in db.query(DepartmentMember.department_id, DepartmentMember.user_id).join(AppUser, AppUser.id == DepartmentMember.user_id).filter(AppUser.is_deleted.is_(False)):
                if department_id in members:
                    members[department_id].add(uid)
    return {'ready': available, 'canManage': can_manage(db,user), 'aliases': alias_map(db),
            'items': [{'id': str(row.id), 'name': row.name, 'revision': row.revision,
                       'userCount': len(members[row.id])} for row in rows] if available else
                     [{'id': name, 'name': name, 'revision': 0, 'userCount': counts.get(name,0)} for name in DEFAULT_DEPARTMENTS]}


def save(db, user, name, department_id=None, revision=None):
    if not can_manage(db,user):
        raise HTTPException(403,'仅行政部、ethan、jimmy 和超级管理员可管理部门')
    if not ready(db):
        raise HTTPException(503,'部门目录尚未初始化')
    # 串行化目录编辑，防止两个部门同时改为同名或占用历史别名。
    rows = db.query(Department).order_by(Department.id).with_for_update().all()
    row = next((item for item in rows if item.id == department_id),None) if department_id else None
    if department_id and not row:
        raise HTTPException(404,'部门不存在')
    if row and row.revision != revision:
        raise HTTPException(409,'部门已被其他人修改，请刷新后重试')
    if any(item.id != department_id and name.casefold() in {value.casefold() for value in [item.name,*(item.aliases or [])]} for item in rows):
        raise HTTPException(409,'部门名称已存在或属于其他部门的历史名称')
    if row:
        if row.name != name:
            aliases = list(dict.fromkeys([*(row.aliases or []),row.name]))
            aliases = [item for item in aliases if item != name]
            mapping = {old:name for old in [row.name,*aliases]}
            db.query(AppUser).filter(AppUser.department.in_(mapping)).update({AppUser.department:name},synchronize_session=False)
            for schedule in db.query(WorkSchedule).all():
                changed = False
                for field in ['shift_table','leave_notes','urgent_table_zh_en','urgent_table_en_zh','dept_person_data','not_scheduled_tasks']:
                    previous = getattr(schedule,field)
                    updated = rename_fields(previous,mapping)
                    if updated != previous:
                        setattr(schedule,field,updated)
                        changed = True
                if changed:
                    schedule.updated_by = user.id
                    schedule.updated_at = now().replace(tzinfo=None)
            row.name = name; row.aliases = aliases
        row.revision += 1
    else:
        row = Department(name=name,aliases=[],revision=1)
        db.add(row)
    row.updated_by=user.id;row.updated_at=now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'部门名称已存在，请刷新后重试')
    from notification_ws import broadcast_to_users
    broadcast_to_users([str(uid) for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True))],{'type':'departments_changed'})
    return catalog(db,user)
