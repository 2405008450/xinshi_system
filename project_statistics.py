"""口译、标注、招聘的新老客户统计；只读，按各模块完整历史判断首次下单。"""
from datetime import date, timedelta
from typing import Literal
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from database import get_db
from models import Client, SubClient, TranslationProject
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from annotation_progress_time import business_datetime, business_now
from routers.auth import require_module_access
from search_matching import matches_keywords
from translation_statistics import summarize, period_bounds, percentage

MODELS = {'translation':(TranslationProject,'TP'),'interpretation': (InterpretationProject, 'IP'), 'annotation': (AnnotationProject, 'AP'), 'recruitment': (RecruitmentProject, 'HP')}
INTERPRETATION_STATUSES = {
    'initial_follow_up':'初步跟进中','client_contract_signed':'客户合同签署','interpreter_contract_signed':'译员合同签署','both_contracts_signed':'客户+译员合同签署','client_interpreter_connected':'客户与译员对接', 'deal_pending_execution':'已成交待执行',
    'candidates_provided':'已提供人选','candidates_added':'人选增加','candidates_adjusted':'人选调整','client_selected':'客户已定人选','client_changed':'客户改变人选','client_cancelled':'客户取消人选','client_added':'客户增加人选','client_reduced':'客户减少人数','client_mixed':'客户增减人选',
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


def report(db, module, *, start, end, granularity='month', date_basis='order', client_keyword='', all_dates=False, merge_deal_statuses=False,tax_basis='excl_tax'):
    if module not in MODELS or granularity not in ('day', 'week', 'month', 'quarter', 'all') or date_basis not in ('order', 'reception'):
        raise HTTPException(422, '无效的统计条件')
    if not all_dates and (start > end or (end-start).days > 1095):
        raise HTTPException(422, '请选择不超过三年的有效日期范围')
    model, prefix = MODELS[module]
    query = db.query(model.id, model.project_name, model.order_no, model.client_id, SubClient.parent_client_id, model.created_at,
                     getattr(model,'customer_reception_time' if module=='translation' else 'customer_consultation_time').label('customer_consultation_time'), Client.client_name, Client.client_short_name, Client.client_code, model.project_status).outerjoin(
        SubClient, model.sub_client_id == SubClient.id).outerjoin(Client, func.coalesce(model.client_id, SubClient.parent_client_id) == Client.id)
    if module=='translation':query=query.filter(model.annotation_migrated_at.is_(None))
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
        selected.append(dict(id=str(row.id),project_name=row.project_name or '',order_no=row.order_no,day=day, client_key=key, client_name=name, client_short_name=short, finance={},status=str(row.project_status or '').strip()))
    if all_dates:
        start = min((item['day'] for item in selected), default=business_now().date())
        end = max((item['day'] for item in selected), default=start)
    bounds = lambda day:project_period_bounds(day,granularity,start,end)
    from client_cohort import snapshots
    states=snapshots(db,start=None if all_dates else start,end=end,date_basis=date_basis)
    first_dates={key:date.fromisoformat(row['first_order_date']) for key,row in states.items() if row['first_order_date']}
    from project_statistics_finance import attach_finance,attach_order_details
    attach_finance(db,module,selected)
    for item in selected:
        item['cohort']=states.get(item['client_key'],{}).get('cohort','unknown')
        if 'incomplete_'+tax_basis in item:item['incomplete']=item['incomplete_'+tax_basis]
    result = summarize(selected, first_dates, start, end, granularity, tax_basis,period_bounds_fn=bounds)
    attach_order_details(result,selected,bounds,tax_basis)
    if True:
        if module=='interpretation':labels=dict(INTERPRETATION_STATUSES)
        elif module=='annotation':
            from annotation_schemas import ANNOTATION_PROJECT_STATUS_LABELS
            labels=dict(ANNOTATION_PROJECT_STATUS_LABELS)
        elif module=='recruitment':
            from recruitment_schemas import PROJECT_STATUSES
            labels=dict(PROJECT_STATUSES)
        else:
            from translation_project_export_service import STATUS_LABELS
            labels=dict(STATUS_LABELS)
        labels.setdefault('','（空白）')
        merge_deal_statuses=bool(module=='interpretation' and merge_deal_statuses)
        if merge_deal_statuses:
            labels = {key:label for key,label in labels.items() if key not in DEAL_STATUSES}
            labels = {'deal_merged':'已成交项目（合并）', **labels}
        for item in selected:
            key = 'deal_merged' if merge_deal_statuses and item['status'] in DEAL_STATUSES else item['status']
            item['status_key'] = key
            labels.setdefault(key, f'其他状态（{key}）')
        indexed = {row['period_start']:row for row in result['periods']}
        deal_keys=[key for key in INTERPRETATION_STATUSES if key in DEAL_STATUSES]
        for row in indexed.values():
            row['status_counts'] = {key:{'count':0,'share':0} for key in labels}
            row['deal_status_counts']={key:{'label':INTERPRETATION_STATUSES[key],'count':0,'share':0} for key in deal_keys}
        for item in selected:
            row=indexed[bounds(item['day'])[0].isoformat()]
            row['status_counts'][item['status_key']]['count'] += 1
            if item['status'] in DEAL_STATUSES:row['deal_status_counts'][item['status']]['count']+=1
        for row in indexed.values():
            for item in row['status_counts'].values():item['share'] = percentage(item['count'],row['order_count'])
            for item in row['deal_status_counts'].values():item['share'] = percentage(item['count'],row['order_count'])
        result['status_columns'] = [{'key':key,'label':label} for key,label in labels.items()]
        result['status_totals']={key:{'count':sum(row['status_counts'][key]['count'] for row in indexed.values())} for key in labels}
        result['deal_status_totals']={key:{'label':INTERPRETATION_STATUSES[key],'count':sum(row['deal_status_counts'][key]['count'] for row in indexed.values())} for key in deal_keys}
        for values in [result['status_totals'],result['deal_status_totals']]:
            for item in values.values():item['share']=percentage(item['count'],len(selected))
        if module=='interpretation':
            # 未成交原因仅来自明确取消项目的状态说明，不把仍在跟进的项目当作失败。
            cancelled=[item for item in selected if item['status'] in {'cancelled','partially_cancelled'}]
            from interpretation_models import InterpretationProjectStatusHistory
            from uuid import UUID
            latest={}
            if cancelled:
                statuses={item['id']:item['status'] for item in cancelled}
                events=db.query(InterpretationProjectStatusHistory).filter(InterpretationProjectStatusHistory.project_id.in_([UUID(key) for key in statuses])).order_by(InterpretationProjectStatusHistory.changed_at.desc(),InterpretationProjectStatusHistory.effective_on.desc(),InterpretationProjectStatusHistory.id.desc())
                for event in events:
                    key=str(event.project_id)
                    if key not in latest and event.to_status==statuses[key]:latest[key]=event
            result['unconverted_projects']=[dict(id=item['id'],order_no=item['order_no'],project_name=item['project_name'],client_name=item['client_name'],client_short_name=item['client_short_name'],status=item['status'],status_label=INTERPRETATION_STATUSES[item['status']],order_date=item['day'].isoformat(),reason=(latest[item['id']].change_note or '').strip() if item['id'] in latest else '',reason_at=business_datetime(latest[item['id']].changed_at).isoformat() if item['id'] in latest and latest[item['id']].changed_at else None) for item in sorted(cancelled,key=lambda item:(item['day'],item['order_no']),reverse=True)]
        if module=='interpretation' and result.get('unconverted_projects'):
            from interpretation_partial_cancellation import InterpretationCancellationClassification
            from sqlalchemy import inspect
            if inspect(db.connection()).has_table(InterpretationCancellationClassification.__tablename__):
                classifications=db.query(InterpretationCancellationClassification).filter(InterpretationCancellationClassification.project_id.in_([UUID(item['id']) for item in result['unconverted_projects']])).order_by(InterpretationCancellationClassification.created_at.desc()).all()
                lookup={}
                for value in classifications:lookup.setdefault((str(value.project_id),value.project_status),value)
                for item in result['unconverted_projects']:
                    value=lookup.get((item['id'],item['status']))
                    item['classification_paths']=(value.details or {}).get('reason_paths',[]) if value else []
                    item['classification_needs_review']=(value.details or {}).get('needs_review',False) if value else False
                    item['original_reason']=value.original_note if value else item['reason']
                    item['classification_id']=str(value.id) if value else None
                    item['classification_details']=value.details if value else None
        if module=='recruitment':
            from recruitment_models import RecruitmentProjectProgress
            from uuid import UUID
            cancelled=[item for item in selected if item['status']=='cancelled']
            events=db.query(RecruitmentProjectProgress).filter(RecruitmentProjectProgress.project_id.in_([UUID(item['id']) for item in cancelled]),RecruitmentProjectProgress.to_status=='cancelled').order_by(RecruitmentProjectProgress.occurred_at.desc(),RecruitmentProjectProgress.id.desc()) if cancelled else []
            latest={}
            for event in events:latest.setdefault(str(event.project_id),event)
            result['unconverted_projects']=[dict(id=item['id'],order_no=item['order_no'],project_name=item['project_name'],client_name=item['client_name'],client_short_name=item['client_short_name'],status=item['status'],status_label=labels['cancelled'],reason=latest[item['id']].note if item['id'] in latest and not latest[item['id']].is_system else '',reason_at=business_datetime(latest[item['id']].occurred_at).isoformat() if item['id'] in latest else None) for item in cancelled]
    clients_by_project={item['id']:item for item in selected}
    for item in result.get('unconverted_projects',[]):item['client_id']=clients_by_project[item['id']]['client_key']
    return dict(**result, module=module, generated_at=business_now().isoformat(), start=start.isoformat(), end=end.isoformat(),
                granularity=granularity, date_basis=date_basis, all_dates=all_dates, merge_deal_statuses=merge_deal_statuses,
                order_count=len(selected), fallback_date_orders=fallback_count, undated_orders=undated)


@router.get('/{module}')
def statistics(module: Literal['translation','interpretation', 'annotation', 'recruitment'], start: date, end: date,
               granularity: Literal['day', 'week', 'month', 'quarter', 'all']='month', date_basis: Literal['order', 'reception']='order',
               tax_basis:Literal['excl_tax','incl_tax']='excl_tax',client_keyword: str=Query('', max_length=255), all_dates: bool=False, merge_deal_statuses: bool=False, db=Depends(get_db)):
    return report(db, module, start=start, end=end, granularity=granularity, date_basis=date_basis, client_keyword=client_keyword,
                  all_dates=all_dates, merge_deal_statuses=merge_deal_statuses,tax_basis=tax_basis)
