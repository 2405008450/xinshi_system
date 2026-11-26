"""UTC+8创建日编号；沿用关联快照保存编号，无需改变既有表结构。"""
from datetime import datetime, time, timedelta
from sqlalchemy import String, cast, func, select, case, text
from chat_time import BUSINESS_TIMEZONE
from meeting_models import Meeting


def codes_query(db):
    postgres = db.bind.dialect.name == 'postgresql'
    local = func.timezone('Asia/Hong_Kong', Meeting.created_at) if postgres else Meeting.created_at
    day = func.date(local)
    sequence = func.row_number().over(partition_by=day, order_by=Meeting.number)
    digits = cast(sequence, String)
    suffix = case((sequence < 1000, func.lpad(digits, 3, '0')), else_=digits) if postgres else func.printf('%03d', sequence)
    prefix = cast(func.to_char(local, 'YYMMDD') if postgres else func.substr(func.strftime('%Y%m%d', local), 3), String)
    legacy = 'MT-' + prefix + '-' + suffix
    return select(Meeting.id.label('meeting_id'), func.coalesce(Meeting.association['meeting_no'].as_string(), legacy).label('meeting_no')).subquery()


def code_for(db, row):
    if (row.association or {}).get('meeting_no'):
        return row.association['meeting_no']
    codes = codes_query(db)
    return db.query(codes.c.meeting_no).filter(codes.c.meeting_id == row.id).scalar()


def allocate(db, moment):
    day = moment.astimezone(BUSINESS_TIMEZONE).date()
    # 同日并发创建串行分配；锁随事务提交/回滚释放。
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:namespace, :day)'), {'namespace': 1297370703, 'day': int(day.strftime('%Y%m%d'))})
    start = datetime.combine(day, time.min, BUSINESS_TIMEZONE)
    snapshots = db.query(Meeting.association).filter(Meeting.created_at >= start, Meeting.created_at < start + timedelta(days=1)).all()
    prefix = f'MT-{day:%y%m%d}-'
    used = [int(value['meeting_no'][len(prefix):]) for value, in snapshots if (value or {}).get('meeting_no', '').startswith(prefix)]
    return prefix + f'{max([len(snapshots), *used]) + 1:03d}'
