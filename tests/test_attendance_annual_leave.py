"""年假优先、手调扣薪、来源审计及补班排重；仅隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException,FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text,inspect
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload,sync
from test_attendance import at
from models import EmployeeLeave
from employee_employment import EmployeeEmployment
from attendance_models import AttendanceLeave,AttendanceClockSession
import attendance_annual_leave as annual
import attendance_comp_time as comp


def entry(day,minutes=480,unit=480,key='application:1'):
    return {'entry_id':f'{key}:{day}','source_key':key,'user_id':'self','day':day,'minutes':minutes,'day_minutes':unit,'start_at':f'{day}T09:00:00+08:00'}


def test_actual_effective_quota_partial_days_and_future_reservation():
    rows=[entry('2026-09-29',key='application:1'),entry('2026-09-29',key='application:2'),entry('2026-10-30',key='application:3')]
    value=annual.allocate(rows,date(2025,6,30),2026,on_date=date(2026,10,29))
    assert [row['annual_minutes'] for row in value['entries']]==[480,0,480]
    assert value['used_days']==1 and value['reserved_days']==1 and value['remaining_days']==0
    assert value['makeup_required_minutes']==480
    # 不能在满周年再过三个月之前预支增加的1天。
    early=annual.allocate([entry('2026-09-29'),entry('2026-09-30',key='application:2')],date(2025,6,30),2026,on_date=date(2026,9,29))
    assert early['entries'][1]['annual_minutes']==0


def test_late_year_hire_january_grant_applies_to_leave_only_after_effective_date():
    hire=date(2024,9,9)
    before=annual.allocate([entry('2024-12-31')],hire,2024,on_date=date(2024,12,31))
    assert before['annual_minutes']==0 and before['makeup_required_minutes']==480
    january=annual.allocate([entry('2025-01-01')],hire,2025,on_date=date(2025,1,1))
    assert january['annual_leave_days']==1 and january['annual_minutes']==480
    later=annual.allocate([entry('2025-01-01'),entry('2025-12-09',key='application:2')],hire,2025,on_date=date(2025,12,9))
    assert later['annual_leave_days']==2 and later['annual_minutes']==960 and later['makeup_required_minutes']==0


def test_one_day_uses_each_actual_full_shift_length_not_fixed_eight_hours():
    value=annual.allocate([entry('2026-10-01',300,600),entry('2026-10-02',480,480,key='application:2')],date(2026,1,1),2026,on_date=date(2026,10,29))
    assert [row['annual_minutes'] for row in value['entries']]==[300,240]
    assert value['used_days']==1 and value['remaining_days']==0
    assert value['makeup_required_minutes']==240


def test_manual_wage_releases_annual_for_other_leave_and_never_requires_makeup():
    rows=[entry('2026-10-01'),entry('2026-10-02',key='application:2')]
    value=annual.allocate(rows,date(2026,1,1),2026,{'application:1':{'mode':'wage','revision':1}},date(2026,10,29))
    assert value['entries'][0]['wage_minutes']==480 and value['entries'][0]['annual_minutes']==0
    assert value['entries'][1]['annual_minutes']==480 and value['makeup_required_minutes']==0
    assert value['entries'][0]['revision']==1


def test_missing_employment_or_shift_does_not_invent_quota():
    value=annual.allocate([entry('2026-10-01')],None,2026,on_date=date(2026,10,29))
    assert value['remaining_days'] is None and value['entries'][0]['quota_pending']
    assert value['makeup_required_minutes']==480
    value=annual.allocate([entry('2026-10-01',unit=0)],date(2026,1,1),2026,on_date=date(2026,10,29))
    assert value['annual_minutes']==0 and value['makeup_required_minutes']==480


@pytest.fixture
def annual_environment(environment,monkeypatch):
    db,users=environment;setup(db,users)
    import weekly_shift
    weekly_shift.save_plan(db,users[0],'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(users[1]).assignments));sync(db,users[0],'2026-10-26')
    db.add(EmployeeEmployment(user_id=users[1].id,hire_date=date(2026,1,1)));db.commit()
    monkeypatch.setattr(annual,'now',lambda:at('2026-10-29T10:00'))
    monkeypatch.setattr(comp,'now',lambda:at('2026-10-29T10:00'))
    return db,users


def add_leave(db,user,day,minutes=480):
    from attendance_service import preview_leave,LeaveWindow
    start=at(f'{day}T09:00');end=at(f'{day}T18:30')
    values=preview_leave(db,user,LeaveWindow(start_at=start,end_at=end))
    uid=uuid4();days=[{**item,'minutes':minutes} for item in values['days']]
    db.add(AttendanceLeave(id=uid,client_id=uuid4(),user_id=user.id,start_at=start,end_at=end,reason='隔离请假',days=days))
    db.add(EmployeeLeave(id=uid,employee_id=user.id,employee_name=user.username,start_date=start.replace(tzinfo=None),end_date=end.replace(tzinfo=None),reason='隔离请假',leave_type='请假'))
    db.commit();return uid


def test_automatic_annual_and_immutable_adjustment_history_and_idempotency(annual_environment):
    db,(admin,person,other)=annual_environment
    first=add_leave(db,person,'2026-10-29');second=add_leave(db,person,'2026-10-30')
    rows=annual.ledger(db,[person],2026)[0]
    assert [item['annual_minutes'] for item in rows['entries']]==[480,0]
    request=annual.SettlementWrite(client_id=uuid4(),source_kind='application',source_id=first,mode='wage',revision=0,reason='本人确认本次改为扣工资')
    with pytest.raises(HTTPException):annual.adjustment(db,person,request)
    assert annual.adjustment(db,admin,request)['revision']==1
    assert annual.adjustment(db,admin,request)['revision']==1
    rows=annual.ledger(db,[person],2026)[0]
    assert [item['annual_minutes'] for item in rows['entries']]==[0,480]
    assert rows['wage_minutes']==480 and rows['makeup_required_minutes']==0
    assert len(rows['entries'][0]['history'])==1
    assert rows['entries'][0]['history'][0]['actor_name']==admin.username
    assert annual.overview(db,other,2026)['people'][0]['entries']==[]
    with pytest.raises(HTTPException) as conflict:annual.adjustment(db,admin,request.model_copy(update={'client_id':uuid4(),'mode':'auto'}))
    assert conflict.value.status_code==409
    reverted=request.model_copy(update={'client_id':uuid4(),'mode':'auto','revision':1,'reason':'恢复优先抵扣年假'})
    annual.adjustment(db,admin,reverted)
    audits=db.query(annual.LeaveSettlementAudit).order_by(annual.LeaveSettlementAudit.revision).all()
    assert len(audits)==2 and audits[0].before_snapshot['2026']['entries'][0]['annual_minutes']==480
    assert audits[0].after_snapshot['2026']['entries'][0]['wage_minutes']==480
    assert audits[1].after_snapshot['2026']['entries'][0]['annual_minutes']==480
    # 恢复后第一笔仍年假优先，第二笔仅剩补班；不会重复生成请假记录。
    assert db.query(AttendanceLeave).count()==2
    balance=comp.balances(db,[person],date(2026,10,29))[0]
    assert [row['minutes'] for row in balance['obligations']]==[0,480]


def test_lateness_also_consumes_annual_but_keeps_late_and_bonus_sources(annual_environment):
    db,(admin,person,_)=annual_environment
    row=AttendanceClockSession(user_id=person.id,day=date(2026,10,28),segment=0,check_in=at('2026-10-28T09:30'),check_out=at('2026-10-28T18:30'),shift_snapshot={'code':'early','periods':['09:00–12:00','13:30–18:30']},confirmations={'breakfast_after_eating':True,'early_work_confirmed':True})
    db.add(row);db.commit()
    value=annual.ledger(db,[person],2026)[0]
    assert value['entries'][0]['source_kind']=='lateness' and value['annual_minutes']==15
    assert value['entries'][0]['source_key']==f'lateness:{row.id}'
    assert value['entries'][0]['makeup_required_minutes']==0
    assert comp.balances(db,[person],date(2026,10,29))[0]['obligations'][0]['minutes']==0
    annual.adjustment(db,admin,annual.SettlementWrite(client_id=uuid4(),source_kind='lateness',source_id=row.id,mode='wage',revision=0,reason='保留迟到调整历史'))
    # 后补的正式请假使该次迟到不再发生，年度入口仍保留原始调整历史。
    db.add(EmployeeLeave(id=uuid4(),employee_id=person.id,employee_name=person.username,start_date=at('2026-10-28T09:00').replace(tzinfo=None),end_date=at('2026-10-28T10:00').replace(tzinfo=None),reason='补录请假'))
    db.commit();value=annual.ledger(db,[person],2026)[0]
    assert not any(item['source_kind']=='lateness' for item in value['entries'])
    assert value['history'][0]['source_key']==f'lateness:{row.id}'


def test_preview_is_read_only_and_accounts_for_existing_requests(annual_environment):
    db,(_,person,_)=annual_environment
    add_leave(db,person,'2026-10-29',240)
    from attendance_service import preview_leave,LeaveWindow
    days=preview_leave(db,person,LeaveWindow(start_at=at('2026-10-30T09:00'),end_at=at('2026-10-30T18:30')))['days']
    value=annual.preview(db,person,days)
    assert value['annual_minutes']==240 and value['makeup_required_minutes']==240
    assert db.query(AttendanceLeave).count()==1 and db.query(annual.LeaveSettlement).count()==0


def test_company_permissions_mobile_adjustment_and_reason_validation(annual_environment):
    db,(admin,person,_)=annual_environment;uid=add_leave(db,person,'2026-10-29')
    from routers.attendance import router
    from routers.auth import get_current_user
    from database import get_db
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    request={'client_id':str(uuid4()),'source_kind':'application','source_id':str(uid),'mode':'wage','revision':0,'reason':'调整说明'}
    with TestClient(app) as client:
        assert client.get('/attendance/annual-leave/company?year=2026').status_code==403
        assert client.get('/attendance/annual-leave?year=2026').status_code==200
        assert client.post('/attendance/annual-leave/settlement',headers={'user-agent':'Mozilla/5.0 (Windows NT 10.0)'},json=request).status_code==403
        app.dependency_overrides[get_current_user]=lambda:admin
        assert client.post('/attendance/annual-leave/settlement',headers={'user-agent':'iPhone Mobile'},json=request).status_code==403
        assert client.post('/attendance/annual-leave/settlement',json={**request,'reason':'   '}).status_code==422


def test_cross_year_sources_consume_separate_years_and_adjust_whole_request(annual_environment):
    db,(admin,person,_)=annual_environment
    start=at('2025-12-31T09:00');end=at('2026-01-02T18:30');uid=uuid4()
    shift={'code':'early','periods':['09:00–12:00','13:30–18:30']}
    employment=db.get(EmployeeEmployment,person.id);employment.hire_date=date(2025,1,1)
    db.add(AttendanceLeave(id=uid,client_id=uuid4(),user_id=person.id,start_at=start,end_at=end,reason='跨年隔离',days=[{'day':'2025-12-31','minutes':480,'shift':shift},{'day':'2026-01-02','minutes':480,'shift':shift}]))
    db.add(EmployeeLeave(id=uid,employee_id=person.id,employee_name=person.username,start_date=start.replace(tzinfo=None),end_date=end.replace(tzinfo=None),reason='跨年隔离'));db.commit()
    assert annual.ledger(db,[person],2025)[0]['annual_minutes']==480 and annual.ledger(db,[person],2026)[0]['annual_minutes']==480
    annual.adjustment(db,admin,annual.SettlementWrite(client_id=uuid4(),source_kind='application',source_id=uid,mode='wage',revision=0,reason='跨年整次改工资'))
    audit=db.query(annual.LeaveSettlementAudit).one()
    assert set(audit.before_snapshot)=={'2025','2026'}
    assert annual.ledger(db,[person],2025)[0]['wage_minutes']==480 and annual.ledger(db,[person],2026)[0]['wage_minutes']==480


def test_migration_idempotent_does_not_alter_existing_tables():
    from tools.apply_attendance_annual_leave_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE app_user (id UUID PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert inspect(connection).has_table('attendance_leave_settlement_audit')
        assert [row['name'] for row in inspect(connection).get_columns('app_user')]==['id']
    engine.dispose()
