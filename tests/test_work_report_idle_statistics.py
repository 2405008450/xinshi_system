"""空闲统计跨周跨月、权限、分页和历史缺失数据，仅使用隔离 SQLite。"""
from datetime import date, datetime
from uuid import uuid4

from task_models import DailyReport, DailyReportItem
from task_schemas import DailyReportSaveRequest
from test_chat_participant_access import environment
from work_report_idle import save_declaration
from work_report_idle_statistics import statistics
import work_report_access as access


def add_report(db, person, day, minutes, status='finalized', lunch=False):
    row = DailyReport(id=uuid4(), user_id=person.id, report_date=day, status=status,
                      generated_at=datetime(2026,11,1,12), finalized_at=datetime(2026,11,1,12))
    row.items = [DailyReportItem(id=uuid4(), source_type='manual', task_type='非项目工作',
                                task_name='', progress_content='工作记录', duration_minutes=60,
                                sort_order=0, display_metadata={'lunch_overtime': lunch})]
    if minutes is not None:
        save_declaration(row, DailyReportSaveRequest(idle_minutes=minutes, idle_declaration_confirmed=True))
    db.add(row)
    return row


def test_idle_totals_are_permission_scoped_unpaginated_and_live(environment):
    db, (owner, viewer, other) = environment
    owner.username = 'williamzhao'
    db.commit()
    access.save_rule(db, owner, access.AccessRuleWrite(
        name='空闲统计测试', viewer_ids=[viewer.id], sender_ids=[owner.id, other.id],
    ))
    add_report(db, owner, date(2026,10,26), 60)
    high = add_report(db, owner, date(2026,10,31), 61, lunch=True)
    add_report(db, owner, date(2026,11,1), 0)
    add_report(db, owner, date(2026,11,2), 90)
    add_report(db, owner, date(2026,10,30), None)
    add_report(db, owner, date(2026,10,29), 600, status='draft')
    add_report(db, other, date(2026,11,1), 30)
    add_report(db, viewer, date(2026,10,31), 900)
    db.commit()

    result = access.received_reports(db, viewer, date(2026,10,31), date(2026,10,31), None, 1, 1)
    assert result['total'] == 1 and result['idle_over_limit_count'] == 1
    item = result['items'][0]
    assert item['idle_minutes'] == 61 and item['has_lunch_work']
    assert item['week_idle_minutes'] == 121 and item['month_idle_minutes'] == 121
    assert item['week_date_from'] == date(2026,10,26) and item['week_date_to'] == date(2026,11,1)
    assert item['month_date_from'] == date(2026,10,1) and item['month_date_to'] == date(2026,10,31)
    week = statistics(db, viewer, date(2026,11,1), 'week', page_size=1)
    assert week['total'] == 2 and len(week['items']) == 1
    both = week['items'] + statistics(db, viewer, date(2026,11,1), 'week', page=2, page_size=1)['items']
    person = next(row for row in both if row['id'] == str(owner.id))
    assert person['idle_minutes'] == 121 and person['over_limit_days'] == 1
    assert person['report_count'] == 4 and person['declared_count'] == 3 and person['missing_idle_count'] == 1
    month = statistics(db, viewer, date(2026,11,1), 'month', sender_id=owner.id)
    assert month['items'][0]['idle_minutes'] == 90 and month['items'][0]['over_limit_days'] == 1
    day = statistics(db, viewer, date(2026,10,30), 'day', sender_id=owner.id)['items'][0]
    assert day['idle_minutes'] is None and day['missing_idle_count'] == 1
    assert statistics(db, viewer, date(2026,10,31), 'day', sender_id=viewer.id)['total'] == 0
    limit = statistics(db, viewer, date(2026,10,26), 'day', sender_id=owner.id)['items'][0]
    assert limit['idle_minutes'] == 60 and limit['over_limit_days'] == 0
    high.idle_declaration.idle_minutes = 10
    db.commit()
    revised = access.received_reports(db, viewer, date(2026,10,31), date(2026,10,31), None, 1, 1)
    assert revised['items'][0]['week_idle_minutes'] == 70 and revised['idle_over_limit_count'] == 0
    assert statistics(db, viewer, date(2026,10,31), 'week', sender_id=owner.id)['items'][0]['idle_minutes'] == 70


def test_unfilled_and_zero_remain_different_and_totals_ignore_page_size(environment):
    db, (owner, viewer, other) = environment
    owner.username = 'williamzhao'
    db.commit()
    access.save_rule(db, owner, access.AccessRuleWrite(name='只看一人', viewer_ids=[viewer.id], sender_ids=[other.id]))
    add_report(db, other, date(2026,11,1), None)
    add_report(db, other, date(2026,11,2), 0)
    add_report(db, other, date(2026,11,3), 61)
    db.commit()
    records = access.received_reports(db, viewer, None, None, None, 1, 1)
    assert records['total'] == 3 and records['idle_over_limit_count'] == 1
    assert records['items'][0]['month_idle_minutes'] == 61
    missing = access.received_reports(db, viewer, date(2026,11,1), date(2026,11,1), None, 1, 20)['items'][0]
    assert missing['idle_minutes'] is None and missing['week_idle_minutes'] is None
    zero = statistics(db, viewer, date(2026,11,2), 'day')['items'][0]
    assert zero['idle_minutes'] == 0 and zero['declared_count'] == 1
    empty = statistics(db, viewer, date(2026,11,4), 'day')['items'][0]
    assert empty['idle_minutes'] is None and empty['report_count'] == 0
