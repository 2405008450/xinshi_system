"""渠道与开拓平台共享资料，所有写入使用同一平台版本号。"""
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_

from models import AppUser
from resource_development_models import DevelopmentAudit as Audit, DevelopmentChannelMember as Member, DevelopmentOption as Option
from resource_development_service import check_revision, lock_writes, snapshot


def channel(db, platform_id):
    row = db.get(Option, platform_id)
    if not row or row.kind != "platform":
        raise HTTPException(404, "渠道不存在")
    return row


def serialize_channels(db, rows):
    """批量读取分工和系统人员，避免列表逐行查询。"""
    if not rows:
        return []
    members = db.query(Member, AppUser).join(AppUser, AppUser.id == Member.user_id).filter(Member.platform_id.in_([r.id for r in rows])).order_by(AppUser.full_name, AppUser.username).all()
    actor_ids = {value for row in rows for value in (row.created_by, row.updated_by) if value}
    actors = {u.id: u.full_name or u.username for u in db.query(AppUser).filter(AppUser.id.in_(actor_ids)).all()} if actor_ids else {}
    grouped = {}
    for member, person in members:
        grouped.setdefault((member.platform_id, member.role), []).append({
            "id": str(person.id), "name": person.full_name or person.username, "is_active": person.is_active,
        })
    result = []
    for row in rows:
        result.append({**snapshot(row), "maintainers": grouped.get((row.id, "maintainer"), []),
                       "users": grouped.get((row.id, "user"), []),
                       "created_by_name": actors.get(row.created_by), "updated_by_name": actors.get(row.updated_by)})
    return result


def read_channel(db, platform_id):
    return serialize_channels(db, [channel(db, platform_id)])[0]


def list_channels(db, keyword=None, category=None, maintainer_ids=None, user_ids=None, skip=0, limit=20):
    query = db.query(Option).filter(Option.kind == "platform")
    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.filter(or_(Option.name.icontains(value, autoescape=True), Option.purpose.icontains(value, autoescape=True)))
    if category:
        query = query.filter(Option.category == category)
    for role, ids in (("maintainer", maintainer_ids), ("user", user_ids)):
        if ids:
            query = query.filter(Option.id.in_(db.query(Member.platform_id).filter(Member.role == role, Member.user_id.in_(ids))))
    total = query.count()
    rows = query.order_by(Option.name, Option.id).offset(skip).limit(limit).all()
    return {"items": serialize_channels(db, rows), "total": total}


def check_name(db, name, skip_id=None):
    query = db.query(Option.id).filter(Option.kind == "platform", func.lower(func.trim(Option.name)) == name.strip().lower())
    if skip_id:
        query = query.filter(Option.id != skip_id)
    if query.first():
        raise HTTPException(409, "已有同名渠道，请使用现有渠道或修改名称")


def record_audit(db, user, row, before=None):
    db.flush()
    after = read_channel(db, row.id)
    db.add(Audit(entity_id=row.id, entity_type="option", actor_id=user.id,
                 action="update" if before else "create", before=before or {}, after=after))
    return after


def save_channel(db, user, payload, platform_id=None):
    lock_writes(db)
    row = channel(db, platform_id) if platform_id else None
    if row:
        check_revision(row, payload.revision)
    elif payload.revision:
        raise HTTPException(409, "新增渠道不能携带已有版本号")
    check_name(db, payload.name, platform_id)
    before = read_channel(db, row.id) if row else None
    existing = {(m.role, m.user_id) for m in db.query(Member).filter(Member.platform_id == row.id).all()} if row else set()
    assignments = [(role, person_id) for role, ids in (("maintainer", payload.maintainer_ids), ("user", payload.user_ids)) for person_id in ids]
    people = {u.id: u for u in db.query(AppUser).filter(AppUser.id.in_([i for _, i in assignments])).all()} if assignments else {}
    for role, person_id in assignments:
        person = people.get(person_id)
        if not person or (not person.is_active and (role, person_id) not in existing):
            raise HTTPException(422, "请选择在职系统人员；已停用的历史分工仅允许保留或移除")
    now = datetime.now()
    if not row:
        row = Option(id=uuid4(), kind="platform", created_by=user.id, created_at=now, revision=0)
        row.code = "P" + row.id.hex[:12].upper()
        db.add(row)
    row.name, row.category, row.description, row.purpose = payload.name, payload.category, payload.description, payload.purpose
    row.updated_by, row.updated_at, row.revision = user.id, now, row.revision + 1
    db.flush()
    db.query(Member).filter(Member.platform_id == row.id).delete(synchronize_session=False)
    for role, person_id in assignments:
        db.add(Member(platform_id=row.id, user_id=person_id, role=role))
    return record_audit(db, user, row, before)


def save_description(db, user, platform_id, description, revision):
    lock_writes(db)
    row = channel(db, platform_id)
    check_revision(row, revision)
    before = read_channel(db, row.id)
    row.description, row.revision = description, row.revision + 1
    row.updated_by, row.updated_at = user.id, datetime.now()
    return record_audit(db, user, row, before)
