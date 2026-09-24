"""开拓记录保存、权限、查重、统计及日报来源。事务由 API 统一提交。"""
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, text, cast, String
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
)
from talent_privacy import can_view_talent_contacts
from permission_service import user_has_permission


def previous_workday(today: date) -> date:
    result = today - timedelta(days=1)
    while result.weekday() > 4:
        result -= timedelta(days=1)
    return result


def lock_writes(db):
    # 开拓事务串行分配编号、核重与入库，锁在事务结束自动释放。
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(724092401)"))


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
        raise HTTPException(422, "平台或对接账号无效")
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


PRIVATE_ENTRY_STATUSES = {"wechat": "已添加", "enterprise": "已添加", "group": "已进群"}


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


def sync_person(db, row, payload, languages, *, eligible):
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
    person = create_talent(db, person_payload, idempotency_key=f"development:{row.id}", commit=False)
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
    old_date, old_owner = (row.work_date, row.owner_id) if row else (payload.work_date, payload.owner_id)
    if not row:
        row = Record(id=payload.id, greeting_no=allocate_greeting(db, platform, payload.work_date),
                     created_by=user.id, revision=0, historical_only=historical_markers is not None,
                     historical_markers=historical_markers or {})
        db.add(row)
    for key in ["platform_id", "work_date", "owner_id", "full_name", "account_id", "phone", "wechat", "follow_up", "remarks", "duplicate_note"]:
        setattr(row, key, getattr(payload, key))
    row.updated_by, row.updated_at = user.id, datetime.now()
    row.revision += 1
    # flush 前先填满记录的所有必填字段。
    db.flush()
    db.query(Language).filter_by(record_id=row.id).delete(synchronize_session=False)
    db.add_all([Language(record_id=row.id, language_id=lang.id) for lang in languages])
    existing = {a.id: a for a in db.query(Action).filter_by(record_id=row.id).all()}
    previous_states = {a.id: (a.channel, a.status) for a in existing.values()}
    if not set(existing).issubset({a.id for a in payload.actions}):
        raise HTTPException(422, "已保存的操作历史不能删除，可修正日期、人员或状态")
    for entry in payload.actions:
        active_user(db, entry.operator_id)
        if entry.account_id:
            option(db, entry.account_id, "account")
        action = existing.get(entry.id)
        action_before = snapshot(action) if action else None
        if not action:
            if db.get(Action, entry.id):
                raise HTTPException(409, "操作标识冲突，请重新打开表单")
            action = Action(id=entry.id, record_id=row.id, created_by=user.id, created_at=datetime.now())
            db.add(action)
        elif all(getattr(action, key) == getattr(entry, key) for key in ["channel", "status", "action_date", "operator_id", "account_id"]):
            # 快捷追加跟进不改写既有历史的真实修改人和时间。
            continue
        for key in ["channel", "status", "action_date", "operator_id", "account_id"]:
            setattr(action, key, getattr(entry, key))
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
            if action.status == "已发请求":
                count += 1
                action.request_number = count
            else:
                action.request_number = 0
            current = action.status
        setattr(row, field, current)
    sync_person(db, row, payload, languages,
                eligible=historical_markers is None and has_new_private_entry(actions, previous_states))
    audit(db, user, row, "update" if before else "create", before)
    db.flush()
    if not defer_refresh:
        refresh_draft(db, old_owner, old_date)
    if not defer_refresh and (row.owner_id, row.work_date) != (old_owner, old_date):
        refresh_draft(db, row.owner_id, row.work_date)
    return row


def serialize_record(db, user, row, detail=False):
    allowed = owns(db, user, row.owner_id)
    result = snapshot(row)
    for key in ["wechat_status", "enterprise_status"]:
        if not allowed and result[key] not in {"未处理", "搜不到", "已发请求", "已添加"}:
            result[key] = "自定义状态"
    for key in ["phone", "wechat"]:
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
    result["progress"] = {key: {"status": value["status"], "action_date": value.get("action_date"),
                               "operator_name": value.get("operator_name") or "原表未填写", "request_number": 0}
                          for key, value in (row.historical_markers or {}).items()}
    # 来源原文可能含联系方式，未授权人员只看标准进展。
    if not allowed:
        result["historical_markers"] = {}
    labels = {"wechat": "微信", "enterprise": "企微", "group": "进群", "communication": "沟通", "project": "入项"}
    for action in actions:
        result["progress"][action.channel] = {
            "status": action.status if allowed or action.status in {"未处理", "搜不到", "已发请求", "已添加", "已邀进群", "已进群", "已沟通", "已入项"} else "自定义状态",
            "action_date": action.action_date.isoformat(), "operator_name": user_name(db, action.operator_id),
        }
    latest = actions[-1] if actions else None
    result["latest_follow_up"] = (f"{latest.action_date:%m-%d} · {user_name(db, latest.operator_id)} · {labels.get(latest.channel, latest.channel)}" if latest else "")
    if detail:
        result["actions"] = [{**snapshot(a), "operator_name": user_name(db, a.operator_id),
                              "created_by_name": user_name(db, a.created_by), "updated_by_name": user_name(db, a.updated_by)}
                             for a in actions]
        if not allowed:
            for action in result["actions"]:
                if action["status"] not in {"未处理", "搜不到", "已发请求", "已添加", "已邀进群", "已进群", "已沟通", "已入项"}:
                    action["status"] = "自定义状态"
        result["audit"] = [{**snapshot(a), "actor_name": user_name(db, a.actor_id)}
                           for a in db.query(Audit).filter(Audit.entity_id.in_([row.id, *[UUID(a["id"]) for a in result["actions"]]])).order_by(Audit.created_at)] if allowed else []
    return result


def filtered_records(db, user, start, end, keyword=None, owner_id=None, platform_id=None, account_id=None, state=None, column_filters=None):
    q = db.query(Record).filter(Record.work_date.between(start, end))
    for field, value in [(Record.owner_id, owner_id), (Record.platform_id, platform_id), (Record.account_id, account_id)]:
        if value:
            q = q.filter(field == value)
    if state:
        q = q.filter(or_(Record.wechat_status == state, Record.enterprise_status == state))
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        common = [Record.full_name.ilike(pattern), Record.greeting_no.ilike(pattern)]
        contacts = or_(Record.phone.ilike(pattern), Record.wechat.ilike(pattern))
        q = q.filter(or_(*common, contacts if can_delegate(db, user) else and_(Record.owner_id == user.id, contacts)))
    unrestricted = can_delegate(db, user)
    for key, value in (column_filters or {}).items():
        if not value:
            continue
        values = value if isinstance(value, list) else [value]
        pattern = f"%{values[0]}%"
        identifiers = {'platform_name': Record.platform_id, 'owner_name': Record.owner_id, 'account_name': Record.account_id}
        channels = {'wechat_status': 'wechat', 'enterprise_status': 'enterprise', 'group_status': 'group', 'communication_status': 'communication', 'project_status': 'project'}
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
            if not unrestricted and any(v not in {'未处理','搜不到','已发请求','已添加','已邀进群','已进群','已沟通','已入项'} for v in values):
                q = q.filter(Record.owner_id == user.id)
            latest = db.query(Action.status).filter(Action.record_id == Record.id, Action.channel == channels[key]).order_by(Action.created_at.desc(), Action.id.desc()).limit(1).correlate(Record).scalar_subquery()
            q = q.filter(func.coalesce(latest, '未处理').in_(values))
        elif key == 'resource_code':
            q = q.filter(db.query(ResourcePerson).filter(ResourcePerson.id == Record.person_id, ResourcePerson.resource_code.ilike(pattern)).exists())
        elif key == 'latest_follow_up':
            latest = db.query(Action.id).filter(Action.record_id == Record.id).order_by(Action.created_at.desc(), Action.id.desc()).limit(1).correlate(Record).scalar_subquery()
            q = q.filter(db.query(Action).join(AppUser, AppUser.id == Action.operator_id).filter(Action.id == latest, or_(Action.status.ilike(pattern), AppUser.full_name.ilike(pattern), AppUser.username.ilike(pattern), cast(Action.action_date, String).ilike(pattern))).exists())
            if not unrestricted:
                q = q.filter(Record.owner_id == user.id)
        elif key in {'full_name','greeting_no','phone','wechat','work_date','follow_up','remarks','updated_at'}:
            q = q.filter(cast(getattr(Record, key), String).ilike(pattern))
            if key in {'phone','wechat','follow_up','remarks'} and not unrestricted:
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
