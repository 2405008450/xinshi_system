"""客户来源只读统计；复用新咨询与客户的既有关联，不维护来源副本。"""
from datetime import date, datetime, time, timedelta
import json

from fastapi import HTTPException
from sqlalchemy import case, distinct, func

from chat_time import api_time
from models import Client, Consultation


DIMENSION_FIELDS = {
    'source': ('client_source',), 'method': ('consultation_method',),
    'type': ('consultation_type',), 'keyword': ('source_keyword',),
    'status': ('status',), 'type_status': ('consultation_type', 'status'),
}
VALUE_ALIASES = {
    'consultation_method': {'phone': '电话', 'email': '邮件', 'online': '在线咨询', 'onsite': '上门', 'other': '其他'},
    'consultation_type': {
        'simple': '简单咨询', 'translation': '笔译项目', '笔译': '笔译项目',
        'interpretation': '口译项目', '口译': '口译项目', 'recruitment': '招聘项目', '招聘': '招聘项目',
        'annotation': '标注项目', 'dubbing': '配音项目',
        'subtitle': '（音视频）转录/字幕项目', '字幕项目': '（音视频）转录/字幕项目',
        'notarization': '公证项目', 'certification': '认证项目',
        'equipment_rental': '其他项目', 'other': '其他项目', '其他': '其他项目',
    },
    'status': {'待处理': 'pending', '跟进中': 'following', '重点跟进': 'emphasis', '未成交': 'failed', '已确认': 'success'},
}


def normalized_field(field):
    value = func.coalesce(func.nullif(func.trim(getattr(Consultation, field)), ''), '未知')
    aliases = VALUE_ALIASES.get(field)
    return case(aliases, value=value, else_=value) if aliases else value


def dimension_expressions(dimension):
    if dimension not in DIMENSION_FIELDS:
        raise HTTPException(422, '不支持的分析维度')
    return [normalized_field(field) for field in DIMENSION_FIELDS[dimension]]


def source_expression():
    return dimension_expressions('source')[0]


def dimension_key(values):
    return values[0] if len(values) == 1 else json.dumps(list(values), ensure_ascii=False)


def source_query(db, client_id=None, start=None, end=None, source=None, dimension='source'):
    expressions = dimension_expressions(dimension)
    if start and end and start > end:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    query = db.query(Consultation)
    if client_id is not None:
        if db.get(Client, client_id) is None:
            raise HTTPException(404, '客户不存在')
        query = query.filter(Consultation.client_id == client_id)
    # 既有 consultation_time 是表单填写的 UTC+8 本地时间（无时区字段）。
    # 缺少咨询时间的历史记录不猜测日期，汇总保留并单独计数。
    if start:
        query = query.filter(Consultation.consultation_time >= datetime.combine(start, time.min))
    if end:
        if end == date.max:
            raise HTTPException(422, '结束日期超出支持范围')
        query = query.filter(Consultation.consultation_time < datetime.combine(end + timedelta(days=1), time.min))
    if source is not None:
        if len(expressions) == 1:
            values = [source]
        else:
            try:
                values = json.loads(source)
            except (ValueError, TypeError):
                raise HTTPException(422, '组合分析筛选值无效')
            if not isinstance(values, list) or len(values) != len(expressions) or not all(isinstance(value, str) for value in values):
                raise HTTPException(422, '组合分析筛选值无效')
        for expression, value in zip(expressions, values):
            query = query.filter(expression == value)
    return query


def period_start(day, granularity):
    if granularity == 'week':
        return day - timedelta(days=day.weekday())
    if granularity == 'month':
        return day.replace(day=1)
    return day


def summary(db, granularity='day', client_id=None, start=None, end=None, dimension='source'):
    if granularity not in {'day', 'week', 'month'}:
        raise HTTPException(422, '不支持的统计周期')
    query = source_query(db, client_id, start, end, dimension=dimension)
    expressions = dimension_expressions(dimension)
    total, clients = query.with_entities(func.count(Consultation.id), func.count(distinct(Consultation.client_id))).one()
    sources = [dict(source=dimension_key(row[:-2]), values=list(row[:-2]), count=row[-2], client_count=row[-1])
               for row in query.with_entities(
                   *expressions, func.count(Consultation.id), func.count(distinct(Consultation.client_id))
               ).group_by(*expressions).order_by(func.count(Consultation.id).desc(), *expressions).all()]
    # 数据库先按日、来源聚合，避免将所有业务记录载入内存。
    # SQLite date() 会把 23:59:59.999999 四舍五入到次日；隔离库保留本地日期原值。
    day_expr = (func.substr(Consultation.consultation_time, 1, 10)
                if db.get_bind().dialect.name == 'sqlite' else func.date(Consultation.consultation_time))
    daily = query.with_entities(day_expr, *expressions, func.count(Consultation.id)).group_by(day_expr, *expressions).all()
    periods = {}
    undated = 0
    for row in daily:
        day, name, count = row[0], dimension_key(row[1:-1]), row[-1]
        if day is None:
            undated += count
            continue
        if isinstance(day, str):
            day = date.fromisoformat(day)
        key = period_start(day, granularity).isoformat()
        item = periods.setdefault(key, {'period': key, 'count': 0, 'sources': {}})
        item['count'] += count
        item['sources'][name] = count + item['sources'].get(name, 0)
    return dict(total=total, client_count=clients, sources=sources,
                periods=[periods[key] for key in sorted(periods)], undated_count=undated)


def records(db, client_id=None, start=None, end=None, source=None, page=1, page_size=20, dimension='source'):
    query = source_query(db, client_id, start, end, source, dimension)
    total = query.count()
    page = min(page, max(1, (total + page_size - 1) // page_size))
    rows = query.outerjoin(Client, Consultation.client_id == Client.id).with_entities(
        Consultation.id, Consultation.consultation_code, Consultation.consultation_time,
        source_expression().label('client_source'), Consultation.source_keyword,
        normalized_field('consultation_type').label('consultation_type'),
        normalized_field('status').label('status'), Consultation.consultation_description,
        Consultation.contact_name, Consultation.handling_method, Consultation.follow_up_remarks,
        Consultation.project_intake,
        normalized_field('consultation_method').label('consultation_method'), Consultation.consultation_method_detail,
        Client.client_name, Client.client_short_name,
    ).order_by(Consultation.consultation_time.desc().nullslast(), Consultation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    from consultation_outcome import FAILURE_KEY
    items = []
    for row in rows:
        item = dict(row._mapping)
        item['failure_reason'] = (item.pop('project_intake') or {}).get(FAILURE_KEY)
        items.append(api_time(item))
    return dict(items=items, total=total, page=page, page_size=page_size)
