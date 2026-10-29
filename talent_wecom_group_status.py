"""从已关联开拓记录实时读取企微群状态，不在人才档案中保存状态副本。"""
from datetime import date, datetime, time

from business_time import BUSINESS_TIMEZONE

CHANNEL_FIELDS = {'group': 'wecom_small_group_status', 'group_large': 'wecom_large_group_status'}
GROUP_STATUSES = {'未处理', '已拉群', '已发码', '已进群', '已退群'}


def _moment(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)


def summarize_group_status(records, actions):
    result = {field: ('未处理' if records else None) for field in CHANNEL_FIELDS.values()}
    latest = {}
    for record in records:
        for channel, marker in (record.historical_markers or {}).items():
            if channel not in CHANNEL_FIELDS or not isinstance(marker, dict) or not marker.get('status'):
                continue
            moment = _moment(marker.get('action_date')) or _moment(record.work_date)
            if moment:
                key = (moment, 0, str(record.id))
                if channel not in latest or key > latest[channel][0]:
                    latest[channel] = (key, marker['status'])
    for action in actions:
        key = (_moment(action.created_at), 1, str(action.id))
        if key[0] and (action.channel not in latest or key > latest[action.channel][0]):
            latest[action.channel] = (key, action.status)
    for channel, (_, status) in latest.items():
        if channel == 'group' and status == '已邀进群':
            status = '已拉群'
        result[CHANNEL_FIELDS[channel]] = status if status in GROUP_STATUSES else '自定义状态'
    return result


def get_talent_wecom_group_status(db, person_id):
    from sqlalchemy import func
    from resource_development_models import DevelopmentAction, DevelopmentRecord
    from talent_duplicate_service import family_ids
    ids = family_ids(db, person_id)
    records = db.query(DevelopmentRecord.id, DevelopmentRecord.historical_markers, DevelopmentRecord.work_date).filter(
        DevelopmentRecord.person_id.in_(ids)
    ).all()
    if not records:
        return summarize_group_status([], [])
    ranked = db.query(
        DevelopmentAction.id, DevelopmentAction.channel, DevelopmentAction.status, DevelopmentAction.created_at,
        func.row_number().over(partition_by=DevelopmentAction.channel,
                               order_by=(DevelopmentAction.created_at.desc(), DevelopmentAction.id.desc())).label('rank'),
    ).join(DevelopmentRecord, DevelopmentRecord.id == DevelopmentAction.record_id).filter(
        DevelopmentRecord.person_id.in_(ids), DevelopmentAction.channel.in_(CHANNEL_FIELDS),
    ).subquery()
    actions = db.query(ranked.c.id, ranked.c.channel, ranked.c.status, ranked.c.created_at).filter(ranked.c.rank == 1).all()
    return summarize_group_status(records, actions)
