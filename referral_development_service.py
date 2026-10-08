"""推荐奖励台账服务；事务提交由路由负责。"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, text

from models import AppUser
from permission_service import get_user_permission_codes
from resource_development_service import can_delegate, is_admin
from referral_development_models import ReferralRecord as Record, ReferralImage as Image, ReferralAudit as Audit

READ_PERMISSIONS = ("talents:read", "talents:write", "translators:read", "translators:write", "resource_development:delegate")
WRITE_PERMISSIONS = ("talents:write", "translators:write", "resource_development:delegate")
BUSINESS_FIELDS = ("work_date", "full_name", "wechat", "pull_description", "moments_description", "groups_description", "amount", "remarks")
PRIVATE_FIELDS = {"wechat", "pull_description", "moments_description", "groups_description", "remarks"}
CATEGORIES = {"pull", "moments", "groups", "qr"}
LOCAL_ZONE = timezone(timedelta(hours=8))


def now():
    return datetime.now(LOCAL_ZONE).replace(tzinfo=None)


def iso_time(value):
    return value.replace(tzinfo=LOCAL_ZONE).isoformat() if value else None


def can_write(db, user):
    permissions = set(get_user_permission_codes(db, user.id))
    return "*" in permissions or not permissions.isdisjoint(WRITE_PERMISSIONS)


def access(db, user, row):
    return row.created_by == user.id or can_delegate(db, user)


def require_edit(db, user, row):
    if not can_write(db, user) or not access(db, user, row):
        raise HTTPException(403, "只能维护本人录入记录；维护他人记录需要资源开拓代录权限")


def snapshot(row):
    data = {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "content"}
    if "amount" in data:
        data["amount"] = format(data["amount"], ".2f")
    for key in ("created_at", "updated_at"):
        if key in data:
            data[key] = iso_time(data[key])
    return jsonable_encoder(data)


def audit(db, user, row, action, before=None, after=None):
    db.add(Audit(record_id=row.id, action=action, actor_id=user.id, created_at=now(),
                 before=before or {}, after=after if after is not None else snapshot(row)))


def locked_record(db, record_id, *, required=True):
    # 同一 UUID 的新建、重试和后续操作串行；与人才开拓业务锁相互独立。
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "referral:" + str(record_id)})
    row = db.query(Record).filter_by(id=record_id).populate_existing().with_for_update().first()
    if not row and required:
        raise HTTPException(404, "推荐拓展记录不存在")
    return row


def check_revision(row, revision):
    if row.revision != revision:
        raise HTTPException(409, "记录已被修改，请重新加载后再保存")


def touch(row, user):
    row.updated_by, row.updated_at = user.id, now()
    row.revision += 1


def save_record(db, user, payload):
    if not can_write(db, user):
        raise HTTPException(403, "没有推荐拓展编辑权限")
    row = locked_record(db, payload.id, required=False)
    if row:
        require_edit(db, user, row)
        # 首次保存响应丢失后可以用同一 ID 重试，避免重复创建。
        if payload.revision == 0 and row.created_by == user.id and all(getattr(row, k) == getattr(payload, k) for k in BUSINESS_FIELDS):
            return row
        check_revision(row, payload.revision)
        before = snapshot(row)
        for key in BUSINESS_FIELDS:
            setattr(row, key, getattr(payload, key))
        touch(row, user)
        audit(db, user, row, "update", before)
    else:
        if payload.revision != 0:
            raise HTTPException(404, "记录已被删除，不能重新创建")
        stamp = now()
        row = Record(id=payload.id, **{key: getattr(payload, key) for key in BUSINESS_FIELDS},
                     payment_status="unpaid", created_by=user.id, updated_by=user.id,
                     created_at=stamp, updated_at=stamp, revision=1)
        db.add(row)
        db.flush()
        audit(db, user, row, "create")
    db.flush()
    return row


def set_payment(db, user, record_id, payload):
    row = locked_record(db, record_id)
    require_edit(db, user, row)
    check_revision(row, payload.revision)
    before = snapshot(row)
    row.payment_status, row.payment_date = payload.payment_status, payload.payment_date
    touch(row, user)
    audit(db, user, row, "payment", before)
    db.flush()
    return row


def filtered_records(db, user, *, start=None, end=None, keyword=None, payment_status=None,
                     creator_id=None, operator_id=None, paid_start=None, paid_end=None):
    query = db.query(Record)
    for field, lower, upper in ((Record.work_date, start, end), (Record.payment_date, paid_start, paid_end)):
        if lower:
            query = query.filter(field >= lower)
        if upper:
            query = query.filter(field <= upper)
    for field, value in ((Record.payment_status, payment_status), (Record.created_by, creator_id), (Record.updated_by, operator_id)):
        if value:
            query = query.filter(field == value)
    if keyword and keyword.strip():
        term = keyword.strip()
        wx_match = Record.wechat.icontains(term, autoescape=True)
        if not can_delegate(db, user):
            wx_match = and_(Record.created_by == user.id, wx_match)
        query = query.filter(or_(Record.full_name.icontains(term, autoescape=True), wx_match))
    return query


def duplicate_records(db, user, work_date, full_name, wechat, exclude_id=None):
    # 缺少微信时不能确定同名人员身份；只提示具有访问权限的确定候选。
    if not wechat.strip():
        return []
    query = db.query(Record).filter(Record.work_date == work_date, Record.full_name == full_name.strip(), Record.wechat == wechat.strip())
    if exclude_id:
        query = query.filter(Record.id != exclude_id)
    if not can_delegate(db, user):
        query = query.filter(Record.created_by == user.id)
    context = serialization_context(db, user)
    return [serialize_record(db, user, row, context=context) for row in query.order_by(Record.created_at.desc()).limit(20)]


def serialization_context(db, user):
    # 每个列表请求只查询一次人员及权限，避免随页大小重复扫描人员表。
    return dict(names={u.id: u.full_name or u.username for u in db.query(AppUser.id, AppUser.full_name, AppUser.username)},
                delegate=can_delegate(db, user), writable=can_write(db, user), admin=is_admin(db, user))


def serialize_record(db, user, row, detail=False, *, context=None):
    context = context if context is not None else serialization_context(db, user)
    allowed = row.created_by == user.id or context['delegate']
    names = context['names']
    result = snapshot(row)
    result.update(created_by_name=names.get(row.created_by, "-"), updated_by_name=names.get(row.updated_by, "-"),
                  can_edit=context['writable'] and allowed,
                  can_delete=context['writable'] and (row.created_by == user.id or context['admin']),
                  contact_restricted=not allowed)
    if not allowed:
        for key in PRIVATE_FIELDS:
            result[key] = "******" if result[key] else ""
    if detail:
        result["images"] = [snapshot(img) for img in db.query(Image).filter_by(record_id=row.id).order_by(Image.created_at, Image.id)] if allowed else []
        history = []
        for entry in db.query(Audit).filter_by(record_id=row.id).order_by(Audit.created_at.desc(), Audit.id.desc()):
            value = snapshot(entry)
            value["actor_name"] = names.get(entry.actor_id, "-")
            if not allowed:
                for side in ("before", "after"):
                    value[side] = {k: v for k, v in value[side].items() if k not in PRIVATE_FIELDS and k != "images"}
            history.append(value)
        result["audit"] = history
    return result
