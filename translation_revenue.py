"""客户营收：复用项目计价树，只读统计，不修改客户或项目计费口径。"""
import json
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload

import crud
import translation_customer_finance as finance
from annotation_progress_time import business_now, business_datetime
from database import get_db
from finance_manager_scope import manager_fields
from models import TranslationProject, TranslationSubOrder, Client, SubClient
from routers.auth import get_current_user, require_module_access
from search_matching import matches_keywords

router = APIRouter(prefix='/translation-revenue', tags=['客户营收统计'])
ZERO = Decimal('0')
FIELDS = {'billing': 'billing_totals', 'excl': 'totals_excl_tax', 'incl': 'totals_incl_tax'}


def money(value):
    return str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def start_of(day, period):
    if period == 'week':
        return day - timedelta(days=day.weekday())
    if period == 'year':
        return date(day.year, 1, 1)
    return date(day.year, ((day.month - 1) // 3 * 3 + 1) if period == 'quarter' else day.month, 1)


def shift(start, period, count):
    if period == 'week':
        return start + timedelta(weeks=count)
    months = start.year * 12 + start.month - 1 + count * {'month': 1, 'quarter': 3, 'year': 12}[period]
    year, month = divmod(months, 12)
    return date(year, month + 1, 1)


def previous_year(start, period):
    if period == 'week':
        year, week, _ = start.isocalendar()
        try:
            return date.fromisocalendar(year - 1, week, 1)
        except ValueError:
            return None  # 第53周不冒充上年的第52周。
    return start.replace(year=start.year - 1)


def bounds(start, period):
    if start is None:
        return None
    end = shift(start, period, 1)
    if period == 'week':
        year, week, _ = start.isocalendar()
        label = f'{year}年第{week}周'
    elif period == 'quarter':
        label = f'{start.year}年第{(start.month - 1) // 3 + 1}季度'
    else:
        label = start.strftime('%Y年%m月' if period == 'month' else '%Y年')
    return {'start': start.isoformat(), 'end': (end - timedelta(days=1)).isoformat(), 'label': label}


def order_date(project):
    match = re.match(r'^TP-(\d{8}|\d{6})-', (project.order_no or '').strip().upper())
    if match:
        digits = match[1] if len(match[1]) == 8 else '20' + match[1]
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])), False
        except ValueError:
            pass
    if project.customer_reception_time:
        return business_datetime(project.customer_reception_time).date(), True
    return None, False


def comparison(current, baseline):
    if baseline is None:
        return {'amount': None, 'difference': None, 'rate': None, 'state': 'unavailable'}
    delta = current - baseline
    return {'amount': money(baseline), 'difference': money(delta),
            'rate': money(delta / abs(baseline) * 100) if baseline else None,
            'state': 'normal' if baseline else 'zero' if not current else 'new'}


def client_modes(raw):
    try:
        values = json.loads(raw or '{}')
        if not isinstance(values, dict) or len(values) > 2000:
            raise ValueError()
        return {str(UUID(key)): value for key, value in values.items()
                if value in FIELDS} if all(value in FIELDS for value in values.values()) else invalid_modes()
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, '客户统计口径无效')


def invalid_modes():
    raise HTTPException(422, '请选择有效的客户统计口径')


def aggregate(entries, start, period, currency, modes):
    if start is None:
        return None
    end = shift(start, period, 1)
    result = {}
    for entry in entries:
        if not start <= entry['day'] < end:
            continue
        group = result.setdefault(entry['key'], {'amount': ZERO, 'projects': 0, 'missing': 0})
        field = FIELDS[modes.get(entry['client_id'], 'billing')]
        values = entry[field]
        if currency in values:
            group['amount'] += Decimal(str(values[currency]))
            group['projects'] += 1
        if not values or field in entry.get('incomplete_fields', []):
            group['missing'] += 1
    return result


def report(entries, period, anchor, currency='CNY', modes=None, keyword='', rank_min=None,
           rank_max=None, amount_min=None, amount_max=None, focus_client=None, skip=0, limit=20):
    modes = modes or {}
    start = start_of(anchor, period)
    starts = [start, shift(start, period, -1), previous_year(start, period)]
    groups = [aggregate(entries, point, period, currency, modes) for point in starts]
    all_clients = {entry['key']: entry for entry in entries}
    keys = set().union(*(set(group or {}) for group in groups))

    def value(group, key=None):
        if group is None:
            return None
        return sum((row['amount'] for uid, row in group.items() if key is None or uid == key), ZERO)

    rows = []
    for key in keys:
        entry = all_clients[key]
        current = value(groups[0], key)
        metrics = groups[0].get(key, {})
        if not any((group or {}).get(key, {}).get('projects', 0) or (group or {}).get(key, {}).get('missing', 0) for group in groups):
            continue  # 该币种在三个周期均未出现的客户不参与排名。
        rows.append({'key': key, 'client_id': entry['client_id'], 'client_name': entry['client_name'],
                     'client_short_name': entry['client_short_name'], 'amount': money(current),
                     'projects': metrics.get('projects', 0), 'missing': metrics.get('missing', 0),
                     'basis': modes.get(entry['client_id'], 'billing'),
                     'mom': comparison(current, value(groups[1], key)), 'yoy': comparison(current, value(groups[2], key))})
    rows.sort(key=lambda row: (-Decimal(row['amount']), row['client_name'], row['key']))
    for index, row in enumerate(rows, 1):
        row['rank'] = index
    ranked_count = len(rows)
    rows = [row for row in rows if (rank_min is None or row['rank'] >= rank_min)
            and (rank_max is None or row['rank'] <= rank_max)
            and (amount_min is None or Decimal(row['amount']) >= amount_min)
            and (amount_max is None or Decimal(row['amount']) <= amount_max)
            and matches_keywords(' '.join([row['client_name'], row['client_short_name']]), keyword)]
    timeline = []
    for offset in range(-11, 1):
        point = shift(start, period, offset)
        current_group = aggregate(entries, point, period, currency, modes)
        current = value(current_group, focus_client)
        timeline.append({**bounds(point, period), 'amount': money(current),
                         'mom': comparison(current, value(aggregate(entries, shift(point, period, -1), period, currency, modes), focus_client)),
                         'yoy': comparison(current, value(aggregate(entries, previous_year(point, period), period, currency, modes), focus_client)),
                         'missing': sum(row['missing'] for key, row in current_group.items() if focus_client is None or key == focus_client)})
    overall = value(groups[0])
    return {'period': bounds(start, period), 'previous': bounds(starts[1], period), 'last_year': bounds(starts[2], period),
            'currency': currency, 'overall': {'amount': money(overall), 'mom': comparison(overall, value(groups[1])),
            'yoy': comparison(overall, value(groups[2])), 'customers': sum(row['projects'] > 0 for row in groups[0].values()),
            'missing': sum(row['missing'] for row in groups[0].values())},
            'items': rows[skip:skip + limit], 'total': len(rows), 'ranked_customers': ranked_count,
            'filtered_amount': money(sum((Decimal(row['amount']) for row in rows), ZERO)),
            'timeline': timeline, 'focus_client': focus_client,
            'client_options': [{'key': key, 'id': item['client_id'], 'name': item['client_name']} for key, item in sorted(all_clients.items(), key=lambda pair: (pair[1]['client_name'], pair[0]))]}


@router.get('', dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])
def revenue(period: Literal['week', 'month', 'quarter', 'year'] = 'month', anchor: date | None = None,
            currency: str = Query('CNY', pattern=r'^[A-Z]{3}$'), client_basis: str = Query('{}', max_length=100000),
            keyword: str = Query('', max_length=300), rank_min: int | None = Query(None, ge=1),
            rank_max: int | None = Query(None, ge=1), amount_min: Decimal | None = Query(None, allow_inf_nan=False),
            amount_max: Decimal | None = Query(None, allow_inf_nan=False),
            focus_client: str | None = Query(None, max_length=100), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            manager_ids: list[UUID] | None = Query(None, max_length=2000), only_mine: bool = False,
            client_id: UUID | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    anchor = anchor or business_now().date()
    if not 2000 <= anchor.year <= 2100:
        raise HTTPException(422, '统计年份须为2000至2100年')
    if rank_min is not None and rank_max is not None and rank_min > rank_max:
        rank_min, rank_max = rank_max, rank_min
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        amount_min, amount_max = amount_max, amount_min
    modes = client_modes(client_basis)
    fields = manager_fields(db, user, manager_ids, only_mine)
    query = db.query(TranslationProject).outerjoin(Client, TranslationProject.client_id == Client.id).outerjoin(
        SubClient, TranslationProject.sub_client_id == SubClient.id).filter(TranslationProject.annotation_migrated_at.is_(None))
    query = crud._apply_translation_project_filters(query, field_filters=fields)
    if client_id:
        from sqlalchemy import func
        query = query.filter(func.coalesce(TranslationProject.client_id, SubClient.parent_client_id) == client_id)
    query = query.options(joinedload(TranslationProject.client), joinedload(TranslationProject.sub_client).joinedload(SubClient.parent_client),
                          selectinload(TranslationProject.customer_charge_items),
                          selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items))
    start = start_of(anchor, period)
    earliest = previous_year(shift(start, period, -11), period)
    if earliest is None:
        earliest = shift(start, period, -65)
    end = shift(start, period, 1)
    projects = []
    dates = {}
    missing_date = fallback_date = 0
    for project in query.all():
        day, fallback = order_date(project)
        if day is None:
            missing_date += 1
        elif earliest <= day < end:
            dates[project.id] = day
            fallback_date += int(fallback)
            projects.append(project)
    crud._attach_word_count_matrices(db, projects=projects)
    entries = []
    currencies = {'CNY'}
    for project in projects:
        crud._attach_project_client_fields(project)
        node = finance.tree(project, summary_only=True)['item']
        def incomplete(item, field):
            return any(incomplete(child, field) for child in item['children']) if item['children'] else not item.get(field)
        parent = project.client or (project.sub_client.parent_client if project.sub_client else None)
        uid = str(parent.id) if parent else None
        entry = {'key': uid or 'unlinked:' + str(project.id), 'client_id': uid,
                 'client_name': parent.client_name if parent else (project.client_name or '未关联客户') + '（未关联）',
                 'client_short_name': parent.client_short_name or '' if parent else '', 'day': dates[project.id],
                 'incomplete_fields': [field for field in FIELDS.values() if incomplete(node, field)],
                 **{field: node.get(field) or {} for field in FIELDS.values()}}
        entries.append(entry)
        for field in FIELDS.values():
            currencies.update(entry[field])
    result = report(entries, period, anchor, currency, modes, keyword, rank_min, rank_max, amount_min, amount_max,
                    focus_client, skip, limit)
    result.update(currencies=sorted(currencies), missing_date=missing_date, fallback_date=fallback_date,
                  generated_at=business_now().isoformat(), partial_period=start <= business_now().date() < end)
    return result
