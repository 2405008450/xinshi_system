"""渠道、平台分组与账号分工；保留原账号 ID 及全部业务关联。"""
from uuid import uuid4
from search_matching import keyword_any, matches_keywords, search_terms

from fastapi import HTTPException
from sqlalchemy import func, inspect, or_, select

from business_time import business_iso, business_now
from models import AppUser
from resource_channel_models import ChannelAccountLink as Link
from resource_development_models import DevelopmentAudit as Audit, DevelopmentChannelMember as Member, DevelopmentOption as Option
from resource_development_service import check_revision, lock_writes, snapshot

CHANNEL_KINDS = ("platform", "channel_group")


def hierarchy_available(db):
    # 独立关系表未迁移时继续兼容原列表，不影响其他模块读取原账号。
    return inspect(db.connection()).has_table(Link.__tablename__)


def arrangement_platforms(db):
    """只读批量提供分类及账号归属，不改变原账号和历史安排。"""
    rows = db.query(Option).filter(Option.kind.in_(CHANNEL_KINDS)).order_by(Option.name, Option.id).all()
    by_id = {row.id: row for row in rows}
    links = db.query(Link).all() if hierarchy_available(db) else []
    parents = {link.account_id: link.parent_id for link in links}
    grouped_ids = set(parents.values())
    result = []
    for row in rows:
        parent = by_id.get(parents.get(row.id))
        result.append({
            "id": str(row.id), "name": row.name, "kind": row.kind,
            "description": row.description or "", "has_accounts": row.id in grouped_ids,
            "category": parent.category if parent else row.category,
            "parent_id": str(parent.id) if parent else None,
            "parent_name": parent.name if parent else None,
        })
    return result


def channel(db, platform_id):
    row = db.get(Option, platform_id)
    if not row or row.kind not in CHANNEL_KINDS:
        raise HTTPException(404, "渠道不存在")
    return row


def serialize_channels(db, rows, with_accounts=True):
    """批量读取账号、分工和人员；汇总按人员 ID 去重，不逐行查询。"""
    if not rows:
        return []
    available = hierarchy_available(db)
    ids = [r.id for r in rows]
    links = db.query(Link).filter(or_(Link.parent_id.in_(ids), Link.account_id.in_(ids))).all() if available else []
    child_ids = {link.account_id for link in links if link.parent_id in ids}
    extra = db.query(Option).filter(Option.id.in_(child_ids)).order_by(Option.name, Option.id).all() if child_ids else []
    all_rows = {row.id: row for row in [*rows, *extra]}
    parent_ids = {link.parent_id for link in links}
    parents = {row.id: row for row in db.query(Option).filter(Option.id.in_(parent_ids)).all()} if parent_ids else {}
    members = db.query(Member, AppUser).join(AppUser, AppUser.id == Member.user_id).filter(Member.platform_id.in_(all_rows)).order_by(AppUser.full_name, AppUser.username, AppUser.id).all()
    actor_ids = {value for row in all_rows.values() for value in (row.created_by, row.updated_by) if value}
    actors = {u.id: u.full_name or u.username for u in db.query(AppUser).filter(AppUser.id.in_(actor_ids)).all()} if actor_ids else {}
    grouped = {}
    for member, person in members:
        grouped.setdefault((member.platform_id, member.role), []).append({
            "id": str(person.id), "name": person.full_name or person.username, "is_active": person.is_active,
        })
    children = {}
    assignments = {link.account_id: link.parent_id for link in links}
    for child in extra:
        children.setdefault(assignments[child.id], []).append(child)

    def result(row, include_children):
        accounts = children.get(row.id, [])
        parent = parents.get(assignments.get(row.id))
        direct = {role: grouped.get((row.id, role), []) for role in ("maintainer", "user")}
        effective = {}
        for role in direct:
            people = [person for account in accounts for person in grouped.get((account.id, role), [])] if accounts else direct[role]
            unique = {person["id"]: person for person in people}
            effective[role] = sorted(unique.values(), key=lambda p: (p["name"], p["id"]))
        return {**snapshot(row), "created_at": business_iso(row.created_at), "updated_at": business_iso(row.updated_at),
                "maintainers": effective["maintainer"], "users": effective["user"],
                "direct_maintainers": direct["maintainer"], "direct_users": direct["user"],
                "created_by_name": actors.get(row.created_by), "updated_by_name": actors.get(row.updated_by),
                "parent_id": str(parent.id) if parent else None, "parent_name": parent.name if parent else None,
                "parent_revision": parent.revision if parent else None, "account_count": len(accounts),
                "accounts": [result(account, False) for account in accounts] if include_children else [],
                "hierarchy_available": available}

    return [result(row, with_accounts) for row in rows]


def read_channel(db, platform_id):
    return serialize_channels(db, [channel(db, platform_id)])[0]


def list_channels(db, keyword=None, category=None, maintainer_ids=None, user_ids=None, skip=0, limit=20):
    available = hierarchy_available(db)
    query = db.query(Option).filter(Option.kind.in_(CHANNEL_KINDS))
    if available:
        query = query.filter(~Option.id.in_(select(Link.account_id)))
    if keyword and keyword.strip():
        for term in search_terms(keyword):
            matching = select(Option.id).where(keyword_any([Option.name, Option.purpose], term))
            conditions = [Option.id.in_(matching)]
            if available:
                conditions.append(Option.id.in_(select(Link.parent_id).where(Link.account_id.in_(matching))))
            query = query.filter(or_(*conditions))
    if category:
        query = query.filter(Option.category == category)
    for role, ids in (("maintainer", maintainer_ids), ("user", user_ids)):
        if ids:
            matching = select(Member.platform_id).where(Member.role == role, Member.user_id.in_(ids))
            if available:
                # 有账号只查账号人员；无账号才采用平台直属人员，与展示口径一致。
                query = query.filter(or_(
                    (~Option.id.in_(select(Link.parent_id))) & Option.id.in_(matching),
                    Option.id.in_(select(Link.parent_id).where(Link.account_id.in_(matching))),
                ))
            else:
                query = query.filter(Option.id.in_(matching))
    total = query.count()
    rows = query.order_by(Option.name, Option.id).offset(skip).limit(limit).all()
    items = serialize_channels(db, rows)
    value = (keyword or "").strip().casefold()
    for item in items:
        item["expand_accounts"] = bool(value and any(matches_keywords(f"{account['name']} {account['purpose']}", term) for term in search_terms(value) for account in item["accounts"]))
    return {"items": items, "total": total, "hierarchy_available": available}


def account_options(db):
    """账号候选保留已有归属，客户端可明确确认转移，不凭名称推断归属。"""
    query = db.query(Option).filter(Option.kind == "platform")
    if hierarchy_available(db):
        query = query.filter(~Option.id.in_(select(Link.parent_id)))
    return serialize_channels(db, query.order_by(Option.name, Option.id).all(), with_accounts=False)


def check_name(db, name, skip_id=None):
    query = db.query(Option.id).filter(Option.kind.in_(CHANNEL_KINDS), func.lower(func.trim(Option.name)) == name.strip().lower())
    if skip_id:
        query = query.filter(Option.id != skip_id)
    if query.first():
        raise HTTPException(409, "已有同名渠道，请使用现有渠道或修改名称")


def record_audit(db, user, row, before=None):
    db.flush()
    after = read_channel(db, row.id)
    db.add(Audit(entity_id=row.id, entity_type="option", actor_id=user.id, created_at=business_now(),
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
    available = hierarchy_available(db)
    if not available and (payload.account_ids or payload.parent_id):
        raise HTTPException(503, "账号归属功能暂不可用，请联系管理员")
    old = {link.account_id: link.parent_id for link in db.query(Link).all()} if available else {}
    row_id = row.id if row else uuid4()
    planned = dict(old)
    if payload.account_ids is not None:
        planned = {account: parent for account, parent in planned.items() if parent != row_id}
        for account in payload.account_ids:
            planned[account] = row_id
    if "parent_id" in payload.model_fields_set:
        if payload.parent_id:
            parent = channel(db, payload.parent_id)
            check_revision(parent, payload.parent_revision)
            planned[row_id] = parent.id
        else:
            planned.pop(row_id, None)
    # 服务端强制两级层次，杜绝自关联、循环、分组嵌套和交换微信账号误关联。
    affected_ids = set(planned) | set(planned.values())
    records = {o.id: o for o in db.query(Option).filter(Option.id.in_(affected_ids | set(old) | set(old.values()))).all()} if affected_ids or old else {}
    for account, parent in planned.items():
        account_kind = records[account].kind if account in records else ("channel_group" if payload.is_group else "platform") if account == row_id else None
        if account == parent or parent in planned or account_kind != "platform" or (parent != row_id and (parent not in records or records[parent].kind not in CHANNEL_KINDS)):
            raise HTTPException(422, "账号只能归属一个平台，不能关联自身、分组或多层账号")
    changed = {account for account in set(old) | set(planned) if old.get(account) != planned.get(account)}
    for account in changed - {row_id}:
        account_row = records.get(account)
        if not account_row or payload.account_revisions.get(account) != account_row.revision:
            raise HTTPException(409, "账号资料或归属已被修改，请重新读取最新内容")
    touched = (changed | {old.get(i) for i in changed} | {planned.get(i) for i in changed} | {old.get(row_id)} | {planned.get(row_id)}) - {None, row_id}
    prior = {key: read_channel(db, key) for key in touched}
    has_accounts = row_id in planned.values()
    existing = {(m.role, m.user_id) for m in db.query(Member).filter(Member.platform_id == row_id).all()}
    assignments = [(role, person_id) for role, ids in (("maintainer", payload.maintainer_ids), ("user", payload.user_ids)) for person_id in ids]
    if not has_accounts:
        people = {u.id: u for u in db.query(AppUser).filter(AppUser.id.in_([i for _, i in assignments])).all()} if assignments else {}
        for role, person_id in assignments:
            person = people.get(person_id)
            if not person or (not person.is_active and (role, person_id) not in existing):
                raise HTTPException(422, "请选择在职系统人员；已停用的历史分工仅允许保留或移除")
    now = business_now()
    if not row:
        row = Option(id=row_id, kind="channel_group" if payload.is_group else "platform", created_by=user.id, created_at=now, revision=0)
        row.code = "P" + row.id.hex[:12].upper()
        db.add(row)
    row.name, row.category, row.description, row.purpose = payload.name, payload.category, payload.description, payload.purpose
    row.updated_by, row.updated_at, row.revision = user.id, now, row.revision + 1
    db.flush()
    if not has_accounts:
        db.query(Member).filter(Member.platform_id == row.id).delete(synchronize_session=False)
        for role, person_id in assignments:
            db.add(Member(platform_id=row.id, user_id=person_id, role=role))
    for account in changed:
        db.query(Link).filter(Link.account_id == account).delete(synchronize_session=False)
        if account in planned:
            db.add(Link(account_id=account, parent_id=planned[account]))
    for key in touched:
        target = records[key]
        target.revision += 1
        target.updated_at, target.updated_by = now, user.id
    db.flush()
    for key in touched:
        record_audit(db, user, records[key], prior[key])
    return record_audit(db, user, row, before)


def save_description(db, user, platform_id, description, revision):
    lock_writes(db)
    row = channel(db, platform_id)
    check_revision(row, revision)
    before = read_channel(db, row.id)
    parent_id = before["parent_id"]
    parent = channel(db, parent_id) if parent_id else None
    parent_before = read_channel(db, parent_id) if parent else None
    row.description, row.revision = description, row.revision + 1
    row.updated_by, row.updated_at = user.id, business_now()
    if parent:
        parent.revision += 1
        parent.updated_by, parent.updated_at = user.id, row.updated_at
        record_audit(db, user, parent, parent_before)
    return record_audit(db, user, row, before)
