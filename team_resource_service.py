"""团队查询、原子写入和审计，事务由路由统一提交。"""
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, text
from sqlalchemy.dialects.postgresql import ARRAY

from business_time import BUSINESS_TIMEZONE, business_iso
from models import AppUser
from team_resource_models import TeamResource as Team, TeamResourceAudit as Audit
from talent_privacy import CONTACT_MASK, can_view_talent_contacts

TEAM_TYPES = [{"value": "small_team", "label": "小团队"}, {"value": "medium_large_company", "label": "中大型企业"}, {"value": "small_medium_company", "label": "中小型企业"}]
RESOURCE_TYPES = [{"value": "annotation", "label": "标注"}, {"value": "interpretation", "label": "口译"}, {"value": "written_translation", "label": "笔译"}, {"value": "full_time", "label": "全职"}, {"value": "other", "label": "其他"}]
BUSINESS_FIELDS = ("short_name", "full_name", "team_type", "introduction", "resource_types", "other_resource_description", "resource_situation", "remarks", "contact_user_id", "contact_date", "follow_up_user_id")


def ensure_schema(db):
    ready = db.execute(text("SELECT to_regclass('resource_team') IS NOT NULL AND to_regclass('resource_team_audit') IS NOT NULL AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'resource_team' AND column_name = 'contacts')")).scalar()
    if not ready:
        raise HTTPException(503, {"code": "team_module_uninitialized", "message": "团队资源结构待更新，请联系管理员执行显式迁移（含团队对接人）"})


def person_data(person):
    return {"id": str(person.id), "name": person.full_name or person.username, "is_active": bool(person.is_active)} if person else None


def people_options(db):
    referenced = db.query(Team.contact_user_id).union(db.query(Team.follow_up_user_id))
    return [person_data(p) for p in db.query(AppUser).filter(or_(AppUser.is_active.is_(True), AppUser.id.in_(referenced))).order_by(AppUser.full_name, AppUser.username).all()]


def serialize_many(db, rows, *, contacts_visible=False):
    ids = {getattr(row, key) for row in rows for key in ("contact_user_id", "follow_up_user_id", "created_by", "updated_by") if getattr(row, key)}
    users = {p.id: p for p in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}
    result = []
    for row in rows:
        data = {key: getattr(row, key) for key in BUSINESS_FIELDS}
        data["contact_restricted"] = not contacts_visible
        data["contacts"] = [dict(item, contact_info=(item.get("contact_info", "") if contacts_visible else CONTACT_MASK if item.get("contact_info") else "")) for item in row.contacts or []]
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


def list_teams(db, skip=0, limit=20, *, contacts_visible=False, **filters):
    query = filtered_teams(db, **filters)
    return {"items": serialize_many(db, query.order_by(Team.updated_at.desc(), Team.id.desc()).offset(skip).limit(limit).all(), contacts_visible=contacts_visible), "total": query.count()}


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


def prepare_contacts(payload, existing, *, contacts_visible):
    """按稳定标识保留受保护联系方式，禁止受限用户通过删行绕过权限。"""
    if payload.contacts is None:
        return existing or []
    old = {item["id"]: item for item in existing or []}
    result = []
    for item in payload.contacts:
        key = str(item.id) if item.id else None
        if key and key not in old:
            raise HTTPException(422, "对接人不存在，请重新读取团队资料")
        if not contacts_visible and item.contact_info:
            raise HTTPException(403, "只有超级管理员可以录入或修改团队对接人联系方式")
        result.append({"id": key or str(uuid4()), "name": item.name, "nickname": item.nickname,
                       "contact_info": item.contact_info if contacts_visible else old.get(key, {}).get("contact_info", "")})
    if not contacts_visible:
        retained = {item["id"] for item in result}
        if any(item.get("contact_info") and key not in retained for key, item in old.items()):
            raise HTTPException(403, "含联系方式的对接人仅超级管理员可以移除")
    return result


def save_team(db, user, payload, team_id=None):
    # 串行检查名称，避免两个同时新增的未确认请求绕过重名提示。
    db.execute(text("SELECT pg_advisory_xact_lock(718203884)"))
    row = get_team(db, team_id, lock=True) if team_id else None
    if row:
        check_revision(row, payload.revision)
    elif payload.revision:
        raise HTTPException(422, "新增团队版本号必须为0")
    contacts_visible = can_view_talent_contacts(db, user)
    contacts = prepare_contacts(payload, row.contacts if row else [], contacts_visible=contacts_visible)
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
    # 审计只记录联系方式是否存在，不复制敏感明文到历史快照。
    before = serialize_many(db, [row])[0] if row else None
    now = datetime.now(BUSINESS_TIMEZONE)
    if not row:
        row = Team(id=uuid4(), created_by=user.id, created_at=now, revision=0)
        db.add(row)
    for key in BUSINESS_FIELDS:
        setattr(row, key, getattr(payload, key))
    row.contacts = contacts
    row.updated_by, row.updated_at, row.revision = user.id, now, row.revision + 1
    db.flush()
    audit(db, user, row, "update" if before else "create", before, serialize_many(db, [row])[0])
    return serialize_many(db, [row], contacts_visible=contacts_visible)[0]


def delete_team(db, user, team_id, revision):
    row = get_team(db, team_id, lock=True)
    check_revision(row, revision)
    audit(db, user, row, "delete", before=serialize_many(db, [row])[0])
    db.delete(row)
