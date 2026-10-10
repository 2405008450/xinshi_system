"""公司微信账号汇总与渠道状态同步；不改写业务跟进历史或日报依据。"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text

from resource_models import ResourcePerson
from resource_development_models import DevelopmentAudit, DevelopmentRecord, DevelopmentOption
from business_time import business_now


DELETED_MARKERS = {"wechat": "已删微信", "enterprise": "已删企微"}
ACCOUNT_FIELDS = {"wechat_account", "wechat_accounts", "wechat_accounts_revision"}


def normalize_accounts(values):
    """旧字符串整体保留，不按逗号、顿号等猜测拆分。"""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def person_accounts(person):
    return normalize_accounts(person.wechat_accounts or person.wechat_account)


def lock_account_writes(db):
    # 与开拓保存共用事务锁，所有入口保持相同的加锁顺序。
    if hasattr(db, "get_bind") and db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(724092401)"))


def audit_accounts(db, actor, entity, action, before, after):
    if actor is not None:
        db.add(DevelopmentAudit(entity_id=entity.id, entity_type="person" if isinstance(entity, ResourcePerson) else "record",
                                actor_id=actor.id, action=action, before=before, after=after))


def store_accounts(db, person, values, *, actor=None, source="talent", force=False, source_record_ids=None):
    values = normalize_accounts(values)
    old = person_accounts(person)
    if len(values) > 100 or any(len(value) > 100 for value in values):
        raise HTTPException(422, "微信账号最多100项，每项最多100个字符")
    if values == old and not force:
        return
    person.wechat_accounts = values
    person.wechat_account = "、".join(values) or None
    person.wechat_accounts_revision = (person.wechat_accounts_revision or 1) + (values != old)
    if values != old:
        person.updated_at = business_now()
        audit_accounts(db, actor, person, "account_merge" if source in {"development", "migration"} else "accounts_update",
                       {"wechat_accounts": old}, {"wechat_accounts": values, "source": source,
                                                  "source_record_ids": source_record_ids or []})


def sync_channel(db, person, channel, status, *, actor=None, source="talent", source_record=None):
    now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
    state = {"status": status, "action_date": now.date().isoformat(), "updated_at": now.isoformat(),
             "operator_id": str(actor.id) if actor else None,
             "operator_name": (actor.full_name or actor.username) if actor else "系统",
             "source": source, "source_record_id": str(source_record.id) if source_record else None}
    before = dict(person.wechat_contact_state or {})
    person.wechat_contact_state = {**before, channel: state}
    # 状态变化也推进账号版本，防止另一端的旧账号表单撤销最新状态。
    person.wechat_accounts_revision = (person.wechat_accounts_revision or 1) + 1
    person.updated_at = now
    audit_accounts(db, actor, person, "contact_sync", {"contact_state": before}, {"contact_state": person.wechat_contact_state})
    db.flush()
    from talent_duplicate_service import family_ids
    for row in db.query(DevelopmentRecord).filter(DevelopmentRecord.person_id.in_(family_ids(db, person.id))).order_by(DevelopmentRecord.id).all():
        old = dict(row.contact_state or {})
        row.contact_state = {**old, channel: state}
        if source_record is None or row.id != source_record.id:
            row.revision += 1
        row.updated_at = now
        if actor:
            row.updated_by = actor.id
        audit_accounts(db, actor, row, "contact_sync", {"contact_state": old}, {"contact_state": row.contact_state})


def write_talent_accounts(db, person, payload, *, actor=None, creating=False):
    fields = payload.model_fields_set
    if not fields & {"wechat_accounts", "wechat_account"}:
        return
    if "wechat_accounts" in fields:
        values = normalize_accounts(payload.wechat_accounts)
    else:
        values = normalize_accounts(payload.wechat_account)
    old = person_accounts(person)
    if not creating and values != old:
        expected = payload.wechat_accounts_revision
        if "wechat_accounts" in fields and expected is None:
            raise HTTPException(409, "所在微信已启用版本保护，请重新打开人才资料后再保存")
        if expected is not None and expected != (person.wechat_accounts_revision or 1):
            raise HTTPException(409, "所在微信或联系状态已被修改，请重新打开人才资料后再保存")
    store_accounts(db, person, values, actor=actor, force=creating)
    for channel, marker in DELETED_MARKERS.items():
        if (marker in old) != (marker in values):
            sync_channel(db, person, channel, "（对方）已删" if marker in values else "已添加", actor=actor)


def merge_development_accounts(db, row, *, actor=None):
    if not row.person_id:
        return
    from talent_duplicate_service import canonical_id
    person = db.get(ResourcePerson, canonical_id(db, row.person_id))
    account = db.get(DevelopmentOption, row.account_id) if row.account_id else None
    values = [account.name] if account else []
    values.extend(row.friend_accounts or [])
    # 只有账号真的新增、修改或首次关联时调用，普通保存不回填被总库主动移除的账号。
    store_accounts(db, person, [*person_accounts(person), *values], actor=actor, source="development", source_record_ids=[str(row.id)])


def sync_development_channels(db, row, changes, *, actor=None):
    if not row.person_id:
        return
    from talent_duplicate_service import canonical_id
    person = db.get(ResourcePerson, canonical_id(db, row.person_id))
    for channel, status in changes.items():
        if channel not in DELETED_MARKERS or status not in {"已添加", "（对方）已删"}:
            continue
        marker = DELETED_MARKERS[channel]
        values = person_accounts(person)
        if status == "（对方）已删":
            values = [*values, marker]
        else:
            values = [value for value in values if value != marker]
        store_accounts(db, person, values, actor=actor, source="development")
        sync_channel(db, person, channel, status, actor=actor, source="development", source_record=row)
