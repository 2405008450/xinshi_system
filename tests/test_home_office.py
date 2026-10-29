"""居家资格、自然周期限额、年度补录及通知原子性；仅隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_monthly_shift import setup
from test_attendance import at,request
from models import AppNotification
import employee_employment as employment
import home_office_service as service
import home_office_setup


@pytest.fixture
def office(environment,monkeypatch):
    db,users=environment;setup(db,users);admin,person,manager=users
    manager.full_name='赵震锋';db.commit();home_office_setup.configure(db);db.commit()
    monkeypatch.setattr(service,'now',lambda:at('2026-10-28T09:00'))
    employment.write(db,person,date(2025,1,1));db.commit()
    service.save_usage(db,admin,service.UsageWrite(user_id=person.id,year=2026,used_days=0,revision=0))
    return db,users


def seed(db,user,dates):
    for day in dates:db.add(service.Application(id=uuid4(),client_id=uuid4(),user_id=user.id,requested_date=date.fromisoformat(day),reason='',status='pending',created_at=at('2026-10-28T09:00')))
    db.commit()


def apply(db,user,day='2026-10-28',client_id=None):return service.apply(db,user,service.ApplicationWrite(client_id=client_id or uuid4(),requested_date=day))


@pytest.mark.parametrize('hire,limit',[('2026-04-01',6),('2026-04-12',6),('2026-04-13',5),('2026-04-15',5),('2026-01-01',9),('2025-01-01',12),('2026-11-01',0)])
def test_calendar_year_proration_20_day_boundary(hire,limit):
    assert service.annual_limit(date.fromisoformat(hire),2026)==limit


def test_qualification_three_six_months_and_required_reason(office,monkeypatch):
    db,(admin,person,manager)=office
    employment.write(db,person,date(2026,7,28));db.commit()
    assert service.eligibility(db,person,date(2026,10,27))['can_apply_qualification'] is False
    assert service.eligibility(db,person)['can_apply_qualification'] is True
    with pytest.raises(ValidationError):service.QualificationWrite(client_id=uuid4(),reason='  ')
    client=uuid4();payload=service.QualificationWrite(client_id=client,reason='通勤时间较长')
    result=service.apply_qualification(db,person,payload);assert result['qualification_pending'] and not result['qualified']
    notices=db.query(AppNotification).filter_by(notification_type='home_office_application').all()
    assert {row.recipient_user_id for row in notices}=={admin.id,manager.id}
    from schemas import NotificationResponse
    assert NotificationResponse.model_validate(notices[0]).model_dump(mode='json')['created_at'].endswith('+08:00')
    service.apply_qualification(db,person,payload);assert db.query(service.Qualification).count()==1 and db.query(AppNotification).filter_by(notification_type='home_office_application').count()==2
    with pytest.raises(HTTPException):apply(db,person)
    assert service.eligibility(db,person,date(2027,1,28))['automatic'] is True


def test_monthly_cap_idempotence_and_notifications(office):
    db,(admin,person,manager)=office;client=uuid4()
    first=apply(db,person,client_id=client);assert first['month_used']==1
    apply(db,person,client_id=client);assert db.query(service.Application).count()==1
    apply(db,person,'2026-10-29')
    with pytest.raises(HTTPException) as error:apply(db,person,'2026-10-30')
    assert '本月2次已满' in error.value.detail
    assert db.query(AppNotification).filter_by(notification_type='home_office_application').count()==4


@pytest.mark.parametrize('dates,target,messages',[
    (['2026-10-01','2026-10-02','2026-11-02','2026-11-03'],'2026-12-01',['本季度4天已满']),
    (['2026-07-01','2026-07-02','2026-08-03','2026-08-04','2026-10-01','2026-10-02','2026-11-02','2026-11-03'],'2026-12-01',['本季度4天已满','本半年8天已满']),
    (['2026-01-01','2026-01-02','2026-02-02','2026-02-03','2026-04-01','2026-04-02','2026-05-04','2026-05-05','2026-07-01','2026-07-02','2026-08-03','2026-08-04'],'2026-10-28',['年度额度12天已满']),
])
def test_quarter_half_and_annual_caps(office,dates,target,messages):
    db,(_,person,_)=office;seed(db,person,dates)
    with pytest.raises(HTTPException) as error:apply(db,person,target)
    for message in messages:assert message in error.value.detail


def test_manual_usage_reflected_to_person_company_and_limits(office):
    db,(admin,person,manager)=office
    service.save_usage(db,admin,service.UsageWrite(user_id=person.id,year=2026,used_days=11,revision=1,note='系统启用前累计'))
    assert service.overview(db,person)['manual_used_days']==11
    apply(db,person)
    assert service.overview(db,person)['annual_used']==12
    with pytest.raises(HTTPException):apply(db,person,'2026-10-29')
    company=service.company(db,admin);row=next(row for row in company['usage_people'] if row['user_id']==str(person.id))
    assert row['manual_used_days']==11 and row['system_used_days']==1 and len(row['history'])==2
    with pytest.raises(HTTPException):service.save_usage(db,admin,service.UsageWrite(user_id=person.id,year=2026,used_days=0,revision=0))
    with pytest.raises(HTTPException):service.save_usage(db,person,service.UsageWrite(user_id=person.id,year=2026,used_days=0,revision=2))
    with pytest.raises(HTTPException):service.company(db,person)


def test_no_baseline_is_not_assumed_zero_and_notify_failure_rolls_back(office,monkeypatch):
    db,(admin,person,manager)=office
    db.delete(db.get(service.AnnualUsage,(person.id,2026)));db.commit()
    assert not service.quota(db,person,date(2026,10,28))['manual_usage_ready']
    with pytest.raises(HTTPException):apply(db,person)
    service.save_usage(db,admin,service.UsageWrite(user_id=person.id,year=2026,used_days=0,revision=0))
    monkeypatch.setattr(service,'notify',lambda *a:(_ for _ in ()).throw(RuntimeError('通知失败')))
    with pytest.raises(RuntimeError):apply(db,person)
    assert db.query(service.Application).count()==0


def test_ordinary_home_day_checkout_requires_statement_and_invalid_time(office,monkeypatch):
    import attendance_clock,weekly_shift
    from test_monthly_shift import payload,sync
    db,(admin,person,manager)=office
    weekly_shift.save_plan(db,admin,'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments));sync(db,admin,'2026-10-26')
    apply(db,person)
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-28T08:00'))
    record=attendance_clock.check_in(db,person,request(),attendance_clock.CheckInWrite(breakfast_notice_accepted=True))['record']
    assert record['shift']['home_office_day'] and record['shift']['code']=='early'
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-28T19:30'))
    with pytest.raises(HTTPException):attendance_clock.check_out(db,person,request(),attendance_clock.CheckOutWrite(record_id=record['id'],early_work_confirmed=True,breakfast_after_eating=True))
    result=attendance_clock.check_out(db,person,request(),attendance_clock.CheckOutWrite(record_id=record['id'],early_work_confirmed=True,breakfast_after_eating=True,deduct_invalid_time=True,invalid_minutes=15,invalid_reason='处理私人事务'))
    assert result['record']['invalid_deduction_minutes']==15 and result['record']['overtime_minutes']==105


def test_setup_idempotent_preserves_other_memberships(office):
    from department_models import DepartmentMember
    db,(_,_,manager)=office;before=db.query(DepartmentMember).count()
    assert home_office_setup.configure(db)['changed'] is False
    db.commit();assert db.query(DepartmentMember).count()==before
    assert service.manager(db).id==manager.id


def test_create_tables_idempotent_without_touching_existing(office):
    from tools.apply_home_office_migration import apply_migration
    db,(_,person,_)=office;before=db.get(employment.EmployeeEmployment,person.id).hire_date
    for model in (service.Qualification,service.Application,service.AnnualUsage):model.__table__.drop(db.connection())
    db.commit();apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert db.get(employment.EmployeeEmployment,person.id).hire_date==before


def test_company_home_overtime_no_qualification_application_or_quota_consumption(office,monkeypatch):
    import attendance_clock
    db,(admin,person,manager)=office
    employment.write(db,person,date(2026,10,1));db.commit()
    service.save_usage(db,admin,service.UsageWrite(user_id=person.id,year=2026,used_days=12,revision=1))
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-31T09:00'))
    before=service.quota(db,person,date(2026,10,31))
    assert not service.eligibility(db,person)['qualified']
    record=attendance_clock.check_in(db,person,request(),attendance_clock.CheckInWrite(breakfast_notice_accepted=True,work_mode='company_home_overtime'))['record']
    assert record['shift']['overtime_only'] and record['segment']==2
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-31T11:00'))
    result=attendance_clock.check_out(db,person,request(),attendance_clock.CheckOutWrite(record_id=record['id'],breakfast_after_eating=True,deduct_invalid_time=True,invalid_minutes=15,invalid_reason='个人事务'))
    assert result['record']['overtime_minutes']==105
    assert db.query(service.Application).count()==0
    assert service.quota(db,person,date(2026,10,31))==before
    assert attendance_clock.today_status(db,person)['can_home_overtime_check_in'] is False


def test_company_overtime_never_overlaps_open_normal_shift(office,monkeypatch):
    import attendance_clock,weekly_shift
    from test_monthly_shift import payload,sync
    db,(admin,person,manager)=office
    weekly_shift.save_plan(db,admin,'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments));sync(db,admin,'2026-10-26')
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-28T09:00'))
    record=attendance_clock.check_in(db,person,request(),attendance_clock.CheckInWrite(breakfast_notice_accepted=True))['record']
    with pytest.raises(HTTPException):attendance_clock.check_in(db,person,request(),attendance_clock.CheckInWrite(breakfast_notice_accepted=True,work_mode='company_home_overtime'))
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-28T18:30'))
    attendance_clock.check_out(db,person,request(),attendance_clock.CheckOutWrite(record_id=record['id'],early_work_confirmed=True,breakfast_after_eating=True))
    assert attendance_clock.today_status(db,person)['can_home_overtime_check_in']
    overtime=attendance_clock.check_in(db,person,request(),attendance_clock.CheckInWrite(breakfast_notice_accepted=True,work_mode='company_home_overtime'))['record']
    monkeypatch.setattr(attendance_clock,'now',lambda:at('2026-10-28T20:00'))
    attendance_clock.check_out(db,person,request(),attendance_clock.CheckOutWrite(record_id=overtime['id'],breakfast_after_eating=True,deduct_invalid_time=False))
    import attendance_service
    report=attendance_service.attendance_report(db,person,date(2026,10,28),'month')
    assert report['records'][0]['shift']['code']=='early' and report['totals']['overtime_minutes']==90
