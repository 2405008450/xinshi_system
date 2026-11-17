"""按客户查看笔译项目的子客户关联。"""

import re
from datetime import datetime

from sqlalchemy import and_, case, func, or_

from annotation_progress_time import business_datetime, business_now
from models import Client, SubClient, TranslationProject
from search_matching import keyword_any


def month_bounds(value):
    months = sorted(set(value.split(','))) if value else [business_now().strftime('%Y-%m')]
    if len(months) > 36:
        raise ValueError('一次最多查询 36 个月')
    bounds = []
    for month in months:
        if not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', month):
            raise ValueError('月份请使用 YYYY-MM 格式')
        year, number = map(int, month.split('-'))
        if not 1 <= year <= 9998:
            raise ValueError('月份超出可查询范围')
        start = datetime(year, number, 1)
        end = datetime(year + (number == 12), number % 12 + 1, 1)
        bounds.append((start, end))
    return bounds


def filtered_projects(db, months, keyword, presence):
    project = TranslationProject
    client_id = func.coalesce(project.client_id, SubClient.parent_client_id)
    # 两个现有日期字段均保存香港业务本地时间。
    received_at = func.coalesce(project.customer_reception_time, project.created_at)
    bounds = month_bounds(months)
    query = (db.query(project.id).select_from(project)
             .outerjoin(SubClient, project.sub_client_id == SubClient.id)
             .outerjoin(Client, client_id == Client.id)
             .filter(project.annotation_migrated_at.is_(None),
                     or_(*(and_(received_at >= start, received_at < end) for start, end in bounds)),
                     keyword_any((Client.client_name, Client.client_short_name, Client.client_code), keyword)))
    if presence == 'with':
        query = query.filter(project.sub_client_id.is_not(None))
    elif presence == 'without':
        query = query.filter(project.sub_client_id.is_(None))
    return query, client_id, received_at


def customer_groups(db, *, months, keyword, skip, limit, presence='all'):
    query, client_id, _ = filtered_projects(db, months, keyword, presence)
    total_orders = func.count(TranslationProject.id)
    with_sub_client = func.sum(case((TranslationProject.sub_client_id.is_not(None), 1), else_=0))
    groups = (query.with_entities(client_id.label('client_id'), Client.client_name, Client.client_short_name,
                                  Client.client_code, total_orders.label('order_count'),
                                  with_sub_client.label('with_sub_client'),
                                  (total_orders - with_sub_client).label('without_sub_client'))
              .group_by(client_id, Client.client_name, Client.client_short_name, Client.client_code))
    rows = groups.order_by(Client.client_short_name.asc().nulls_last(), client_id).offset(skip).limit(limit)
    return {'items': [dict(row._mapping) for row in rows], 'total': groups.count()}


def customer_projects(db, *, months, keyword, client, presence, skip, limit,
                      project_keyword='', sub_client_id=None, sort_by='received_at', sort_direction='desc'):
    query, client_id, received_at = filtered_projects(db, months, keyword, presence)
    project = TranslationProject
    query = query.filter(client_id.is_(None) if client == 'unlinked' else client_id == client)
    sub_client_name = func.coalesce(func.nullif(SubClient.client_short_name, ''), SubClient.client_name)
    sub_clients = []
    if client != 'unlinked':
        choices = (db.query(SubClient.id, SubClient.client_name, SubClient.client_short_name, SubClient.sub_client_code)
                   .filter(SubClient.parent_client_id == client)
                   .order_by(sub_client_name, SubClient.sub_client_code, SubClient.id))
        sub_clients = [dict(row._mapping) for row in choices]
    if sub_client_id is not None:
        query = query.filter(project.sub_client_id == sub_client_id, SubClient.parent_client_id == client) if client != 'unlinked' else query.filter(False)
    query = query.filter(keyword_any((project.order_no, project.project_name, SubClient.client_name,
                                      SubClient.client_short_name, SubClient.sub_client_code), project_keyword))
    total = query.count()
    sort_column = {'order_no': project.order_no, 'project_name': func.lower(project.project_name),
                   'sub_client': func.lower(sub_client_name), 'received_at': received_at}[sort_by]
    primary_sort = sort_column.asc() if sort_direction == 'asc' else sort_column.desc()
    ordered = [primary_sort.nulls_last()]
    if sort_by != 'received_at':
        ordered.append(received_at.desc().nulls_last())
    if sort_by != 'order_no':
        ordered.append(project.order_no.desc().nulls_last())
    rows = (query.with_entities(project.id, project.order_no, project.project_name, project.sub_client_id,
                               SubClient.client_short_name.label('sub_client_short_name'),
                               SubClient.client_name.label('sub_client_name'), received_at.label('received_at'))
            .order_by(*ordered, project.id).offset(skip).limit(limit))
    items = []
    for row in rows:
        data = dict(row._mapping)
        data['received_at'] = business_datetime(data['received_at']).isoformat()
        items.append(data)
    return {'items': items, 'total': total, 'sub_clients': sub_clients}
