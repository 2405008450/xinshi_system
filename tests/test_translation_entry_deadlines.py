"""录入期限边界、工作日顺延及首次逾期留痕；仅使用隔离 SQLite。"""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import translation_entry_deadlines as deadlines
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case


def calendar_db(leaves=()):
    query = SimpleNamespace(all=lambda: leaves)
    query.filter = lambda *_: query
    return SimpleNamespace(query=lambda *_: query)


@pytest.mark.parametrize('files,words,days', [
    (10, 50_000, 2), (11, 50_000, 2), (11, 50_001, 4),
    (50, 100_000, 4), (51, 100_000, 2), (51, 100_001, 6),
])
def test_deadline_thresholds(monkeypatch, files, words, days):
    monkeypatch.setattr(deadlines, 'is_workday', lambda day: day.weekday() < 5)
    result = deadlines.deadline(calendar_db(), date(2026, 11, 13), 'manager', files, words)
    assert result == {'workdays': days, 'due_on': {
        2: date(2026, 11, 17), 4: date(2026, 11, 19), 6: date(2026, 11, 23),
    }[days]}


def test_weekend_holiday_and_partial_day_leave_extend_deadline(monkeypatch):
    holiday = date(2026, 11, 17)
    monkeypatch.setattr(deadlines, 'is_workday', lambda day: day.weekday() < 5 and day != holiday)
    leaves = [(datetime(2026, 11, 16, 13), datetime(2026, 11, 16, 18))]
    assert deadlines.deadline(calendar_db(leaves), date(2026, 11, 13), 'manager', 1, 100)['due_on'] == date(2026, 11, 19)


def test_first_overdue_is_recorded_once_with_business_timezone(case, monkeypatch):
    from project_client_manager import ProjectClientManagerChange
    from schemas import TranslationProjectCreate
    from translation_document_requirements import TranslationProjectDocuments
    from word_count_models import WordCountMetric

    db, actor, crud = case
    root = crud.create_translation_project(db, TranslationProjectCreate(
        project_name='期限测试', created_by=actor.id,
        customer_reception_time='2026-11-02T09:00:00+08:00',
        initial_sub_order_names=['待填写.pdf'],
        word_count_matrix={'company': {'documents': 1}, 'preliminary': {'words': 100}},
    ), order_no='TP-261102-991')
    manager = db.query(ProjectClientManagerChange).filter_by(project_type='translation', project_id=root.id).first()
    if manager is None:
        manager = ProjectClientManagerChange(project_type='translation', project_id=root.id,
            revision=1, actor_user_id=actor.id, actor_name=actor.full_name, reason='隔离测试')
        db.add(manager)
    manager.new_manager_id = actor.id
    for child in root.sub_orders:
        db.query(WordCountMetric).filter_by(sub_order_id=child.id).delete()
    db.commit()
    moment = datetime(2026, 11, 6, 9, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(deadlines, 'business_now', lambda: moment)
    monkeypatch.setattr(deadlines, 'is_workday', lambda day: day.weekday() < 5)

    first = deadlines.project_status(db, root.id)
    assert first['due_on'] == date(2026, 11, 4)
    assert first['overdue'] == {'word_count': True, 'unit_price': True}
    assert set(first['first_overdue']) == {'word_count', 'unit_price'}
    assert all(row['recorded_at'] == moment.isoformat() for row in first['first_overdue'].values())
    db.commit()
    monkeypatch.setattr(deadlines, 'business_now', lambda: moment + timedelta(days=3))
    again = deadlines.project_status(db, root.id)
    assert again['first_overdue'] == first['first_overdue']
    stored = db.get(TranslationProjectDocuments, root.id).quotation_data['_entry_deadline_overdue']
    assert stored == first['first_overdue']
