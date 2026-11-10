"""口译、标注、招聘的新老客户统计；只读，按各模块完整历史判断首次下单。"""
from datetime import date
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
from translation_statistics import summarize

MODELS = {'interpretation': (InterpretationProject, 'IP'), 'annotation': (AnnotationProject, 'AP'), 'recruitment': (RecruitmentProject, 'HP')}
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


def report(db, module, *, start, end, granularity='month', date_basis='order', client_keyword=''):
    if module not in MODELS or granularity not in ('day', 'week', 'month') or date_basis not in ('order', 'reception'):
        raise HTTPException(422, '无效的统计条件')
    if start > end or (end-start).days > 1095:
        raise HTTPException(422, '请选择不超过三年的有效日期范围')
    model, prefix = MODELS[module]
    query = db.query(model.order_no, model.client_id, SubClient.parent_client_id, model.created_at,
                     model.customer_consultation_time, Client.client_name, Client.client_short_name, Client.client_code).outerjoin(
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
        if not start <= day <= end or not matches_keywords(' '.join([name, short, row.client_code or '']), client_keyword):
            continue
        fallback_count += int(fallback)
        selected.append(dict(day=day, client_key=key, client_name=name, client_short_name=short, finance={}))
    result = summarize(selected, first_dates, start, end, granularity, 'excl_tax')
    return dict(**result, module=module, generated_at=business_now().isoformat(), start=start.isoformat(), end=end.isoformat(),
                granularity=granularity, date_basis=date_basis, order_count=len(selected), fallback_date_orders=fallback_count, undated_orders=undated)


@router.get('/{module}')
def statistics(module: Literal['interpretation', 'annotation', 'recruitment'], start: date, end: date,
               granularity: Literal['day', 'week', 'month']='month', date_basis: Literal['order', 'reception']='order',
               client_keyword: str=Query('', max_length=255), db=Depends(get_db)):
    return report(db, module, start=start, end=end, granularity=granularity, date_basis=date_basis, client_keyword=client_keyword)
