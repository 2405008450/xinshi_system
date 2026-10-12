"""团队查询、原子写入和审计，事务由路由统一提交。"""
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, text
from sqlalchemy.dialects.postgresql import ARRAY

from business_time import BUSINESS_TIMEZONE, business_iso
from models import AppUser
from team_resource_models import TeamResource as Team, TeamResourceAudit as Audit

TEAM_TYPES = [{"value": "small_team", "label": "小团队"}, {"value": "medium_large_company", "label": "中大型企业"}, {"value": "small_medium_company", "label": "中小型企业"}]
RESOURCE_TYPES = [{"value": "annotation", "label": "标注"}, {"value": "interpretation", "label": "口译"}, {"value": "written_translation", "label": "笔译"}, {"value": "full_time", "label": "全职"}, {"value": "other", "label": "其他"}]
BUSINESS_FIELDS = ("short_name", "full_name", "team_type", "introduction", "resource_types", "other_resource_description", "resource_situation", "remarks", "contact_user_id", "contact_date", "follow_up_user_id")


def ensure_schema(db):
    ready = db.execute(text("SELECT to_regclass('resource_team') IS NOT NULL AND to_regclass('resource_team_audit') IS NOT NULL")).scalar()
    if not ready:
        raise HTTPException(503, {"code": "team_module_uninitialized", "message": "团队资源模块尚未初始化，请联系管理员执行显式迁移"})


def person_data(person):
    return {"id": str(person.id), "name": person.full_name or person.username, "is_active": bool(person.is_active)} if person else None


def people_options(db):
    referenced = db.query(Team.contact_user_id).union(db.query(Team.follow_up_user_id))
    return [person_data(p) for p in db.query(AppUser).filter(or_(AppUser.is_active.is_(True), AppUser.id.in_(referenced))).order_by(AppUser.full_name, AppUser.username).all()]


def serialize_many(db, rows):
    ids = {getattr(row, key) for row in rows for key in ("contact_user_id", "follow_up_user_id", "created_by", "updated_by") if getattr(row, key)}
    users = {p.id: p for p in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    result = []
    for row in rows:
        data = {key: getattr(row, key) for key in BUSINESS_FIELDS}
        for key in ("contact_user_id", "follow_up_user_id"):
            data[key] = str(data[key]) if data[key] else None
        data["contact_date"] = row.contact_date.isoformat() if row.contact_date else None
        data.update(id=str(row.id), revision=row.revision, contact_user=person_data(users.get(row.contact_user_id)), follow_up_user=person_data(users.get(row.follow_up_user_id)),
                    created_by=str(row.created_by) if row.created_by else None, updated_by=str(row.updated_by) if row.updated_by else None,
                    created_by_name=(users[row.created_by].full_name or users[row.created_by].username) if row.created_by in users else None,
                    updated_by_name=(users[row.updated_by].full_name or users[row.updated_by].username) if row.updated_by in users else None,
                    created_at=business_iso(row.created_at), updated_at=business_iso(row.updated_at))
        result.append(data)
    return result


def filtered_teams(db, keyword=None, team_type=None, resource_types=None, contact_user_id=None, follow_up_user_id=None, contact_start=None, contact_end=None):
    if contact_start and contact_end and contact_start > contact_end:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    query = db.query(Team)
    if keyword and keyword.strip():
        value = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(or_(Team.short_name.ilike(f"%{value}%", escape="\\"), Team.full_name.ilike(f"%{value}%", escape="\\")))
    if team_type:
        query = query.filter(Team.team_type == team_type)
    if resource_types:
        query = query.filter(Team.resource_types.has_any(cast(resource_types, ARRAY(String))))
    for field, value in ((Team.contact_user_id, contact_user_id), (Team.follow_up_user_id, follow_up_user_id)):
        if value:
            query = query.filter(field == value)
    if contact_start:
        query = query.filter(Team.contact_date >= contact_start)
    if contact_end:
        query = query.filter(Team.contact_date <= contact_end)
    return query


def list_teams(db, skip=0, limit=20, **filters):
    query = filtered_teams(db, **filters)
    return {"items": serialize_many(db, query.order_by(Team.updated_at.desc(), Team.id.desc()).offset(skip).limit(limit).all()), "total": query.count()}


def get_team(db, team_id, lock=False):
    query = db.query(Team).filter(Team.id == team_id)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, "团队档案不存在或已被删除")
    return row


def check_revision(row, revision):
    if row.revision != revision:
        raise HTTPException(409, {"code": "team_revision_conflict", "message": "团队已被其他人修改，草稿已保留，请重新读取最新内容"})


def audit(db, user, row, action, before=None, after=None):
    db.add(Audit(id=uuid4(), team_id=row.id, action=action, actor_id=user.id, actor_name=user.full_name or user.username,
                 before=before, after=after, occurred_at=datetime.now(BUSINESS_TIMEZONE)))


def save_team(db, user, payload, team_id=None):
    # 串行检查名称，避免两个同时新增的未确认请求绕过重名提示。
    db.execute(text("SELECT pg_advisory_xact_lock(718203884)"))
    row = get_team(db, team_id, lock=True) if team_id else None
    if row:
        check_revision(row, payload.revision)
    elif payload.revision:
        raise HTTPException(422, "新增团队版本号必须为0")
    for key in ("contact_user_id", "follow_up_user_id"):
        person_id = getattr(payload, key)
        if person_id:
            person = db.get(AppUser, person_id)
            if not person or (not person.is_active and (not row or getattr(row, key) != person_id)):
                raise HTTPException(422, {"message": "请选择在职人员；历史停用人员仅允许原字段保留", "fieldErrors": [{"path": key, "message": "请选择在职人员"}]})
    conditions = [func.lower(func.btrim(Team.short_name)) == payload.short_name.lower()]
    if payload.full_name:
        conditions.append(func.lower(func.btrim(Team.full_name)) == payload.full_name.lower())
    duplicates = db.query(Team).filter(or_(*conditions))
    if row:
        duplicates = duplicates.filter(Team.id != row.id)
    matches = duplicates.order_by(Team.updated_at.desc(), Team.id.desc()).limit(20).all()
    if matches and not payload.allow_duplicate:
        raise HTTPException(409, {"code": "team_duplicate_warning", "message": "已有简称或全称相同的团队，请核对后确认是否仍然保存", "candidates": [{"id": str(r.id), "short_name": r.short_name, "full_name": r.full_name} for r in matches]})
    before = serialize_many(db, [row])[0] if row else None
    now = datetime.now(BUSINESS_TIMEZONE)
    if not row:
        row = Team(id=uuid4(), created_by=user.id, created_at=now, revision=0)
        db.add(row)
    for key in BUSINESS_FIELDS:
        setattr(row, key, getattr(payload, key))
    row.updated_by, row.updated_at, row.revision = user.id, now, row.revision + 1
    db.flush()
    after = serialize_many(db, [row])[0]
    audit(db, user, row, "update" if before else "create", before, after)
    return after


def delete_team(db, user, team_id, revision):
    row = get_team(db, team_id, lock=True)
    check_revision(row, revision)
    audit(db, user, row, "delete", before=serialize_many(db, [row])[0])
    db.delete(row)
