"""客户营收：复用项目计价树，只读统计，不修改客户或项目计费口径。"""
import json
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, inspect

import crud
import translation_customer_finance as finance
from annotation_progress_time import business_now, business_datetime
from database import get_db
from finance_manager_scope import manager_fields
from models import TranslationProject, TranslationSubOrder, Client, SubClient
from routers.auth import get_current_user, require_module_access
from search_matching import matches_keywords
from translation_document_requirements import load_order_pricing_modes

router = APIRouter(prefix='/translation-revenue', tags=['客户营收统计'])
ZERO = Decimal('0')
FIELDS = {'billing': 'billing_totals', 'excl': 'totals_excl_tax', 'incl': 'totals_incl_tax'}
AMOUNT_LABELS = {'billing_totals': '计费金额', 'totals_excl_tax': '不含税金额', 'totals_incl_tax': '含税金额'}
AMOUNT_SHORTCUT_RANGES = (
    (50000, None), (10000, 50000), (5000, 10000), (1000, 5000),
    (500, 1000), (100, 500), (1, 100),
)
PROJECT_TYPES = ('translation', 'interpretation', 'annotation', 'recruitment')


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
    match = re.match(r'^(?:TP|IP|AP|HP)-(\d{8}|\d{6})-', (project.order_no or '').strip().upper())
    if match:
        digits = match[1] if len(match[1]) == 8 else '20' + match[1]
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])), False
        except ValueError:
            pass
    fallback = (project.customer_reception_time if hasattr(project, 'customer_reception_time') else
                project.customer_confirmation_time or project.customer_consultation_time or project.created_at)
    if fallback:
        return business_datetime(fallback).date(), True
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


def aggregate_periods(entries, starts, period, currency, modes, *, details_start=None):
    result = {start: {} for start in starts if start is not None}
    for entry in entries:
        start = start_of(entry['day'], period)
        group_by_customer = result.get(start)
        if group_by_customer is None:
            continue
        group = group_by_customer.setdefault(entry['key'], {'amount': ZERO, 'projects': 0, 'missing': 0})
        field = FIELDS[modes.get(entry['client_id'], 'billing')]
        values = entry[field]
        if currency in values:
            group['amount'] += Decimal(str(values[currency]))
            group['projects'] += 1
        missing_orders = entry.get('missing_orders')
        if missing_orders is not None:
            is_missing = bool(missing_orders)
        else:
            is_missing = not values or field in entry.get('incomplete_fields', [])
        group['visible'] = group.get('visible') or is_missing or currency in values or (
            missing_orders == [] and (
                currency in entry.get('priced_currencies', ())
                or any(currency in entry[amount_field] for amount_field in FIELDS.values())
            )
        )
        if is_missing:
            group['missing'] += 1
            if start == details_start:
                details = missing_orders or ([{
                    'order_no': entry.get('order_no'), 'project_name': entry.get('project_name'),
                    'reasons': [f'{AMOUNT_LABELS[field]}待补'],
                }] if entry.get('order_no') else [])
                group.setdefault('missing_orders', []).extend(details)
    return result


def amount_in_range(amount, minimum, maximum):
    return (minimum is None or amount >= minimum) and (maximum is None or amount <= maximum)


def project_type_totals(entries, start, end, currency, modes):
    summaries = {module: {'clients': set(), 'orders': 0, 'amount': ZERO} for module in PROJECT_TYPES}
    for entry in entries:
        if not start <= entry['day'] < end:
            continue
        summary = summaries[entry['module']]
        summary['orders'] += 1
        client = entry['client_id']
        if client:
            summary['clients'].add(client)
        field = FIELDS[modes.get(client, 'billing')]
        summary['amount'] += Decimal(str(entry[field].get(currency, ZERO)))
    return [{'module': module, 'customers': len(summary['clients']), 'orders': summary['orders'],
             'amount': money(summary['amount'])} for module, summary in summaries.items()]


def report(entries, period, anchor, currency='CNY', modes=None, keyword='', rank_min=None,
           rank_max=None, amount_min=None, amount_max=None, focus_client=None, skip=0, limit=20):
    modes = modes or {}
    start = start_of(anchor, period)
    timeline_starts = [shift(start, period, offset) for offset in range(-11, 1)]
    comparisons = [(point, shift(point, period, -1), previous_year(point, period)) for point in timeline_starts]
    starts = comparisons[-1]
    report_starts = {point for comparison_dates in comparisons for point in comparison_dates}
    by_period = aggregate_periods(entries, report_starts, period, currency, modes, details_start=start)
    groups = [by_period.get(point) for point in starts]
    all_clients = {entry['key']: entry for entry in entries}
    keys = set().union(*(set(group or {}) for group in groups))

    def value(group, key=None):
        if group is None:
            return None
        if key is not None:
            return group.get(key, {}).get('amount', ZERO)
        return sum((row['amount'] for row in group.values()), ZERO)

    rows = []
    for key in keys:
        entry = all_clients[key]
        current = value(groups[0], key)
        metrics = groups[0].get(key, {})
        if not any((group or {}).get(key, {}).get('visible') for group in groups):
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
    matching_rows = [(row, Decimal(row['amount'])) for row in rows
                     if matches_keywords(' '.join([row['client_name'], row['client_short_name']]), keyword)]
    amount_shortcuts = [
        {'min': minimum, 'max': maximum,
         'customers': sum(amount_in_range(amount, minimum, maximum) for _, amount in matching_rows)}
        for minimum, maximum in AMOUNT_SHORTCUT_RANGES
    ]
    rows = [row for row, amount in matching_rows if (rank_min is None or row['rank'] >= rank_min)
            and (rank_max is None or row['rank'] <= rank_max)
            and amount_in_range(amount, amount_min, amount_max)]
    page = rows[skip:skip + limit]
    for row in page:
        row['missing_orders'] = sorted(groups[0].get(row['key'], {}).get('missing_orders', []),
                                       key=lambda item: item['order_no'])
    timeline = []
    for point, previous, last_year in comparisons:
        current_group = by_period[point]
        current = value(current_group, focus_client)
        timeline.append({**bounds(point, period), 'amount': money(current),
                         'mom': comparison(current, value(by_period[previous], focus_client)),
                         'yoy': comparison(current, value(by_period.get(last_year), focus_client)),
                         'missing': sum(row['missing'] for key, row in current_group.items() if focus_client is None or key == focus_client)})
    overall = value(groups[0])
    return {'period': bounds(start, period), 'previous': bounds(starts[1], period), 'last_year': bounds(starts[2], period),
            'currency': currency, 'overall': {'amount': money(overall), 'mom': comparison(overall, value(groups[1])),
            'yoy': comparison(overall, value(groups[2])), 'customers': sum(row['projects'] > 0 for row in groups[0].values()),
            'missing': sum(row['missing'] for row in groups[0].values())},
            'items': page, 'total': len(rows), 'ranked_customers': ranked_count,
            'amount_shortcuts': amount_shortcuts, 'amount_shortcut_total': len(matching_rows),
            'filtered_amount': money(sum((Decimal(row['amount']) for row in rows), ZERO)),
            'timeline': timeline, 'focus_client': focus_client,
            'client_options': [{'key': key, 'id': item['client_id'], 'name': item['client_name']} for key, item in sorted(all_clients.items(), key=lambda pair: (pair[1]['client_name'], pair[0]))]}


def scope_detail(query, client_column, order_column, detail_key):
    if detail_key is None:
        return query
    key, unlinked = detail_key
    if unlinked:
        return query.filter(client_column.is_(None), order_column == key)
    return query.filter(client_column == key)


def other_project_query(db, module, client_id, fields, detail_key=None):
    from interpretation_models import InterpretationProject
    from project_customer_finance import MODELS
    from project_client_manager import manager_ids_expression

    model = InterpretationProject if module == 'interpretation' else MODELS[module]
    if not inspect(db.connection()).has_table(model.__tablename__):
        return model, None
    query = db.query(model).outerjoin(SubClient, model.sub_client_id == SubClient.id).outerjoin(
        Client, func.coalesce(model.client_id, SubClient.parent_client_id) == Client.id)
    if module == 'annotation':
        # 子订单会复制母订单价格，按母订单统计，避免重复计入。
        query = query.filter(model.parent_project_id.is_(None))
    if client_id:
        query = query.filter(Client.id == client_id)
    if fields:
        spec = next(iter(fields.values()))['value']
        ids = [UUID(value) for value in (spec.get('ids') or [spec['id']])]
        query = query.filter(manager_ids_expression(module, model.id, ids, spec['names'],
                             func.coalesce(SubClient.client_manager, Client.client_manager)))
    return model, scope_detail(query, Client.id, model.id, detail_key)


def other_amounts(module, project, record):
    if module == 'interpretation':
        import interpretation_customer_finance as oral
        payload = record.payload if record else {}
        totals = oral.calculate(payload)
        result = {field: totals[field] for field in ('totals_excl_tax', 'totals_incl_tax')}
        result['billing_totals'] = oral.billing_totals(payload, totals)
        rates = payload.get('rates', [])
        overtime = payload.get('overtime') if payload.get('has_overtime') else None
        complete = oral.settlement(payload).pricing_mode != 'fixed' and bool(rates) and all(
            row.get('quantity') is not None and has_unit_price(row) for row in rates
        ) and (not overtime or overtime.get('amount') is not None)
        if complete:
            result['missing_orders'] = []
        else:
            result['incomplete_fields'] = ['totals_' + basis for basis in ('incl_tax', 'excl_tax')
                                           if oral.incomplete_tax_basis(payload, basis)]
            if 'totals_' + oral.settlement(payload).tax_basis in result['incomplete_fields']:
                result['incomplete_fields'].append('billing_totals')
        return result

    from project_customer_finance import totals
    amounts = totals(module, [project])
    if module == 'recruitment':
        legacy = {project.service_fee_currency or 'CNY': project.service_fee_amount} if project.service_fee_amount is not None else {}
    else:
        # 标注历史单价没有已确认工作量，只有已登记的总价可计入。
        legacy = {}
    excl, incl = amounts['totals_excl_tax'], amounts['totals_incl_tax']
    result = {'totals_excl_tax': excl, 'totals_incl_tax': incl, 'billing_totals': {**legacy, **incl, **excl}}
    result['incomplete_fields'] = ['totals_' + kind for kind, count in amounts['missing_totals'].items() if count]
    return result


def other_entries(db, module, client_id, fields, earliest, end, detail_key=None):
    from interpretation_customer_finance import finance_records, ready
    from project_customer_finance import project_query

    model, query = other_project_query(db, module, client_id, fields, detail_key)
    if query is None:
        return [], 0, 0
    candidates = query.with_entities(model.id, model.order_no, model.customer_confirmation_time,
                                     model.customer_consultation_time, model.created_at)
    dates = {}
    missing_date = fallback_date = 0
    for project in candidates:
        day, fallback = order_date(project)
        if day is None:
            missing_date += 1
        elif earliest <= day < end:
            dates[project.id] = day
            fallback_date += int(fallback)
    entries = []
    if not dates:
        return entries, missing_date, fallback_date
    if module == 'interpretation':
        details = db.query(model).options(joinedload(model.client),
                                          joinedload(model.sub_client).joinedload(SubClient.parent_client))
    else:
        details = project_query(db, module).options(selectinload(model.sub_client).joinedload(SubClient.parent_client))
    project_ids = list(dates)
    for offset in range(0, len(project_ids), 500):
        selected = details.filter(model.id.in_(project_ids[offset:offset + 500])).all()
        records, _ = finance_records(db, selected, ready(db)) if module == 'interpretation' else ({}, {})
        for project in selected:
            client = project.client or (project.sub_client.parent_client if project.sub_client else None)
            uid = str(client.id) if client else None
            record = records.get(project.id)
            entry = dict(key=uid or 'unlinked:' + str(project.id), client_id=uid, module=module,
                                client_name=(client.client_name or client.client_short_name) if client else '未关联客户',
                                client_short_name=(client.client_short_name or '') if client else '',
                                day=dates[project.id], order_no=project.order_no or '未登记订单号', project_name=project.project_name,
                                **other_amounts(module, project, record))
            if detail_key is not None:
                entry['order_details'] = [{
                    **{name: entry[name] for name in ('order_no', 'project_name', *FIELDS.values())},
                    'id': f'{module}:{project.id}', 'module': module, 'depth': 0,
                    'prices': other_unit_prices(module, project, record),
                }]
            entries.append(entry)
    return entries, missing_date, fallback_date


def has_unit_price(price):
    tax = price.get('tax_prices') or {}
    return any(value is not None and value != '' for value in (
        price.get('amount'), tax.get('unit_price_excl_tax'), tax.get('unit_price_incl_tax'),
    ))


def order_unit_price(price):
    tax = price.get('tax_prices') or {}
    return {
        'label': price.get('language_pair') or price.get('language_display'),
        'currency': price.get('currency') or 'CNY',
        'excl': tax.get('unit_price_excl_tax'),
        'incl': tax.get('unit_price_incl_tax'),
        'legacy': price.get('amount') if not any(tax.get(key) is not None for key in (
            'unit_price_excl_tax', 'unit_price_incl_tax',
        )) else None,
        'unit': price.get('unit') or price.get('quantity_metric') or price.get('metric'),
        'unit_size': price.get('unit_size') or '1',
    }


def other_unit_prices(module, project, record):
    if module == 'interpretation':
        from interpretation_customer_finance import settlement
        payload = record.payload if record else {}
        prices = payload.get('rates', []) if settlement(payload).pricing_mode != 'fixed' else []
    elif module == 'annotation':
        from project_customer_finance import prices as annotation_prices
        prices = annotation_prices(project)
    else:
        prices = [{'tax_prices': project.tax_prices, 'currency': project.service_fee_currency}]
    return [order_unit_price(price) for price in prices if has_unit_price(price)]


def translation_order_details(node, depth=0):
    yield {
        **{name: node[name] for name in ('id', 'order_no', 'project_name', *FIELDS.values())},
        'module': 'translation', 'depth': depth, 'pricing_mode': node['pricing_mode'],
        'prices': [order_unit_price(price) for price in node['prices'] if has_unit_price(price)],
    }
    for child in node['children']:
        yield from translation_order_details(child, depth + 1)


def translation_priced_currencies(node):
    for price in node['prices']:
        if has_unit_price(price):
            yield price['currency']
    for child in node['children']:
        yield from translation_priced_currencies(child)


def translation_missing_orders(node, field):
    tax = node.get('effective_billing_tax_mode') if field == 'billing_totals' else field.removeprefix('totals_')
    amount_field = 'totals_' + tax if tax in ('incl_tax', 'excl_tax') else field
    amount_label = AMOUNT_LABELS[amount_field]
    prices = node['prices']
    override = node.get('total_adjustment') or {}
    if tax in override and {price['currency'] for price in prices} <= {override['currency']}:
        return []
    if not node.get('direct_pricing') and node['children']:
        return [item for child in node['children'] for item in translation_missing_orders(child, field)]
    if node.get(field) and not (field == 'billing_totals' and node.get('billing_tax_pending')):
        return []
    if node['pricing_mode'] == 'fixed':
        reasons = [f'固定收费的{amount_label}未填写']
    else:
        reasons = []
        if not any(has_unit_price(price) for price in prices) and node.get('amount') is None:
            reasons.append('未填写单价')
        if not any(price.get('quantity') is not None for price in prices) and finance.matches_missing_fields(node, word_count=True):
            reasons.append('缺少计价所需工作量')
        if not reasons:
            return []
    return [{'order_no':node['order_no'] or '未登记订单号', 'project_name':node['project_name'], 'reasons':reasons}]


@router.get('', dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])
def revenue(period: Literal['week', 'month', 'quarter', 'year'] = 'month', anchor: date | None = None,
            currency: str = Query('CNY', pattern=r'^[A-Z]{3}$'), client_basis: str = Query('{}', max_length=100000),
            keyword: str = Query('', max_length=300), rank_min: int | None = Query(None, ge=1),
            rank_max: int | None = Query(None, ge=1), amount_min: Decimal | None = Query(None, allow_inf_nan=False),
            amount_max: Decimal | None = Query(None, allow_inf_nan=False),
            focus_client: str | None = Query(None, max_length=100), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            manager_ids: list[UUID] | None = Query(None, max_length=2000), only_mine: bool = False,
            client_id: UUID | None = None, db: Session = Depends(get_db), user=Depends(get_current_user),
            project_type: Literal['all', 'translation', 'interpretation', 'annotation', 'recruitment'] = 'translation',
            detail_client: Annotated[str, Query(max_length=50)] = ''):
    anchor = anchor or business_now().date()
    if not 2000 <= anchor.year <= 2100:
        raise HTTPException(422, '统计年份须为2000至2100年')
    if rank_min is not None and rank_max is not None and rank_min > rank_max:
        rank_min, rank_max = rank_max, rank_min
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        amount_min, amount_max = amount_max, amount_min
    modes = client_modes(client_basis)
    detail_key = None
    if detail_client:
        unlinked = detail_client.startswith('unlinked:')
        try:
            detail_key = (UUID(detail_client.removeprefix('unlinked:')), unlinked)
        except ValueError:
            raise HTTPException(422, '客户标识无效')
    fields = manager_fields(db, user, manager_ids, only_mine)
    query = db.query(TranslationProject).outerjoin(Client, TranslationProject.client_id == Client.id).outerjoin(
        SubClient, TranslationProject.sub_client_id == SubClient.id).filter(TranslationProject.annotation_migrated_at.is_(None))
    query = crud._apply_translation_project_filters(query, field_filters=fields)
    client_column = func.coalesce(TranslationProject.client_id, SubClient.parent_client_id)
    if client_id:
        query = query.filter(client_column == client_id)
    query = scope_detail(query, client_column, TranslationProject.id, detail_key)
    start = start_of(anchor, period)
    earliest = previous_year(shift(start, period, -11), period)
    if earliest is None:
        earliest = shift(start, period, -65)
    if detail_key is not None:
        earliest = start
    end = shift(start, period, 1)
    dates = {}
    missing_date = fallback_date = 0
    if project_type in ('all', 'translation'):
        candidates = query.with_entities(TranslationProject.id, TranslationProject.order_no,
                                         TranslationProject.customer_reception_time)
        for project in candidates:
            day, fallback = order_date(project)
            if day is None:
                missing_date += 1
            elif earliest <= day < end:
                dates[project.id] = day
                fallback_date += int(fallback)
    projects_query = db.query(TranslationProject).options(
        joinedload(TranslationProject.client),
        joinedload(TranslationProject.sub_client).joinedload(SubClient.parent_client),
        selectinload(TranslationProject.customer_charge_items),
        selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
    )
    entries = []
    currencies = {'CNY'}

    project_ids = list(dates)
    for offset in range(0, len(project_ids), 500):
        projects = projects_query.filter(TranslationProject.id.in_(project_ids[offset:offset + 500])).all()
        load_order_pricing_modes(db, projects)
        finance.load_finance_details(db, projects, tax_only=True)
        crud._attach_word_count_matrices(db, projects=projects)
        for project in projects:
            parent = project.client or (project.sub_client.parent_client if project.sub_client else None)
            project.client_name = parent.client_name if parent else None
            project.client_short_name = parent.client_short_name if parent else None
            node = finance.tree(project, summary_only=True)['item']
            uid = str(parent.id) if parent else None
            field = FIELDS[modes.get(uid, 'billing')]
            missing = translation_missing_orders(node, field)
            entry = {'key': uid or 'unlinked:' + str(project.id), 'client_id': uid, 'module': 'translation',
                     'client_name': parent.client_name if parent else '未关联客户（未关联）',
                     'client_short_name': parent.client_short_name or '' if parent else '', 'day': dates[project.id],
                     'order_no': node['order_no'] or '未登记订单号', 'project_name': node['project_name'],
                     'missing_orders': missing,
                     **{field: node.get(field) or {} for field in FIELDS.values()}}
            if not missing and not any(entry[field] for field in FIELDS.values()):
                entry['priced_currencies'] = set(translation_priced_currencies(node))
            if detail_key is not None:
                entry['order_details'] = list(translation_order_details(node))
            entries.append(entry)
            for field in FIELDS.values():
                currencies.update(entry[field])
    for module in ('interpretation', 'annotation', 'recruitment'):
        if project_type not in ('all', module):
            continue
        extra, undated, fallback = other_entries(db, module, client_id, fields, earliest, end, detail_key)
        entries.extend(extra)
        missing_date += undated
        fallback_date += fallback
        for entry in extra:
            for field in FIELDS.values():
                currencies.update(entry[field])
    if detail_key is not None:
        entries.sort(key=lambda entry: (entry['day'], entry['order_no']), reverse=True)
        return {'items': [{**order, 'date': entry['day'].isoformat()}
                          for entry in entries for order in entry['order_details']]}
    result = report(entries, period, anchor, currency, modes, keyword, rank_min, rank_max, amount_min, amount_max,
                    focus_client, skip, limit)
    if project_type == 'all':
        result['project_type_totals'] = project_type_totals(entries, start, end, currency, modes)
    result.update(currencies=sorted(currencies), missing_date=missing_date, fallback_date=fallback_date,
                  generated_at=business_now().isoformat(), partial_period=start <= business_now().date() < end)
    return result
