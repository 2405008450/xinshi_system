"""已确认工作报告的空闲时间实时汇总，沿用报告查看权限。"""
from collections import defaultdict

from sqlalchemy import case, func
from sqlalchemy.orm import joinedload

from task_models import DailyReport, DailyReportIdleDeclaration
from models import AppUser
from work_report_calendar import period_bounds

IDLE_WARNING_MINUTES = 60


def declared_minutes(declaration):
    return declaration.idle_minutes if declaration and declaration.confirmed else None


def totals_for_reports(db, reports):
    """一次读取当前页涉及的自然周、自然月，汇总不受列表分页限制。"""
    if not reports:
        return {}
    starts, ends = [], []
    for report in reports:
        for period in ('week', 'month'):
            start, end = period_bounds(report.report_date, period)
            starts.append(start)
            ends.append(end)
    records = db.query(DailyReport.user_id, DailyReport.report_date, DailyReportIdleDeclaration.idle_minutes).join(
        DailyReportIdleDeclaration, DailyReportIdleDeclaration.report_id == DailyReport.id
    ).filter(
        DailyReport.user_id.in_({report.user_id for report in reports}),
        DailyReport.status == 'finalized', DailyReportIdleDeclaration.confirmed.is_(True),
        DailyReport.report_date >= min(starts), DailyReport.report_date <= max(ends),
    ).all()
    totals = defaultdict(int)
    for user_id, day, minutes in records:
        for period in ('week', 'month'):
            start, _ = period_bounds(day, period)
            totals[user_id, period, start] += minutes
    result = {}
    for report in reports:
        entry = {}
        for period in ('week', 'month'):
            start, end = period_bounds(report.report_date, period)
            key = report.user_id, period, start
            entry[period + '_idle_minutes'] = totals.get(key)
            entry[period + '_date_from'] = start
            entry[period + '_date_to'] = end
        result[report.id] = entry
    return result


def statistics(db, user, anchor, period, department_id=None, keyword=None, sender_id=None, page=1, page_size=20):
    import work_report_access as access

    start, end = period_bounds(anchor, period)
    allowed = access.sender_ids_for_rules(db, access.receiving_rules(db, user))
    allowed = access.filter_people_ids(db, allowed, department_id, keyword)
    if sender_id:
        allowed.intersection_update({sender_id})
    has_idle = DailyReportIdleDeclaration.confirmed.is_(True)
    over_limit = has_idle & (DailyReportIdleDeclaration.idle_minutes > IDLE_WARNING_MINUTES)
    reports = db.query(
        DailyReport.user_id.label('user_id'),
        func.count(DailyReport.id).label('report_count'),
        func.sum(case((has_idle, 1), else_=0)).label('declared_count'),
        func.sum(case((has_idle, DailyReportIdleDeclaration.idle_minutes), else_=0)).label('idle_minutes'),
        func.sum(case((over_limit, 1), else_=0)).label('over_limit_days'),
    ).outerjoin(
        DailyReportIdleDeclaration, DailyReportIdleDeclaration.report_id == DailyReport.id
    ).filter(
        DailyReport.user_id.in_(allowed), DailyReport.status == 'finalized',
        DailyReport.report_date.between(start, end),
    ).group_by(DailyReport.user_id).subquery()
    query = db.query(
        AppUser.id, AppUser.full_name, AppUser.username, reports.c.report_count, reports.c.declared_count,
        reports.c.idle_minutes, reports.c.over_limit_days,
    ).outerjoin(reports, reports.c.user_id == AppUser.id).filter(AppUser.id.in_(allowed))
    total = query.count()
    selected = query.order_by(AppUser.full_name, AppUser.username, AppUser.id).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    ids = [row.id for row in selected]
    daily = defaultdict(list)
    for report in db.query(DailyReport).options(joinedload(DailyReport.idle_declaration)).filter(
        DailyReport.user_id.in_(ids), DailyReport.status == 'finalized',
        DailyReport.report_date.between(start, end),
    ).order_by(DailyReport.report_date).all():
        minutes = declared_minutes(report.idle_declaration)
        daily[report.user_id].append({
            'report_id': str(report.id), 'date': report.report_date, 'idle_minutes': minutes,
            'over_limit': minutes is not None and minutes > IDLE_WARNING_MINUTES,
        })
    return {
        'date_from': start, 'date_to': end, 'period': period, 'total': total,
        'items': [{
            'id': str(row.id), 'name': row.full_name or row.username,
            'idle_minutes': row.idle_minutes if row.declared_count else None,
            'report_count': row.report_count or 0, 'declared_count': row.declared_count or 0,
            'missing_idle_count': (row.report_count or 0) - (row.declared_count or 0),
            'over_limit_days': row.over_limit_days or 0, 'days': daily[row.id],
        } for row in selected],
        'basis': '按已确认报告实时汇总，周一至周日为一周，自然月为一月；未填写的历史空闲时间不按零计算。',
    }
