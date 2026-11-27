"""口译、标注、招聘的新老客户统计；只读，按各模块完整历史判断首次下单。"""
from datetime import date, timedelta
from typing import Literal
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from database import get_db
from models import Client, SubClient
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from annotation_progress_time import business_datetime, business_now
from routers.auth import require_module_access
from search_matching import matches_keywords
from translation_statistics import summarize, period_bounds, percentage

MODELS = {'interpretation': (InterpretationProject, 'IP'), 'annotation': (AnnotationProject, 'AP'), 'recruitment': (RecruitmentProject, 'HP')}
INTERPRETATION_STATUSES = {
    'initial_follow_up':'初步跟进中', 'deal_pending_execution':'已成交待执行',
    'candidates_provided':'已提供人选','client_selected':'客户已定人选','client_changed':'客户改变人选',
    'in_progress':'进行中', 'cancelled':'已取消', 'partially_cancelled':'已部分取消',
    'ended':'已结束', 'settled':'已结款', '':'（空白）',
}
DEAL_STATUSES = frozenset({'deal_pending_execution','in_progress','ended','settled'})
router = APIRouter(prefix='/project-statistics', tags=['项目客户统计'], dependencies=[Depends(require_module_access('projects:read', 'projects:write'))])


def project_day(number, prefix):
    match = re.fullmatch(prefix + r'-(\d{8}|\d{6})-\d+', str(number or '').upper())
    if not match:
        return None
    digits = match[1]
    if len(digits) == 6:
        digits = '20' + digits
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def project_period_bounds(day, granularity, start, end):
    if granularity == 'all':return start, end
    if granularity == 'quarter':
        left = day.replace(month=(day.month-1)//3*3+1, day=1)
        following = date(left.year+1,1,1) if left.month==10 else left.replace(month=left.month+3)
        return left, following-timedelta(days=1)
    return period_bounds(day, granularity)


def report(db, module, *, start, end, granularity='month', date_basis='order', client_keyword='', all_dates=False, merge_deal_statuses=False):
    if module not in MODELS or granularity not in ('day', 'week', 'month', 'quarter', 'all') or date_basis not in ('order', 'reception'):
        raise HTTPException(422, '无效的统计条件')
    if not all_dates and (start > end or (end-start).days > 1095):
        raise HTTPException(422, '请选择不超过三年的有效日期范围')
    model, prefix = MODELS[module]
    query = db.query(model.order_no, model.client_id, SubClient.parent_client_id, model.created_at,
                     model.customer_consultation_time, Client.client_name, Client.client_short_name, Client.client_code, model.project_status).outerjoin(
        SubClient, model.sub_client_id == SubClient.id).outerjoin(Client, func.coalesce(model.client_id, SubClient.parent_client_id) == Client.id)
    if module == 'annotation':
        query = query.filter(model.parent_project_id.is_(None))
    first_dates, selected = {}, []
    undated, fallback_count = 0, 0
    for row in query.all():
        day = project_day(row.order_no, prefix) if date_basis == 'order' else business_datetime(row.customer_consultation_time).date() if row.customer_consultation_time else None
        fallback = day is None
        if fallback and row.created_at:
            day = business_datetime(row.created_at).date()
        if day is None:
            undated += 1
            continue
        client_id = row.client_id or row.parent_client_id
        key = str(client_id) if client_id else None
        if key:
            first_dates[key] = min(first_dates.get(key, day), day)
        name = (row.client_name or row.client_short_name or '未命名客户') if key else '未关联客户'
        short = row.client_short_name or name
        if (not all_dates and not start <= day <= end) or not matches_keywords(' '.join([name, short, row.client_code or '']), client_keyword):
            continue
        fallback_count += int(fallback)
        selected.append(dict(day=day, client_key=key, client_name=name, client_short_name=short, finance={},status=str(row.project_status or '').strip()))
    if all_dates:
        start = min((item['day'] for item in selected), default=business_now().date())
        end = max((item['day'] for item in selected), default=start)
    bounds = lambda day:project_period_bounds(day,granularity,start,end)
    result = summarize(selected, first_dates, start, end, granularity, 'excl_tax',period_bounds_fn=bounds)
    if module == 'interpretation':
        labels = dict(INTERPRETATION_STATUSES)
        if merge_deal_statuses:
            labels = {key:label for key,label in labels.items() if key not in DEAL_STATUSES}
            labels = {'deal_merged':'已成交项目（合并）', **labels}
        for item in selected:
            key = 'deal_merged' if merge_deal_statuses and item['status'] in DEAL_STATUSES else item['status']
            item['status_key'] = key
            labels.setdefault(key, f'其他状态（{key}）')
        indexed = {row['period_start']:row for row in result['periods']}
        for row in indexed.values():row['status_counts'] = {key:{'count':0,'share':0} for key in labels}
        for item in selected:
            indexed[bounds(item['day'])[0].isoformat()]['status_counts'][item['status_key']]['count'] += 1
        for row in indexed.values():
            for item in row['status_counts'].values():item['share'] = percentage(item['count'],row['order_count'])
        result['status_columns'] = [{'key':key,'label':label} for key,label in labels.items()]
    return dict(**result, module=module, generated_at=business_now().isoformat(), start=start.isoformat(), end=end.isoformat(),
                granularity=granularity, date_basis=date_basis, all_dates=all_dates, merge_deal_statuses=merge_deal_statuses,
                order_count=len(selected), fallback_date_orders=fallback_count, undated_orders=undated)


@router.get('/{module}')
def statistics(module: Literal['interpretation', 'annotation', 'recruitment'], start: date, end: date,
               granularity: Literal['day', 'week', 'month', 'quarter', 'all']='month', date_basis: Literal['order', 'reception']='order',
               client_keyword: str=Query('', max_length=255), all_dates: bool=False, merge_deal_statuses: bool=False, db=Depends(get_db)):
    return report(db, module, start=start, end=end, granularity=granularity, date_basis=date_basis, client_keyword=client_keyword,
                  all_dates=all_dates, merge_deal_statuses=merge_deal_statuses)
