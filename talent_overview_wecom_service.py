"""企微大群管理：独立乐观锁、日期优先人数统计和事务内审计。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from concurrency import StaleUpdateError
from talent_overview_models import TalentOverviewSnapshot
from talent_overview_wecom_models import (
    TalentOverviewLanguageManagement as LanguageManagement,
    TalentOverviewManagementAudit as Audit,
    TalentOverviewWecomCount as Count,
    TalentOverviewWecomGroup as Group,
)


def _ensure_language(db, overview_key):
    from talent_overview_service import load_talent_overview_data
    snapshot = db.query(TalentOverviewSnapshot).filter_by(id=1).first()
    data = snapshot.payload if snapshot else load_talent_overview_data()
    if not any(row["overview_key"] == overview_key for row in data["rows"]):
        raise LookupError("语种行不存在，请先保存人才概览")


def _stamp(user):
    return dict(operator_id=user.id, operator_name=user.full_name or user.username,
                operated_at=datetime.now(ZoneInfo("Asia/Hong_Kong")))


def _fresh(row, expected_revision):
    if row.revision != expected_revision:
        raise StaleUpdateError("该语种或群已被其他人更新，请保留草稿并重新加载后核对")


def _group(db, group_id, expected_revision=None):
    query = db.query(Group).filter_by(id=group_id)
    if expected_revision is not None:
        query = query.with_for_update().populate_existing()
    row = query.first()
    if row is None:
        raise LookupError("企微群不存在")
    if expected_revision is not None:
        _fresh(row, expected_revision)
    return row


def _touch(row, stamp):
    row.revision += 1
    for key, value in stamp.items():
        setattr(row, key, value)


def _json_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _audit(db, overview_key, group_id, operation, before, after, stamp):
    db.add(Audit(overview_key=overview_key, group_id=group_id, operation=operation,
                 before={key: _json_value(value) for key, value in before.items()},
                 after={key: _json_value(value) for key, value in after.items()}, **stamp))


def _latest(db, group_ids):
    if not group_ids:
        return {}
    ranked = select(Count.id, func.row_number().over(
        partition_by=Count.group_id, order_by=(Count.statistics_date.desc(), Count.id.desc()),
    ).label("position")).where(Count.group_id.in_(group_ids), Count.voided_at.is_(None)).subquery()
    rows = db.query(Count).join(ranked, Count.id == ranked.c.id).filter(
        ranked.c.position <= 2,
    ).order_by(Count.statistics_date.desc(), Count.id.desc()).all()
    result = {}
    for row in rows:
        result.setdefault(row.group_id, []).append(row)
    return result


def summarize_groups(groups, latest):
    """未登记与零分开；仅未归档已建群参与人数汇总。"""
    active = [group for group in groups if not group.archived]
    built = [group for group in active if group.is_built]
    recorded = [latest[group.id][0] for group in built if latest.get(group.id)]
    return dict(built_group_count=len(built), unbuilt_group_count=len(active) - len(built),
                recorded_group_count=len(recorded),
                people_count_total=sum(row.people_count for row in recorded) if recorded else None,
                latest_statistics_date=max((row.statistics_date for row in recorded), default=None))


def with_wecom_summaries(db, data):
    groups = db.query(Group).filter(Group.archived.is_(False)).all()
    latest = _latest(db, [group.id for group in groups if group.is_built])
    by_key = {}
    for group in groups:
        by_key.setdefault(group.overview_key, []).append(group)
    return {**data, "rows": [{**row, "wecom_summary": summarize_groups(
        by_key.get(row["overview_key"], []), latest,
    )} for row in data["rows"]]}


def group_dict(row, latest):
    records = latest.get(row.id, [])
    current = records[0] if records else None
    return dict(id=row.id, overview_key=row.overview_key, name=row.name,
                is_built=row.is_built, built_date=row.built_date, archived=row.archived,
                plan=row.plan, remarks=row.remarks, revision=row.revision,
                operator_name=row.operator_name, operated_at=row.operated_at,
                latest_count_id=current.id if current else None,
                statistics_date=current.statistics_date if current else None,
                people_count=current.people_count if current else None,
                change=(current.people_count - records[1].people_count) if len(records) > 1 else None)


def get_group(db, group_id):
    row = _group(db, group_id)
    return group_dict(row, _latest(db, [row.id]))


def get_language_management(db, overview_key):
    _ensure_language(db, overview_key)
    row = db.get(LanguageManagement, overview_key)
    return dict(overview_key=overview_key, plan=row.plan if row else "", remarks=row.remarks if row else "",
                revision=row.revision if row else 0, operator_name=row.operator_name if row else None,
                operated_at=row.operated_at if row else None)


def save_language_management(db, overview_key, payload, user):
    _ensure_language(db, overview_key)
    stamp = _stamp(user)
    db.execute(pg_insert(LanguageManagement).values(
        overview_key=overview_key, plan="", remarks="", revision=0, **stamp,
    ).on_conflict_do_nothing(index_elements=["overview_key"]))
    row = db.query(LanguageManagement).filter_by(overview_key=overview_key).with_for_update().populate_existing().one()
    _fresh(row, payload.expected_revision)
    before = dict(plan=row.plan, remarks=row.remarks)
    after = payload.model_dump(exclude={"expected_revision"})
    if before != after:
        for key, value in after.items():
            setattr(row, key, value)
        _touch(row, stamp)
        _audit(db, overview_key, None, "language_edit", before, after, stamp)
    db.flush()
    return get_language_management(db, overview_key)


def list_groups(db, overview_key, include_archived=False):
    _ensure_language(db, overview_key)
    query = db.query(Group).filter_by(overview_key=overview_key)
    if not include_archived:
        query = query.filter(Group.archived.is_(False))
    groups = query.order_by(Group.archived, Group.name, Group.id).all()
    latest = _latest(db, [group.id for group in groups])
    return [group_dict(row, latest) for row in groups]


def create_group(db, overview_key, payload, user):
    _ensure_language(db, overview_key)
    stamp = _stamp(user)
    row = Group(overview_key=overview_key, revision=1, archived=False, **payload.model_dump(), **stamp)
    db.add(row)
    db.flush()
    _audit(db, overview_key, row.id, "group_create", {}, payload.model_dump(), stamp)
    db.flush()
    return group_dict(row, {})


def update_group(db, group_id, payload, user):
    row = _group(db, group_id, payload.expected_revision)
    if row.archived:
        raise ValueError("请先恢复归档群再编辑")
    after = payload.model_dump(exclude={"expected_revision"})
    before = {key: getattr(row, key) for key in after}
    changed = [key for key in after if before[key] != after[key]]
    if changed:
        stamp = _stamp(user)
        for key, value in after.items():
            setattr(row, key, value)
        _touch(row, stamp)
        _audit(db, row.overview_key, row.id, "group_edit",
               {key: before[key] for key in changed}, {key: after[key] for key in changed}, stamp)
    db.flush()
    return get_group(db, row.id)


def archive_group(db, group_id, payload, user):
    row = _group(db, group_id, payload.expected_revision)
    if row.archived != payload.archived:
        stamp = _stamp(user)
        _audit(db, row.overview_key, row.id, "archive" if payload.archived else "restore",
               {"archived": row.archived}, {"archived": payload.archived}, stamp)
        row.archived = payload.archived
        _touch(row, stamp)
    db.flush()
    return get_group(db, row.id)


def register_count(db, group_id, payload, user):
    row = _group(db, group_id, payload.expected_revision)
    if row.archived or not row.is_built:
        raise ValueError("只有未归档的已建群可以登记人数")
    stamp = _stamp(user)
    previous = _latest(db, [row.id]).get(row.id, [])
    count = Count(group_id=row.id, statistics_date=payload.statistics_date, people_count=payload.people_count, **stamp)
    db.add(count)
    db.flush()
    _touch(row, stamp)
    _audit(db, row.overview_key, row.id, "count_register",
           dict(statistics_date=previous[0].statistics_date, people_count=previous[0].people_count) if previous else {},
           dict(count_id=count.id, statistics_date=count.statistics_date, people_count=count.people_count), stamp)
    db.flush()
    return get_group(db, row.id)


def void_count(db, group_id, count_id, payload, user):
    row = _group(db, group_id, payload.expected_revision)
    if row.archived:
        raise ValueError("请先恢复归档群再作废统计")
    count = db.query(Count).filter_by(id=count_id, group_id=row.id).first()
    if count is None:
        raise LookupError("人数统计记录不存在")
    if count.voided_at is not None:
        raise ValueError("该统计记录已经作废")
    stamp = _stamp(user)
    count.voided_at, count.voided_by, count.voided_by_name = stamp["operated_at"], stamp["operator_id"], stamp["operator_name"]
    count.void_reason = payload.reason
    _touch(row, stamp)
    _audit(db, row.overview_key, row.id, "count_void",
           dict(count_id=count.id, statistics_date=count.statistics_date, people_count=count.people_count),
           dict(count_id=count.id, void_reason=payload.reason), stamp)
    db.flush()
    return get_group(db, row.id)


def history_page(db, overview_key=None, group_id=None, page=1, page_size=10):
    if group_id is not None:
        _group(db, group_id)
        query = db.query(Audit).filter_by(group_id=group_id)
    else:
        _ensure_language(db, overview_key)
        query = db.query(Audit).filter_by(overview_key=overview_key, group_id=None)
    total = query.count()
    rows = query.order_by(Audit.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return dict(total=total, items=[dict(id=row.id, operation=row.operation, before=row.before, after=row.after,
                                      operator_name=row.operator_name, operated_at=row.operated_at) for row in rows])


def counts_page(db, group_id, page=1, page_size=10):
    _group(db, group_id)
    query = db.query(Count).filter_by(group_id=group_id)
    total = query.count()
    rows = query.order_by(Count.statistics_date.desc(), Count.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return dict(total=total, items=[dict(id=row.id, statistics_date=row.statistics_date, people_count=row.people_count,
                                      operator_name=row.operator_name, operated_at=row.operated_at,
                                      voided_at=row.voided_at, voided_by_name=row.voided_by_name,
                                      void_reason=row.void_reason) for row in rows])
