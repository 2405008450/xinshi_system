"""固定人员配置、跨周期生效和历史保护，使用隔离数据库。"""
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload
import fixed_shift as fixed
import monthly_shift as monthly
import weekly_shift as weekly


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(fixed,'now',lambda:datetime(2026,10,25,12,tzinfo=timezone(timedelta(hours=8))))


def test_fixed_current_future_history_and_personal_view(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    weekly.save_plan(db,admin,'2026-10-12',weekly.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments))
    monthly.save_plan(db,admin,'2026-09',payload(person))
    fixed.save_config(db,admin,payload(person,shift='late'))
    for week in ['2026-10-19','2026-10-26','2027-01-04']:
        entry=weekly.get_plan(db,admin,week)['assignments'][0]
        assert entry['shift']=='late' and entry['fixed']
        assert weekly.my_plan(db,person,week)['assignment']['shift']=='late'
        assert weekly.my_plan(db,other,week)['assignment'] is None
    assert weekly.get_plan(db,admin,'2026-10-12')['assignments'][0]['shift']=='early'
    assert monthly.get_plan(db,admin,'2026-09')['assignments'][0]['shift']=='early'
    for month in ['2026-10','2026-11']:
        assert monthly.get_plan(db,admin,month)['assignments'][0]['fixed']
        assert monthly.my_plan(db,person,month)['assignment']['shift']=='late'
    # 即使过时的客户端尝试挪动或移除，服务端仍强制使用当前固定位置。
    value=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments))
    assert value['assignments'][0]['shift']=='late'
    value=monthly.save_plan(db,admin,'2026-11',monthly.PlanWrite(revision=0,assignments=[]))
    assert value['assignments'][0]['shift']=='late'
    fixed.save_config(db,admin,monthly.PlanWrite(revision=1,assignments=[]))
    assert weekly.get_plan(db,admin,'2027-01-04')['assignments']==[]
    assert weekly.get_plan(db,admin,'2026-10-26')['assignments'][0]['shift']=='late'
    assert 'fixed' not in weekly.get_plan(db,admin,'2026-10-26')['assignments'][0]


def test_permissions_conflict_inactive_and_migration(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    with pytest.raises(HTTPException) as error:fixed.get_config(db,person)
    assert error.value.status_code==403
    with pytest.raises(HTTPException):fixed.save_config(db,other,payload(person))
    fixed.save_config(db,admin,payload(person))
    with pytest.raises(HTTPException) as error:fixed.save_config(db,admin,payload(person))
    assert error.value.status_code==409
    person.is_active=False;db.commit()
    assert fixed.effective(db,[],datetime(2026,11,1).date())==[]
    with pytest.raises(HTTPException):fixed.save_config(db,admin,payload(person,revision=1))
    from tools.apply_fixed_shift_migration import apply_migration
    apply_migration(db.connection());apply_migration(db.connection())
    assert fixed.get_config(db,admin)['revision']==1


def test_automatic_fixed_history_survives_next_week_and_reconfiguration(environment,monkeypatch):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    fixed.save_config(db,admin,payload(person,shift='early'))
    monkeypatch.setattr(fixed,'now',lambda:datetime(2026,11,2,12,tzinfo=timezone(timedelta(hours=8))))
    # 即便该周期没有手动保存，自动班次仍留在历史周/月。
    assert weekly.get_plan(db,admin,'2026-10-19')['assignments'][0]['shift']=='early'
    assert monthly.get_plan(db,admin,'2026-10')['assignments'][0]['shift']=='early'
    fixed.save_config(db,admin,payload(person,revision=1,shift='late'))
    assert weekly.get_plan(db,admin,'2026-10-19')['assignments'][0]['shift']=='early'
    assert monthly.get_plan(db,admin,'2026-10')['assignments'][0]['shift']=='early'
    assert weekly.get_plan(db,admin,'2026-11-02')['assignments'][0]['shift']=='late'


def test_fixed_dialog_includes_people_outside_schedule_groups(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    other.department='财务部';db.commit()
    assert any(row['id']==str(other.id) for row in fixed.get_config(db,admin)['people'])
    fixed.save_config(db,admin,payload(other,department='administration'))
    saved=weekly.save_plan(db,admin,'2026-10-26',weekly.WeeklyPlanWrite(revision=0,assignments=[]))
    assert saved['assignments'][0]['user_id']==str(other.id)
