from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect
from test_technical_development import environment, setup, payload
import technical_development as tasks
import technical_task_incentives as service


def task(db, owner, executor, name='开发任务'):
    return tasks.create_task(db, owner, payload(owner, executor, name, due_at='2026-10-30T12:00:00+08:00'))


def completed(db, owner, row, value, reason=''):
    state = db.get(service.TaskCompletion, row['id'])
    current = tasks.get_task(db, row['id'])
    return service.save_date(db, owner, row['id'], service.DateWrite(request_id=uuid4(), task_revision=current.revision, completion_revision=state.revision if state else 0, completed_on=value, reason=reason))


def amount(db, owner, value, number, reason=''):
    return service.save_amount(db, owner, value['task_id'], service.AmountWrite(request_id=uuid4(), completion_revision=value['completion_revision'], expected_latest_id=value['incentive']['id'] if value['incentive'] else None, amount=number, reason=reason))


def hr(db, user):
    user.department = '行政部'; db.commit(); return user


def test_on_time_calendar_date_and_idempotent_amount_history(setup):
    db, (owner, executor, _) = setup
    row = task(db, owner, executor)
    assert row['on_time'] is None and row['completed_on'] is None
    result = completed(db, owner, row, '2026-10-30')
    assert result['on_time'] is True and result['completion_revision'] == 1
    request = service.AmountWrite(request_id=uuid4(), completion_revision=1, amount='100.25')
    result = service.save_amount(db, owner, row['id'], request)
    assert result['incentive']['amount'] == '100.25' and result['incentive']['kind'] == 'reward'
    assert result['incentive']['executor_id'] == executor.id
    assert result['incentive']['created_at'].utcoffset().total_seconds() == 28800
    assert len(service.save_amount(db, owner, row['id'], request)['ledger_history']) == 1
    with pytest.raises(HTTPException): amount(db, owner, result, '120')
    updated = amount(db, owner, result, '120', '修正金额')
    assert len(updated['ledger_history']) == 2
    assert sum(record['effective'] for record in updated['ledger_history']) == 1
    with pytest.raises(HTTPException): amount(db, owner, result, '130', '旧版本')


def test_date_adjustments_reassess_and_exclude_old_money(setup):
    db, (owner, executor, administrator) = setup
    row = task(db, owner, executor)
    result = amount(db, owner, completed(db, owner, row, '2026-10-29'), '100')
    admin = hr(db, administrator)
    assert service.statistics(db, admin)['totals']['reward_total'] == '100.00'
    with pytest.raises(HTTPException): completed(db, owner, row, '2026-10-31')
    result = completed(db, owner, row, '2026-10-31', '实际完成日期录入错误')
    assert result['on_time'] is False and result['incentive'] is None
    assert result['changes'][0]['previous_date'] == date(2026,10,29)
    assert result['changes'][0]['author_id'] == owner.id
    assert not any(record['effective'] for record in result['ledger_history'])
    assert service.statistics(db, admin)['totals']['reward_total'] == '0.00'
    assert service.statistics(db, admin)['totals']['pending'] == 1
    result = amount(db, owner, result, '60')
    assert result['incentive']['kind'] == 'deduction'
    assert service.statistics(db, admin)['totals']['net_deduction'] == '60.00'
    result = completed(db, owner, row, None, '撤销误填完成日期')
    assert result['on_time'] is None and result['completed_on'] is None
    assert service.statistics(db, admin)['totals']['deduction_total'] == '0.00'


def test_offsets_are_per_executor_not_cross_person(setup):
    db, (owner, executor, administrator) = setup
    first = task(db, owner, executor, '奖励100')
    second = task(db, owner, executor, '抵消60')
    third = task(db, owner, owner, '另一人抵消80')
    amount(db, owner, completed(db, owner, first, '2026-10-30'), '100')
    amount(db, owner, completed(db, owner, second, '2026-10-31'), '60')
    amount(db, owner, completed(db, owner, third, '2026-10-31'), '80')
    stats = service.statistics(db, hr(db, administrator))
    assert stats['totals'] == dict(reward_total='100.00',deduction_total='140.00',offset_total='60.00',net_reward='40.00',net_deduction='80.00',pending=0)
    assert len(stats['people']) == 2 and len(stats['tasks']) == 3


def test_deadline_and_executor_changes_invalidate_assessment_and_are_audited(setup):
    db, (owner, executor, _) = setup
    row = task(db, owner, executor)
    amount(db, owner, completed(db, owner, row, '2026-10-30'), '100')
    fields = payload(owner, executor, due_at='2026-10-29T18:00:00+08:00').model_dump(exclude={'parent_id'})
    changed = tasks.update_task(db, owner, row['id'], tasks.TaskUpdate(**fields, revision=1))
    assert changed['on_time'] is False and changed['completion_revision'] == 2 and changed['incentive'] is None
    fields['executor_id'] = owner.id
    changed = tasks.update_task(db, owner, row['id'], tasks.TaskUpdate(**fields, revision=2))
    assert changed['completion_revision'] == 3
    history = service.read(db, owner, row['id'])
    assert history['changes'][0]['previous_executor_id'] == executor.id
    assert history['ledger_history'][0]['executor_id'] == executor.id and not history['ledger_history'][0]['effective']


def test_permissions_stale_versions_missing_deadline_and_migration(setup):
    db, (owner, executor, outsider) = setup
    row = tasks.create_task(db, owner, payload(owner, executor))
    with pytest.raises(HTTPException): completed(db, owner, row, '2026-10-30')
    row = task(db, owner, executor)
    with pytest.raises(HTTPException): service.read(db, outsider, row['id'])
    with pytest.raises(HTTPException): service.statistics(db, owner)
    result = completed(db, owner, row, '2026-10-30')
    with pytest.raises(HTTPException): service.save_date(db, owner, row['id'], service.DateWrite(request_id=uuid4(),task_revision=1,completion_revision=0,completed_on='2026-10-31',reason='旧版本'))
    from tools.apply_technical_incentives_migration import apply_migration
    for table in reversed(service.TABLES): table.drop(db.connection())
    db.commit()
    apply_migration(db.connection()); apply_migration(db.connection()); db.commit()
    assert all(inspect(db.connection()).has_table(table.name) for table in service.TABLES)
    assert tasks.get_task(db, row['id']).name == row['name']


@pytest.mark.parametrize('number',['-1','1.234','NaN','Infinity','1000000000000'])
def test_decimal_amount_validation(number):
    with pytest.raises(ValidationError): service.AmountWrite(request_id=uuid4(),completion_revision=1,amount=number)
