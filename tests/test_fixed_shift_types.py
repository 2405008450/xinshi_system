"""新固定类型与多组打卡；全部使用隔离 SQLite。"""
from datetime import date
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload,sync
from test_attendance_clock import punch,out
import fixed_shift as fixed
import monthly_shift as monthly
import weekly_shift as weekly
import attendance_clock as clock
import attendance_service as attendance


def configure(db,users,code,monkeypatch):
    setup(db,users)
    from test_attendance import at
    monkeypatch.setattr(fixed,'now',lambda:at('2026-10-26T07:00'))
    return fixed.save_config(db,users[0],fixed.FixedWrite(revision=0,assignments=[{'user_id':users[1].id,'department':'customer','shift':code}]))


@pytest.mark.parametrize('code',['fixed_early_early','management','flexible'])
def test_fixed_only_types_hidden_from_roster_and_both_plan_views(environment,monkeypatch,code):
    db,users=environment
    configure(db,users,code,monkeypatch)
    assert str(users[1].id) not in {p['id'] for p in monthly.directory(db,users[0])['people']}
    plan=weekly.get_plan(db,users[0],'2026-10-26')
    assert plan['assignments']==[]
    assert monthly.get_plan(db,users[0],'2026-10')['assignments']==[]
    assert attendance.shift_for(db,users[1],date(2026,10,26))['code']==code
    with pytest.raises(ValidationError):monthly.Assignment(user_id=users[1].id,department='customer',shift=code)


def test_fixed_early_multiple_pairs_any_time_and_dinner_once(environment,monkeypatch):
    db,users=environment;configure(db,users,'fixed_early_early',monkeypatch);person=users[1]
    first=punch(db,person,monkeypatch,'2026-10-26T08:30')
    first=out(db,person,first,monkeypatch,'2026-10-26T09:00')
    assert first['dinner_deduction_minutes']==20 and first['late_count']==0
    assert clock.today_status(db,person)['next_segment']==1
    second=punch(db,person,monkeypatch,'2026-10-26T09:30',1)
    second=out(db,person,second,monkeypatch,'2026-10-26T10:00')
    assert second['dinner_deduction_minutes']==0 and second['raw_overtime_minutes']==0 and second['late_count']==0
    third=punch(db,person,monkeypatch,'2026-10-26T10:15',3)
    third=out(db,person,third,monkeypatch,'2026-10-26T11:00')
    assert third['late_count']==0 and third['dinner_deduction_minutes']==0
    fourth=punch(db,person,monkeypatch,'2026-10-26T15:00',4)
    fourth=out(db,person,fourth,monkeypatch,'2026-10-26T16:30')
    assert fourth['raw_overtime_minutes']==30 and fourth['late_count']==0
    assert clock.today_status(db,person)['can_check_in']
    assert clock.today_status(db,person)['next_segment']==5
    assert clock.monthly_balances(db,[person.id],date(2026,10,26),date(2026,10,26))[0]['overtime_minutes']==10


def test_fixed_early_existing_split_snapshot_can_continue_without_rewrite(environment,monkeypatch):
    db,users=environment;configure(db,users,'fixed_early_early',monkeypatch);person=users[1]
    from attendance_models import AttendanceClockSession as Clock
    from test_attendance import at
    original={'code':'fixed_early_early','label':'早早班（固定）','periods':['08:30–12:00'],'full_periods':['08:30–12:00','13:30–16:00'],'fixed':True,'clock_segments':2}
    row=Clock(user_id=person.id,day=date(2026,10,26),segment=0,check_in=at('2026-10-26T08:30'),check_out=at('2026-10-26T09:00'),shift_snapshot=original,confirmations={'breakfast_after_eating':True})
    db.add(row);db.commit();monkeypatch.setattr(clock,'now',lambda:at('2026-10-26T09:15'))
    status=clock.today_status(db,person)
    assert status['can_check_in'] and status['multiple_clock_sessions'] and status['next_segment']==1
    value=punch(db,person,monkeypatch,'2026-10-26T09:15',1)
    assert value['shift']['periods']==original['full_periods']
    db.refresh(row);assert row.shift_snapshot==original


def test_flexible_more_than_two_pairs_reserves_home_overtime_index(environment,monkeypatch):
    db,users=environment;configure(db,users,'flexible',monkeypatch);person=users[1]
    for index,(start,end) in zip([0,1,3,4],[('08:00','09:00'),('10:00','11:00'),('14:00','15:00'),('16:00','17:00')]):
        before=clock.today_status(db,person) if index else None
        if before:assert before['can_check_in'] and before['next_segment']==index
        record=punch(db,person,monkeypatch,'2026-10-26T'+start,index)
        with pytest.raises(HTTPException):punch(db,person,monkeypatch,'2026-10-26T'+start,5)
        record=out(db,person,record,monkeypatch,'2026-10-26T'+end,early_work_confirmed=None)
        assert record['late_minutes']==0 and record['raw_overtime_minutes']==0 and record['work_minutes']==60
        assert record['dinner_deduction_minutes']==(20 if index==0 else 0)
    assert clock.today_status(db,person)['can_check_in']
    with pytest.raises(HTTPException):punch(db,person,monkeypatch,'2026-10-26T18:00',2)
    assert attendance.shift_for(db,person,date(2026,10,31))['flexible']
    from chat_work_presence import work_presence
    from test_attendance import at
    presence=work_presence(db,[person],at('2026-10-26T14:30'))[str(person.id)]
    assert presence['work_state']=='unknown' and presence['working_now'] is None


def test_management_times_and_home_rotation_remains_movable_published(environment,monkeypatch):
    db,users=environment;configure(db,users,'management',monkeypatch)
    assert attendance.shift_for(db,users[1],date(2026,10,26))['periods']==['08:50–12:00','13:30–20:00']
    fixed.save_config(db,users[0],fixed.FixedWrite(revision=1,assignments=[{'user_id':users[1].id,'department':'customer','shift':'home_rotation'}]))
    saved=weekly.save_plan(db,users[0],'2026-10-26',weekly.WeeklyPlanWrite(revision=0,assignments=payload(users[1],shift='late').assignments))
    entry=saved['assignments'][0]
    assert entry['home_rotation'] and not entry['fixed'] and entry['shift']=='late'
    assert str(users[1].id) in {p['id'] for p in monthly.directory(db,users[0])['people']}
    sync(db,users[0],'2026-10-26')
    assert weekly.my_plan(db,users[1],'2026-10-26')['assignment']['home_rotation']
    logs=weekly.publication.history(db,users[0],'2026-10-26')['items']
    assert any(change['after'] and change['after'].get('home_rotation') for log in logs for change in log['changes'])
    shift=attendance.shift_for(db,users[1],date(2026,10,26));assert shift['home_office_day']
    first=punch(db,users[1],monkeypatch,'2026-10-26T10:30')
    with pytest.raises(HTTPException):out(db,users[1],first,monkeypatch,'2026-10-26T20:00')
    first=out(db,users[1],first,monkeypatch,'2026-10-26T20:00',deduct_invalid_time=True,invalid_minutes=10,invalid_reason='个人事务')
    assert first['dinner_deduction_minutes']==0 and first['invalid_deduction_minutes']==10
    weekly.save_plan(db,users[0],'2026-11-02',weekly.WeeklyPlanWrite(revision=0,assignments=payload(users[1],shift='early').assignments))
    moved=weekly.transfer_plan(db,users[0],weekly.WeekTransfer(source_week='2026-10-26',target_week='2026-11-09',operation='copy',source_revision=1,target_revision=0))
    assert moved['target']['assignments'][0]['home_rotation']
