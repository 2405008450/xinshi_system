"""聊天工作状态复用排班，所有数据仅使用隔离 SQLite。"""
from datetime import date, datetime
import pytest
from test_chat_participant_access import environment
from chat_time import BUSINESS_TIMEZONE
from monthly_shift import MonthlyShiftPlan
from weekly_shift import WeeklyShiftPlan
from fixed_shift import FixedShiftConfig
from weekend_duty import WeekendDutyPlan
from chat_work_presence import work_presence


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=BUSINESS_TIMEZONE)


def arrange(db, person, shift='early', department='project'):
    db.add(MonthlyShiftPlan(month=date(2026,10,1), assignments=[dict(user_id=str(person.id),department=department,shift=shift)],revision=1,updated_by=person.id))
    db.commit()


@pytest.mark.parametrize('clock,state', [('08:59:59','off_hours'),('09:00:00','working'),('11:59:59','working'),('12:00:00','off_hours'),('13:29:59','off_hours'),('13:30:00','working'),('18:29:59','working'),('18:30:00','off_hours')])
def test_shift_boundaries_and_lunch(environment,clock,state):
    db,(_,person,_)=environment
    arrange(db,person)
    value=work_presence(db,[person],at('2026-10-28T'+clock))[str(person.id)]
    assert value['work_state']==state
    assert value['working_now']==(state=='working')
    assert value['shift_label']=='早班'


def test_weekly_overrides_monthly_and_fixed_overrides_weekly(environment):
    db,(_,person,_)=environment
    arrange(db,person)
    db.add(WeeklyShiftPlan(week_start=date(2026,10,26),assignments=[dict(user_id=str(person.id),department='customer',shift='customer_remote')],revision=1,updated_by=person.id));db.commit()
    assert work_presence(db,[person],at('2026-10-28T21:30'))[str(person.id)]['work_state']=='working'
    assert work_presence(db,[person],at('2026-10-28T19:00'))[str(person.id)]['work_state']=='off_hours'
    entry=dict(user_id=str(person.id),department='project',shift='early_early')
    db.add(FixedShiftConfig(id=1,assignments={'versions':[{'week_start':'2026-10-26','month_start':'2026-10-01','assignments':[entry]}]},revision=1,updated_by=person.id));db.commit()
    value=work_presence(db,[person],at('2026-10-28T08:30'))[str(person.id)]
    assert value['work_state']=='working' and value['shift_label']=='早早班'


def test_weekend_duty_holiday_missing_schedule_and_timezone(environment):
    db,(_,person,other)=environment
    arrange(db,person)
    assert work_presence(db,[person],at('2026-10-31T10:00'))[str(person.id)]['work_state']=='off_hours'
    db.add(WeekendDutyPlan(month=date(2026,10,1),assignments=[{'user_id':str(person.id),'date':'2026-10-31'}],revision=1,updated_by=person.id));db.commit()
    assert work_presence(db,[person],at('2026-10-31T10:00'))[str(person.id)]['work_state']=='working'
    assert work_presence(db,[person],at('2026-10-01T10:00'))[str(person.id)]['work_state']=='off_hours'
    result=work_presence(db,[person,other],datetime.fromisoformat('2026-10-28T01:00:00+00:00'))
    assert result[str(person.id)]['work_state']=='working'
    assert result[str(other.id)]['work_state']=='unscheduled'
    assert result[str(other.id)]['working_now'] is None


def test_cross_midnight_shift_and_unknown_calendar(environment,monkeypatch):
    db,(_,person,_)=environment
    import chat_work_presence as module
    night={'label':'夜班','periods':['22:00–02:00']}
    monkeypatch.setattr(module,'shifts_for',lambda db,users,day:{str(person.id):night} if day==date(2026,10,27) else {})
    assert work_presence(db,[person],at('2026-10-28T01:00'))[str(person.id)]['working_now'] is True
    assert work_presence(db,[person],at('2026-10-28T02:00'))[str(person.id)]['working_now'] is None
    assert work_presence(db,[person],at('2030-01-01T10:00'))[str(person.id)]['work_state']=='unknown'
