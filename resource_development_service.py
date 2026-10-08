"""开拓记录保存、权限、查重、统计及日报来源。事务由 API 统一提交。"""
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, text, cast, String, case
from sqlalchemy.orm import Session

from interpretation_models import InterpretationLanguage
from models import AppUser
from resource_models import ResourcePerson
from resource_schemas import ResourcePersonCreate
from resource_service import create_talent, normalize_phone
from resource_development_models import (
    DevelopmentAction as Action, DevelopmentAudit as Audit,
    DevelopmentCounter as Counter, DevelopmentLanguage as Language,
    DevelopmentOption as Option, DevelopmentRecord as Record,
    DevelopmentScreenshot as Screenshot, DevelopmentWork as Work,
    DevelopmentFollowUp as FollowUp,
)
from talent_privacy import can_view_talent_contacts
from permission_service import user_has_permission
from talent_wechat_accounts import lock_account_writes, merge_development_accounts, sync_development_channels


def previous_workday(today: date) -> date:
    result = today - timedelta(days=1)
    while result.weekday() > 4:
        result -= timedelta(days=1)
    return result


def lock_writes(db):
    # 开拓事务串行分配编号、核重与入库，锁在事务结束自动释放。
    lock_account_writes(db)


def is_admin(db, user):
    return can_view_talent_contacts(db, user)


def owns(db, user, owner_id):
    return user.id == owner_id or can_delegate(db, user)


def can_delegate(db, user):
    return is_admin(db, user) or user_has_permission(db, user.id, "resource_development:delegate")


def can_delete_record(db, user, owner_id):
    # 代录仅扩展录入、修改和必要的联系方式访问，不扩展他人记录的删除权限。
    return user.id == owner_id or is_admin(db, user)


def require_owner(db, user, owner_id):
    if not owns(db, user, owner_id):
        raise HTTPException(403, "只能维护本人名下的开拓记录，代录需要资源开拓代录权限")


def active_user(db, user_id):
    user = db.get(AppUser, user_id)
    if not user or not user.is_active:
        raise HTTPException(422, "请选择在用的公司人员")
    return user


def user_name(db, user_id):
    user = db.get(AppUser, user_id)
    return (user.full_name or user.username) if user else "-"


def option(db, option_id, kind):
    row = db.get(Option, option_id) if option_id else None
    if not row or row.kind != kind:
        raise HTTPException(422, "平台或交换账号无效")
    return row


def snapshot(row):
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder({c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "content"})


def audit(db, user, row, action, before=None):
    db.flush()
    db.add(Audit(entity_id=row.id, entity_type=row.__tablename__.removeprefix("resource_development_"),
                 actor_id=user.id, action=action, before=before or {}, after=snapshot(row)))


def check_revision(row, revision):
    if row.revision != revision:
        raise HTTPException(409, "记录已被修改，请重新打开后再保存")


def allocate_greeting(db, platform, work_date):
    lock_writes(db)
    counter = db.get(Counter, (platform.id, work_date))
    if not counter:
        counter = Counter(platform_id=platform.id, work_date=work_date, value=0)
        db.add(counter)
    counter.value += 1
    db.flush()
    return f"{platform.code}-{work_date:%y%m%d}-{counter.value:03d}"


def record_name_duplicates(db, user, name, skip=0, limit=20):
    """仅查开拓记录；联系方式遵循现有记录所有权，不读取人才总库。"""
    name = name.strip().lower()
    if not name:
        return {"items": [], "total": 0}
    query = db.query(Record).filter(func.lower(func.trim(Record.full_name)) == name)
    total = query.count()
    items = []
    for row in query.order_by(Record.work_date.desc(), Record.updated_at.desc(), Record.id.desc()).offset(skip).limit(limit):
        allowed = owns(db, user, row.owner_id)
        items.append({
            "id": str(row.id), "full_name": row.full_name, "greeting_no": row.greeting_no,
            "work_date": row.work_date, "owner_name": user_name(db, row.owner_id),
            "platform_name": option(db, row.platform_id, "platform").name,
            "phone": row.phone if allowed else "", "wechat": row.wechat if allowed else "",
            "contact_restricted": not allowed,
        })
    return {"items": items, "total": total}


def duplicates(db, name, phone, wechat):
    name = name.strip().casefold()
    phone = normalize_phone(phone)
    wechat = wechat.strip().casefold()
    conditions = [func.lower(func.trim(ResourcePerson.full_name)) == name]
    if wechat:
        conditions.append(func.lower(func.trim(ResourcePerson.wechat)) == wechat)
    if phone:
        if db.get_bind().dialect.name == "postgresql":
            conditions += [func.regexp_replace(col, r"\D", "", "g") == phone
                           for col in [ResourcePerson.primary_phone, ResourcePerson.secondary_phone]]
        else:
            # 测试库不支持 regexp_replace；生产库使用 SQL 匹配。
            conditions.append(ResourcePerson.primary_phone.is_not(None))
            conditions.append(ResourcePerson.secondary_phone.is_not(None))
    result = []
    for person in db.query(ResourcePerson).filter(or_(*conditions)).all():
        matches = []
        if (person.full_name or "").strip().casefold() == name:
            matches.append("name")
        if phone and phone in {normalize_phone(person.primary_phone), normalize_phone(person.secondary_phone)}:
            matches.append("phone")
        if wechat and (person.wechat or "").strip().casefold() == wechat:
            matches.append("wechat")
        if matches:
            # 不把人才总库联系方式返回给开拓人员。
            result.append({"id": str(person.id), "full_name": person.full_name,
                           "resource_code": person.resource_code, "match_fields": matches})
    return result


PRIVATE_ENTRY_STATUSES = {"wechat": "已添加", "enterprise": "已添加", "group": "已进群", "group_large": "已进群"}
GROUP_STATUSES = {"group": {"未处理", "已拉群", "已进群", "已退群"},
                  "group_large": {"未处理", "已拉群", "已发码", "已进群", "已退群"}}


def group_action_date():
    return datetime.now(timezone(timedelta(hours=8))).date()


FRIEND_STATUS_ALIASES = {"已发请求": "一次请求", "二次添加": "二次请求", "三次添加": "三次请求"}
FRIEND_STATUSES = {"未处理", "搜不到", "一次请求", "一次请求未通过", "二次请求", "二次请求未通过",
                   "三次请求", "三次请求未通过", "已添加", "（对方）已删"}
STANDARD_PROGRESS_STATUSES = FRIEND_STATUSES | set(FRIEND_STATUS_ALIASES) | {"已邀进群", "已拉群", "已发码", "已进群", "已退群", "已沟通", "已入项"}


def progress_status(status, channel):
    if channel == "group" and status == "已邀进群":
        return "已拉群"
    return FRIEND_STATUS_ALIASES.get(status, status) if channel in {"wechat", "enterprise"} else status


def status_filter_values(values, channel):
    # 新旧查询名称均能命中同一业务状态；其他渠道不套用加微别名。
    if channel == "group":
        canonical = {progress_status(value, channel) for value in values}
        return canonical | ({"已邀进群"} if "已拉群" in canonical else set())
    if channel not in {"wechat", "enterprise"}:
        return values
    canonical = {progress_status(value, channel) for value in values}
    return canonical | {old for old, new in FRIEND_STATUS_ALIASES.items() if new in canonical}


def has_new_private_entry(actions, previous):
    """只有新确认的成功跟进才入库；沿用创建顺序判断各渠道最终状态。"""
    latest = {a.channel: a.status for a in actions}
    return any(
        a.channel in PRIVATE_ENTRY_STATUSES
        and a.status == PRIVATE_ENTRY_STATUSES[a.channel]
        and latest[a.channel] == a.status
        and previous.get(a.id) != (a.channel, a.status)
        for a in actions
    )


def sync_person(db, row, payload, languages, *, eligible, actor=None):
    if row.person_id or not eligible:
        return
    candidates = duplicates(db, row.full_name, row.phone, row.wechat)
    if payload.link_person_id:
        if str(payload.link_person_id) not in {p["id"] for p in candidates}:
            raise HTTPException(422, "关联档案必须来自本次查重候选")
        if any(set(p["match_fields"]) & {"phone", "wechat"} and p["id"] != str(payload.link_person_id) for p in candidates):
            raise HTTPException(409, "手机号或微信号同时命中其他档案，请先处理冲突")
        row.person_id = payload.link_person_id
        return
    strong = any(set(p["match_fields"]) & {"phone", "wechat"} for p in candidates)
    if strong or (candidates and not payload.duplicate_note):
        raise HTTPException(409, {"message": "发现疑似重复人才，请确认关联或处理冲突", "duplicates": candidates})
    if not payload.capabilities:
        raise HTTPException(422, "进入私域时请至少选择一个人才专业分类")
    platform = option(db, row.platform_id, "platform")
    account = option(db, row.account_id, "account") if row.account_id else None
    person_payload = ResourcePersonCreate(
        full_name=row.full_name, primary_phone=row.phone or None, wechat=row.wechat or None,
        wechat_account=account.name if account else None, registration_source=platform.name,
        remarks=row.remarks or None, dialects=[lang.label for lang in languages if lang.language_type == "dialect"],
        capabilities=[{"capability_type": cap} for cap in set(payload.capabilities) if cap != "recruitment"],
        career_profile={} if "recruitment" in payload.capabilities else None,
        language_skills=[{"language_id": lang.id, "role": "dialect_ethnic" if lang.language_type == "dialect" else "foreign", "priority": 0, "sort_order": i}
                         for i, lang in enumerate(languages)],
        annotation_language_skills=[{"source_language_id": lang.id} for lang in languages] if "annotation" in payload.capabilities else [],
    )
    person = create_talent(db, person_payload, idempotency_key=f"development:{row.id}", commit=False, actor=actor)
    row.person_id = person.id


def save_record(db, user, payload, *, historical_markers=None, defer_refresh=False):
    lock_writes(db)
    row = db.get(Record, payload.id)
    require_owner(db, user, payload.owner_id)
    if row:
        require_owner(db, user, row.owner_id)
        # 客户端 UUID 作为创建幂等键，响应丢失后重试不重复写历史或建档。
        if payload.revision == 0:
            return row
        check_revision(row, payload.revision)
        if "follow_up" in payload.model_fields_set and payload.follow_up != row.follow_up:
            raise HTTPException(422, "历史跟进原文不能修改，请新增跟进情况")
    elif payload.revision:
        raise HTTPException(404, "开拓记录已删除")
    active_user(db, payload.owner_id)
    platform = option(db, payload.platform_id, "platform")
    if payload.account_id:
        option(db, payload.account_id, "account")
    languages = db.query(InterpretationLanguage).filter(InterpretationLanguage.id.in_(payload.language_ids)).all() if payload.language_ids else []
    if len(languages) != len(payload.language_ids):
        raise HTTPException(422, "语种/方言已不存在，请重新选择")
    before = snapshot(row) if row else None
    old_person_id = row.person_id if row else None
    old_date, old_owner = (row.work_date, row.owner_id) if row else (payload.work_date, payload.owner_id)
    if not row:
        row = Record(id=payload.id, greeting_no=allocate_greeting(db, platform, payload.work_date),
                     created_by=user.id, revision=0, historical_only=historical_markers is not None,
                     historical_markers=historical_markers or {})
        db.add(row)
    for key in ["platform_id", "work_date", "owner_id", "full_name", "account_id", "phone", "wechat", "remarks", "duplicate_note"]:
        setattr(row, key, getattr(payload, key))
    # 旧页面未提交新增字段时保留原值；显式提交空字符串仍可清空。
    if "xiaohongshu" in payload.model_fields_set or before is None:
        row.xiaohongshu = payload.xiaohongshu
    if "friend_accounts" in payload.model_fields_set or before is None:
        row.friend_accounts = payload.friend_accounts
    if before is None:
        row.follow_up = payload.follow_up
    row.updated_by, row.updated_at = user.id, datetime.now()
    row.revision += 1
    # flush 前先填满记录的所有必填字段。
    db.flush()
    db.query(Language).filter_by(record_id=row.id).delete(synchronize_session=False)
    db.add_all([Language(record_id=row.id, language_id=lang.id) for lang in languages])
    last_follow_up_time = db.query(func.max(FollowUp.created_at)).filter(FollowUp.record_id == row.id).scalar()
    for entry in payload.follow_ups:
        saved = db.get(FollowUp, entry.id)
        if saved:
            if saved.record_id != row.id or saved.content != entry.content:
                raise HTTPException(409, "跟进标识冲突或历史内容被修改，请重新加载")
            continue
        # 存储香港本地时间；微秒保证同次提交多条记录的先后顺序。
        created_at = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        if last_follow_up_time is not None:
            created_at = max(created_at, last_follow_up_time + timedelta(microseconds=1))
        last_follow_up_time = created_at
        follow_up = FollowUp(id=entry.id, record_id=row.id, content=entry.content,
                             operator_id=user.id, created_at=created_at)
        db.add(follow_up)
        audit(db, user, follow_up, "create")
    existing = {a.id: a for a in db.query(Action).filter_by(record_id=row.id).all()}
    previous_states = {a.id: (a.channel, a.status) for a in existing.values()}
    if not set(existing).issubset({a.id for a in payload.actions}):
        raise HTTPException(422, "已保存的操作历史不能删除，可修正日期、人员或状态")
    for entry in payload.actions:
        if entry.account_id:
            option(db, entry.account_id, "account")
        action = existing.get(entry.id)
        action_before = snapshot(action) if action else None
        values = {key: getattr(entry, key) for key in ["channel", "status", "action_date", "operator_id", "account_id"]}
        values["status"] = progress_status(entry.status, entry.channel)
        if action and (action.channel in GROUP_STATUSES or entry.channel in GROUP_STATUSES):
            if any(getattr(action, key) != value for key, value in values.items()
                   if key != "status") or progress_status(action.status, action.channel) != values["status"]:
                raise HTTPException(422, "已保存的群操作记录不能修改，请新增一次跟进")
        if not action and entry.channel in GROUP_STATUSES and historical_markers is None:
            if values["status"] not in GROUP_STATUSES[entry.channel]:
                raise HTTPException(422, "请选择该群类型支持的状态")
            # 群操作按实际保存人和业务时区记账，不能由客户端伪造。
            values["operator_id"], values["action_date"] = user.id, group_action_date()
        active_user(db, values["operator_id"])
        if action and action.channel == entry.channel and progress_status(action.status, action.channel) == values["status"]:
            # 展示名变化不改写历史原值，也不产生额外的操作审计。
            values["status"] = action.status
        if not action:
            if db.get(Action, entry.id):
                raise HTTPException(409, "操作标识冲突，请重新打开表单")
            action = Action(id=entry.id, record_id=row.id, created_by=user.id, created_at=datetime.now())
            db.add(action)
        elif all(getattr(action, key) == value for key, value in values.items()):
            # 快捷追加跟进不改写既有历史的真实修改人和时间。
            continue
        for key, value in values.items():
            setattr(action, key, value)
        action.updated_by, action.updated_at = user.id, datetime.now()
        audit(db, user, action, "update" if action_before else "create", action_before)
    db.flush()
    # 按录入顺序而非可修改的业务日期确定次数，历史修正不会重排其他申请。
    actions = db.query(Action).filter_by(record_id=row.id).order_by(Action.created_at, Action.id).all()
    for action in actions:
        action.request_number = 0
    for channel, field in [("wechat", "wechat_status"), ("enterprise", "enterprise_status")]:
        count, current = 0, (row.historical_markers or {}).get(channel, {}).get("status", "未处理")
        for action in [a for a in actions if a.channel == channel]:
            status = progress_status(action.status, channel)
            if status in {"一次请求", "二次请求", "三次请求"}:
                count = max(count + 1, {"二次请求": 2, "三次请求": 3}.get(status, 1))
                action.request_number = count
            else:
                action.request_number = 0
            current = action.status
        setattr(row, field, current)
    sync_person(db, row, payload, languages,
                eligible=historical_markers is None and has_new_private_entry(actions, previous_states), actor=user)
    if row.person_id:
        newly_linked = old_person_id != row.person_id
        if newly_linked:
            row.contact_state = dict(db.get(ResourcePerson, row.person_id).wechat_contact_state or {})
        if newly_linked or (before and before.get("account_id") != (str(row.account_id) if row.account_id else None)):
            merge_development_accounts(db, row, actor=user)
        elif before.get("friend_accounts", []) != row.friend_accounts:
            merge_development_accounts(db, row, actor=user)
        # 只有各渠道最后一条操作的新建/状态修正才是新结论；普通保存不重放旧历史。
        latest = {a.channel: a for a in actions if a.channel in {"wechat", "enterprise"}}
        changes = {channel: progress_status(a.status, channel) for channel, a in latest.items()
                   if previous_states.get(a.id) != (a.channel, a.status)}
        overlay = dict(row.contact_state or {})
        for channel in changes:
            overlay.pop(channel, None)
        row.contact_state = overlay
        if historical_markers is None:
            sync_development_channels(db, row, changes, actor=user)
    audit(db, user, row, "update" if before else "create", before)
    db.flush()
    if not defer_refresh:
        refresh_draft(db, old_owner, old_date)
    if not defer_refresh and (row.owner_id, row.work_date) != (old_owner, old_date):
        refresh_draft(db, row.owner_id, row.work_date)
    return row


def current_contact_status(channel):
    """当前状态供查询使用；统计仍读原始业务状态。"""
    return func.coalesce(Record.contact_state[channel]["status"].as_string(), getattr(Record, f"{channel}_status"))


def serialize_record(db, user, row, detail=False):
    allowed = owns(db, user, row.owner_id)
    result = snapshot(row)
    for key in ["wechat_status", "enterprise_status"]:
        result[key] = progress_status(result[key], key.removesuffix("_status"))
        if not allowed and result[key] not in FRIEND_STATUSES:
            result[key] = "自定义状态"
    for key in ["phone", "wechat", "xiaohongshu"]:
        if not allowed and result[key]:
            result[key] = "******"
    # 自由文本可能包含联系方式，同样按记录所有权保护。
    for key in ["remarks", "follow_up", "duplicate_note"]:
        if not allowed and result[key]:
            result[key] = "受限内容"
    result.update(can_edit=allowed, can_delete=can_delete_record(db, user, row.owner_id), contact_restricted=not allowed,
                  owner_name=user_name(db, row.owner_id), platform_name=option(db, row.platform_id, "platform").name,
                  account_name=option(db, row.account_id, "account").name if row.account_id else "")
    langs = db.query(InterpretationLanguage).join(Language, Language.language_id == InterpretationLanguage.id).filter(Language.record_id == row.id).all()
    result["language_ids"] = [str(lang.id) for lang in langs]
    result["language_names"] = "、".join(lang.label for lang in langs)
    person = db.get(ResourcePerson, row.person_id) if row.person_id else None
    result["resource_code"] = person.resource_code if person else None
    actions = db.query(Action).filter_by(record_id=row.id).order_by(Action.created_at, Action.id).all()
    result["progress"] = {key: {"status": progress_status(value["status"], key) if allowed or value["status"] in STANDARD_PROGRESS_STATUSES else "自定义状态", "action_date": value.get("action_date"),
                               "operator_name": value.get("operator_name") or "原表未填写", "request_number": 0}
                          for key, value in (row.historical_markers or {}).items()}
    # 只读人员也能追溯标准群状态；不暴露历史导入原文中的联系方式。
    result["historical_progress"] = {key: dict(value) for key, value in result["progress"].items() if key in GROUP_STATUSES}
    # 来源原文可能含联系方式，未授权人员只看标准进展。
    if not allowed:
        result["historical_markers"] = {}
    labels = {"wechat": "微信", "enterprise": "企微", "group": "企微小群", "group_large": "企微大群", "communication": "沟通", "project": "入项"}
    for action in actions:
        result["progress"][action.channel] = {
            "status": progress_status(action.status, action.channel) if allowed or action.status in STANDARD_PROGRESS_STATUSES else "自定义状态",
            "action_date": action.action_date.isoformat(), "operator_name": user_name(db, action.operator_id),
        }
    for channel, value in (row.contact_state or {}).items():
        if channel in {"wechat", "enterprise"}:
            result[f"{channel}_status"] = value["status"]
            result["progress"][channel] = {key: value.get(key) for key in ["status", "action_date", "operator_name", "source", "updated_at"]}
            result["progress"][channel]["synchronized"] = True
    # 同步来源记录 ID 仅供审计，不在普通响应中暴露其他人员记录标识。
    result.pop("contact_state", None)
    result["friend_accounts_text"] = "、".join(row.friend_accounts or [])
    friend_latest = next((a for a in reversed(actions) if a.channel in {'wechat', 'enterprise'}), None)
    result['add_friend_follow_up'] = (f'{progress_status(friend_latest.status, friend_latest.channel)} · {friend_latest.action_date:%Y-%m-%d} · {user_name(db, friend_latest.operator_id)} · {labels[friend_latest.channel]}' if friend_latest else '')
    if friend_latest and not allowed and progress_status(friend_latest.status, friend_latest.channel) not in FRIEND_STATUSES:
        result['add_friend_follow_up'] = f'自定义状态 · {friend_latest.action_date:%Y-%m-%d} · {user_name(db, friend_latest.operator_id)} · {labels[friend_latest.channel]}'
    follow_ups = db.query(FollowUp).filter_by(record_id=row.id).order_by(FollowUp.created_at.desc(), FollowUp.id.desc())
    latest = follow_ups.first()
    def follow_up_result(entry):
        return {"id": str(entry.id), "content": entry.content if allowed else "受限内容",
                "operator_name": user_name(db, entry.operator_id),
                "created_at": entry.created_at.replace(tzinfo=timezone(timedelta(hours=8))).isoformat()}
    result["latest_follow_up"] = (latest.content if allowed else "受限内容") if latest else result["follow_up"]
    result["latest_follow_up_entry"] = follow_up_result(latest) if latest else None
    result["follow_up_count"] = follow_ups.count()
    if detail:
        result["follow_ups"] = [follow_up_result(entry) for entry in follow_ups.all()]
        result["actions"] = [{**snapshot(a), "status": progress_status(a.status, a.channel), "operator_name": user_name(db, a.operator_id),
                              "created_by_name": user_name(db, a.created_by), "updated_by_name": user_name(db, a.updated_by)}
                             for a in actions]
        if not allowed:
            for action in result["actions"]:
                if action["status"] not in STANDARD_PROGRESS_STATUSES:
                    action["status"] = "自定义状态"
        result["audit"] = [{**snapshot(a), "actor_name": user_name(db, a.actor_id)}
                           for a in db.query(Audit).filter(Audit.entity_id.in_([row.id, *[UUID(a["id"]) for a in result["actions"]], *[UUID(a["id"]) for a in result["follow_ups"]]])).order_by(Audit.created_at)] if allowed else []
    return result


def filtered_records(db, user, start, end, keyword=None, owner_id=None, platform_id=None, account_id=None, state=None, column_filters=None):
    q = db.query(Record)
    if start is not None:
        q = q.filter(Record.work_date >= start)
    if end is not None:
        q = q.filter(Record.work_date <= end)
    for field, value in [(Record.owner_id, owner_id), (Record.platform_id, platform_id), (Record.account_id, account_id)]:
        if value:
            q = q.filter(field == value)
    if state:
        states = status_filter_values([state], "wechat")
        q = q.filter(or_(current_contact_status("wechat").in_(states), current_contact_status("enterprise").in_(states)))
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        language_match = db.query(Language).join(InterpretationLanguage, InterpretationLanguage.id == Language.language_id).filter(Language.record_id == Record.id, InterpretationLanguage.label.ilike(pattern)).exists()
        platform_match = db.query(Option).filter(Option.id == Record.platform_id, Option.kind == "platform", Option.name.ilike(pattern)).exists()
        common = [Record.full_name.ilike(pattern), Record.greeting_no.ilike(pattern), language_match, platform_match]
        contacts = or_(Record.phone.ilike(pattern), Record.wechat.ilike(pattern), Record.xiaohongshu.ilike(pattern))
        q = q.filter(or_(*common, contacts if can_delegate(db, user) else and_(Record.owner_id == user.id, contacts)))
    unrestricted = can_delegate(db, user)
    for key, value in (column_filters or {}).items():
        if not value:
            continue
        values = value if isinstance(value, list) else [value]
        pattern = f"%{values[0]}%"
        identifiers = {'platform_name': Record.platform_id, 'owner_name': Record.owner_id, 'account_name': Record.account_id}
        channels = {'wechat_status': 'wechat', 'enterprise_status': 'enterprise', 'group_status': 'group', 'group_large_status': 'group_large', 'communication_status': 'communication', 'project_status': 'project'}
        if key in identifiers:
            try:
                ids = [UUID(v) for v in values]
            except ValueError:
                raise HTTPException(422, '列筛选标识无效')
            q = q.filter(identifiers[key].in_(ids))
        elif key == 'language_names':
            try:
                ids = [UUID(v) for v in values]
            except ValueError:
                raise HTTPException(422, '语种标识无效')
            q = q.filter(db.query(Language).filter(Language.record_id == Record.id, Language.language_id.in_(ids)).exists())
        elif key in channels:
            if not unrestricted and any(v not in STANDARD_PROGRESS_STATUSES for v in values):
                q = q.filter(Record.owner_id == user.id)
            latest = db.query(Action.status).filter(Action.record_id == Record.id, Action.channel == channels[key]).order_by(Action.created_at.desc(), Action.id.desc()).limit(1).correlate(Record).scalar_subquery()
            fallback = getattr(Record, key) if key in {'wechat_status', 'enterprise_status'} else '未处理'
            if channels[key] in GROUP_STATUSES:
                fallback = func.coalesce(Record.historical_markers[channels[key]]["status"].as_string(), '未处理')
            current = current_contact_status(channels[key]) if channels[key] in {"wechat", "enterprise"} else func.coalesce(latest, fallback)
            q = q.filter(current.in_(status_filter_values(values, channels[key])))
        elif key == 'friend_accounts_text':
            q = q.filter(cast(Record.friend_accounts, String).ilike(pattern))
        elif key == 'resource_code':
            q = q.filter(db.query(ResourcePerson).filter(ResourcePerson.id == Record.person_id, ResourcePerson.resource_code.ilike(pattern)).exists())
        elif key in {'latest_follow_up', 'follow_up'}:
            latest = db.query(FollowUp.id).filter(FollowUp.record_id == Record.id).order_by(FollowUp.created_at.desc(), FollowUp.id.desc()).limit(1).correlate(Record).scalar_subquery()
            current_match = db.query(FollowUp).join(AppUser, AppUser.id == FollowUp.operator_id).filter(
                FollowUp.id == latest, or_(FollowUp.content.ilike(pattern),
                    func.coalesce(func.nullif(AppUser.full_name, ''), AppUser.username).ilike(pattern),
                    cast(FollowUp.created_at, String).ilike(pattern),
                    func.to_char(FollowUp.created_at, 'YYYY"年"MM"月"DD"日" HH24:MI:SS').ilike(pattern))).exists()
            q = q.filter(or_(current_match, and_(latest.is_(None), Record.follow_up.ilike(pattern))))
            if not unrestricted:
                q = q.filter(Record.owner_id == user.id)
        elif key in {'full_name','greeting_no','phone','wechat','xiaohongshu','work_date','follow_up','remarks','updated_at'}:
            q = q.filter(cast(getattr(Record, key), String).ilike(pattern))
            if key in {'phone','wechat','xiaohongshu','follow_up','remarks'} and not unrestricted:
                q = q.filter(Record.owner_id == user.id)
    return q


def work_result(db, user, work_date, owner_id):
    row = db.query(Work).filter_by(work_date=work_date, owner_id=owner_id).first()
    allowed = owns(db, user, owner_id)
    result = snapshot(row) if row else dict(work_date=work_date.isoformat(), owner_id=str(owner_id), periods=[], deduction=0,
                                           completed=None, explanation="", duration_minutes=0, revision=0)
    result.update(owner_name=user_name(db, owner_id), can_edit=allowed, screenshots=[])
    if row and allowed:
        result["screenshots"] = [{"id": str(s.id), "name": s.name} for s in db.query(Screenshot.id, Screenshot.name).filter_by(work_id=row.id)]
    if not allowed:
        result["explanation"] = "受限内容" if result["explanation"] else ""
    return result


def report_item(db, owner_id, work_date):
    count, added = db.query(func.count(Record.id), func.count(Record.id).filter(or_(Record.wechat_status == "已添加", Record.enterprise_status == "已添加"))).filter_by(owner_id=owner_id, work_date=work_date).one()
    work = db.query(Work).filter_by(owner_id=owner_id, work_date=work_date).first()
    if not count and not work:
        return None
    completion = "未填写" if not work or work.completed is None else ("是" if work.completed else "否")
    return dict(source_type="system_event", source_id=uuid5(NAMESPACE_URL, f"resource-development:{owner_id}:{work_date}"),
                task_type="资源开拓", task_name="资源开拓每日汇总", progress_content=f"开拓记录 {count} 条，添加成功 {added} 条；完成：{completion}",
                result_content=work.explanation if work else "", duration_minutes=work.duration_minutes if work else 0,
                display_metadata={"source": "resource_development", "work_date": work_date.isoformat()})


def refresh_draft(db, owner_id, work_date):
    from task_models import DailyReport, DailyReportItem
    report = db.query(DailyReport).filter_by(user_id=owner_id, report_date=work_date, status="draft").first()
    if not report:
        return
    from daily_report_mail_models import DailyReportMailDelivery
    if db.query(DailyReportMailDelivery.id).filter_by(report_id=report.id, status="sent").first():
        return
    source_id = uuid5(NAMESPACE_URL, f"resource-development:{owner_id}:{work_date}")
    current = next((item for item in report.items if item.source_type == "system_event" and item.source_id == source_id), None)
    derived = report_item(db, owner_id, work_date)
    if not derived:
        if current:
            report.items.remove(current)
    elif current:
        for key, value in derived.items():
            setattr(current, key, value)
    else:
        report.items.append(DailyReportItem(**derived, sort_order=max((i.sort_order for i in report.items), default=-1) + 1))


def save_work(db, user, payload):
    lock_writes(db)
    require_owner(db, user, payload.owner_id)
    active_user(db, payload.owner_id)
    row = db.query(Work).filter_by(work_date=payload.work_date, owner_id=payload.owner_id).first()
    before = snapshot(row) if row else None
    if row:
        check_revision(row, payload.revision)
    elif payload.revision:
        raise HTTPException(409, "每日工作记录已发生变化")
    else:
        row = Work(work_date=payload.work_date, owner_id=payload.owner_id, revision=0)
        db.add(row)
    row.periods = [p.model_dump() for p in payload.periods]
    row.deduction, row.duration_minutes = payload.deduction, payload.duration_minutes
    row.completed, row.explanation = payload.completed, payload.explanation
    row.updated_by, row.revision = user.id, row.revision + 1
    audit(db, user, row, "update" if before else "create", before)
    db.flush()
    refresh_draft(db, row.owner_id, row.work_date)
    return row
