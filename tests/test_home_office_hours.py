"""居家小时额度组合和当天任意时段两组打卡。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_home_office import office
from test_attendance import at
from test_attendance_clock import punch,out
import home_office_service as home
import attendance_clock as clock
import weekly_shift
from test_monthly_shift import payload,sync


def apply(db,user,day,minutes):return home.apply(db,user,home.ApplicationWrite(client_id=uuid4(),requested_date=day,minutes=minutes))


@pytest.mark.parametrize('lengths',[(120,120,240,480),(240,240,480)])
def test_allowed_month_patterns_equivalent_two_days_and_annual_usage(office,lengths):
 db,(admin,person,_)=office
 dates=['2026-11-02','2026-11-03','2026-11-04','2026-11-05']
 for day,minutes in zip(dates,lengths):apply(db,person,day,minutes)
 quota=home.quota(db,person,date(2026,11,5))
 assert quota['month_hours']==16 and quota['system_used_days']==2 and not quota['quota_available']
 with pytest.raises(HTTPException):apply(db,person,'2026-11-06',120)
 company=home.company(db,admin);assert next(row for row in company['usage_people'] if row['user_id']==str(person.id))['system_used_days']==2


def test_third_two_hour_and_second_eight_hour_not_allowed(office):
 db,(_,person,_)=office
 apply(db,person,'2026-11-02',120);apply(db,person,'2026-11-03',120)
 with pytest.raises(HTTPException):apply(db,person,'2026-11-04',120)
 apply(db,person,'2026-11-04',480)
 with pytest.raises(HTTPException):apply(db,person,'2026-11-05',480)
 assert home.quota(db,person,date(2026,11,5))['allowed_minutes']==[240]


@pytest.mark.parametrize('minutes',[120,240])
def test_partial_home_allows_two_groups_in_one_morning(office,monkeypatch,minutes):
 db,(admin,person,_)=office
 weekly_shift.save_plan(db,admin,'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments));sync(db,admin,'2026-10-26')
 apply(db,person,'2026-10-28',minutes)
 first=punch(db,person,monkeypatch,'2026-10-28T09:00')
 out(db,person,first,monkeypatch,'2026-10-28T10:00',deduct_invalid_time=False)
 second=punch(db,person,monkeypatch,'2026-10-28T10:30',1)
 assert second['late_minutes']==0
 out(db,person,second,monkeypatch,'2026-10-28T11:30',deduct_invalid_time=False)
 assert not clock.today_status(db,person)['can_check_in']
 with pytest.raises(HTTPException):punch(db,person,monkeypatch,'2026-10-28T11:45',3)
